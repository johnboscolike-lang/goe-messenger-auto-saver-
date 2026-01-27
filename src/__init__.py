"""
GOE 메신저 도우미 - 메인 패키지

경기교육통합메신저의 안 읽은 쪽지를 자동으로 저장하고,
AI 기반 대시보드를 통해 업무를 효율적으로 관리하는 프로그램입니다.
"""

__version__ = '1.0.0'

# ============================================================
# Config 모듈
# ============================================================
from .config import (
    ConfigManager,
    get_data_folder,
    get_attachments_folder,
    get_config_path,
    get_db_path,
    get_log_path,
    get_token_path,
    is_first_run,
    init_first_run,
)

# ============================================================
# 데이터 모델
# ============================================================
from .models import (
    Message,
    MessageStatus,
    MessageCategory,
    TaskGroup,
    ImportanceGrade,
    MessageFilter,
    DashboardStats,
    Attachment,
    ImportanceScore,
    ActionProcess,
    create_message,
    create_attachment,
    GRADE_COLORS,
    GROUP_ICONS,
)

# ============================================================
# 데이터베이스
# ============================================================
from .database import (
    MessageDatabase,
    StatusManager,
    get_database,
    init_database,
)

# ============================================================
# 저장 모듈
# ============================================================
from .saver import MessageSaver, save_message

# ============================================================
# 중요도 판단 시스템
# ============================================================
from .importance import ImportanceCalculator, InfoMetadataExtractor

# ============================================================
# 업무 그룹핑
# ============================================================
from .grouping import MessageGrouper, DeadlineSummarizer

# ============================================================
# 캘린더 연동
# ============================================================
try:
    from .calendar_sync import GoogleCalendarSync
    # 별칭 제공
    CalendarSync = GoogleCalendarSync
    CALENDAR_AVAILABLE = True
except ImportError:
    GoogleCalendarSync = None
    CalendarSync = None
    CALENDAR_AVAILABLE = False

# ============================================================
# Windows 전용 모듈 (조건부 임포트)
# ============================================================

# 메신저 컨트롤러 (Windows 전용 - pywinauto 필요)
try:
    from .messenger import GOEMessengerController, MessageWindow
    MESSENGER_AVAILABLE = True
except ImportError:
    GOEMessengerController = None
    MessageWindow = None
    MESSENGER_AVAILABLE = False

# 내용 추출기 (Windows 전용 - pywinauto 필요)
try:
    from .extractor import MessageExtractor, ExtractionError
    EXTRACTOR_AVAILABLE = True
except ImportError:
    MessageExtractor = None
    ExtractionError = None
    EXTRACTOR_AVAILABLE = False

# ============================================================
# AI 채팅 엔진 (utils 의존성 있음)
# ============================================================
try:
    from .ai_chat import AIChatEngine, QueryClassifier
    AI_CHAT_AVAILABLE = True
except ImportError:
    AIChatEngine = None
    QueryClassifier = None
    AI_CHAT_AVAILABLE = False


# ============================================================
# __all__ - 공개 API 정의
# ============================================================
__all__ = [
    # 버전
    '__version__',

    # 가용성 플래그
    'MESSENGER_AVAILABLE',
    'EXTRACTOR_AVAILABLE',
    'CALENDAR_AVAILABLE',
    'AI_CHAT_AVAILABLE',

    # config
    'ConfigManager',
    'get_data_folder',
    'get_attachments_folder',
    'get_config_path',
    'get_db_path',
    'get_log_path',
    'get_token_path',
    'is_first_run',
    'init_first_run',

    # models
    'Message',
    'MessageStatus',
    'MessageCategory',
    'TaskGroup',
    'ImportanceGrade',
    'MessageFilter',
    'DashboardStats',
    'Attachment',
    'ImportanceScore',
    'ActionProcess',
    'create_message',
    'create_attachment',
    'GRADE_COLORS',
    'GROUP_ICONS',

    # database
    'MessageDatabase',
    'StatusManager',
    'get_database',
    'init_database',

    # saver
    'MessageSaver',
    'save_message',

    # importance
    'ImportanceCalculator',
    'InfoMetadataExtractor',

    # grouping
    'MessageGrouper',
    'DeadlineSummarizer',

    # calendar_sync
    'GoogleCalendarSync',
    'CalendarSync',

    # messenger (Windows only)
    'GOEMessengerController',
    'MessageWindow',

    # extractor (Windows only)
    'MessageExtractor',
    'ExtractionError',

    # ai_chat
    'AIChatEngine',
    'QueryClassifier',
]
