"""
AI 채팅 검색 모듈
- 자연어 질의응답
- 쪽지 검색 및 요약
- 업무 가이드 제공
"""

import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple

from utils import MessageRepository, get_d_day, format_d_day
from importance import ImportanceCalculator
from grouping import MessageGrouper, DeadlineSummarizer


# ============================================================
# 질의 분류기
# ============================================================

class QueryClassifier:
    """사용자 질의 분류기"""

    # 질의 유형별 키워드
    QUERY_PATTERNS = {
        'search': {
            'keywords': ['찾아', '검색', '있어', '어디', '뭐야', '알려'],
            'patterns': [
                r'(.+)\s*관련\s*(쪽지|업무)',
                r'(.+)\s*쪽지\s*찾아',
                r'(.+)\s*(있어|있나요)',
            ]
        },
        'deadline': {
            'keywords': ['마감', '기한', '언제까지', 'D-', '디데이'],
            'patterns': [
                r'(.+)\s*언제까지',
                r'(.+)\s*마감일',
            ]
        },
        'summary': {
            'keywords': ['요약', '정리', '알려줘', '뭐야'],
            'patterns': [
                r'오늘\s*(쪽지|업무)',
                r'이번\s*주\s*(마감|업무)',
                r'(오늘|내일)\s*뭐',
            ]
        },
        'guide': {
            'keywords': ['어떻게', '방법', '해야', '뭐해', '순서'],
            'patterns': [
                r'(.+)\s*어떻게\s*(해|하)',
                r'(.+)\s*뭐\s*해야',
            ]
        },
        'priority': {
            'keywords': ['먼저', '우선', '중요', '급한', '긴급'],
            'patterns': [
                r'뭐\s*먼저',
                r'뭐부터',
                r'(중요한|급한)\s*거',
            ]
        },
        'status': {
            'keywords': ['현황', '상태', '몇 개', '얼마나'],
            'patterns': [
                r'(쪽지|업무)\s*몇',
                r'현황',
                r'완료.*몇',
            ]
        }
    }

    def classify(self, query: str) -> Tuple[str, Optional[str]]:
        """질의 분류

        Returns:
            (query_type, extracted_topic)
        """
        query_lower = query.lower().strip()

        # 패턴 매칭
        for query_type, config in self.QUERY_PATTERNS.items():
            # 키워드 체크
            if any(kw in query_lower for kw in config['keywords']):
                topic = self._extract_topic(query, config.get('patterns', []))
                return query_type, topic

            # 정규식 패턴 체크
            for pattern in config.get('patterns', []):
                match = re.search(pattern, query_lower)
                if match:
                    topic = match.group(1) if match.lastindex else None
                    return query_type, topic

        # 기본: 검색으로 처리
        return 'search', query_lower

    def _extract_topic(self, query: str, patterns: List[str]) -> Optional[str]:
        """질의에서 주제 추출"""
        for pattern in patterns:
            match = re.search(pattern, query.lower())
            if match and match.lastindex:
                return match.group(1).strip()

        # 일반적인 주제어 추출
        stopwords = ['쪽지', '업무', '관련', '찾아줘', '알려줘', '뭐야', '있어', '해줘']
        words = query.split()
        for word in words:
            if word not in stopwords and len(word) > 1:
                return word

        return None


# ============================================================
# AI 채팅 엔진
# ============================================================

class AIChatEngine:
    """AI 채팅 엔진

    사용법:
        engine = AIChatEngine()
        response = engine.process("생기부 관련 쪽지 찾아줘")
        print(response['text'])
    """

    def __init__(self, repo: Optional[MessageRepository] = None):
        self.repo = repo or MessageRepository()
        self.classifier = QueryClassifier()
        self.importance_calc = ImportanceCalculator()
        self.grouper = MessageGrouper()
        self.summarizer = DeadlineSummarizer()

        # 대화 컨텍스트 (마지막 검색 결과 등)
        self.context = {
            'last_search_results': [],
            'last_topic': None
        }

    def process(self, query: str) -> Dict[str, Any]:
        """사용자 질의 처리

        Args:
            query: 사용자 질의

        Returns:
            {
                'text': str,           # 응답 텍스트
                'messages': list,      # 관련 쪽지 목록
                'suggestions': list,   # 추천 질문
                'query_type': str      # 질의 유형
            }
        """
        if not query.strip():
            return self._error_response("질문을 입력해 주세요.")

        # 질의 분류
        query_type, topic = self.classifier.classify(query)

        # 유형별 처리
        handlers = {
            'search': self._handle_search,
            'deadline': self._handle_deadline,
            'summary': self._handle_summary,
            'guide': self._handle_guide,
            'priority': self._handle_priority,
            'status': self._handle_status
        }

        handler = handlers.get(query_type, self._handle_search)
        return handler(query, topic)

    def _handle_search(self, query: str, topic: Optional[str]) -> Dict[str, Any]:
        """검색 질의 처리"""
        search_term = topic or query

        # 검색 실행
        results = self.repo.search(search_term)
        self.context['last_search_results'] = results
        self.context['last_topic'] = topic

        if not results:
            return {
                'text': f"'{search_term}' 관련 쪽지를 찾지 못했습니다.\n\n"
                       "다른 키워드로 검색해 보세요.",
                'messages': [],
                'suggestions': [
                    "'오늘 온 쪽지 정리해줘'",
                    "'이번 주 마감 업무 알려줘'"
                ],
                'query_type': 'search'
            }

        # 응답 생성
        text = f"'{search_term}' 관련 쪽지 {len(results)}건을 찾았습니다:\n\n"

        for i, msg in enumerate(results[:5], 1):
            d_day = format_d_day(msg.get('deadline'))
            status_emoji = self._get_status_icon(msg)
            star = "**" if msg.get('starred') else ""

            text += f"{i}. {star}{msg['title']}{star}\n"
            text += f"   {status_emoji} 마감: {msg.get('deadline', '-')} ({d_day})\n"
            text += f"   발신: {msg['sender']}\n"

            if msg.get('summary'):
                text += f"   요약: {msg['summary'][:50]}\n"

            text += "\n"

        return {
            'text': text,
            'messages': results[:5],
            'suggestions': [
                f"'{search_term} 마감까지 해야 할 일 알려줘'",
                f"'{search_term} 관련 첨부파일 찾아줘'"
            ],
            'query_type': 'search'
        }

    def _handle_deadline(self, query: str, topic: Optional[str]) -> Dict[str, Any]:
        """마감 관련 질의 처리"""
        if topic:
            # 특정 주제의 마감일 조회
            results = self.repo.search(topic)
            if results:
                msg = results[0]
                deadline = msg.get('deadline')

                if deadline:
                    d_day = get_d_day(deadline)
                    text = f"'{msg['title']}'의 마감일:\n\n"
                    text += f"**{deadline}** ({format_d_day(deadline)})\n\n"

                    if d_day <= 0:
                        text += "마감일이 지났습니다!"
                    elif d_day <= 2:
                        text += "긴급합니다! 서둘러 처리해 주세요."
                    elif d_day <= 7:
                        text += "이번 주 내로 처리가 필요합니다."
                    else:
                        text += "여유가 있지만 미리 준비하시면 좋겠습니다."

                    return {
                        'text': text,
                        'messages': [msg],
                        'suggestions': [
                            f"'{topic} 어떻게 처리해?'",
                            "'이번 주 마감 업무 알려줘'"
                        ],
                        'query_type': 'deadline'
                    }
                else:
                    return {
                        'text': f"'{msg['title']}'에는 마감일이 지정되어 있지 않습니다.",
                        'messages': [msg],
                        'suggestions': [],
                        'query_type': 'deadline'
                    }

        # 전체 마감 현황
        return self._handle_summary(query, topic)

    def _handle_summary(self, query: str, topic: Optional[str]) -> Dict[str, Any]:
        """요약 질의 처리"""
        messages = self.repo.get_pending()
        summary = self.summarizer.generate_summary(messages)

        text = f"**쪽지 요약** ({summary['summary_date']})\n\n"

        # 긴급
        urgent = summary.get('urgent', [])
        if urgent:
            text += "**긴급 (D-2 이내)**\n"
            for item in urgent[:3]:
                star = "**" if item['starred'] else ""
                text += f"  {star}{item['title']}{star} (D-{item['d_day']})\n"
            text += "\n"

        # 이번 주
        this_week = summary.get('this_week', [])
        if this_week:
            text += "**이번 주**\n"
            for item in this_week[:3]:
                text += f"  {item['title']} (D-{item['d_day']})\n"
            text += "\n"

        # 참고
        no_deadline = summary.get('no_deadline', [])
        if no_deadline:
            text += "**참고/공지**\n"
            for item in no_deadline[:2]:
                text += f"  {item['title']}\n"
            text += "\n"

        stats = self.repo.get_stats()
        text += f"---\n"
        text += f"전체 {stats['total']}건 | 미완료 {stats['pending']}건 | 완료 {stats['completed']}건"

        return {
            'text': text,
            'messages': messages[:5],
            'suggestions': [
                "'긴급한 거 먼저 알려줘'",
                "'완료 처리된 쪽지 보여줘'"
            ],
            'query_type': 'summary'
        }

    def _handle_guide(self, query: str, topic: Optional[str]) -> Dict[str, Any]:
        """가이드 질의 처리"""
        if not topic:
            # 컨텍스트에서 주제 찾기
            if self.context.get('last_search_results'):
                topic = self.context['last_search_results'][0].get('title', '')[:10]

        if topic:
            results = self.repo.search(topic)
            if results:
                msg = results[0]
                process = msg.get('process', [])

                text = f"**{msg['title']}** 처리 방법:\n\n"

                if msg.get('deadline'):
                    text += f"마감: {msg['deadline']} ({format_d_day(msg['deadline'])})\n\n"

                if process:
                    text += "**실행 단계:**\n"
                    for i, step in enumerate(process, 1):
                        text += f"  {i}. {step}\n"
                else:
                    text += "**실행 단계:**\n"
                    text += "  1. 내용 확인\n"
                    text += "  2. 필요한 조치 수행\n"
                    text += "  3. 완료 처리\n"

                if msg.get('summary'):
                    text += f"\n**핵심:** {msg['summary']}\n"

                return {
                    'text': text,
                    'messages': [msg],
                    'suggestions': [
                        f"'{topic} 캘린더에 등록해줘'",
                        "'다음으로 뭐 해야 해?'"
                    ],
                    'query_type': 'guide'
                }

        return {
            'text': "어떤 업무에 대한 가이드가 필요하신가요?\n\n"
                   "예시:\n"
                   "  '생기부 제출 어떻게 해?'\n"
                   "  '교육과정 계획 작성 방법 알려줘'",
            'messages': [],
            'suggestions': [
                "'생기부 어떻게 해?'",
                "'예산 집행 방법 알려줘'"
            ],
            'query_type': 'guide'
        }

    def _handle_priority(self, query: str, topic: Optional[str]) -> Dict[str, Any]:
        """우선순위 질의 처리"""
        urgent = self.repo.get_urgent()

        if not urgent:
            pending = self.repo.get_pending()
            if pending:
                return {
                    'text': "긴급 업무는 없습니다!\n\n"
                           f"미완료 업무 {len(pending)}건이 있습니다.\n"
                           "여유롭게 처리하시면 됩니다.",
                    'messages': pending[:3],
                    'suggestions': [
                        "'오늘 온 쪽지 알려줘'",
                        "'완료 처리된 거 보여줘'"
                    ],
                    'query_type': 'priority'
                }
            else:
                return {
                    'text': "처리할 업무가 없습니다! 좋은 하루 되세요.",
                    'messages': [],
                    'suggestions': [],
                    'query_type': 'priority'
                }

        text = "**오늘의 우선순위**\n\n"

        for i, msg in enumerate(urgent[:5], 1):
            d_day = get_d_day(msg.get('deadline'))
            process = msg.get('process', [])

            text += f"**{i}. {msg['title']}** (D-{d_day})\n"
            text += f"   발신: {msg['sender']}\n"

            if process:
                text += f"   실행: {' -> '.join(process[:3])}\n"

            text += "\n"

        if urgent:
            text += f"\n가장 긴급한 건 **{urgent[0]['title']}**입니다.\n"
            text += "이것부터 처리하시는 걸 추천드립니다!"

        return {
            'text': text,
            'messages': urgent[:5],
            'suggestions': [
                f"'{urgent[0]['title'][:10]}... 어떻게 해?'" if urgent else "",
                "'완료 처리해줘'"
            ],
            'query_type': 'priority'
        }

    def _handle_status(self, query: str, topic: Optional[str]) -> Dict[str, Any]:
        """상태/현황 질의 처리"""
        stats = self.repo.get_stats()
        cat_stats = self.repo.get_category_stats()

        text = "**업무 현황**\n\n"

        text += f"**전체:** {stats['total']}건\n"
        text += f"  - 행동 필요: {stats['action']}건\n"
        text += f"  - 정보/공지: {stats['information']}건\n"
        text += f"  - 긴급 (D-2): {stats['urgent']}건\n"
        text += f"  - 완료: {stats['completed']}건\n\n"

        if cat_stats:
            text += "**카테고리별:**\n"
            for cat, info in cat_stats.items():
                text += f"  - {cat}: {info['pending']}건 (긴급 {info['urgent']}건)\n"

        # 진행률
        if stats['total'] > 0:
            progress = int(stats['completed'] / stats['total'] * 100)
            text += f"\n**진행률:** {progress}%"

        return {
            'text': text,
            'messages': [],
            'suggestions': [
                "'긴급한 거 알려줘'",
                "'오늘 뭐부터 해야 해?'"
            ],
            'query_type': 'status'
        }

    def _get_status_icon(self, msg: Dict[str, Any]) -> str:
        """상태 아이콘 반환"""
        if msg.get('status') == 'completed':
            return "[완료]"

        d_day = get_d_day(msg.get('deadline'))

        if d_day <= 0:
            return "[지남]"
        elif d_day <= 2:
            return "[긴급]"
        elif d_day <= 7:
            return "[주의]"
        else:
            return "[여유]"

    def _error_response(self, message: str) -> Dict[str, Any]:
        """에러 응답 생성"""
        return {
            'text': message,
            'messages': [],
            'suggestions': [
                "'오늘 쪽지 정리해줘'",
                "'이번 주 마감 알려줘'"
            ],
            'query_type': 'error'
        }

    def get_suggestions(self) -> List[str]:
        """추천 질문 목록 반환"""
        return [
            "오늘 온 쪽지 정리해줘",
            "이번 주 마감 업무 알려줘",
            "지금 뭐부터 해야 해?",
            "생기부 관련 쪽지 찾아줘",
            "업무 현황 알려줘"
        ]


# ============================================================
# 테스트
# ============================================================

if __name__ == "__main__":
    from utils import MessageRepository

    print("=" * 50)
    print("AI 채팅 엔진 테스트")
    print("=" * 50)

    # 샘플 데이터 초기화
    repo = MessageRepository()
    repo.init_sample_data()

    engine = AIChatEngine(repo)

    test_queries = [
        "생기부 관련 쪽지 찾아줘",
        "이번 주 마감 업무 알려줘",
        "출결 마감 언제까지야?",
        "생기부 제출 어떻게 해?",
        "지금 뭐부터 해야 해?",
        "업무 현황 알려줘",
    ]

    for query in test_queries:
        print(f"\n{'='*50}")
        print(f"질문: {query}")
        print("-" * 50)

        response = engine.process(query)
        print(f"유형: {response['query_type']}")
        print(f"\n{response['text']}")

        if response['suggestions']:
            print("\n추천 질문:")
            for s in response['suggestions']:
                print(f"  - {s}")
