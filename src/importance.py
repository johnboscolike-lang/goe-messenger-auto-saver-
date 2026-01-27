"""
중요도 판단 시스템 (수정본)
- 발신자 점수 제거
- 행동/정보 대분류 추가
- 정보 쪽지 메타데이터 추출
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
import re


# ==================== 대분류 키워드 ====================

# 📋 행동 필요 (Action Required)
ACTION_KEYWORDS = {
    '강한_행동': [
        '제출', '보고', '마감', '기한', '까지', '내로',
        '처리', '입력', '작성', '완료', '등록',
        '필수', '반드시', '꼭', '필히', '의무',
        '요청', '협조', '부탁', '바랍니다',
        '결재', '품의', '승인', '기안'
    ],
    '담임_행동': [
        '생기부', '생활기록부', '출결', '결석', '조퇴',
        '상담', '학부모', '가정통신문',
        '성적', '세특', '행동발달', '창체'
    ],
    '예산_행동': [
        '예산', '지출', '집행', '정산',
        '에듀파인', '품의', '구매'
    ]
}

# 📢 정보 제공 (Information Only)
INFO_KEYWORDS = {
    '공지': [
        '안내', '공지', '알림', '전달',
        '참고', '공유', '배포', '홍보',
        '변경', '개정', '시행'
    ],
    '일정': [
        '예정', '계획', '일정',
        '개최', '실시', '진행', '있습니다'
    ]
}


# ==================== 중요도 키워드 (60점 만점, 발신자 제거) ====================

IMPORTANCE_KEYWORDS = {
    'task_type': {  # A. 업무 유형 (40점)
        '담임': {
            'score': 40,
            'category': 'action',
            'keywords': [
                '생활기록부', '생기부', '출결', '결석', '조퇴', '지각',
                '학부모', '상담', '가정통신문', '알림장',
                '성적', '세특', '행동발달', '창체', '교과세특',
                '담임', '학급', '반', '우리반'
            ]
        },
        '제출': {
            'score': 35,
            'category': 'action',
            'keywords': [
                '제출', '보고', '마감', '기한', '까지',
                '필수', '반드시', '꼭', '필히',
                '공문', '결재', '품의', '기안'
            ]
        },
        '협조': {
            'score': 30,
            'category': 'action',
            'keywords': [
                '협조', '요청', '부탁', '처리',
                '담당', '업무'
            ]
        },
        '회의': {
            'score': 20,
            'category': 'action',  # 참석 행동 필요하므로 action
            'keywords': [
                '회의', '연수', '교육', '참석', '참가',
                '워크숍', '세미나', '연찬회'
            ]
        },
        '공지': {
            'score': 10,
            'category': 'information',
            'keywords': [
                '안내', '공지', '알림', '참고', '전달',
                '공유', '배포'
            ]
        }
    },
    'urgency': {  # 긴급 키워드
        'keywords': ['긴급', '급', '시급', '즉시', '오늘', '당일', '바로']
    }
}

# 자동 중요 표시 키워드
AUTO_STAR_KEYWORDS = ['필수', '반드시', '마감', '긴급', '중요', '꼭']


class ImportanceCalculator:
    """쪽지 중요도 계산기 (발신자 점수 제거, 80점 만점)"""
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.keywords = IMPORTANCE_KEYWORDS
    
    def calculate(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """중요도 계산 (80점 만점)
        
        Args:
            message: {
                'title': str,
                'content': str,
                'deadline': str (YYYY-MM-DD) or None
            }
        
        Returns:
            {
                'grade': 'S'|'A'|'B'|'C'|'D',
                'score': int (0-60),
                'main_category': 'action'|'information',
                'breakdown': {...},
                'color_code': '🔴'|'🟠'|'🟡'|'🟢'|'⚪',
                'auto_starred': bool
            }
        """
        text = (message.get('title', '') + ' ' + message.get('content', '')).lower()
        deadline = message.get('deadline')
        
        # 대분류 먼저 판단
        main_category = self._determine_main_category(text)
        
        # 점수 계산 (업무유형 + 시급성만, 발신자/영향범위 제외)
        scores = {
            'task_type': self._calc_task_type(text),
            'urgency': self._calc_urgency(deadline, text)
        }
        
        # 총점 계산 (60점 만점)
        total = sum(s['score'] for s in scores.values())
        
        # 등급 산정 (60점 기준)
        grade, color = self._get_grade(total)
        
        # 자동 중요 표시 여부
        auto_starred = self._should_auto_star(text, grade, main_category)
        
        return {
            'grade': grade,
            'score': total,
            'max_score': 60,
            'main_category': main_category,
            'main_category_label': '✋ 행동 필요' if main_category == 'action' else '📢 정보/공지',
            'breakdown': scores,
            'color_code': color,
            'auto_starred': auto_starred
        }
    
    def _determine_main_category(self, text: str) -> str:
        """대분류 판단: action(행동) vs information(정보)"""
        action_score = 0
        info_score = 0
        
        # 행동 키워드 점수
        for category, keywords in ACTION_KEYWORDS.items():
            action_score += sum(2 if kw in text else 0 for kw in keywords)
        
        # 정보 키워드 점수
        for category, keywords in INFO_KEYWORDS.items():
            info_score += sum(1 if kw in text else 0 for kw in keywords)
        
        # 행동 키워드가 더 강하면 action
        return 'action' if action_score >= info_score else 'information'
    
    def _calc_task_type(self, text: str) -> Dict[str, Any]:
        """업무 유형 점수 (40점 만점)"""
        result = {'score': 10, 'reason': '기타', 'category': 'information'}
        
        for task_type, info in self.keywords['task_type'].items():
            if any(kw in text for kw in info['keywords']):
                if info['score'] > result['score']:
                    result = {
                        'score': info['score'], 
                        'reason': task_type,
                        'category': info['category']
                    }
        
        return result
    
    def _calc_urgency(self, deadline: Optional[str], text: str) -> Dict[str, Any]:
        """시급성 점수 (20점 만점)"""
        result = {'score': 0, 'd_day': None, 'reason': '기한없음'}
        
        # 기한 기반 계산
        if deadline:
            try:
                deadline_date = datetime.strptime(deadline, '%Y-%m-%d')
                d_day = (deadline_date - datetime.now()).days
                result['d_day'] = d_day
                
                if d_day <= 0:
                    result = {'score': 20, 'd_day': d_day, 'reason': 'D-day/지남'}
                elif d_day == 1:
                    result = {'score': 18, 'd_day': d_day, 'reason': '내일'}
                elif d_day <= 3:
                    result = {'score': 15, 'd_day': d_day, 'reason': '3일 이내'}
                elif d_day <= 7:
                    result = {'score': 8, 'd_day': d_day, 'reason': '이번 주'}
                else:
                    result = {'score': 3, 'd_day': d_day, 'reason': '여유'}
            except ValueError:
                pass
        
        # 긴급 키워드 보너스
        if any(kw in text for kw in self.keywords['urgency']['keywords']):
            result['score'] = min(result['score'] + 5, 20)
            result['reason'] += '+긴급키워드'
        
        return result
    
    def _get_grade(self, score: int) -> Tuple[str, str]:
        """등급 및 색상 반환 (60점 만점 기준)"""
        if score >= 50:
            return 'S', '🔴'
        elif score >= 40:
            return 'A', '🟠'
        elif score >= 25:
            return 'B', '🟡'
        elif score >= 10:
            return 'C', '🟢'
        else:
            return 'D', '⚪'
    
    def _should_auto_star(self, text: str, grade: str, category: str) -> bool:
        """자동 중요 표시 여부"""
        # S등급 자동 표시
        if grade == 'S':
            return True
        
        # 행동 필요 + A등급 이상
        if category == 'action' and grade in ['S', 'A']:
            return True
        
        # 키워드 기반
        if any(kw in text for kw in AUTO_STAR_KEYWORDS):
            return True
        
        return False


class InfoMetadataExtractor:
    """정보 쪽지 메타데이터 추출기"""
    
    def __init__(self):
        self.date_patterns = [
            # "2월 5일", "02월 05일"
            (r'(\d{1,2})월\s*(\d{1,2})일', 'month_day'),
            # "2025-02-05", "2025.02.05", "2025/02/05"
            (r'(\d{4})[-./](\d{1,2})[-./](\d{1,2})', 'full_date'),
            # "2/5", "02/05"
            (r'(\d{1,2})[/](\d{1,2})', 'short_date'),
        ]
        
        self.time_patterns = [
            # "15:00", "15시", "15시 30분"
            (r'(\d{1,2})[:\s시]\s*(\d{2})?분?', 'time'),
            # "오후 3시", "오전 10시"
            (r'(오전|오후)\s*(\d{1,2})시\s*(\d{2})?분?', 'ampm_time'),
        ]
        
        self.location_patterns = [
            r'장소[:\s]*([^\n,]+)',
            r'(\w{2,10}(?:실|관|홀|센터|회의실|강당))',
        ]
    
    def extract(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """정보 쪽지에서 메타데이터 추출
        
        Returns:
            {
                'type': 'information',
                'summary': {...},
                'dates': [...],
                'location': str or None,
                'remember': [...],
                'tags': [...],
                'calendar_events': [...]
            }
        """
        title = message.get('title', '')
        content = message.get('content', '')
        text = title + ' ' + content
        
        # 일시 추출
        dates = self._extract_dates(text)
        times = self._extract_times(text)
        
        # 장소 추출
        location = self._extract_location(text)
        
        # 기억해야 할 사항 추출
        remember = self._extract_remember_items(text)
        
        # 캘린더 이벤트 생성
        calendar_events = self._create_calendar_events(
            title, dates, times, location, message.get('sender', '')
        )
        
        # 태그 생성
        tags = self._generate_tags(text)
        
        return {
            'type': 'information',
            'title': title,
            'summary': {
                '핵심': self._summarize_core(text, dates, times, location),
                '장소': location,
                '일시': self._format_datetime(dates, times)
            },
            'dates': dates,
            'times': times,
            'location': location,
            'remember': remember,
            'tags': tags,
            'calendar_events': calendar_events,
            'has_calendar_event': len(calendar_events) > 0
        }
    
    def _extract_dates(self, text: str) -> List[Dict[str, Any]]:
        """텍스트에서 날짜 추출"""
        dates = []
        today = datetime.now()
        
        for pattern, pattern_type in self.date_patterns:
            for match in re.finditer(pattern, text):
                try:
                    if pattern_type == 'full_date':
                        year, month, day = map(int, match.groups())
                    elif pattern_type == 'month_day':
                        month, day = map(int, match.groups())
                        year = today.year
                        # 지난 달이면 다음 해로
                        if month < today.month or (month == today.month and day < today.day):
                            year += 1
                    elif pattern_type == 'short_date':
                        month, day = map(int, match.groups())
                        year = today.year
                        if month < today.month:
                            year += 1
                    
                    date_str = f"{year:04d}-{month:02d}-{day:02d}"
                    if date_str not in [d['date'] for d in dates]:
                        dates.append({
                            'date': date_str,
                            'original': match.group(),
                            'position': match.start()
                        })
                except (ValueError, TypeError):
                    continue
        
        return sorted(dates, key=lambda x: x['date'])
    
    def _extract_times(self, text: str) -> List[Dict[str, Any]]:
        """텍스트에서 시간 추출"""
        times = []
        
        for pattern, pattern_type in self.time_patterns:
            for match in re.finditer(pattern, text):
                try:
                    groups = match.groups()
                    
                    if pattern_type == 'ampm_time':
                        ampm, hour, minute = groups
                        hour = int(hour)
                        minute = int(minute) if minute else 0
                        if ampm == '오후' and hour < 12:
                            hour += 12
                    else:
                        hour = int(groups[0])
                        minute = int(groups[1]) if groups[1] else 0
                    
                    time_str = f"{hour:02d}:{minute:02d}"
                    if time_str not in [t['time'] for t in times]:
                        times.append({
                            'time': time_str,
                            'original': match.group(),
                            'position': match.start()
                        })
                except (ValueError, TypeError):
                    continue
        
        return times
    
    def _extract_location(self, text: str) -> Optional[str]:
        """텍스트에서 장소 추출"""
        for pattern in self.location_patterns:
            match = re.search(pattern, text)
            if match:
                location = match.group(1) if match.lastindex else match.group()
                return location.strip()
        return None
    
    def _extract_remember_items(self, text: str) -> List[str]:
        """기억해야 할 사항 추출"""
        items = []
        
        # "준비", "지참", "확인" 등의 키워드 주변 문장 추출
        remember_keywords = ['준비', '지참', '확인', '필요', '가져', '검토']
        
        sentences = re.split(r'[.。\n]', text)
        for sentence in sentences:
            if any(kw in sentence for kw in remember_keywords):
                clean = sentence.strip()
                if clean and len(clean) > 5:
                    items.append(clean[:100])
        
        return items[:5]  # 최대 5개
    
    def _create_calendar_events(self, title: str, dates: List[Dict], 
                               times: List[Dict], location: Optional[str],
                               sender: str) -> List[Dict[str, Any]]:
        """캘린더 이벤트 생성"""
        events = []
        
        if not dates:
            return events
        
        # 첫 번째 날짜와 시간으로 이벤트 생성
        date = dates[0]['date']
        time = times[0]['time'] if times else None
        
        event = {
            'summary': title,
            'date': date,
            'time': time,
            'location': location,
            'description': f"📬 GOE메신저 정보 쪽지\n발신: {sender}",
            'reminders': [
                {'method': 'popup', 'minutes': 1440},  # D-1
                {'method': 'popup', 'minutes': 60}     # 1시간 전
            ]
        }
        
        events.append(event)
        
        return events
    
    def _format_datetime(self, dates: List[Dict], times: List[Dict]) -> str:
        """일시 포맷"""
        if not dates:
            return "미정"
        
        date_str = dates[0]['date']
        time_str = times[0]['time'] if times else ""
        
        return f"{date_str} {time_str}".strip()
    
    def _summarize_core(self, text: str, dates: List, times: List, 
                       location: Optional[str]) -> str:
        """핵심 내용 요약"""
        parts = []
        
        if dates:
            parts.append(dates[0]['date'])
        if times:
            parts.append(times[0]['time'])
        if location:
            parts.append(location)
        
        if parts:
            return ' '.join(parts) + " 예정"
        
        # 첫 문장 반환
        sentences = re.split(r'[.。\n]', text)
        if sentences:
            return sentences[0][:50].strip()
        
        return text[:50]
    
    def _generate_tags(self, text: str) -> List[str]:
        """태그 생성"""
        tags = []
        
        tag_keywords = {
            '회의': ['회의', '미팅'],
            '연수': ['연수', '교육', '워크숍'],
            '행사': ['행사', '축제', '체육'],
            '평가': ['평가', '시험', '고사'],
        }
        
        for tag, keywords in tag_keywords.items():
            if any(kw in text for kw in keywords):
                tags.append(tag)
        
        return tags


# 테스트
if __name__ == "__main__":
    calc = ImportanceCalculator()
    extractor = InfoMetadataExtractor()
    
    test_messages = [
        # 행동 쪽지
        {
            'title': '2학기 생활기록부 최종 마감 안내',
            'content': '담임선생님께서는 1월 29일까지 나이스에 생기부를 제출해 주세요.',
            'sender': '교무기획부 김OO 부장',
            'deadline': '2025-01-29'
        },
        # 정보 쪽지
        {
            'title': '2월 교직원 회의 안내',
            'content': '2월 5일 15시에 시청각실에서 교직원 회의가 있습니다. 회의 자료를 사전에 검토해 주세요.',
            'sender': '교무기획부',
            'deadline': None
        }
    ]
    
    for msg in test_messages:
        print(f"\n{'='*50}")
        print(f"제목: {msg['title']}")

        result = calc.calculate(msg)
        print(f"\n📊 중요도 분석:")
        print(f"  대분류: {result['main_category_label']}")
        print(f"  등급: {result['grade']} ({result['score']}/{result['max_score']}점) {result['color_code']}")
        print(f"  자동 중요: {'⭐' if result['auto_starred'] else '☆'}")
        print(f"  상세: {result['breakdown']}")
        
        if result['main_category'] == 'information':
            meta = extractor.extract(msg)
            print(f"\n📝 메타데이터:")
            print(f"  요약: {meta['summary']}")
            print(f"  기억사항: {meta['remember']}")
            print(f"  태그: {meta['tags']}")
            if meta['calendar_events']:
                print(f"  📅 캘린더 이벤트: {meta['calendar_events'][0]}")

