"""
MCP 도구 정의 및 구현
CLAUDE.md에 정의된 10개 도구 구현
"""

import os
import sys
import json
import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from pathlib import Path

# 상위 디렉토리를 path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import ConfigManager, get_data_folder, get_db_path
from src.importance import ImportanceCalculator, InfoMetadataExtractor
from src.grouping import MessageGrouper, DeadlineSummarizer, TASK_GROUPS
from src.calendar_sync import GoogleCalendarSync


# ============================================================
# 데이터 저장소 (간단한 JSON 파일 기반)
# ============================================================

class MessageStore:
    """쪽지 데이터 저장소"""

    def __init__(self):
        self.data_folder = get_data_folder()
        self.messages_file = os.path.join(self.data_folder, 'messages.json')
        self.status_file = os.path.join(self.data_folder, 'status.json')
        self._load()

    def _load(self):
        """데이터 로드"""
        self.messages = []
        self.status = {}

        if os.path.exists(self.messages_file):
            try:
                with open(self.messages_file, 'r', encoding='utf-8') as f:
                    self.messages = json.load(f)
            except:
                pass

        if os.path.exists(self.status_file):
            try:
                with open(self.status_file, 'r', encoding='utf-8') as f:
                    self.status = json.load(f)
            except:
                pass

    def _save(self):
        """데이터 저장"""
        with open(self.messages_file, 'w', encoding='utf-8') as f:
            json.dump(self.messages, f, ensure_ascii=False, indent=2)

        with open(self.status_file, 'w', encoding='utf-8') as f:
            json.dump(self.status, f, ensure_ascii=False, indent=2)

    def add_message(self, message: Dict[str, Any]) -> str:
        """쪽지 추가"""
        if 'id' not in message:
            message['id'] = f"msg_{len(self.messages) + 1}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        message['created_at'] = datetime.now().isoformat()
        self.messages.append(message)
        self._save()
        return message['id']

    def get_message(self, message_id: str) -> Optional[Dict[str, Any]]:
        """ID로 쪽지 조회"""
        for msg in self.messages:
            if msg.get('id') == message_id:
                # 상태 정보 병합
                status_info = self.status.get(message_id, {})
                return {**msg, **status_info}
        return None

    def get_message_by_path(self, path: str) -> Optional[Dict[str, Any]]:
        """파일 경로로 쪽지 조회"""
        for msg in self.messages:
            if msg.get('file_path') == path:
                status_info = self.status.get(msg['id'], {})
                return {**msg, **status_info}
        return None

    def get_all_messages(self) -> List[Dict[str, Any]]:
        """모든 쪽지 조회"""
        result = []
        for msg in self.messages:
            status_info = self.status.get(msg.get('id', ''), {})
            result.append({**msg, **status_info})
        return result

    def update_status(self, message_id: str, status_data: Dict[str, Any]):
        """상태 업데이트"""
        if message_id not in self.status:
            self.status[message_id] = {}
        self.status[message_id].update(status_data)
        self.status[message_id]['updated_at'] = datetime.now().isoformat()
        self._save()

    def search(self, query: str = None, date_from: str = None,
               date_to: str = None, sender: str = None,
               status: str = None) -> List[Dict[str, Any]]:
        """쪽지 검색"""
        results = []

        for msg in self.messages:
            # 상태 필터
            msg_status = self.status.get(msg.get('id', ''), {})
            if status and msg_status.get('status') != status:
                continue

            # 날짜 필터
            msg_date = msg.get('date', '')
            if date_from and msg_date < date_from:
                continue
            if date_to and msg_date > date_to:
                continue

            # 발신자 필터
            if sender and sender.lower() not in msg.get('sender', '').lower():
                continue

            # 검색어 필터
            if query:
                text = (msg.get('title', '') + ' ' + msg.get('content', '')).lower()
                if query.lower() not in text:
                    continue

            # 결과에 상태 병합
            results.append({**msg, **msg_status})

        return results


# ============================================================
# 3단계 실행 프로세스 생성기
# ============================================================

# 업무 유형별 프로세스 템플릿
ACTION_TEMPLATES = {
    '담임': {
        'base': ['학생/자료 확인', '나이스 입력', '검토 요청'],
        'details': {
            '생기부': ['담당반 미입력 항목 확인', '세특/행발/창체 최종 입력', '부장 검토 요청'],
            '출결': ['결석 학생 확인', '나이스 출결 처리', '담임 확인'],
            '상담': ['상담 일정 조율', '상담 실시 및 기록', '나이스 상담 입력'],
            '성적': ['성적 입력 확인', '나이스 성적 처리', '확인 및 제출'],
        }
    },
    '제출': {
        'base': ['양식 확인', '내용 작성', '제출 및 확인'],
        'details': {
            '공문': ['공문 내용 및 양식 확인', '기안문 작성', '결재 요청'],
            '보고서': ['양식 다운로드', '내용 작성 및 검토', '기한 내 제출'],
            '계획서': ['작년 자료 참고', '올해 계획 수립', '결재 및 제출'],
        }
    },
    '회의': {
        'base': ['일정 확인', '사전 준비', '참석'],
        'details': {
            '교직원회의': ['회의 시간/장소 확인', '안건 사전 검토', '참석 및 기록'],
            '연수': ['연수 신청/등록', '사전 자료 검토', '이수 및 결과 제출'],
        }
    },
    '협조': {
        'base': ['요청 내용 파악', '업무 처리', '완료 회신'],
        'details': {}
    },
    '예산': {
        'base': ['품의서 확인', '에듀파인 처리', '결재 확인'],
        'details': {}
    },
    '공지': {
        'base': ['내용 확인', '해당 시 일정 등록', '필요 시 공유'],
        'details': {}
    }
}

# 예상 소요 시간
TIME_ESTIMATES = {
    '담임': {'생기부': '2-3시간', '출결': '30분', '상담': '1시간', '성적': '1시간', 'default': '1시간'},
    '제출': {'공문': '1시간', '보고서': '2시간', '계획서': '3시간', 'default': '1시간'},
    '회의': {'default': '1-2시간'},
    '협조': {'default': '30분-1시간'},
    '예산': {'default': '30분'},
    '공지': {'default': '10분'}
}


class ActionProcessGenerator:
    """3단계 실행 프로세스 생성기"""

    def __init__(self):
        self.templates = ACTION_TEMPLATES
        self.time_estimates = TIME_ESTIMATES

    def generate(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """3단계 실행 프로세스 생성"""
        text = (message.get('title', '') + ' ' + message.get('content', '')).lower()

        # 1. 업무 유형 식별
        task_type = self._identify_task_type(text)

        # 2. 세부 유형 식별
        sub_type = self._identify_sub_type(text, task_type)

        # 3. 템플릿 선택
        template = self.templates.get(task_type, self.templates['공지'])

        if sub_type and sub_type in template.get('details', {}):
            actions = template['details'][sub_type]
        else:
            actions = template['base']

        # 4. 프로세스 구성
        process = []
        for i, action in enumerate(actions):
            process.append({
                'step': i + 1,
                'action': action,
                'detail': self._get_action_detail(action, text)
            })

        # 5. 예상 시간 및 권장 시작일
        estimated_time = self._estimate_time(task_type, sub_type)
        recommended_start = self._calculate_recommended_start(
            message.get('deadline'),
            estimated_time
        )

        return {
            'task_type': task_type,
            'sub_type': sub_type,
            'process': process,
            'estimated_time': estimated_time,
            'recommended_start': recommended_start
        }

    def _identify_task_type(self, text: str) -> str:
        """업무 유형 식별"""
        type_keywords = {
            '담임': ['생기부', '생활기록부', '출결', '결석', '상담', '학부모', '성적', '세특', '담임'],
            '제출': ['제출', '보고', '마감', '기한', '공문', '결재', '품의'],
            '회의': ['회의', '연수', '교육', '참석', '워크숍'],
            '협조': ['협조', '요청', '부탁'],
            '예산': ['예산', '지출', '에듀파인', '품의', '정산'],
        }

        for task_type, keywords in type_keywords.items():
            if any(kw in text for kw in keywords):
                return task_type

        return '공지'

    def _identify_sub_type(self, text: str, task_type: str) -> Optional[str]:
        """세부 유형 식별"""
        sub_type_keywords = {
            '담임': {
                '생기부': ['생기부', '생활기록부', '세특', '행발', '창체'],
                '출결': ['출결', '결석', '조퇴', '지각'],
                '상담': ['상담', '학부모'],
                '성적': ['성적', '평가'],
            },
            '제출': {
                '공문': ['공문', '기안'],
                '보고서': ['보고', '보고서'],
                '계획서': ['계획', '계획서'],
            },
            '회의': {
                '교직원회의': ['교직원', '전체', '회의'],
                '연수': ['연수', '교육', '워크숍'],
            }
        }

        if task_type in sub_type_keywords:
            for sub_type, keywords in sub_type_keywords[task_type].items():
                if any(kw in text for kw in keywords):
                    return sub_type

        return None

    def _get_action_detail(self, action: str, text: str) -> str:
        """액션에 대한 상세 설명"""
        # 간단한 컨텍스트 기반 설명
        if '나이스' in action:
            return 'NEIS 시스템에서 처리'
        elif '확인' in action:
            return '관련 자료 및 대상 확인'
        elif '검토' in action:
            return '최종 검토 후 담당자에게 확인 요청'
        elif '제출' in action:
            return '기한 내 제출 완료'
        return action

    def _estimate_time(self, task_type: str, sub_type: Optional[str]) -> str:
        """예상 소요 시간"""
        type_times = self.time_estimates.get(task_type, {'default': '30분'})
        if sub_type and sub_type in type_times:
            return type_times[sub_type]
        return type_times['default']

    def _calculate_recommended_start(self, deadline: Optional[str],
                                     estimated_time: str) -> Optional[str]:
        """권장 시작일 계산"""
        if not deadline:
            return None

        try:
            deadline_date = datetime.strptime(deadline, '%Y-%m-%d')

            # 예상 시간에서 일수 추정
            if '시간' in estimated_time:
                hours = int(re.search(r'(\d+)', estimated_time).group(1))
                buffer_days = max(1, hours // 4)  # 4시간당 1일 여유
            else:
                buffer_days = 1

            # 최소 1일 전, 최대 3일 전
            buffer_days = min(3, max(1, buffer_days))
            recommended = deadline_date - timedelta(days=buffer_days)

            # 오늘보다 이전이면 오늘로
            if recommended.date() < datetime.now().date():
                recommended = datetime.now()

            return recommended.strftime('%Y-%m-%d')
        except:
            return None


# ============================================================
# MCP 도구 함수들
# ============================================================

# 글로벌 인스턴스
_store = None
_importance_calc = None
_grouper = None
_summarizer = None
_process_gen = None
_calendar = None
_meta_extractor = None


def _init_globals():
    """글로벌 인스턴스 초기화"""
    global _store, _importance_calc, _grouper, _summarizer, _process_gen, _calendar, _meta_extractor

    if _store is None:
        _store = MessageStore()
    if _importance_calc is None:
        _importance_calc = ImportanceCalculator()
    if _grouper is None:
        _grouper = MessageGrouper()
    if _summarizer is None:
        _summarizer = DeadlineSummarizer()
    if _process_gen is None:
        _process_gen = ActionProcessGenerator()
    if _calendar is None:
        _calendar = GoogleCalendarSync()
    if _meta_extractor is None:
        _meta_extractor = InfoMetadataExtractor()


# ------------------------------------------------------------
# Tool 1: process_unread_messages
# ------------------------------------------------------------

def process_unread_messages(
    save_markdown: bool = True,
    save_pdf: bool = True,
    download_attachments: bool = True
) -> Dict[str, Any]:
    """안 읽은 쪽지를 모두 처리하여 저장합니다

    Args:
        save_markdown: 마크다운으로 저장할지 여부
        save_pdf: PDF로 저장할지 여부
        download_attachments: 첨부파일 다운로드 여부

    Returns:
        {
            'processed_count': int,
            'saved_files': list[str],
            'errors': list[str]
        }
    """
    _init_globals()

    # 실제 GOE 메신저 자동화는 Windows에서만 동작
    # 여기서는 시뮬레이션/테스트용 응답 반환

    result = {
        'processed_count': 0,
        'saved_files': [],
        'errors': [],
        'message': 'GOE 메신저 자동화는 Windows 환경에서만 지원됩니다. src/messenger.py 구현 필요.'
    }

    # 저장 경로 정보 추가
    save_folder = os.path.join(get_data_folder(), 'saved_messages')
    os.makedirs(save_folder, exist_ok=True)
    result['save_folder'] = save_folder

    return result


# ------------------------------------------------------------
# Tool 2: summarize_message
# ------------------------------------------------------------

def summarize_message(message_path: str) -> Dict[str, Any]:
    """저장된 쪽지 내용을 요약합니다

    Args:
        message_path: 쪽지 파일 경로 또는 메시지 ID

    Returns:
        {
            'summary': str,
            'key_points': list[str],
            'action_items': list[str]
        }
    """
    _init_globals()

    # 메시지 조회
    message = _store.get_message(message_path) or _store.get_message_by_path(message_path)

    if not message:
        return {
            'error': f'메시지를 찾을 수 없습니다: {message_path}',
            'summary': '',
            'key_points': [],
            'action_items': []
        }

    content = message.get('content', '') or message.get('title', '')
    title = message.get('title', '')

    # 핵심 문장 추출 (간단한 휴리스틱)
    sentences = re.split(r'[.。\n]', content)

    # 키워드 기반 중요 문장 선별
    important_keywords = ['마감', '제출', '필수', '반드시', '까지', '기한', '요청']
    key_points = []
    action_items = []

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence or len(sentence) < 5:
            continue

        # 중요 문장 추출
        if any(kw in sentence for kw in important_keywords):
            if '마감' in sentence or '까지' in sentence or '제출' in sentence:
                action_items.append(sentence[:100])
            else:
                key_points.append(sentence[:100])

    # 요약 생성
    summary_parts = []
    if title:
        summary_parts.append(f"제목: {title}")
    if message.get('deadline'):
        summary_parts.append(f"마감: {message['deadline']}")
    if message.get('sender'):
        summary_parts.append(f"발신: {message['sender']}")
    if action_items:
        summary_parts.append(f"실행사항 {len(action_items)}건")

    return {
        'summary': ' | '.join(summary_parts) if summary_parts else content[:200],
        'key_points': key_points[:5],
        'action_items': action_items[:5]
    }


# ------------------------------------------------------------
# Tool 3: classify_message
# ------------------------------------------------------------

def classify_message(message_path: str) -> Dict[str, Any]:
    """쪽지의 중요도와 카테고리를 분류합니다

    Args:
        message_path: 쪽지 파일 경로 또는 메시지 ID

    Returns:
        {
            'importance': 'high'|'medium'|'low',
            'urgency': 'urgent'|'normal'|'low',
            'category': '담임'|'제출'|'회의'|'예산'|'공지'|'기타',
            'tags': list[str]
        }
    """
    _init_globals()

    # 메시지 조회
    message = _store.get_message(message_path) or _store.get_message_by_path(message_path)

    if not message:
        return {
            'error': f'메시지를 찾을 수 없습니다: {message_path}',
            'importance': 'low',
            'urgency': 'low',
            'category': '기타',
            'tags': []
        }

    # 중요도 계산
    importance_result = _importance_calc.calculate(message)

    # 카테고리 분류
    category = _grouper.categorize(message)

    # 중요도 매핑
    grade = importance_result['grade']
    if grade in ['S', 'A']:
        importance = 'high'
    elif grade in ['B', 'C']:
        importance = 'medium'
    else:
        importance = 'low'

    # 긴급도 판단
    d_day = importance_result['breakdown'].get('urgency', {}).get('d_day')
    if d_day is not None:
        if d_day <= 2:
            urgency = 'urgent'
        elif d_day <= 7:
            urgency = 'normal'
        else:
            urgency = 'low'
    else:
        urgency = 'low'

    # 태그 생성
    tags = []
    if importance_result.get('auto_starred'):
        tags.append('중요')
    if importance_result.get('main_category') == 'action':
        tags.append('행동필요')
    else:
        tags.append('정보')
    tags.append(category)

    return {
        'importance': importance,
        'urgency': urgency,
        'category': category,
        'tags': tags,
        'grade': grade,
        'score': importance_result['score'],
        'color_code': importance_result['color_code']
    }


# ------------------------------------------------------------
# Tool 4: search_messages
# ------------------------------------------------------------

def search_messages(
    query: str = None,
    date_from: str = None,
    date_to: str = None,
    sender: str = None
) -> Dict[str, Any]:
    """저장된 쪽지를 검색합니다

    Args:
        query: 검색어
        date_from: 시작 날짜 (YYYY-MM-DD)
        date_to: 종료 날짜 (YYYY-MM-DD)
        sender: 발신자

    Returns:
        {
            'results': list[MessageInfo]
        }
    """
    _init_globals()

    results = _store.search(
        query=query,
        date_from=date_from,
        date_to=date_to,
        sender=sender
    )

    # 결과 포맷팅
    formatted_results = []
    for msg in results:
        importance = _importance_calc.calculate(msg)
        formatted_results.append({
            'id': msg.get('id'),
            'title': msg.get('title'),
            'sender': msg.get('sender'),
            'date': msg.get('date'),
            'deadline': msg.get('deadline'),
            'status': msg.get('status', 'pending'),
            'starred': msg.get('starred', False),
            'grade': importance['grade'],
            'color_code': importance['color_code'],
            'category': _grouper.categorize(msg)
        })

    return {
        'results': formatted_results,
        'count': len(formatted_results)
    }


# ------------------------------------------------------------
# Tool 5: add_to_calendar
# ------------------------------------------------------------

def add_to_calendar(
    message_path: str,
    calendar_id: str = 'primary',
    add_reminders: bool = True
) -> Dict[str, Any]:
    """쪽지 기한을 구글 캘린더에 자동 등록합니다

    Args:
        message_path: 쪽지 파일 경로 또는 메시지 ID
        calendar_id: 캘린더 ID
        add_reminders: 알림 추가 여부

    Returns:
        {
            'event_id': str,
            'event_link': str,
            'reminders_set': list[str]
        }
    """
    _init_globals()

    # 메시지 조회
    message = _store.get_message(message_path) or _store.get_message_by_path(message_path)

    if not message:
        return {
            'error': f'메시지를 찾을 수 없습니다: {message_path}',
            'event_id': None,
            'event_link': None,
            'reminders_set': []
        }

    # 캘린더 인증 확인
    if not _calendar.is_available():
        return {
            'error': 'Google Calendar API를 사용할 수 없습니다. 라이브러리를 설치해주세요.',
            'event_id': None,
            'event_link': None,
            'reminders_set': []
        }

    if not _calendar.is_authenticated():
        return {
            'error': 'Google 계정 인증이 필요합니다. GUI에서 캘린더 연동을 설정해주세요.',
            'event_id': None,
            'event_link': None,
            'reminders_set': []
        }

    # 중요도 기반 정보 추가
    importance = _importance_calc.calculate(message)
    process_info = _process_gen.generate(message)

    # 이벤트 데이터 구성
    if importance['main_category'] == 'action':
        # 행동형 쪽지 → 마감일 이벤트
        if not message.get('deadline'):
            return {
                'error': '마감일이 없는 쪽지입니다.',
                'event_id': None,
                'event_link': None,
                'reminders_set': []
            }

        event_data = {
            'title': message['title'],
            'deadline': message['deadline'],
            'category': process_info['task_type'],
            'summary': summarize_message(message_path)['summary'],
            'process': [p['action'] for p in process_info['process']]
        }

        event_id = _calendar.create_deadline_event(event_data)
        reminders = ['D-3', 'D-1', '당일 오전']
    else:
        # 정보형 쪽지 → 메타데이터 기반 이벤트
        meta = _meta_extractor.extract(message)

        if not meta.get('has_calendar_event'):
            return {
                'error': '일정 정보가 없는 쪽지입니다.',
                'event_id': None,
                'event_link': None,
                'reminders_set': []
            }

        cal_event = meta['calendar_events'][0]
        event_data = {
            'title': message['title'],
            'event_date': cal_event['date'],
            'event_time': cal_event.get('time'),
            'location': cal_event.get('location'),
            'remember': meta.get('remember', [])
        }

        event_id = _calendar.create_info_event(event_data)
        reminders = ['D-1', '1시간 전']

    if event_id:
        # 메시지 상태 업데이트
        _store.update_status(message.get('id'), {
            'calendar_event_id': event_id,
            'calendar_added_at': datetime.now().isoformat()
        })

        return {
            'event_id': event_id,
            'event_link': f'https://calendar.google.com/calendar/event?eid={event_id}',
            'reminders_set': reminders if add_reminders else []
        }

    return {
        'error': '캘린더 이벤트 생성에 실패했습니다.',
        'event_id': None,
        'event_link': None,
        'reminders_set': []
    }


# ------------------------------------------------------------
# Tool 6: calculate_importance
# ------------------------------------------------------------

def calculate_importance(message_path: str) -> Dict[str, Any]:
    """학교업무 특수성을 반영하여 쪽지 중요도를 계산합니다

    Args:
        message_path: 쪽지 파일 경로 또는 메시지 ID

    Returns:
        {
            'grade': 'S'|'A'|'B'|'C'|'D',
            'score': int (0-100),
            'breakdown': {...},
            'color_code': '🔴'|'🟠'|'🟡'|'🟢'|'⚪'
        }
    """
    _init_globals()

    # 메시지 조회
    message = _store.get_message(message_path) or _store.get_message_by_path(message_path)

    if not message:
        # 경로가 실제 파일인 경우 내용 읽기 시도
        if os.path.exists(message_path):
            try:
                with open(message_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                message = {
                    'title': os.path.basename(message_path),
                    'content': content
                }
            except:
                pass

    if not message:
        return {
            'error': f'메시지를 찾을 수 없습니다: {message_path}',
            'grade': 'D',
            'score': 0,
            'breakdown': {},
            'color_code': '⚪'
        }

    result = _importance_calc.calculate(message)

    return {
        'grade': result['grade'],
        'score': result['score'],
        'max_score': result.get('max_score', 60),
        'main_category': result['main_category'],
        'main_category_label': result.get('main_category_label', ''),
        'breakdown': {
            'task_type': result['breakdown']['task_type'],
            'urgency': result['breakdown']['urgency']
        },
        'color_code': result['color_code'],
        'auto_starred': result.get('auto_starred', False)
    }


# ------------------------------------------------------------
# Tool 7: generate_action_process
# ------------------------------------------------------------

def generate_action_process(message_path: str) -> Dict[str, Any]:
    """쪽지 내용을 분석하여 3단계 실행 프로세스를 생성합니다

    Args:
        message_path: 쪽지 파일 경로 또는 메시지 ID

    Returns:
        {
            'task_type': str,
            'process': [...],
            'estimated_time': str,
            'recommended_start': str
        }
    """
    _init_globals()

    # 메시지 조회
    message = _store.get_message(message_path) or _store.get_message_by_path(message_path)

    if not message:
        if os.path.exists(message_path):
            try:
                with open(message_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                message = {
                    'title': os.path.basename(message_path),
                    'content': content
                }
            except:
                pass

    if not message:
        return {
            'error': f'메시지를 찾을 수 없습니다: {message_path}',
            'task_type': '기타',
            'process': [],
            'estimated_time': '알 수 없음',
            'recommended_start': None
        }

    result = _process_gen.generate(message)

    return {
        'task_type': result['task_type'],
        'sub_type': result.get('sub_type'),
        'process': result['process'],
        'estimated_time': result['estimated_time'],
        'recommended_start': result['recommended_start']
    }


# ------------------------------------------------------------
# Tool 8: generate_deadline_summary
# ------------------------------------------------------------

def generate_deadline_summary(
    date_range: str = 'week',
    include_completed: bool = False
) -> Dict[str, Any]:
    """기한 중심으로 쪽지들을 요약합니다

    Args:
        date_range: 'today'|'week'|'month'
        include_completed: 완료된 항목 포함 여부

    Returns:
        {
            'summary_date': str,
            'urgent': list[MessageSummary],
            'this_week': list[MessageSummary],
            'upcoming': list[MessageSummary],
            'no_deadline': list[MessageSummary]
        }
    """
    _init_globals()

    # 모든 메시지 조회
    messages = _store.get_all_messages()

    # 완료 항목 필터링
    if not include_completed:
        messages = [m for m in messages if m.get('status') != 'completed']

    # 요약 생성
    summary = _summarizer.generate_summary(messages, date_range)

    # 마크다운 형식도 추가
    summary['markdown'] = _summarizer.format_as_markdown(summary)
    summary['dashboard'] = _summarizer.format_as_dashboard(summary)

    return summary


# ------------------------------------------------------------
# Tool 9: extract_info_metadata
# ------------------------------------------------------------

def extract_info_metadata(message_path: str) -> Dict[str, Any]:
    """정보 쪽지에서 메타데이터를 추출하고 캘린더에 등록합니다

    Args:
        message_path: 쪽지 파일 경로 또는 메시지 ID

    Returns:
        {
            'type': 'information',
            'summary': {...},
            'dates': [...],
            'location': str,
            'remember': [...],
            'calendar_events': [...],
            'has_calendar_event': bool
        }
    """
    _init_globals()

    # 메시지 조회
    message = _store.get_message(message_path) or _store.get_message_by_path(message_path)

    if not message:
        if os.path.exists(message_path):
            try:
                with open(message_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                message = {
                    'title': os.path.basename(message_path),
                    'content': content
                }
            except:
                pass

    if not message:
        return {
            'error': f'메시지를 찾을 수 없습니다: {message_path}',
            'type': 'information',
            'summary': {},
            'dates': [],
            'location': None,
            'remember': [],
            'calendar_events': [],
            'has_calendar_event': False
        }

    # 메타데이터 추출
    result = _meta_extractor.extract(message)

    return result


# ------------------------------------------------------------
# Tool 10: mark_complete
# ------------------------------------------------------------

def mark_complete(message_path: str) -> Dict[str, Any]:
    """쪽지를 완료 처리합니다

    Args:
        message_path: 쪽지 파일 경로 또는 메시지 ID

    Returns:
        {
            'success': bool,
            'message': str,
            'completed_at': str
        }
    """
    _init_globals()

    # 메시지 조회
    message = _store.get_message(message_path) or _store.get_message_by_path(message_path)

    if not message:
        return {
            'success': False,
            'message': f'메시지를 찾을 수 없습니다: {message_path}',
            'completed_at': None
        }

    message_id = message.get('id')
    completed_at = datetime.now().isoformat()

    # 상태 업데이트
    _store.update_status(message_id, {
        'status': 'completed',
        'completed_at': completed_at
    })

    return {
        'success': True,
        'message': f'완료 처리되었습니다: {message.get("title", message_id)}',
        'completed_at': completed_at
    }


# ------------------------------------------------------------
# 추가 유틸리티 도구
# ------------------------------------------------------------

def check_unread_messages() -> Dict[str, Any]:
    """안 읽은 쪽지 개수를 확인합니다

    Returns:
        {
            'unread_count': int,
            'total_count': int
        }
    """
    _init_globals()

    all_messages = _store.get_all_messages()
    unread = [m for m in all_messages if m.get('status') != 'read' and m.get('status') != 'completed']

    return {
        'unread_count': len(unread),
        'total_count': len(all_messages)
    }


def toggle_star(message_path: str) -> Dict[str, Any]:
    """쪽지의 중요 표시를 토글합니다

    Args:
        message_path: 쪽지 파일 경로 또는 메시지 ID

    Returns:
        {
            'success': bool,
            'starred': bool
        }
    """
    _init_globals()

    message = _store.get_message(message_path) or _store.get_message_by_path(message_path)

    if not message:
        return {
            'success': False,
            'starred': False,
            'error': f'메시지를 찾을 수 없습니다: {message_path}'
        }

    current_starred = message.get('starred', False)
    new_starred = not current_starred

    _store.update_status(message.get('id'), {
        'starred': new_starred
    })

    return {
        'success': True,
        'starred': new_starred
    }


# ============================================================
# 도구 목록 (MCP 서버에서 사용)
# ============================================================

TOOLS = {
    'process_unread_messages': {
        'function': process_unread_messages,
        'description': '안 읽은 쪽지를 모두 처리하여 저장합니다',
        'parameters': {
            'save_markdown': {'type': 'boolean', 'default': True},
            'save_pdf': {'type': 'boolean', 'default': True},
            'download_attachments': {'type': 'boolean', 'default': True}
        }
    },
    'summarize_message': {
        'function': summarize_message,
        'description': '저장된 쪽지 내용을 요약합니다',
        'parameters': {
            'message_path': {'type': 'string', 'required': True}
        }
    },
    'classify_message': {
        'function': classify_message,
        'description': '쪽지의 중요도와 카테고리를 분류합니다',
        'parameters': {
            'message_path': {'type': 'string', 'required': True}
        }
    },
    'search_messages': {
        'function': search_messages,
        'description': '저장된 쪽지를 검색합니다',
        'parameters': {
            'query': {'type': 'string'},
            'date_from': {'type': 'string', 'format': 'YYYY-MM-DD'},
            'date_to': {'type': 'string', 'format': 'YYYY-MM-DD'},
            'sender': {'type': 'string'}
        }
    },
    'add_to_calendar': {
        'function': add_to_calendar,
        'description': '쪽지 기한을 구글 캘린더에 자동 등록합니다',
        'parameters': {
            'message_path': {'type': 'string', 'required': True},
            'calendar_id': {'type': 'string', 'default': 'primary'},
            'add_reminders': {'type': 'boolean', 'default': True}
        }
    },
    'calculate_importance': {
        'function': calculate_importance,
        'description': '학교업무 특수성을 반영하여 쪽지 중요도를 계산합니다',
        'parameters': {
            'message_path': {'type': 'string', 'required': True}
        }
    },
    'generate_action_process': {
        'function': generate_action_process,
        'description': '쪽지 내용을 분석하여 3단계 실행 프로세스를 생성합니다',
        'parameters': {
            'message_path': {'type': 'string', 'required': True}
        }
    },
    'generate_deadline_summary': {
        'function': generate_deadline_summary,
        'description': '기한 중심으로 쪽지들을 요약합니다',
        'parameters': {
            'date_range': {'type': 'string', 'default': 'week'},
            'include_completed': {'type': 'boolean', 'default': False}
        }
    },
    'extract_info_metadata': {
        'function': extract_info_metadata,
        'description': '정보 쪽지에서 메타데이터를 추출합니다',
        'parameters': {
            'message_path': {'type': 'string', 'required': True}
        }
    },
    'mark_complete': {
        'function': mark_complete,
        'description': '쪽지를 완료 처리합니다',
        'parameters': {
            'message_path': {'type': 'string', 'required': True}
        }
    },
    'check_unread_messages': {
        'function': check_unread_messages,
        'description': '안 읽은 쪽지 개수를 확인합니다',
        'parameters': {}
    },
    'toggle_star': {
        'function': toggle_star,
        'description': '쪽지의 중요 표시를 토글합니다',
        'parameters': {
            'message_path': {'type': 'string', 'required': True}
        }
    }
}


# ============================================================
# 테스트
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("MCP Tools 테스트")
    print("=" * 60)

    # 테스트 메시지 추가
    _init_globals()

    test_msg = {
        'title': '2학기 생활기록부 최종 마감 안내',
        'content': '''안녕하세요. 교무기획부입니다.

2학기 생활기록부 최종 마감일을 안내드립니다.
담임선생님께서는 1월 29일까지 나이스에 생기부를 제출해 주세요.

- 세부특기사항: 필수 입력
- 행동발달: 필수 입력
- 창의적체험활동: 필수 입력

마감 후에는 수정이 불가하오니 기한 내 완료 부탁드립니다.''',
        'sender': '교무기획부 김OO 부장',
        'date': datetime.now().strftime('%Y-%m-%d'),
        'deadline': (datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d')
    }

    msg_id = _store.add_message(test_msg)
    print(f"\n테스트 메시지 추가됨: {msg_id}")

    # 도구 테스트
    print("\n--- calculate_importance ---")
    result = calculate_importance(msg_id)
    print(f"등급: {result['grade']} ({result['score']}점) {result['color_code']}")

    print("\n--- classify_message ---")
    result = classify_message(msg_id)
    print(f"카테고리: {result['category']}, 중요도: {result['importance']}")

    print("\n--- generate_action_process ---")
    result = generate_action_process(msg_id)
    print(f"업무유형: {result['task_type']}")
    for p in result['process']:
        print(f"  {p['step']}. {p['action']}")

    print("\n--- summarize_message ---")
    result = summarize_message(msg_id)
    print(f"요약: {result['summary']}")

    print("\n--- search_messages ---")
    result = search_messages(query="생기부")
    print(f"검색 결과: {result['count']}건")

    print("\n--- generate_deadline_summary ---")
    result = generate_deadline_summary()
    print(result['dashboard'])
