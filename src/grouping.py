"""
업무 그룹핑 및 중복 병합 시스템
비슷한 업무 자동 분류, 중복 쪽지 병합
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from collections import defaultdict

try:
    from rapidfuzz import fuzz
    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False
    print("rapidfuzz 미설치. 기본 유사도 사용.")


# 업무 그룹 정의
TASK_GROUPS = {
    '담임': {
        'icon': '🎓',
        'keywords': [
            '생기부', '생활기록부', '출결', '결석', '조퇴',
            '상담', '학부모', '가정통신문', '성적', '세특',
            '행동발달', '창체', '담임', '학급', '반'
        ],
        'priority': 1
    },
    '제출': {
        'icon': '📋',
        'keywords': [
            '제출', '보고', '마감', '기한', '공문',
            '결재', '품의', '기안', '계획서', '보고서'
        ],
        'priority': 2
    },
    '회의': {
        'icon': '📅',
        'keywords': [
            '회의', '연수', '참석', '교육', '워크숍',
            '세미나', '연찬회', '간담회'
        ],
        'priority': 3
    },
    '예산': {
        'icon': '💰',
        'keywords': [
            '예산', '지출', '품의', '에듀파인', '집행',
            '정산', '구매', '계약'
        ],
        'priority': 4
    },
    '공지': {
        'icon': '📢',
        'keywords': [
            '안내', '공지', '알림', '전달', '공유',
            '배포', '홍보'
        ],
        'priority': 5
    }
}


class MessageGrouper:
    """메시지 그룹화 및 중복 병합"""
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.groups = TASK_GROUPS

        # 중복 판단 임계값
        self.similarity_threshold = self.config.get('similarity_threshold', 0.8)
        self.time_threshold_hours = self.config.get('time_threshold_hours', 24)
    
    def categorize(self, message: Dict[str, Any]) -> str:
        """메시지를 카테고리로 분류
        
        Args:
            message: {'title': str, 'content': str, ...}
        
        Returns:
            카테고리 이름 (담임, 제출, 회의, 예산, 공지)
        """
        text = (message.get('title', '') + ' ' + message.get('content', '')).lower()
        
        # 키워드 매칭 점수 계산
        scores = {}
        for category, info in self.groups.items():
            score = sum(1 for kw in info['keywords'] if kw in text)
            if score > 0:
                scores[category] = score
        
        if not scores:
            return '공지'
        
        # 가장 높은 점수의 카테고리 반환
        return max(scores, key=scores.get)
    
    def group_messages(self, messages: List[Dict[str, Any]]) -> Dict[str, List[Dict]]:
        """메시지를 카테고리별로 그룹화
        
        Args:
            messages: 메시지 리스트
        
        Returns:
            {'담임': [...], '제출': [...], ...}
        """
        groups = defaultdict(list)
        
        for msg in messages:
            category = msg.get('category') or self.categorize(msg)
            groups[category].append(msg)
        
        # 우선순위 순으로 정렬된 딕셔너리 반환
        sorted_groups = {}
        for cat in sorted(self.groups.keys(), 
                        key=lambda x: self.groups[x]['priority']):
            if cat in groups:
                sorted_groups[cat] = groups[cat]
        
        # 미분류 항목
        if '공지' in groups and '공지' not in sorted_groups:
            sorted_groups['공지'] = groups['공지']
        
        return sorted_groups
    
    def get_group_summary(self, messages: List[Dict[str, Any]]) -> List[Dict]:
        """그룹 요약 정보 반환
        
        Returns:
            [{'category': str, 'icon': str, 'count': int, 'urgent': int}, ...]
        """
        groups = self.group_messages(messages)
        summary = []
        
        for category, msgs in groups.items():
            info = self.groups.get(category, {'icon': '📌'})
            urgent_count = sum(1 for m in msgs 
                              if self._is_urgent(m) and m.get('status') != 'completed')
            pending_count = sum(1 for m in msgs if m.get('status') != 'completed')
            
            summary.append({
                'category': category,
                'icon': info['icon'],
                'count': len(msgs),
                'pending': pending_count,
                'urgent': urgent_count
            })
        
        return summary
    
    def _is_urgent(self, message: Dict[str, Any]) -> bool:
        """긴급 여부 판단 (D-2 이내)"""
        deadline = message.get('deadline')
        if not deadline:
            return False
        
        try:
            deadline_date = datetime.strptime(deadline, '%Y-%m-%d')
            d_day = (deadline_date - datetime.now()).days
            return d_day <= 2
        except ValueError:
            return False
    
    def find_duplicates(self, messages: List[Dict[str, Any]]) -> List[Tuple[int, int]]:
        """중복 쪽지 쌍 찾기
        
        Returns:
            [(idx1, idx2), ...] - 중복으로 판단된 메시지 인덱스 쌍
        """
        duplicates = []
        
        for i in range(len(messages)):
            for j in range(i + 1, len(messages)):
                if self._is_duplicate(messages[i], messages[j]):
                    duplicates.append((i, j))
        
        return duplicates
    
    def _is_duplicate(self, msg1: Dict, msg2: Dict) -> bool:
        """두 메시지가 중복인지 판단
        
        기준:
        1. 제목 유사도 > 80%
        2. 발신자 동일
        3. 수신 간격 < 24시간
        """
        # 발신자 확인
        if msg1.get('sender') != msg2.get('sender'):
            return False
        
        # 시간 간격 확인
        try:
            date1 = datetime.strptime(msg1.get('date', ''), '%Y-%m-%d')
            date2 = datetime.strptime(msg2.get('date', ''), '%Y-%m-%d')
            if abs((date1 - date2).total_seconds()) > self.time_threshold_hours * 3600:
                return False
        except ValueError:
            pass
        
        # 제목 유사도 확인
        title1 = msg1.get('title', '')
        title2 = msg2.get('title', '')
        
        similarity = self._calc_similarity(title1, title2)
        return similarity >= self.similarity_threshold
    
    def _calc_similarity(self, text1: str, text2: str) -> float:
        """텍스트 유사도 계산 (0.0 ~ 1.0)"""
        if HAS_RAPIDFUZZ:
            return fuzz.ratio(text1, text2) / 100.0
        else:
            # 간단한 자카드 유사도
            set1 = set(text1.lower().split())
            set2 = set(text2.lower().split())
            
            if not set1 or not set2:
                return 0.0
            
            intersection = len(set1 & set2)
            union = len(set1 | set2)
            return intersection / union if union > 0 else 0.0
    
    def merge_duplicates(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """중복 메시지 병합
        
        Returns:
            병합된 메시지 리스트 (중복은 merged_from 필드에 원본 정보 포함)
        """
        duplicates = self.find_duplicates(messages)
        
        if not duplicates:
            return messages
        
        # 병합 그룹 생성
        merged_indices = set()
        result = []
        
        for i, msg in enumerate(messages):
            if i in merged_indices:
                continue
            
            # 이 메시지와 중복인 것들 찾기
            related = [i]
            for idx1, idx2 in duplicates:
                if idx1 == i:
                    related.append(idx2)
                    merged_indices.add(idx2)
                elif idx2 == i:
                    related.append(idx1)
                    merged_indices.add(idx1)
            
            if len(related) > 1:
                # 병합
                merged_msg = self._merge_messages([messages[idx] for idx in related])
                result.append(merged_msg)
            else:
                result.append(msg)
        
        return result
    
    def _merge_messages(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """여러 메시지를 하나로 병합"""
        # 가장 최근 메시지를 기준으로
        messages = sorted(messages, key=lambda x: x.get('date', ''), reverse=True)
        base = messages[0].copy()
        
        # 병합 정보 추가
        base['merged_count'] = len(messages)
        base['merged_from'] = [
            {
                'title': m.get('title'),
                'date': m.get('date'),
                'summary': m.get('summary', '')[:50]
            }
            for m in messages[1:]
        ]
        
        # 제목에 병합 표시
        base['title'] = f"{base['title']} ({len(messages)}건 병합)"
        
        # 가장 이른 마감일 사용
        deadlines = [m.get('deadline') for m in messages if m.get('deadline')]
        if deadlines:
            base['deadline'] = min(deadlines)
        
        # 중요 표시는 하나라도 있으면 유지
        base['starred'] = any(m.get('starred') for m in messages)
        
        return base


class DeadlineSummarizer:
    """기한 중심 요약 생성기"""
    
    def __init__(self):
        self.grouper = MessageGrouper()
    
    def generate_summary(self, messages: List[Dict[str, Any]], 
                        date_range: str = 'week') -> Dict[str, Any]:
        """기한 중심 요약 생성
        
        Args:
            messages: 메시지 리스트
            date_range: 'today', 'week', 'month'
        
        Returns:
            {
                'summary_date': str,
                'urgent': [...],       # D-0 ~ D-2
                'this_week': [...],    # D-3 ~ D-7
                'upcoming': [...],     # D-8+
                'no_deadline': [...],  # 기한 없음
                'completed': [...]     # 완료
            }
        """
        today = datetime.now().date()
        
        categorized = {
            'urgent': [],
            'this_week': [],
            'upcoming': [],
            'no_deadline': [],
            'completed': []
        }
        
        for msg in messages:
            # 완료된 항목
            if msg.get('status') == 'completed':
                categorized['completed'].append(self._format_summary_item(msg))
                continue
            
            deadline = msg.get('deadline')
            
            if not deadline:
                categorized['no_deadline'].append(self._format_summary_item(msg))
                continue
            
            try:
                deadline_date = datetime.strptime(deadline, '%Y-%m-%d').date()
                d_day = (deadline_date - today).days
                
                item = self._format_summary_item(msg, d_day)
                
                if d_day <= 2:
                    categorized['urgent'].append(item)
                elif d_day <= 7:
                    categorized['this_week'].append(item)
                else:
                    categorized['upcoming'].append(item)
            except ValueError:
                categorized['no_deadline'].append(self._format_summary_item(msg))
        
        # 각 카테고리 내에서 D-day 순 정렬
        for key in ['urgent', 'this_week', 'upcoming']:
            categorized[key].sort(key=lambda x: x.get('d_day', 999))
        
        return {
            'summary_date': today.strftime('%Y-%m-%d'),
            **categorized
        }
    
    def _format_summary_item(self, msg: Dict[str, Any], 
                            d_day: Optional[int] = None) -> Dict[str, Any]:
        """요약 아이템 포맷"""
        category = msg.get('category') or self.grouper.categorize(msg)
        icon = TASK_GROUPS.get(category, {}).get('icon', '📌')
        
        # 상태 이모지
        if d_day is not None:
            if d_day <= 2:
                status_emoji = '🔴'
            elif d_day <= 7:
                status_emoji = '🟡'
            else:
                status_emoji = '🟢'
        else:
            status_emoji = '⚪'
        
        return {
            'title': msg.get('title', ''),
            'sender': msg.get('sender', ''),
            'deadline': msg.get('deadline'),
            'd_day': d_day,
            'category': category,
            'category_icon': icon,
            'status_emoji': status_emoji,
            'starred': msg.get('starred', False),
            'process': msg.get('process', []),
            'summary': msg.get('summary', '')
        }
    
    def format_as_markdown(self, summary: Dict[str, Any]) -> str:
        """마크다운 형식으로 변환"""
        output = [f"# 📬 쪽지 요약 ({summary['summary_date']})\n"]
        
        sections = [
            ('🔴 긴급 (D-0 ~ D-2)', 'urgent'),
            ('🟡 주의 (D-3 ~ D-7)', 'this_week'),
            ('🟢 예정 (D-8+)', 'upcoming'),
            ('⚪ 참고/공지', 'no_deadline')
        ]
        
        for title, key in sections:
            items = summary.get(key, [])
            if not items:
                continue
            
            output.append(f"\n## {title}\n")
            output.append("| 마감 | 제목 | 발신자 | 실행 프로세스 |")
            output.append("|------|------|--------|---------------|")
            
            for item in items:
                d_day_str = f"D-{item['d_day']}" if item['d_day'] is not None else "-"
                deadline = item['deadline'] or "-"
                star = "⭐" if item['starred'] else ""
                process = " → ".join(item.get('process', [])[:3]) or "-"
                
                output.append(
                    f"| {star}{deadline} ({d_day_str}) | "
                    f"{item['title'][:20]} | {item['sender'][:10]} | {process} |"
                )
        
        return "\n".join(output)
    
    def format_as_dashboard(self, summary: Dict[str, Any]) -> str:
        """대시보드 형식 텍스트로 변환"""
        lines = [
            "┌─────────────────────────────────────────────────────────┐",
            f"│ 📬 쪽지 요약 ({summary['summary_date']})                        │",
            "├─────────────────────────────────────────────────────────┤"
        ]
        
        # 긴급
        urgent = summary.get('urgent', [])
        if urgent:
            for item in urgent[:3]:
                star = "⭐" if item['starred'] else "  "
                d_day = f"D-{item['d_day']}"
                title = item['title'][:20]
                lines.append(f"│ {star}🔴 [{d_day}] {title:<25} │")
        
        # 이번 주
        this_week = summary.get('this_week', [])
        if this_week:
            lines.append("├─────────────────────────────────────────────────────────┤")
            for item in this_week[:3]:
                star = "⭐" if item['starred'] else "  "
                d_day = f"D-{item['d_day']}"
                title = item['title'][:20]
                lines.append(f"│ {star}🟡 [{d_day}] {title:<25} │")
        
        lines.append("└─────────────────────────────────────────────────────────┘")
        
        return "\n".join(lines)


# 테스트
if __name__ == "__main__":
    grouper = MessageGrouper()
    summarizer = DeadlineSummarizer()
    
    today = datetime.now()
    
    test_messages = [
        {
            'id': 1,
            'title': '생활기록부 최종 마감 안내',
            'content': '담임선생님 생기부 제출',
            'sender': '교무기획부',
            'date': today.strftime('%Y-%m-%d'),
            'deadline': (today + timedelta(days=2)).strftime('%Y-%m-%d'),
            'starred': True,
            'status': 'pending',
            'process': ['미입력 확인', '나이스 입력', '부장 검토']
        },
        {
            'id': 2,
            'title': '출결 마감',
            'content': '출결 처리',
            'sender': '교무기획부',
            'date': today.strftime('%Y-%m-%d'),
            'deadline': (today + timedelta(days=1)).strftime('%Y-%m-%d'),
            'starred': True,
            'status': 'pending',
            'process': ['결석 확인', '나이스 처리', '확인']
        },
        {
            'id': 3,
            'title': '교육과정 운영계획 제출',
            'content': '교육과정 계획',
            'sender': '교육과정부',
            'date': today.strftime('%Y-%m-%d'),
            'deadline': (today + timedelta(days=7)).strftime('%Y-%m-%d'),
            'starred': False,
            'status': 'pending',
            'process': ['양식 확인', '작성', '결재']
        },
        {
            'id': 4,
            'title': '2월 회의 안내',
            'content': '교직원 회의',
            'sender': '교무기획부',
            'date': today.strftime('%Y-%m-%d'),
            'deadline': None,
            'starred': False,
            'status': 'pending',
            'process': ['일정 확인', '참석']
        }
    ]
    
    # 그룹핑 테스트
    print("=== 그룹핑 테스트 ===")
    groups = grouper.group_messages(test_messages)
    for cat, msgs in groups.items():
        icon = TASK_GROUPS.get(cat, {}).get('icon', '📌')
        print(f"{icon} {cat}: {len(msgs)}건")
    
    # 요약 테스트
    print("\n=== 기한 중심 요약 ===")
    summary = summarizer.generate_summary(test_messages)
    print(summarizer.format_as_dashboard(summary))
    
    print("\n=== 마크다운 요약 ===")
    print(summarizer.format_as_markdown(summary))
