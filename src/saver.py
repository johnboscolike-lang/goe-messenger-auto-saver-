"""
파일 저장 모듈
- 쪽지를 Markdown 형식으로 저장
- 쪽지를 PDF로 저장 (인쇄 버튼 → Hancom PDF)
- 첨부파일 저장
- 폴더 구조 자동 생성
"""

import os
import re
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

# 조건부 임포트 (Windows 전용)
try:
    from pywinauto import Application
    from pywinauto.findwindows import ElementNotFoundError
    PYWINAUTO_AVAILABLE = True
except ImportError:
    PYWINAUTO_AVAILABLE = False

from .config import get_data_folder, get_attachments_folder, ConfigManager


# 로거 설정
logger = logging.getLogger(__name__)


# ==================== 상수 ====================

# 마크다운 템플릿
MARKDOWN_TEMPLATE = """# {title}

| 항목 | 내용 |
|------|------|
| 발신자 | {sender} ({affiliation}) |
| 수신일 | {received_date} |
| 수신자 | {recipients} |

## 본문

{content}

## 첨부파일

{attachments}

---
*저장일시: {saved_at}*
*GOE 메신저 도우미로 자동 저장됨*
"""

# 파일명에서 제거할 특수문자
INVALID_FILENAME_CHARS = r'[<>:"/\\|?*\x00-\x1f]'


class MessageSaver:
    """쪽지 저장 관리자

    쪽지를 다양한 형식(Markdown, PDF)으로 저장하고,
    첨부파일을 관리합니다.

    사용 예:
        saver = MessageSaver()

        # 마크다운으로 저장
        md_path = saver.save_as_markdown(message_data)

        # PDF로 저장
        pdf_path = saver.save_as_pdf(message_window)

        # 첨부파일 저장
        saved_files = saver.save_attachments(attachments, folder)
    """

    def __init__(self, base_path: Optional[str] = None):
        """MessageSaver 초기화

        Args:
            base_path: 기본 저장 경로. 없으면 config에서 가져옴
                      (기본값: ~/Documents/GOE메신저도우미/쪽지)
        """
        self.config = ConfigManager()

        if base_path:
            self.base_path = Path(base_path)
        else:
            self.base_path = Path(get_data_folder()) / '쪽지'

        # 기본 폴더 생성
        self.base_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"MessageSaver 초기화: {self.base_path}")

    # ==================== Markdown 저장 ====================

    def save_as_markdown(self, message_data: Dict[str, Any],
                         path: Optional[str] = None) -> str:
        """마크다운으로 저장

        Args:
            message_data: extractor에서 추출한 쪽지 데이터
                {
                    'title': str,           # 제목
                    'sender': str,          # 발신자 이름
                    'affiliation': str,     # 발신자 소속
                    'received_date': str,   # 수신일 (YYYY-MM-DD HH:MM)
                    'recipients': str,      # 수신자 목록
                    'content': str,         # 본문 내용
                    'attachments': List[Dict]  # 첨부파일 정보
                }
            path: 저장 경로 (없으면 자동 생성)

        Returns:
            저장된 파일의 절대 경로

        Raises:
            ValueError: message_data가 유효하지 않은 경우
            IOError: 파일 저장 실패
        """
        # 데이터 검증
        if not message_data or not message_data.get('title'):
            raise ValueError("message_data에 title이 필요합니다")

        # 저장 경로 결정
        if path:
            save_path = Path(path)
        else:
            save_path = Path(self.get_save_path(message_data, extension='md'))

        # 폴더 생성
        save_path.parent.mkdir(parents=True, exist_ok=True)

        # 마크다운 내용 생성
        markdown_content = self._generate_markdown(message_data)

        # 파일 저장
        try:
            with open(save_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)

            logger.info(f"마크다운 저장 완료: {save_path}")
            return str(save_path.absolute())

        except IOError as e:
            logger.error(f"마크다운 저장 실패: {e}")
            raise IOError(f"마크다운 저장 실패: {e}")

    def _generate_markdown(self, message_data: Dict[str, Any]) -> str:
        """마크다운 내용 생성

        Args:
            message_data: 쪽지 데이터

        Returns:
            마크다운 형식 문자열
        """
        # 기본값 설정
        title = message_data.get('title', '제목 없음')
        sender = message_data.get('sender', '알 수 없음')
        affiliation = message_data.get('affiliation', '')
        received_date = message_data.get('received_date', '')
        recipients = message_data.get('recipients', '')
        content = message_data.get('content', '')
        attachments = message_data.get('attachments', [])

        # 첨부파일 목록 포맷
        if attachments:
            attachment_lines = []
            for att in attachments:
                name = att.get('name', '파일')
                size = att.get('size', '')
                if size:
                    attachment_lines.append(f"- {name} ({size})")
                else:
                    attachment_lines.append(f"- {name}")
            attachments_str = '\n'.join(attachment_lines)
        else:
            attachments_str = "- 없음"

        # 템플릿에 데이터 채우기
        markdown = MARKDOWN_TEMPLATE.format(
            title=title,
            sender=sender,
            affiliation=affiliation,
            received_date=received_date,
            recipients=recipients,
            content=content,
            attachments=attachments_str,
            saved_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )

        return markdown

    # ==================== PDF 저장 ====================

    def save_as_pdf(self, message_window, path: Optional[str] = None,
                    timeout: int = 30) -> str:
        """PDF로 저장 (인쇄 버튼 사용)

        GOE메신저의 쪽지 읽기 창에서 인쇄 버튼을 클릭하고,
        Hancom PDF 프린터를 선택하여 PDF로 저장합니다.

        Args:
            message_window: pywinauto의 쪽지 읽기 창 객체
            path: 저장 경로 (없으면 자동 생성)
            timeout: 대화상자 대기 시간(초)

        Returns:
            저장된 PDF 파일의 절대 경로

        Raises:
            RuntimeError: pywinauto가 설치되지 않은 경우
            RuntimeError: PDF 저장 실패
        """
        if not PYWINAUTO_AVAILABLE:
            raise RuntimeError(
                "pywinauto가 설치되지 않았습니다. "
                "pip install pywinauto로 설치하세요."
            )

        # 저장 경로 결정
        if not path:
            # 창 제목에서 제목 추출 시도
            try:
                window_title = message_window.window_text()
                title = window_title.replace('쪽지 읽기', '').strip() or '쪽지'
            except Exception:
                title = '쪽지'

            save_path = self._generate_save_path_for_title(title, 'pdf')
        else:
            save_path = Path(path)

        # 폴더 생성
        save_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            # 1. 인쇄 버튼 클릭
            logger.info("인쇄 버튼 클릭 시도...")
            self._click_print_button(message_window)
            time.sleep(0.5)

            # 2. 인쇄 대화상자에서 Hancom PDF 선택
            logger.info("인쇄 대화상자 처리...")
            self._handle_print_dialog(timeout)
            time.sleep(1)

            # 3. 저장 대화상자에서 파일명 입력
            logger.info("저장 대화상자 처리...")
            self._handle_save_dialog(str(save_path), timeout)

            # 저장 완료 대기
            time.sleep(2)

            # 파일 존재 확인
            if save_path.exists():
                logger.info(f"PDF 저장 완료: {save_path}")
                return str(save_path.absolute())
            else:
                # 조금 더 대기 후 재확인
                time.sleep(3)
                if save_path.exists():
                    logger.info(f"PDF 저장 완료: {save_path}")
                    return str(save_path.absolute())
                else:
                    raise RuntimeError(f"PDF 파일이 생성되지 않았습니다: {save_path}")

        except Exception as e:
            logger.error(f"PDF 저장 실패: {e}")
            raise RuntimeError(f"PDF 저장 실패: {e}")

    def _click_print_button(self, message_window) -> None:
        """쪽지 읽기 창에서 인쇄 버튼 클릭

        Args:
            message_window: pywinauto의 쪽지 읽기 창 객체
        """
        try:
            # 방법 1: 버튼 컨트롤 찾기
            print_btn = message_window.child_window(
                title="인쇄",
                control_type="Button"
            )
            print_btn.click()
            return
        except Exception:
            pass

        try:
            # 방법 2: 이름에 '인쇄' 포함된 버튼
            print_btn = message_window.child_window(
                title_re=".*인쇄.*",
                control_type="Button"
            )
            print_btn.click()
            return
        except Exception:
            pass

        # 방법 3: pyautogui 이미지 인식 (fallback)
        try:
            import pyautogui
            btn_location = pyautogui.locateOnScreen(
                'assets/images/btn_print.png',
                confidence=0.8
            )
            if btn_location:
                pyautogui.click(pyautogui.center(btn_location))
                return
        except Exception:
            pass

        raise RuntimeError("인쇄 버튼을 찾을 수 없습니다")

    def _handle_print_dialog(self, timeout: int = 30) -> None:
        """인쇄 대화상자 처리

        - Hancom PDF 프린터 선택
        - 확인 버튼 클릭

        Args:
            timeout: 대화상자 대기 시간(초)
        """
        # 인쇄 대화상자 찾기
        app = Application(backend='uia')

        for _ in range(timeout * 2):
            try:
                app.connect(title_re=".*인쇄.*", timeout=0.5)
                break
            except Exception:
                time.sleep(0.5)
        else:
            raise RuntimeError("인쇄 대화상자를 찾을 수 없습니다")

        print_dialog = app.top_window()

        # Hancom PDF 프린터 선택
        try:
            # 프린터 콤보박스 찾기
            printer_combo = print_dialog.child_window(
                control_type="ComboBox",
                found_index=0
            )

            # Hancom PDF 선택 시도
            hancom_found = False
            for printer_name in ["Hancom PDF", "HancomPDF", "한컴 PDF"]:
                try:
                    printer_combo.select(printer_name)
                    hancom_found = True
                    logger.info(f"프린터 선택: {printer_name}")
                    break
                except Exception:
                    continue

            if not hancom_found:
                # Microsoft Print to PDF 대체
                try:
                    printer_combo.select("Microsoft Print to PDF")
                    logger.info("프린터 선택: Microsoft Print to PDF (대체)")
                except Exception:
                    logger.warning("PDF 프린터를 찾을 수 없습니다. 기본 프린터 사용")

        except Exception as e:
            logger.warning(f"프린터 선택 실패: {e}")

        # 확인 버튼 클릭
        time.sleep(0.3)
        try:
            ok_btn = print_dialog.child_window(title="확인", control_type="Button")
            ok_btn.click()
        except Exception:
            try:
                ok_btn = print_dialog.child_window(title="인쇄", control_type="Button")
                ok_btn.click()
            except Exception:
                # Enter 키로 확인
                print_dialog.type_keys("{ENTER}")

    def _handle_save_dialog(self, save_path: str, timeout: int = 30) -> None:
        """저장 대화상자 처리

        Args:
            save_path: 저장할 파일 경로
            timeout: 대화상자 대기 시간(초)
        """
        app = Application(backend='uia')

        # 저장 대화상자 찾기
        for _ in range(timeout * 2):
            try:
                app.connect(title_re=".*저장.*", timeout=0.5)
                break
            except Exception:
                try:
                    app.connect(title_re=".*다른 이름으로.*", timeout=0.5)
                    break
                except Exception:
                    time.sleep(0.5)
        else:
            raise RuntimeError("저장 대화상자를 찾을 수 없습니다")

        save_dialog = app.top_window()

        # 파일명 입력
        try:
            # 파일명 입력 필드 찾기
            filename_edit = save_dialog.child_window(
                control_type="Edit",
                found_index=0
            )

            # 기존 텍스트 지우고 새 경로 입력
            filename_edit.set_text("")
            time.sleep(0.1)
            filename_edit.type_keys(save_path, with_spaces=True)

        except Exception as e:
            logger.warning(f"파일명 입력 필드 접근 실패: {e}")
            # 직접 타이핑 시도
            save_dialog.type_keys(save_path, with_spaces=True)

        # 저장 버튼 클릭
        time.sleep(0.3)
        try:
            save_btn = save_dialog.child_window(title="저장", control_type="Button")
            save_btn.click()
        except Exception:
            save_dialog.type_keys("{ENTER}")

    # ==================== 첨부파일 저장 ====================

    def save_attachments(self, attachments: List[Dict[str, Any]],
                         folder: Optional[str] = None) -> List[str]:
        """첨부파일들을 지정 폴더에 저장

        실제 다운로드는 GOE메신저 UI 조작이 필요하므로,
        이 메서드는 다운로드된 파일을 지정 폴더로 이동/복사합니다.

        Args:
            attachments: 첨부파일 정보 목록
                [
                    {
                        'name': str,           # 파일명
                        'size': str,           # 파일 크기
                        'downloaded_path': str # 다운로드된 경로 (있으면)
                    },
                    ...
                ]
            folder: 저장 폴더 (없으면 기본 첨부파일 폴더)

        Returns:
            저장된 파일 경로 목록
        """
        if not attachments:
            return []

        # 저장 폴더 결정
        if folder:
            save_folder = Path(folder)
        else:
            save_folder = Path(get_attachments_folder())

        save_folder.mkdir(parents=True, exist_ok=True)

        saved_paths = []

        for att in attachments:
            name = att.get('name', 'unknown')
            downloaded_path = att.get('downloaded_path')

            if downloaded_path and Path(downloaded_path).exists():
                # 다운로드된 파일을 저장 폴더로 이동/복사
                src = Path(downloaded_path)
                dst = save_folder / self.sanitize_filename(name)

                # 중복 방지
                dst = self._get_unique_path(dst)

                try:
                    import shutil
                    shutil.copy2(src, dst)
                    saved_paths.append(str(dst.absolute()))
                    logger.info(f"첨부파일 복사: {src} → {dst}")
                except Exception as e:
                    logger.error(f"첨부파일 복사 실패: {e}")
            else:
                logger.warning(f"다운로드된 파일이 없음: {name}")

        return saved_paths

    # ==================== 경로 유틸리티 ====================

    def get_save_path(self, message_data: Dict[str, Any],
                      extension: str = 'md') -> str:
        """저장 경로 자동 생성

        형식: {base_path}/{YYYY}/{MM}/{DD}/{제목_sanitized}_{timestamp}.{ext}

        Args:
            message_data: 쪽지 데이터
            extension: 파일 확장자 (md, pdf 등)

        Returns:
            생성된 저장 경로
        """
        # 날짜 추출 (수신일 또는 현재)
        received_date = message_data.get('received_date', '')
        try:
            if received_date:
                dt = datetime.strptime(received_date[:10], '%Y-%m-%d')
            else:
                dt = datetime.now()
        except ValueError:
            dt = datetime.now()

        # 폴더 구조: YYYY/MM/DD
        date_folder = dt.strftime('%Y/%m/%d')

        # 파일명 생성
        title = message_data.get('title', '쪽지')
        safe_title = self.sanitize_filename(title)

        # 타임스탬프 추가 (중복 방지)
        timestamp = datetime.now().strftime('%H%M%S')
        filename = f"{safe_title}_{timestamp}.{extension}"

        # 전체 경로
        full_path = self.base_path / date_folder / filename

        return str(full_path)

    def _generate_save_path_for_title(self, title: str,
                                      extension: str) -> Path:
        """제목으로 저장 경로 생성 (PDF용)

        Args:
            title: 쪽지 제목
            extension: 파일 확장자

        Returns:
            저장 경로 Path 객체
        """
        today = datetime.now()
        date_folder = today.strftime('%Y/%m/%d')

        safe_title = self.sanitize_filename(title)
        timestamp = today.strftime('%H%M%S')
        filename = f"{safe_title}_{timestamp}.{extension}"

        return self.base_path / date_folder / filename

    def sanitize_filename(self, filename: str, max_length: int = 50) -> str:
        """파일명에서 특수문자 제거

        Windows에서 사용할 수 없는 문자와 특수문자를 제거하고,
        적절한 길이로 자릅니다.

        Args:
            filename: 원본 파일명
            max_length: 최대 길이 (확장자 제외)

        Returns:
            안전한 파일명
        """
        if not filename:
            return "untitled"

        # 확장자 분리
        name_part = Path(filename).stem
        ext_part = Path(filename).suffix

        # 특수문자 제거
        safe_name = re.sub(INVALID_FILENAME_CHARS, '', name_part)

        # 공백 정리
        safe_name = re.sub(r'\s+', ' ', safe_name).strip()

        # 빈 문자열 처리
        if not safe_name:
            safe_name = "untitled"

        # 길이 제한
        if len(safe_name) > max_length:
            safe_name = safe_name[:max_length].rstrip()

        # 확장자가 원래 있었으면 붙이기
        if ext_part:
            return safe_name + ext_part

        return safe_name

    def _get_unique_path(self, path: Path) -> Path:
        """중복되지 않는 경로 반환

        파일이 이미 존재하면 (1), (2) 등을 붙여서 고유한 경로 생성

        Args:
            path: 원본 경로

        Returns:
            고유한 경로
        """
        if not path.exists():
            return path

        stem = path.stem
        suffix = path.suffix
        parent = path.parent

        counter = 1
        while True:
            new_path = parent / f"{stem}({counter}){suffix}"
            if not new_path.exists():
                return new_path
            counter += 1
            if counter > 100:  # 무한 루프 방지
                # 타임스탬프 추가
                ts = datetime.now().strftime('%H%M%S%f')
                return parent / f"{stem}_{ts}{suffix}"


# ==================== 편의 함수 ====================

def save_message(message_data: Dict[str, Any],
                 formats: List[str] = None,
                 base_path: Optional[str] = None) -> Dict[str, str]:
    """쪽지를 지정 형식으로 저장 (편의 함수)

    Args:
        message_data: 쪽지 데이터
        formats: 저장 형식 목록 (기본: ['md'])
                 가능한 값: 'md', 'pdf'
        base_path: 저장 기본 경로

    Returns:
        {'md': '/path/to/file.md', 'pdf': '/path/to/file.pdf'}

    Example:
        result = save_message(data, formats=['md', 'pdf'])
        print(result['md'])  # 마크다운 경로
    """
    if formats is None:
        formats = ['md']

    saver = MessageSaver(base_path)
    results = {}

    if 'md' in formats:
        try:
            results['md'] = saver.save_as_markdown(message_data)
        except Exception as e:
            logger.error(f"마크다운 저장 실패: {e}")
            results['md'] = None

    # PDF는 message_window가 필요하므로 여기서는 경로만 생성
    if 'pdf' in formats:
        results['pdf_path'] = saver.get_save_path(message_data, 'pdf')

    return results


# ==================== 테스트 ====================

if __name__ == "__main__":
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("=" * 50)
    print("MessageSaver 테스트")
    print("=" * 50)

    # 테스트 데이터
    test_message = {
        'title': '2학기 생활기록부 최종 마감 안내',
        'sender': '김철수',
        'affiliation': '교무기획부',
        'received_date': '2025-01-27 09:30',
        'recipients': '전체 교원',
        'content': '''안녕하세요, 교무기획부입니다.

2학기 생활기록부 최종 마감일을 안내드립니다.

- 마감일: 2025년 1월 29일(수) 18:00
- 대상: 전 학년 담임교사
- 확인사항:
  1. 세부능력 및 특기사항 입력 완료
  2. 행동발달사항 입력 완료
  3. 창의적 체험활동 입력 완료

마감 후에는 수정이 불가하오니 기한 내 완료 부탁드립니다.

감사합니다.''',
        'attachments': [
            {'name': '생기부_점검표.hwp', 'size': '52KB'},
            {'name': '입력_매뉴얼.pdf', 'size': '1.2MB'}
        ]
    }

    # MessageSaver 인스턴스 생성
    saver = MessageSaver()

    print(f"\n기본 저장 경로: {saver.base_path}")

    # 마크다운 저장 테스트
    print("\n1. 마크다운 저장 테스트")
    try:
        md_path = saver.save_as_markdown(test_message)
        print(f"   저장 완료: {md_path}")

        # 저장된 내용 확인
        with open(md_path, 'r', encoding='utf-8') as f:
            content = f.read()
        print(f"   내용 미리보기:\n{content[:500]}...")
    except Exception as e:
        print(f"   실패: {e}")

    # 파일명 정리 테스트
    print("\n2. 파일명 정리 테스트")
    test_filenames = [
        '생기부/마감:안내?.pdf',
        '이것은 매우 긴 제목의 파일입니다 어쩌구 저쩌구 계속 길어지는 제목',
        '',
        '정상파일.hwp'
    ]
    for fn in test_filenames:
        safe_fn = saver.sanitize_filename(fn)
        print(f"   '{fn}' → '{safe_fn}'")

    # 경로 생성 테스트
    print("\n3. 저장 경로 생성 테스트")
    save_path = saver.get_save_path(test_message, 'md')
    print(f"   MD 경로: {save_path}")

    save_path = saver.get_save_path(test_message, 'pdf')
    print(f"   PDF 경로: {save_path}")

    # 편의 함수 테스트
    print("\n4. 편의 함수 테스트")
    result = save_message(test_message)
    print(f"   결과: {result}")

    print("\n테스트 완료!")
