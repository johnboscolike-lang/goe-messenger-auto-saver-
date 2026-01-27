"""
쪽지 내용 추출 모듈
- 열린 쪽지 읽기 창에서 메타데이터, 본문, 첨부파일 정보 추출
- pywinauto UIA 백엔드 사용
- 첨부파일 다운로드 지원
"""

import os
import re
import time
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

# Windows 전용 모듈 (조건부 임포트)
try:
    from pywinauto import Application
    from pywinauto.controls.uiawrapper import UIAWrapper
    from pywinauto.findwindows import ElementNotFoundError
    import pyautogui
    WINDOWS_AVAILABLE = True
except ImportError:
    WINDOWS_AVAILABLE = False

# 로깅 설정
logger = logging.getLogger(__name__)


# ==================== 상수 정의 ====================

# 쪽지 읽기 창 제목 패턴
MESSAGE_WINDOW_TITLE = "쪽지 읽기"

# UI 요소 대기 시간 (초)
DEFAULT_TIMEOUT = 10
CLICK_DELAY = 0.2
DOWNLOAD_WAIT = 3

# 날짜 파싱 패턴
DATE_PATTERNS = [
    # "2025-01-27 14:30"
    (r'(\d{4})[-./](\d{1,2})[-./](\d{1,2})\s+(\d{1,2}):(\d{2})', 'datetime'),
    # "2025-01-27"
    (r'(\d{4})[-./](\d{1,2})[-./](\d{1,2})', 'date'),
    # "01-27 14:30"
    (r'(\d{1,2})[-./](\d{1,2})\s+(\d{1,2}):(\d{2})', 'short_datetime'),
]

# 발신자 정보 파싱 패턴
SENDER_PATTERN = r'^(.+?)\s*\((.+?)\)\s*$'  # "홍길동 (교무기획부)"
SENDER_PATTERN_ALT = r'^(.+?)\s+(.+)$'       # "홍길동 교무기획부"


class MessageExtractor:
    """쪽지 내용 추출기

    GOE 메신저의 쪽지 읽기 창에서 내용을 추출합니다.

    사용법:
        extractor = MessageExtractor()

        # 열린 쪽지 창에서 전체 추출
        message = extractor.extract_all(window)

        # 개별 추출
        metadata = extractor.extract_metadata(window)
        body = extractor.extract_body(window)
        attachments = extractor.extract_attachments(window)
    """

    def __init__(self, config: Optional[Dict] = None):
        """초기화

        Args:
            config: 설정 딕셔너리 (선택)
                - timeout: UI 요소 대기 시간 (초)
                - click_delay: 클릭 후 대기 시간 (초)
                - download_wait: 다운로드 완료 대기 시간 (초)
                - use_clipboard: 클립보드 기반 추출 사용 여부
        """
        self.config = config or {}
        self.timeout = self.config.get('timeout', DEFAULT_TIMEOUT)
        self.click_delay = self.config.get('click_delay', CLICK_DELAY)
        self.download_wait = self.config.get('download_wait', DOWNLOAD_WAIT)
        self.use_clipboard = self.config.get('use_clipboard', False)

        if not WINDOWS_AVAILABLE:
            logger.warning("pywinauto/pyautogui를 사용할 수 없습니다. Windows에서만 실행 가능합니다.")

    # ==================== 메인 추출 메서드 ====================

    def extract_all(self, window) -> Dict[str, Any]:
        """전체 추출 (메타데이터 + 본문 + 첨부파일)

        Args:
            window: pywinauto 윈도우 객체 (쪽지 읽기 창)

        Returns:
            {
                'title': str,           # 제목
                'sender': str,          # 발신자 이름
                'sender_dept': str,     # 발신자 소속
                'date': str,            # 수신 일시 (YYYY-MM-DD HH:MM)
                'recipients': List[str], # 수신자 목록
                'content': str,         # 본문 내용
                'attachments': List[Dict], # 첨부파일 목록
                'raw_sender': str,      # 원본 발신자 문자열
                'extracted_at': str     # 추출 시각
            }

        Raises:
            ExtractionError: 추출 실패 시
        """
        logger.info("쪽지 전체 내용 추출 시작")

        result = {
            'title': '',
            'sender': '',
            'sender_dept': '',
            'date': '',
            'recipients': [],
            'content': '',
            'attachments': [],
            'raw_sender': '',
            'extracted_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        try:
            # 메타데이터 추출
            metadata = self.extract_metadata(window)
            result.update(metadata)

            # 본문 추출
            result['content'] = self.extract_body(window)

            # 첨부파일 목록 추출
            result['attachments'] = self.extract_attachments(window)

            logger.info(f"쪽지 추출 완료: {result['title'][:30]}...")
            return result

        except Exception as e:
            logger.error(f"쪽지 추출 실패: {e}")
            raise ExtractionError(f"쪽지 내용 추출 실패: {e}") from e

    def extract_metadata(self, window) -> Dict[str, Any]:
        """메타데이터 추출

        쪽지 읽기 창에서 제목, 발신자, 날짜, 수신자 정보를 추출합니다.

        Args:
            window: pywinauto 윈도우 객체

        Returns:
            {
                'title': str,
                'sender': str,
                'sender_dept': str,
                'date': str,
                'recipients': List[str],
                'raw_sender': str
            }
        """
        logger.debug("메타데이터 추출 시작")

        result = {
            'title': '',
            'sender': '',
            'sender_dept': '',
            'date': '',
            'recipients': [],
            'raw_sender': ''
        }

        if not WINDOWS_AVAILABLE:
            logger.warning("Windows 모듈을 사용할 수 없습니다.")
            return result

        try:
            # 제목 추출
            result['title'] = self._extract_field(window, '제목')

            # 발신자 추출 및 파싱
            raw_sender = self._extract_field(window, '발신자')
            result['raw_sender'] = raw_sender

            sender_info = self._parse_sender(raw_sender)
            result['sender'] = sender_info['name']
            result['sender_dept'] = sender_info['dept']

            # 날짜 추출 및 파싱
            raw_date = self._extract_field(window, '날짜') or self._extract_field(window, '수신일')
            result['date'] = self._parse_date(raw_date)

            # 수신자 추출
            raw_recipients = self._extract_field(window, '수신자')
            result['recipients'] = self._parse_recipients(raw_recipients)

            logger.debug(f"메타데이터 추출 완료: 제목={result['title'][:20]}...")
            return result

        except Exception as e:
            logger.error(f"메타데이터 추출 실패: {e}")
            return result

    def extract_body(self, window) -> str:
        """본문 내용 추출

        쪽지 읽기 창에서 본문 텍스트를 추출합니다.

        Args:
            window: pywinauto 윈도우 객체

        Returns:
            본문 텍스트 (str)
        """
        logger.debug("본문 추출 시작")

        if not WINDOWS_AVAILABLE:
            return ""

        try:
            # 방법 1: 본문 영역 직접 접근
            body_text = self._try_extract_body_control(window)
            if body_text:
                return body_text

            # 방법 2: 클립보드 기반 추출 (전체 선택 → 복사)
            if self.use_clipboard:
                body_text = self._try_extract_body_clipboard(window)
                if body_text:
                    return body_text

            # 방법 3: 모든 텍스트 컨트롤 탐색
            body_text = self._try_extract_body_scan(window)
            if body_text:
                return body_text

            logger.warning("본문 추출 실패: 텍스트를 찾을 수 없습니다.")
            return ""

        except Exception as e:
            logger.error(f"본문 추출 실패: {e}")
            return ""

    def extract_attachments(self, window) -> List[Dict]:
        """첨부파일 목록 추출

        쪽지 읽기 창에서 첨부파일 정보를 추출합니다.

        Args:
            window: pywinauto 윈도우 객체

        Returns:
            [
                {
                    'filename': str,    # 파일명
                    'size': str,        # 파일 크기 (예: "100KB")
                    'index': int        # 첨부파일 순서 (0부터)
                },
                ...
            ]
        """
        logger.debug("첨부파일 목록 추출 시작")

        if not WINDOWS_AVAILABLE:
            return []

        attachments = []

        try:
            # 첨부파일 영역 찾기
            attachment_area = self._find_attachment_area(window)
            if not attachment_area:
                logger.debug("첨부파일 없음")
                return []

            # 파일 항목 추출
            items = self._extract_attachment_items(attachment_area)

            for idx, item in enumerate(items):
                attachment = self._parse_attachment_info(item, idx)
                if attachment:
                    attachments.append(attachment)

            logger.debug(f"첨부파일 {len(attachments)}개 발견")
            return attachments

        except Exception as e:
            logger.error(f"첨부파일 목록 추출 실패: {e}")
            return []

    def download_attachment(self, window, index: int, save_path: str) -> bool:
        """첨부파일 다운로드

        지정된 인덱스의 첨부파일을 다운로드합니다.

        Args:
            window: pywinauto 윈도우 객체
            index: 첨부파일 인덱스 (0부터 시작)
            save_path: 저장 경로 (폴더)

        Returns:
            성공 여부 (bool)
        """
        logger.info(f"첨부파일 다운로드 시작: index={index}")

        if not WINDOWS_AVAILABLE:
            logger.error("Windows 모듈을 사용할 수 없습니다.")
            return False

        try:
            # 저장 폴더 확인/생성
            os.makedirs(save_path, exist_ok=True)

            # 다운로드 버튼 찾기 및 클릭
            if not self._click_download_button(window, index):
                logger.error("다운로드 버튼 클릭 실패")
                return False

            time.sleep(self.click_delay)

            # 저장 대화상자 처리
            if not self._handle_save_dialog(save_path):
                logger.warning("저장 대화상자 처리 실패 (자동 다운로드 설정일 수 있음)")

            # 다운로드 완료 대기
            time.sleep(self.download_wait)

            logger.info("첨부파일 다운로드 완료")
            return True

        except Exception as e:
            logger.error(f"첨부파일 다운로드 실패: {e}")
            return False

    def download_all_attachments(self, window, save_path: str) -> Tuple[int, int]:
        """모든 첨부파일 다운로드

        Args:
            window: pywinauto 윈도우 객체
            save_path: 저장 경로 (폴더)

        Returns:
            (성공 개수, 전체 개수) 튜플
        """
        attachments = self.extract_attachments(window)
        total = len(attachments)
        success = 0

        if total == 0:
            logger.info("다운로드할 첨부파일이 없습니다.")
            return (0, 0)

        logger.info(f"첨부파일 {total}개 다운로드 시작")

        for idx, attachment in enumerate(attachments):
            if self.download_attachment(window, idx, save_path):
                success += 1
            else:
                logger.warning(f"첨부파일 다운로드 실패: {attachment.get('filename', f'index {idx}')}")

        logger.info(f"첨부파일 다운로드 완료: {success}/{total}")
        return (success, total)

    # ==================== 내부 헬퍼 메서드 ====================

    def _extract_field(self, window, field_name: str) -> str:
        """특정 필드 값 추출

        레이블-값 형태의 UI 요소에서 값을 추출합니다.
        예: "제목: 생기부 마감 안내" → "생기부 마감 안내"
        """
        try:
            # 방법 1: 레이블 기반 검색
            label = window.child_window(title_re=f".*{field_name}.*", control_type="Text")
            if label.exists(timeout=1):
                # 인접한 Edit 또는 Text 컨트롤 찾기
                parent = label.parent()
                for child in parent.children():
                    text = child.window_text()
                    if text and field_name not in text and len(text) > 0:
                        return text.strip()

            # 방법 2: Static 텍스트에서 직접 파싱
            all_texts = window.children(control_type="Text")
            for text_ctrl in all_texts:
                text = text_ctrl.window_text()
                if field_name in text and ':' in text:
                    # "제목: 값" 형태 파싱
                    parts = text.split(':', 1)
                    if len(parts) == 2:
                        return parts[1].strip()

            # 방법 3: Edit 컨트롤 검색
            edits = window.children(control_type="Edit")
            for edit in edits:
                # 앞에 있는 레이블 확인 (heuristic)
                pass

        except Exception as e:
            logger.debug(f"필드 '{field_name}' 추출 실패: {e}")

        return ""

    def _parse_sender(self, raw_sender: str) -> Dict[str, str]:
        """발신자 정보 파싱

        "홍길동 (교무기획부)" → {'name': '홍길동', 'dept': '교무기획부'}
        """
        result = {'name': raw_sender.strip(), 'dept': ''}

        if not raw_sender:
            return result

        # 패턴 1: "이름 (소속)"
        match = re.match(SENDER_PATTERN, raw_sender)
        if match:
            result['name'] = match.group(1).strip()
            result['dept'] = match.group(2).strip()
            return result

        # 패턴 2: "이름 소속" (공백 구분)
        match = re.match(SENDER_PATTERN_ALT, raw_sender)
        if match:
            result['name'] = match.group(1).strip()
            result['dept'] = match.group(2).strip()
            return result

        return result

    def _parse_date(self, raw_date: str) -> str:
        """날짜 문자열을 표준 형식으로 변환

        다양한 형식 → "YYYY-MM-DD HH:MM" 또는 "YYYY-MM-DD"
        """
        if not raw_date:
            return ""

        raw_date = raw_date.strip()

        for pattern, pattern_type in DATE_PATTERNS:
            match = re.search(pattern, raw_date)
            if match:
                groups = match.groups()

                if pattern_type == 'datetime':
                    year, month, day, hour, minute = map(int, groups)
                    return f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}"

                elif pattern_type == 'date':
                    year, month, day = map(int, groups)
                    return f"{year:04d}-{month:02d}-{day:02d}"

                elif pattern_type == 'short_datetime':
                    month, day, hour, minute = map(int, groups)
                    year = datetime.now().year
                    return f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}"

        # 파싱 실패 시 원본 반환
        return raw_date

    def _parse_recipients(self, raw_recipients: str) -> List[str]:
        """수신자 목록 파싱

        "홍길동, 김철수, 박영희" → ['홍길동', '김철수', '박영희']
        """
        if not raw_recipients:
            return []

        # 쉼표, 세미콜론, 줄바꿈으로 분리
        recipients = re.split(r'[,;，；\n]+', raw_recipients)

        # 정리
        result = []
        for r in recipients:
            name = r.strip()
            if name and len(name) > 0:
                result.append(name)

        return result

    def _try_extract_body_control(self, window) -> str:
        """본문 컨트롤 직접 접근으로 추출"""
        try:
            # RichEdit, Edit, Document 컨트롤 검색
            control_types = ["Edit", "Document", "Text"]

            for ctrl_type in control_types:
                controls = window.children(control_type=ctrl_type)

                for ctrl in controls:
                    text = ctrl.window_text()

                    # 본문은 보통 가장 긴 텍스트
                    if text and len(text) > 50:
                        # 메타데이터 필드가 아닌지 확인
                        if not any(kw in text[:20] for kw in ['제목', '발신', '수신', '날짜', '첨부']):
                            return text.strip()

        except Exception as e:
            logger.debug(f"본문 컨트롤 접근 실패: {e}")

        return ""

    def _try_extract_body_clipboard(self, window) -> str:
        """클립보드 기반 본문 추출 (Ctrl+A, Ctrl+C)"""
        try:
            import win32clipboard
            import win32con

            # 창에 포커스
            window.set_focus()
            time.sleep(0.1)

            # 본문 영역 클릭 (heuristic: 창 중앙)
            rect = window.rectangle()
            center_x = (rect.left + rect.right) // 2
            center_y = (rect.top + rect.bottom) // 2
            pyautogui.click(center_x, center_y)
            time.sleep(0.1)

            # 전체 선택 및 복사
            pyautogui.hotkey('ctrl', 'a')
            time.sleep(0.1)
            pyautogui.hotkey('ctrl', 'c')
            time.sleep(0.1)

            # 클립보드에서 읽기
            win32clipboard.OpenClipboard()
            try:
                text = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
            finally:
                win32clipboard.CloseClipboard()

            return text.strip() if text else ""

        except Exception as e:
            logger.debug(f"클립보드 추출 실패: {e}")

        return ""

    def _try_extract_body_scan(self, window) -> str:
        """모든 텍스트 컨트롤 스캔하여 본문 추출"""
        try:
            all_texts = []

            def scan_children(element, depth=0):
                if depth > 10:  # 재귀 깊이 제한
                    return

                try:
                    text = element.window_text()
                    if text and len(text) > 30:
                        all_texts.append((len(text), text))

                    for child in element.children():
                        scan_children(child, depth + 1)
                except:
                    pass

            scan_children(window)

            # 가장 긴 텍스트가 본문일 가능성이 높음
            if all_texts:
                all_texts.sort(reverse=True)
                # 메타데이터 제외
                for length, text in all_texts:
                    if not any(kw in text[:30] for kw in ['제목', '발신', '수신', '날짜']):
                        return text.strip()

        except Exception as e:
            logger.debug(f"스캔 추출 실패: {e}")

        return ""

    def _find_attachment_area(self, window):
        """첨부파일 영역 찾기"""
        try:
            # "첨부파일" 레이블 찾기
            attachment_label = window.child_window(
                title_re=".*첨부.*파일.*",
                control_type="Text"
            )

            if attachment_label.exists(timeout=1):
                # 레이블의 부모 또는 인접 영역이 첨부파일 목록
                return attachment_label.parent()

            # 대안: 다운로드 버튼 근처
            download_btn = window.child_window(
                title_re=".*다운로드.*",
                control_type="Button"
            )

            if download_btn.exists(timeout=1):
                return download_btn.parent()

        except Exception as e:
            logger.debug(f"첨부파일 영역 찾기 실패: {e}")

        return None

    def _extract_attachment_items(self, area) -> List:
        """첨부파일 영역에서 개별 항목 추출"""
        items = []

        try:
            # 리스트 아이템 또는 텍스트 컨트롤 검색
            for child in area.children():
                text = child.window_text()
                # 파일 확장자가 있는 항목
                if text and re.search(r'\.\w{2,4}(\s|$)', text):
                    items.append(child)

        except Exception as e:
            logger.debug(f"첨부파일 항목 추출 실패: {e}")

        return items

    def _parse_attachment_info(self, item, index: int) -> Optional[Dict]:
        """첨부파일 항목에서 정보 추출

        "📎 파일명.hwp (100KB)" → {'filename': '파일명.hwp', 'size': '100KB', 'index': 0}
        """
        try:
            text = item.window_text() if hasattr(item, 'window_text') else str(item)

            # 파일명과 크기 추출
            # 패턴: "파일명.확장자 (크기)" 또는 "파일명.확장자 크기"
            match = re.search(r'([^\s/\\]+\.\w{2,4})\s*(?:\(([^)]+)\)|(\d+\s*[KMG]?B))?', text)

            if match:
                filename = match.group(1)
                size = match.group(2) or match.group(3) or ''

                return {
                    'filename': filename.strip(),
                    'size': size.strip(),
                    'index': index
                }

        except Exception as e:
            logger.debug(f"첨부파일 정보 파싱 실패: {e}")

        return None

    def _click_download_button(self, window, index: int) -> bool:
        """다운로드 버튼 클릭"""
        try:
            # 방법 1: 다운로드 버튼 직접 클릭
            download_btn = window.child_window(
                title_re=".*다운로드.*",
                control_type="Button"
            )

            if download_btn.exists(timeout=2):
                download_btn.click()
                return True

            # 방법 2: 이미지 인식 (pyautogui)
            # btn_location = pyautogui.locateOnScreen('assets/images/btn_download.png')
            # if btn_location:
            #     pyautogui.click(pyautogui.center(btn_location))
            #     return True

            # 방법 3: 첨부파일 항목 더블클릭
            attachment_area = self._find_attachment_area(window)
            if attachment_area:
                items = self._extract_attachment_items(attachment_area)
                if index < len(items):
                    item = items[index]
                    if hasattr(item, 'double_click'):
                        item.double_click()
                        return True

        except Exception as e:
            logger.error(f"다운로드 버튼 클릭 실패: {e}")

        return False

    def _handle_save_dialog(self, save_path: str) -> bool:
        """저장 대화상자 처리"""
        try:
            # 저장 대화상자 대기
            time.sleep(0.5)

            app = Application(backend='uia').connect(title_re=".*저장.*", timeout=5)
            save_dialog = app.top_window()

            # 경로 입력
            path_edit = save_dialog.child_window(control_type="Edit")
            if path_edit.exists(timeout=2):
                path_edit.set_text(save_path)

            # 저장 버튼 클릭
            save_btn = save_dialog.child_window(title_re=".*저장.*", control_type="Button")
            if save_btn.exists(timeout=2):
                save_btn.click()
                return True

        except Exception as e:
            logger.debug(f"저장 대화상자 처리 실패 (자동 저장일 수 있음): {e}")

        return False


class ExtractionError(Exception):
    """추출 오류 예외"""
    pass


# ==================== 유틸리티 함수 ====================

def connect_to_message_window(timeout: int = DEFAULT_TIMEOUT):
    """쪽지 읽기 창 연결

    이미 열려 있는 쪽지 읽기 창에 연결합니다.

    Args:
        timeout: 연결 대기 시간 (초)

    Returns:
        pywinauto 윈도우 객체

    Raises:
        ExtractionError: 창을 찾을 수 없을 때
    """
    if not WINDOWS_AVAILABLE:
        raise ExtractionError("Windows 모듈을 사용할 수 없습니다.")

    try:
        app = Application(backend='uia').connect(
            title_re=f".*{MESSAGE_WINDOW_TITLE}.*",
            timeout=timeout
        )
        return app.top_window()

    except ElementNotFoundError:
        raise ExtractionError(f"'{MESSAGE_WINDOW_TITLE}' 창을 찾을 수 없습니다.")


def extract_from_window(window=None) -> Dict[str, Any]:
    """현재 열린 쪽지 창에서 내용 추출 (편의 함수)

    Args:
        window: pywinauto 윈도우 객체 (없으면 자동 연결)

    Returns:
        추출된 쪽지 정보 딕셔너리
    """
    if window is None:
        window = connect_to_message_window()

    extractor = MessageExtractor()
    return extractor.extract_all(window)


# ==================== 테스트 ====================

if __name__ == "__main__":
    # 로깅 설정
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("=" * 60)
    print("쪽지 내용 추출기 테스트")
    print("=" * 60)

    # 테스트 1: 발신자 파싱
    print("\n[테스트 1: 발신자 파싱]")
    extractor = MessageExtractor()

    test_senders = [
        "홍길동 (교무기획부)",
        "김철수(행정실)",
        "박영희 교육과정부",
        "이순신",
    ]

    for sender in test_senders:
        result = extractor._parse_sender(sender)
        print(f"  '{sender}' → 이름: {result['name']}, 소속: {result['dept']}")

    # 테스트 2: 날짜 파싱
    print("\n[테스트 2: 날짜 파싱]")

    test_dates = [
        "2025-01-27 14:30",
        "2025.01.27",
        "01-27 09:00",
        "2025/1/27",
    ]

    for date in test_dates:
        result = extractor._parse_date(date)
        print(f"  '{date}' → '{result}'")

    # 테스트 3: 수신자 파싱
    print("\n[테스트 3: 수신자 파싱]")

    test_recipients = "홍길동, 김철수, 박영희; 이순신"
    result = extractor._parse_recipients(test_recipients)
    print(f"  '{test_recipients}' → {result}")

    # 테스트 4: 실제 창 연결 (Windows에서만)
    if WINDOWS_AVAILABLE:
        print("\n[테스트 4: 실제 창 연결]")
        print("쪽지 읽기 창을 열어두세요...")

        try:
            window = connect_to_message_window(timeout=5)
            print(f"  창 연결 성공: {window.window_text()}")

            message = extract_from_window(window)
            print(f"\n추출 결과:")
            print(f"  제목: {message['title']}")
            print(f"  발신자: {message['sender']} ({message['sender_dept']})")
            print(f"  날짜: {message['date']}")
            print(f"  수신자: {message['recipients']}")
            print(f"  본문 길이: {len(message['content'])}자")
            print(f"  첨부파일: {len(message['attachments'])}개")

        except ExtractionError as e:
            print(f"  연결 실패: {e}")
    else:
        print("\n[테스트 4: 스킵 - Windows가 아닙니다]")

    print("\n" + "=" * 60)
    print("테스트 완료")
