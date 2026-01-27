"""
데이터 모델 정의
다른 모듈에서 import하여 사용
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Dict, Any, List, Optional


# ============================================================
# Enums
# ============================================================

class MessageStatus(Enum):
    """메시지 상태"""
    PENDING = "pending"       # 대기 (미완료)
    IN_PROGRESS = "in_progress"  # 진행 중
    COMPLETED = "completed"   # 완료
    ARCHIVED = "archived"     # 보관 (숨김)


class ImportanceGrade(Enum):
    """중요도 등급 (60점 만점)"""
    S = "S"  # 50점 이상 🔴
    A = "A"  # 40-49점 🟠
    B = "B"  # 25-39점 🟡
    C = "C"  # 10-24점 🟢
    D = "D"  # 0-9점 ⚪


class MessageCategory(Enum):
    """메시지 대분류"""
    ACTION = "action"           # 행동 필요
    INFORMATION = "information" # 정보 제공


class TaskGroup(Enum):
    """업무 그룹"""
    HOMEROOM = "담임"   # 🎓 담임업무
    SUBMIT = "제출"     # 📋 제출/보고
    MEETING = "회의"    # 📅 회의/연수
    BUDGET = "예산"     # 💰 예산/행정
    NOTICE = "공지"     # 📢 공지/안내


# ============================================================
# 아이콘/색상 매핑
# ============================================================

GRADE_COLORS = {
    ImportanceGrade.S: "🔴",
    ImportanceGrade.A: "🟠",
    ImportanceGrade.B: "🟡",
    ImportanceGrade.C: "🟢",
    ImportanceGrade.D: "⚪",
}

GROUP_ICONS = {
    TaskGroup.HOMEROOM: "🎓",
    TaskGroup.SUBMIT: "📋",
    TaskGroup.MEETING: "📅",
    TaskGroup.BUDGET: "💰",
    TaskGroup.NOTICE: "📢",
}


# ============================================================
# 데이터 모델
# ============================================================

@dataclass
class Attachment:
    """첨부파일"""
    filename: str
    original_name: str
    size: int = 0
    downloaded: bool = False
    download_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Attachment":
        return cls(**data)


@dataclass
class ImportanceScore:
    """중요도 점수 상세"""
    grade: str                    # S, A, B, C, D
    score: int                    # 총점 (0-60)
    max_score: int = 60
    main_category: str = "action" # action / information
    color_code: str = "⚪"
    auto_starred: bool = False
    breakdown: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ImportanceScore":
        return cls(**data)


@dataclass
class ActionProcess:
    """실행 프로세스 단계"""
    step: int
    action: str
    detail: str
    completed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ActionProcess":
        return cls(**data)


@dataclass
class Message:
    """쪽지 메시지 모델"""

    # 기본 정보
    id: str                           # 고유 ID (UUID)
    title: str                        # 제목
    content: str                      # 본문
    sender: str                       # 발신자
    sender_dept: str = ""             # 발신자 소속
    receivers: List[str] = field(default_factory=list)  # 수신자 목록

    # 날짜/시간
    received_at: str = ""             # 수신 일시 (ISO format)
    deadline: Optional[str] = None    # 마감일 (YYYY-MM-DD)

    # 상태 및 분류
    status: str = MessageStatus.PENDING.value
    starred: bool = False             # 중요 표시
    category: str = MessageCategory.ACTION.value  # 대분류
    task_group: str = TaskGroup.NOTICE.value      # 업무 그룹

    # 중요도
    importance: Optional[Dict[str, Any]] = None   # ImportanceScore as dict

    # 실행 프로세스
    process: List[Dict[str, Any]] = field(default_factory=list)

    # 첨부파일
    attachments: List[Dict[str, Any]] = field(default_factory=list)

    # 저장 경로
    md_path: Optional[str] = None     # 마크다운 파일 경로
    pdf_path: Optional[str] = None    # PDF 파일 경로

    # 메타데이터 (정보 쪽지용)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # 병합 정보
    merged_count: int = 1
    merged_from: List[Dict[str, Any]] = field(default_factory=list)

    # 캘린더 연동
    calendar_event_id: Optional[str] = None

    # 시스템 필드
    created_at: str = ""              # 생성 일시
    updated_at: str = ""              # 수정 일시

    def __post_init__(self):
        """생성 시 기본값 설정"""
        now = datetime.now().isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now
        if not self.received_at:
            self.received_at = now

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환 (DB 저장용)"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        """딕셔너리에서 생성"""
        return cls(**data)

    @property
    def d_day(self) -> Optional[int]:
        """D-day 계산"""
        if not self.deadline:
            return None
        try:
            deadline_date = datetime.strptime(self.deadline, '%Y-%m-%d').date()
            today = datetime.now().date()
            return (deadline_date - today).days
        except ValueError:
            return None

    @property
    def is_urgent(self) -> bool:
        """긴급 여부 (D-2 이내)"""
        d_day = self.d_day
        return d_day is not None and d_day <= 2

    @property
    def is_completed(self) -> bool:
        """완료 여부"""
        return self.status == MessageStatus.COMPLETED.value

    @property
    def grade(self) -> str:
        """중요도 등급"""
        if self.importance:
            return self.importance.get('grade', 'D')
        return 'D'

    @property
    def color_code(self) -> str:
        """상태에 따른 색상 코드"""
        if self.is_completed:
            return "✅"

        d_day = self.d_day
        if d_day is not None:
            if d_day <= 0:
                return "🔴"  # 지남/당일
            elif d_day <= 2:
                return "🔴"  # 긴급
            elif d_day <= 7:
                return "🟡"  # 이번 주
            else:
                return "🟢"  # 여유
        return "⚪"

    def mark_completed(self) -> None:
        """완료 처리"""
        self.status = MessageStatus.COMPLETED.value
        self.updated_at = datetime.now().isoformat()

    def toggle_star(self) -> None:
        """중요 표시 토글"""
        self.starred = not self.starred
        self.updated_at = datetime.now().isoformat()


# ============================================================
# 필터/검색 모델
# ============================================================

@dataclass
class MessageFilter:
    """메시지 검색/필터 조건"""
    query: Optional[str] = None           # 검색어 (제목/본문)
    sender: Optional[str] = None          # 발신자
    status: Optional[str] = None          # 상태
    starred_only: bool = False            # 중요 표시만
    category: Optional[str] = None        # 대분류
    task_group: Optional[str] = None      # 업무 그룹
    date_from: Optional[str] = None       # 시작일
    date_to: Optional[str] = None         # 종료일
    has_deadline: Optional[bool] = None   # 마감일 있음/없음
    grade: Optional[str] = None           # 중요도 등급

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


# ============================================================
# 통계 모델
# ============================================================

@dataclass
class DashboardStats:
    """대시보드 통계"""
    total: int = 0
    pending: int = 0
    in_progress: int = 0
    completed: int = 0
    urgent: int = 0
    starred: int = 0
    today_new: int = 0

    @property
    def completion_rate(self) -> float:
        """완료율"""
        if self.total == 0:
            return 0.0
        return (self.completed / self.total) * 100

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['completion_rate'] = self.completion_rate
        return data


# ============================================================
# 인터페이스 정의 (다른 모듈에서 사용)
# ============================================================

# 타입 힌트용 별칭
MessageDict = Dict[str, Any]
AttachmentDict = Dict[str, Any]
FilterDict = Dict[str, Any]


def create_message(
    title: str,
    content: str,
    sender: str,
    **kwargs
) -> Message:
    """메시지 생성 헬퍼 함수"""
    import uuid
    return Message(
        id=str(uuid.uuid4()),
        title=title,
        content=content,
        sender=sender,
        **kwargs
    )


def create_attachment(
    filename: str,
    original_name: str,
    **kwargs
) -> Attachment:
    """첨부파일 생성 헬퍼 함수"""
    return Attachment(
        filename=filename,
        original_name=original_name,
        **kwargs
    )


# ============================================================
# 테스트
# ============================================================

if __name__ == "__main__":
    # 메시지 생성 테스트
    msg = create_message(
        title="생활기록부 최종 마감 안내",
        content="담임선생님께서는 1월 29일까지 나이스에 생기부를 제출해 주세요.",
        sender="교무기획부 김OO 부장",
        deadline="2025-01-29",
        starred=True
    )

    print("=== 메시지 생성 테스트 ===")
    print(f"ID: {msg.id}")
    print(f"제목: {msg.title}")
    print(f"발신자: {msg.sender}")
    print(f"마감일: {msg.deadline}")
    print(f"D-day: {msg.d_day}")
    print(f"긴급: {msg.is_urgent}")
    print(f"색상: {msg.color_code}")
    print(f"중요: {'⭐' if msg.starred else '☆'}")

    print("\n=== 딕셔너리 변환 ===")
    msg_dict = msg.to_dict()
    print(f"Keys: {list(msg_dict.keys())}")

    print("\n=== 딕셔너리에서 복원 ===")
    msg2 = Message.from_dict(msg_dict)
    print(f"복원 ID: {msg2.id}")
    print(f"복원 제목: {msg2.title}")
