"""
GOE메신저 UI 자동화 모듈

경기교육통합메신저(AtMessenger7)의 UI를 자동으로 제어하여
안 읽은 쪽지를 처리하는 모듈입니다.

주요 기능:
    - 메신저 연결 및 실행 상태 확인
    - 쪽지함 네비게이션
    - 안 읽은 쪽지 개수 확인
    - 쪽지 열기/닫기
    - 첨부파일 다운로드

Dependencies:
    - pywinauto: Windows UI 자동화
    - pyautogui: 이미지 인식 및 마우스/키보드 제어
    - Pillow: 이미지 처리

사용 예시:
    >>> from messenger import GOEMessengerController
    >>> controller = GOEMessengerController()
    >>> if controller.connect():
    ...     controller.navigate_to_inbox()
    ...     count = controller.get_unread_count()
    ...     print(f"안 읽은 쪽지: {count}개")
"""

import os
import sys
import time
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

# Windows 전용 라이브러리 - 조건부 임포트
try:
    import pywinauto
    from pywinauto import Application
    from pywinauto.findwindows import ElementNotFoundError, WindowNotFoundError
    from pywinauto.timings import TimeoutError as PywinautoTimeoutError
    PYWINAUTO_AVAILABLE = True
except ImportError:
    PYWINAUTO_AVAILABLE = False
    pywinauto = None
    Application = None
    ElementNotFoundError = Exception
    WindowNotFoundError = Exception
    PywinautoTimeoutError = Exception

try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False
    pyautogui = None

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    Image = None

# 로컬 모듈
try:
    from .config import ConfigManager, get_app_folder, get_attachments_folder
except ImportError:
    from config import ConfigManager, get_app_folder, get_attachments_folder


# ============================================================
# 로깅 설정
# ============================================================

logger = logging.getLogger(__name__)


# ============================================================
# 상수 정의
# ============================================================

class MessengerState(Enum):
    """메신저 상태"""
    NOT_RUNNING = "not_running"         # 실행 안됨
    RUNNING = "running"                 # 실행 중
    CONNECTED = "connected"             # 연결됨
    INBOX_OPEN = "inbox_open"           # 수신함 열림
    MESSAGE_OPEN = "message_open"       # 쪽지 읽기 창 열림


# 윈도우 제목 패턴
MAIN_WINDOW_TITLE = r".*경기도교육청 메신저.*"
MESSAGE_WINDOW_TITLE = "쪽지 읽기"

# UI 요소 이름
UI_ELEMENTS = {
    'menu_message': '쪽지',
    'btn_inbox': '수신함',
    'btn_outbox': '발신함',
    'btn_download': '다운로드',
    'btn_print': '인쇄',
    'btn_close': '닫기',
    'btn_reply': '답장',
    'btn_forward': '전달',
    'btn_delete': '삭제',
    'sort_dropdown': '정렬',
    'sort_unread_first': '읽지 않은 쪽지 우선순',
}

# 기본 대기 시간 (초)
DEFAULT_TIMEOUT = 10
CLICK_DELAY = 0.2
WINDOW_WAIT = 0.5


# ============================================================
# 데이터 클래스
# ============================================================

@dataclass
class MessageInfo:
    """쪽지 정보"""
    index: int                  # 목록에서의 위치 (0부터)
    title: str                  # 제목
    sender: str                 # 발신자
    sender_dept: str            # 발신자 소속
    date: str                   # 수신 날짜
    time: str                   # 수신 시간
    is_read: bool               # 읽음 여부
    has_attachment: bool        # 첨부파일 여부

    def __str__(self) -> str:
        status = "읽음" if self.is_read else "안읽음"
        attach = "📎" if self.has_attachment else ""
        return f"[{status}] {self.title} - {self.sender} ({self.date}) {attach}"


@dataclass
class MessageContent:
    """쪽지 내용"""
    title: str                          # 제목
    sender: str                         # 발신자
    sender_dept: str                    # 발신자 소속
    recipients: List[str]               # 수신자 목록
    date: str                           # 수신 날짜
    time: str                           # 수신 시간
    body: str                           # 본문
    attachments: List[Dict[str, str]]   # 첨부파일 [{name, size}]

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            'title': self.title,
            'sender': self.sender,
            'sender_dept': self.sender_dept,
            'recipients': self.recipients,
            'date': self.date,
            'time': self.time,
            'body': self.body,
            'attachments': self.attachments
        }


# ============================================================
# 예외 클래스
# ============================================================

class MessengerError(Exception):
    """메신저 관련 기본 예외"""
    pass


class MessengerNotRunningError(MessengerError):
    """메신저가 실행되지 않음"""
    pass


class MessengerConnectionError(MessengerError):
    """메신저 연결 실패"""
    pass


class UIElementNotFoundError(MessengerError):
    """UI 요소를 찾을 수 없음"""
    pass


class MessageWindowError(MessengerError):
    """쪽지 창 관련 오류"""
    pass


# ============================================================
# 메시지 윈도우 클래스
# ============================================================

class MessageWindow:
    """쪽지 읽기 창 컨트롤러

    쪽지를 열면 반환되는 객체로, 해당 창의 내용 추출 및
    첨부파일 다운로드 등의 작업을 수행합니다.
    """

    def __init__(self, window, controller: 'GOEMessengerController'):
        """
        Args:
            window: pywinauto 윈도우 객체
            controller: 부모 컨트롤러 참조
        """
        self._window = window
        self._controller = controller
        self._closed = False

    @property
    def is_open(self) -> bool:
        """창이 열려있는지 확인"""
        if self._closed:
            return False
        try:
            return self._window.exists() and self._window.is_visible()
        except Exception:
            return False

    def get_content(self) -> Optional[MessageContent]:
        """쪽지 내용 추출

        Returns:
            MessageContent: 쪽지 내용 객체, 실패 시 None
        """
        if not self.is_open:
            logger.warning("쪽지 창이 열려있지 않습니다")
            return None

        try:
            # TODO: 실제 UI 구조에 맞게 구현 필요
            # 현재는 기본 구조만 정의

            # 제목 추출
            title = self._extract_field('제목')

            # 발신자 추출 (이름 (소속) 형식)
            sender_full = self._extract_field('발신자')
            sender, sender_dept = self._parse_sender(sender_full)

            # 수신자 추출
            recipients_text = self._extract_field('수신자')
            recipients = self._parse_recipients(recipients_text)

            # 날짜/시간 추출
            date, time = self._extract_datetime()

            # 본문 추출
            body = self._extract_body()

            # 첨부파일 목록 추출
            attachments = self._extract_attachments()

            return MessageContent(
                title=title,
                sender=sender,
                sender_dept=sender_dept,
                recipients=recipients,
                date=date,
                time=time,
                body=body,
                attachments=attachments
            )

        except Exception as e:
            logger.error(f"쪽지 내용 추출 실패: {e}")
            return None

    def _extract_field(self, field_name: str) -> str:
        """특정 필드 값 추출"""
        try:
            # 레이블로 필드 찾기
            field = self._window.child_window(title_re=f".*{field_name}.*")
            if field.exists():
                # 다음 형제 요소에서 값 추출 시도
                return field.window_text().strip()
        except Exception as e:
            logger.debug(f"필드 '{field_name}' 추출 실패: {e}")
        return ""

    def _parse_sender(self, sender_text: str) -> Tuple[str, str]:
        """발신자 정보 파싱 (이름 (소속) 형식)"""
        import re
        match = re.match(r'(.+?)\s*\((.+?)\)', sender_text)
        if match:
            return match.group(1).strip(), match.group(2).strip()
        return sender_text.strip(), ""

    def _parse_recipients(self, recipients_text: str) -> List[str]:
        """수신자 목록 파싱"""
        if not recipients_text:
            return []
        # 쉼표 또는 세미콜론으로 구분
        import re
        return [r.strip() for r in re.split(r'[,;]', recipients_text) if r.strip()]

    def _extract_datetime(self) -> Tuple[str, str]:
        """날짜와 시간 추출"""
        # TODO: 실제 UI에서 날짜/시간 추출
        return "", ""

    def _extract_body(self) -> str:
        """본문 내용 추출"""
        try:
            # 본문 영역 (보통 Edit 또는 Document 컨트롤)
            body_control = self._window.child_window(control_type="Document")
            if body_control.exists():
                return body_control.window_text().strip()

            # Edit 컨트롤 시도
            body_control = self._window.child_window(control_type="Edit")
            if body_control.exists():
                return body_control.window_text().strip()

        except Exception as e:
            logger.debug(f"본문 추출 실패: {e}")
        return ""

    def _extract_attachments(self) -> List[Dict[str, str]]:
        """첨부파일 목록 추출"""
        attachments = []
        try:
            # 첨부파일 영역 찾기
            # TODO: 실제 UI 구조에 맞게 구현
            pass
        except Exception as e:
            logger.debug(f"첨부파일 목록 추출 실패: {e}")
        return attachments

    def has_attachments(self) -> bool:
        """첨부파일 존재 여부"""
        try:
            # 다운로드 버튼 존재 여부로 판단
            download_btn = self._window.child_window(
                title=UI_ELEMENTS['btn_download'],
                control_type="Button"
            )
            return download_btn.exists() and download_btn.is_enabled()
        except Exception:
            return False

    def download_attachments(self, save_path: Optional[str] = None) -> List[str]:
        """첨부파일 다운로드

        Args:
            save_path: 저장 경로 (None이면 기본 경로)

        Returns:
            다운로드된 파일 경로 목록
        """
        downloaded = []

        if not self.has_attachments():
            logger.info("다운로드할 첨부파일이 없습니다")
            return downloaded

        if save_path is None:
            save_path = get_attachments_folder()

        try:
            # 방법 1: 다운로드 버튼 클릭 (pywinauto)
            if self._click_download_button():
                time.sleep(1)  # 다운로드 대기
                # TODO: 다운로드된 파일 경로 추적
                logger.info("첨부파일 다운로드 완료")

            # 방법 2: 이미지 인식 (pyautogui) - fallback
            elif PYAUTOGUI_AVAILABLE:
                if self._click_download_by_image():
                    time.sleep(1)
                    logger.info("첨부파일 다운로드 완료 (이미지 인식)")

        except Exception as e:
            logger.error(f"첨부파일 다운로드 실패: {e}")

        return downloaded

    def _click_download_button(self) -> bool:
        """다운로드 버튼 클릭 (pywinauto)"""
        try:
            download_btn = self._window.child_window(
                title=UI_ELEMENTS['btn_download'],
                control_type="Button"
            )
            if download_btn.exists():
                download_btn.click()
                return True
        except Exception as e:
            logger.debug(f"다운로드 버튼 클릭 실패: {e}")
        return False

    def _click_download_by_image(self) -> bool:
        """다운로드 버튼 클릭 (이미지 인식)"""
        if not PYAUTOGUI_AVAILABLE:
            return False

        try:
            # 이미지 파일 경로
            img_path = os.path.join(
                get_app_folder(),
                'assets', 'images', 'btn_download.png'
            )

            if os.path.exists(img_path):
                location = pyautogui.locateOnScreen(img_path, confidence=0.8)
                if location:
                    pyautogui.click(pyautogui.center(location))
                    return True
        except Exception as e:
            logger.debug(f"이미지 인식 다운로드 실패: {e}")
        return False

    def click_print(self) -> bool:
        """인쇄 버튼 클릭"""
        try:
            print_btn = self._window.child_window(
                title=UI_ELEMENTS['btn_print'],
                control_type="Button"
            )
            if print_btn.exists():
                print_btn.click()
                return True
        except Exception as e:
            logger.error(f"인쇄 버튼 클릭 실패: {e}")
        return False

    def close(self) -> bool:
        """창 닫기"""
        if self._closed:
            return True

        try:
            # 닫기 버튼 클릭
            close_btn = self._window.child_window(
                title=UI_ELEMENTS['btn_close'],
                control_type="Button"
            )
            if close_btn.exists():
                close_btn.click()
                self._closed = True
                return True

            # Alt+F4 시도
            self._window.type_keys('%{F4}')
            self._closed = True
            return True

        except Exception as e:
            logger.error(f"쪽지 창 닫기 실패: {e}")
            return False


# ============================================================
# 메인 컨트롤러 클래스
# ============================================================

class GOEMessengerController:
    """GOE메신저 UI 자동화 컨트롤러

    경기교육통합메신저의 UI를 자동으로 제어하여
    쪽지 처리를 수행하는 메인 컨트롤러입니다.

    Attributes:
        state: 현재 메신저 상태
        main_window: 메인 윈도우 객체

    사용 예시:
        >>> controller = GOEMessengerController()
        >>> if controller.connect():
        ...     controller.navigate_to_inbox()
        ...     count = controller.get_unread_count()
        ...     if count > 0:
        ...         msg_window = controller.open_message(0)
        ...         content = msg_window.get_content()
        ...         msg_window.close()
    """

    def __init__(self, config: Optional[ConfigManager] = None):
        """
        Args:
            config: 설정 관리자 (None이면 새로 생성)
        """
        self._config = config or ConfigManager()
        self._app: Optional[Any] = None
        self._main_window: Optional[Any] = None
        self._state = MessengerState.NOT_RUNNING
        self._current_message_window: Optional[MessageWindow] = None

        # 설정값 로드
        self._click_delay = self._config.get('automation.click_delay_ms', 200) / 1000
        self._timeout = self._config.get('automation.timeout', DEFAULT_TIMEOUT)

        # 플랫폼 확인
        if sys.platform != 'win32':
            logger.warning("이 모듈은 Windows에서만 동작합니다")

        # pywinauto 확인
        if not PYWINAUTO_AVAILABLE:
            logger.warning("pywinauto가 설치되지 않았습니다. pip install pywinauto")

    @property
    def state(self) -> MessengerState:
        """현재 상태"""
        return self._state

    @property
    def main_window(self):
        """메인 윈도우"""
        return self._main_window

    @property
    def is_connected(self) -> bool:
        """연결 상태"""
        return self._state in [
            MessengerState.CONNECTED,
            MessengerState.INBOX_OPEN,
            MessengerState.MESSAGE_OPEN
        ]

    def is_running(self) -> bool:
        """메신저 실행 중인지 확인

        Returns:
            bool: 실행 중이면 True
        """
        if not PYWINAUTO_AVAILABLE:
            return False

        try:
            from pywinauto import findwindows
            handles = findwindows.find_windows(title_re=MAIN_WINDOW_TITLE)
            return len(handles) > 0
        except Exception as e:
            logger.debug(f"메신저 실행 확인 실패: {e}")
            return False

    def connect(self, timeout: Optional[int] = None) -> bool:
        """실행 중인 메신저에 연결

        Args:
            timeout: 연결 대기 시간 (초)

        Returns:
            bool: 연결 성공 여부

        Raises:
            MessengerNotRunningError: 메신저가 실행되지 않음
            MessengerConnectionError: 연결 실패
        """
        if not PYWINAUTO_AVAILABLE:
            raise MessengerConnectionError("pywinauto가 설치되지 않았습니다")

        timeout = timeout or self._timeout

        try:
            self._app = Application(backend='uia').connect(
                title_re=MAIN_WINDOW_TITLE,
                timeout=timeout
            )
            self._main_window = self._app.top_window()
            self._state = MessengerState.CONNECTED

            logger.info("GOE메신저 연결 성공")
            return True

        except WindowNotFoundError:
            self._state = MessengerState.NOT_RUNNING
            raise MessengerNotRunningError("GOE메신저가 실행되지 않았습니다")

        except PywinautoTimeoutError:
            self._state = MessengerState.NOT_RUNNING
            raise MessengerNotRunningError(
                f"GOE메신저를 찾을 수 없습니다 (대기 시간: {timeout}초)"
            )

        except Exception as e:
            raise MessengerConnectionError(f"메신저 연결 실패: {e}")

    def disconnect(self) -> None:
        """연결 해제"""
        self._app = None
        self._main_window = None
        self._state = MessengerState.NOT_RUNNING
        self._current_message_window = None
        logger.info("GOE메신저 연결 해제")

    def navigate_to_inbox(self) -> bool:
        """쪽지 > 수신함으로 이동

        Returns:
            bool: 이동 성공 여부

        Raises:
            MessengerConnectionError: 연결되지 않음
            UIElementNotFoundError: UI 요소를 찾을 수 없음
        """
        if not self.is_connected:
            raise MessengerConnectionError("메신저에 연결되어 있지 않습니다")

        try:
            # 1. 쪽지 메뉴 클릭
            if not self._click_element(UI_ELEMENTS['menu_message']):
                # 이미지 인식으로 시도
                if not self._click_by_image('menu_message.png'):
                    raise UIElementNotFoundError("쪽지 메뉴를 찾을 수 없습니다")

            time.sleep(self._click_delay)

            # 2. 수신함 버튼 클릭
            if not self._click_element(UI_ELEMENTS['btn_inbox']):
                raise UIElementNotFoundError("수신함 버튼을 찾을 수 없습니다")

            time.sleep(WINDOW_WAIT)
            self._state = MessengerState.INBOX_OPEN

            logger.info("수신함으로 이동 완료")
            return True

        except UIElementNotFoundError:
            raise
        except Exception as e:
            logger.error(f"수신함 이동 실패: {e}")
            return False

    def set_sort_unread_first(self) -> bool:
        """정렬: 읽지 않은 쪽지 우선순

        Returns:
            bool: 설정 성공 여부
        """
        if not self.is_connected:
            return False

        try:
            # 정렬 드롭다운 클릭
            sort_combo = self._main_window.child_window(
                control_type="ComboBox"
            )
            if sort_combo.exists():
                sort_combo.click()
                time.sleep(self._click_delay)

                # 옵션 선택
                sort_combo.select(UI_ELEMENTS['sort_unread_first'])
                logger.info("정렬 설정: 읽지 않은 쪽지 우선순")
                return True

        except Exception as e:
            logger.debug(f"정렬 설정 실패: {e}")

        return False

    def get_unread_count(self) -> int:
        """안 읽은 쪽지 개수 반환

        Returns:
            int: 안 읽은 쪽지 개수 (확인 실패 시 -1)
        """
        if not self.is_connected:
            return -1

        try:
            # 방법 1: 목록에서 읽지 않은 항목 수 계산
            messages = self.get_message_list()
            return sum(1 for msg in messages if not msg.is_read)

        except Exception as e:
            logger.error(f"안 읽은 쪽지 개수 확인 실패: {e}")
            return -1

    def get_message_list(self, max_count: int = 50) -> List[MessageInfo]:
        """쪽지 목록 조회

        Args:
            max_count: 최대 조회 개수

        Returns:
            쪽지 정보 목록
        """
        messages = []

        if not self.is_connected:
            return messages

        try:
            # 목록 컨트롤 찾기 (ListView, List, DataGrid 등)
            list_control = self._find_message_list_control()

            if list_control is None:
                logger.warning("쪽지 목록 컨트롤을 찾을 수 없습니다")
                return messages

            # 목록 항목 순회
            items = list_control.children()
            for i, item in enumerate(items[:max_count]):
                try:
                    msg_info = self._parse_message_item(i, item)
                    if msg_info:
                        messages.append(msg_info)
                except Exception as e:
                    logger.debug(f"쪽지 항목 {i} 파싱 실패: {e}")

            logger.info(f"쪽지 목록 조회: {len(messages)}개")

        except Exception as e:
            logger.error(f"쪽지 목록 조회 실패: {e}")

        return messages

    def _find_message_list_control(self):
        """쪽지 목록 컨트롤 찾기"""
        if not self._main_window:
            return None

        # 여러 컨트롤 타입 시도
        for control_type in ['List', 'ListView', 'DataGrid', 'Table']:
            try:
                control = self._main_window.child_window(control_type=control_type)
                if control.exists():
                    return control
            except Exception:
                continue

        return None

    def _parse_message_item(self, index: int, item) -> Optional[MessageInfo]:
        """쪽지 목록 항목 파싱"""
        try:
            # TODO: 실제 UI 구조에 맞게 구현
            # 기본 구조 가정
            text = item.window_text()

            # 텍스트 파싱 (예: "제목 - 발신자 - 날짜" 형식)
            parts = text.split(' - ')

            return MessageInfo(
                index=index,
                title=parts[0] if len(parts) > 0 else "",
                sender=parts[1] if len(parts) > 1 else "",
                sender_dept="",
                date=parts[2] if len(parts) > 2 else "",
                time="",
                is_read=not self._check_unread_style(item),
                has_attachment=self._check_attachment_icon(item)
            )

        except Exception as e:
            logger.debug(f"항목 파싱 실패: {e}")
            return None

    def _check_unread_style(self, item) -> bool:
        """읽지 않은 스타일인지 확인 (굵은 글씨 등)"""
        # TODO: 실제 스타일 확인 로직
        return False

    def _check_attachment_icon(self, item) -> bool:
        """첨부파일 아이콘 존재 확인"""
        # TODO: 첨부파일 아이콘 확인 로직
        return False

    def open_message(self, index: int) -> Optional[MessageWindow]:
        """특정 쪽지 열기 (더블클릭)

        Args:
            index: 목록에서의 위치 (0부터)

        Returns:
            MessageWindow: 열린 쪽지 창 객체, 실패 시 None
        """
        if not self.is_connected:
            return None

        try:
            # 목록 컨트롤 찾기
            list_control = self._find_message_list_control()
            if list_control is None:
                logger.error("쪽지 목록을 찾을 수 없습니다")
                return None

            # 항목 선택 및 더블클릭
            items = list_control.children()
            if index >= len(items):
                logger.error(f"인덱스 {index}가 목록 범위를 벗어났습니다")
                return None

            item = items[index]
            item.double_click_input()

            # 쪽지 읽기 창 대기
            time.sleep(WINDOW_WAIT)

            msg_window = self._wait_for_message_window()
            if msg_window:
                self._state = MessengerState.MESSAGE_OPEN
                self._current_message_window = MessageWindow(msg_window, self)
                logger.info(f"쪽지 열기 완료 (인덱스: {index})")
                return self._current_message_window
            else:
                logger.error("쪽지 창이 열리지 않았습니다")
                return None

        except Exception as e:
            logger.error(f"쪽지 열기 실패: {e}")
            return None

    def open_first_unread(self) -> Optional[MessageWindow]:
        """첫 번째 안 읽은 쪽지 열기

        Returns:
            MessageWindow: 열린 쪽지 창 객체, 안 읽은 쪽지가 없으면 None
        """
        messages = self.get_message_list()

        for msg in messages:
            if not msg.is_read:
                return self.open_message(msg.index)

        logger.info("안 읽은 쪽지가 없습니다")
        return None

    def _wait_for_message_window(self, timeout: Optional[int] = None):
        """쪽지 읽기 창 대기"""
        if not PYWINAUTO_AVAILABLE:
            return None

        timeout = timeout or self._timeout
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                # 새 창 연결 시도
                msg_app = Application(backend='uia').connect(
                    title=MESSAGE_WINDOW_TITLE,
                    timeout=1
                )
                return msg_app.top_window()
            except Exception:
                time.sleep(0.5)

        return None

    def close_message_window(self) -> bool:
        """쪽지 읽기 창 닫기

        Returns:
            bool: 닫기 성공 여부
        """
        if self._current_message_window:
            result = self._current_message_window.close()
            if result:
                self._current_message_window = None
                self._state = MessengerState.INBOX_OPEN
            return result

        # 직접 창 찾아서 닫기
        try:
            if PYWINAUTO_AVAILABLE:
                msg_app = Application(backend='uia').connect(
                    title=MESSAGE_WINDOW_TITLE,
                    timeout=1
                )
                msg_window = msg_app.top_window()
                msg_window.close()
                self._state = MessengerState.INBOX_OPEN
                return True
        except Exception:
            pass

        return False

    def _click_element(self, title: str, control_type: str = "Button") -> bool:
        """UI 요소 클릭

        Args:
            title: 요소 텍스트
            control_type: 컨트롤 타입

        Returns:
            bool: 클릭 성공 여부
        """
        if not self._main_window:
            return False

        try:
            element = self._main_window.child_window(
                title=title,
                control_type=control_type
            )
            if element.exists():
                element.click()
                time.sleep(self._click_delay)
                return True
        except Exception as e:
            logger.debug(f"요소 '{title}' 클릭 실패: {e}")

        return False

    def _click_by_image(self, image_name: str, confidence: float = 0.8) -> bool:
        """이미지 인식으로 클릭

        Args:
            image_name: 이미지 파일명
            confidence: 인식 정확도 (0-1)

        Returns:
            bool: 클릭 성공 여부
        """
        if not PYAUTOGUI_AVAILABLE:
            return False

        try:
            img_path = os.path.join(
                get_app_folder(),
                'assets', 'images', image_name
            )

            if not os.path.exists(img_path):
                logger.debug(f"이미지 파일 없음: {img_path}")
                return False

            location = pyautogui.locateOnScreen(img_path, confidence=confidence)
            if location:
                pyautogui.click(pyautogui.center(location))
                time.sleep(self._click_delay)
                return True

        except Exception as e:
            logger.debug(f"이미지 인식 클릭 실패 ({image_name}): {e}")

        return False

    def bring_to_front(self) -> bool:
        """메신저 창을 앞으로 가져오기

        Returns:
            bool: 성공 여부
        """
        if not self._main_window:
            return False

        try:
            self._main_window.set_focus()
            return True
        except Exception as e:
            logger.error(f"창 앞으로 가져오기 실패: {e}")
            return False

    def minimize(self) -> bool:
        """최소화"""
        if not self._main_window:
            return False

        try:
            self._main_window.minimize()
            return True
        except Exception:
            return False

    def restore(self) -> bool:
        """복원"""
        if not self._main_window:
            return False

        try:
            self._main_window.restore()
            return True
        except Exception:
            return False

    def get_window_rect(self) -> Optional[Tuple[int, int, int, int]]:
        """창 위치/크기 반환 (left, top, right, bottom)"""
        if not self._main_window:
            return None

        try:
            rect = self._main_window.rectangle()
            return (rect.left, rect.top, rect.right, rect.bottom)
        except Exception:
            return None


# ============================================================
# 유틸리티 함수
# ============================================================

def retry(max_attempts: int = 3, delay: float = 1.0):
    """재시도 데코레이터

    Args:
        max_attempts: 최대 시도 횟수
        delay: 시도 간 대기 시간 (초)
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    logger.warning(
                        f"{func.__name__} 실패 (시도 {attempt + 1}/{max_attempts}): {e}"
                    )
                    if attempt < max_attempts - 1:
                        time.sleep(delay)
            raise last_error
        return wrapper
    return decorator


# ============================================================
# 테스트/데모
# ============================================================

def demo():
    """데모 실행"""
    print("=" * 60)
    print("GOE메신저 자동화 컨트롤러 데모")
    print("=" * 60)

    # 환경 확인
    print(f"\n운영체제: {sys.platform}")
    print(f"pywinauto 사용 가능: {PYWINAUTO_AVAILABLE}")
    print(f"pyautogui 사용 가능: {PYAUTOGUI_AVAILABLE}")
    print(f"PIL 사용 가능: {PIL_AVAILABLE}")

    if sys.platform != 'win32':
        print("\n[!] 이 모듈은 Windows에서만 동작합니다.")
        return

    if not PYWINAUTO_AVAILABLE:
        print("\n[!] pywinauto가 설치되지 않았습니다.")
        print("    pip install pywinauto")
        return

    # 컨트롤러 생성
    controller = GOEMessengerController()

    # 실행 상태 확인
    print(f"\n메신저 실행 중: {controller.is_running()}")

    if controller.is_running():
        try:
            # 연결
            print("\n메신저 연결 중...")
            controller.connect()
            print(f"연결 상태: {controller.state.value}")

            # 수신함 이동
            print("\n수신함으로 이동 중...")
            controller.navigate_to_inbox()

            # 정렬 설정
            controller.set_sort_unread_first()

            # 안 읽은 쪽지 확인
            unread = controller.get_unread_count()
            print(f"안 읽은 쪽지: {unread}개")

            # 목록 조회
            messages = controller.get_message_list(max_count=5)
            print(f"\n최근 쪽지 {len(messages)}개:")
            for msg in messages:
                print(f"  {msg}")

        except MessengerNotRunningError:
            print("[!] GOE메신저가 실행되지 않았습니다.")
        except MessengerConnectionError as e:
            print(f"[!] 연결 실패: {e}")
        except UIElementNotFoundError as e:
            print(f"[!] UI 요소 찾기 실패: {e}")
        except Exception as e:
            print(f"[!] 오류: {e}")
    else:
        print("\n[!] GOE메신저가 실행되지 않았습니다.")
        print("    메신저를 먼저 실행해주세요.")


if __name__ == "__main__":
    # 로깅 설정
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    demo()
