#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
GOE 메신저 도우미 - CLI 엔트리포인트

경기교육통합메신저의 안 읽은 쪽지를 자동으로 저장하고,
AI 기반 대시보드를 통해 업무를 효율적으로 관리합니다.

사용법:
    python -m src.main scan          # 안 읽은 쪽지 스캔 및 저장
    python -m src.main list          # 저장된 쪽지 목록
    python -m src.main search "키워드"  # 검색
    python -m src.main summary       # 오늘 요약
    python -m src.main gui           # GUI 대시보드 실행
    python -m src.main mcp           # MCP 서버 실행

PyInstaller로 exe 빌드 시:
    pyinstaller --onefile --windowed --name "GOE메신저도우미" src/main.py
"""

import sys
import os
import argparse
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any

# src 폴더를 path에 추가 (개발 환경용)
if not getattr(sys, 'frozen', False):
    src_path = os.path.dirname(os.path.abspath(__file__))
    if src_path not in sys.path:
        sys.path.insert(0, src_path)
    # 프로젝트 루트도 추가
    project_root = os.path.dirname(src_path)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)


# ============================================================
# 로깅 설정
# ============================================================

def setup_logging(verbose: bool = False, log_file: Optional[str] = None):
    """로깅 설정

    Args:
        verbose: 상세 로그 출력 여부
        log_file: 로그 파일 경로 (없으면 콘솔만)
    """
    level = logging.DEBUG if verbose else logging.INFO

    handlers = [logging.StreamHandler(sys.stdout)]

    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding='utf-8'))

    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers
    )

    # 외부 라이브러리 로그 레벨 조정
    logging.getLogger('pywinauto').setLevel(logging.WARNING)
    logging.getLogger('PIL').setLevel(logging.WARNING)


logger = logging.getLogger(__name__)


# ============================================================
# CLI 명령어 핸들러
# ============================================================

def cmd_scan(args) -> int:
    """안 읽은 쪽지 스캔 및 저장

    GOE메신저에 연결하여 안 읽은 쪽지를 자동으로 처리합니다.
    - 쪽지 내용 추출
    - Markdown/PDF 저장
    - 첨부파일 다운로드
    - 데이터베이스 등록

    Returns:
        종료 코드 (0: 성공, 1: 실패)
    """
    from config import ConfigManager, get_data_folder
    from messenger import GOEMessengerController, MessengerNotRunningError, MessengerConnectionError
    from extractor import MessageExtractor
    from saver import MessageSaver
    from database import MessageDatabase
    from importance import ImportanceCalculator
    from models import create_message

    print("\n" + "=" * 60)
    print("  GOE 메신저 - 안 읽은 쪽지 스캔")
    print("=" * 60 + "\n")

    # 설정 로드
    config = ConfigManager()

    # 저장 옵션
    save_markdown = args.markdown if hasattr(args, 'markdown') else True
    save_pdf = args.pdf if hasattr(args, 'pdf') else False
    download_attachments = args.attachments if hasattr(args, 'attachments') else True

    # Windows 환경 체크
    if sys.platform != 'win32':
        print("[!] 이 기능은 Windows에서만 동작합니다.")
        print("    macOS/Linux에서는 저장된 쪽지 조회만 가능합니다.")
        return 1

    try:
        # 메신저 연결
        print("[1/5] GOE메신저 연결 중...")
        controller = GOEMessengerController(config)

        if not controller.is_running():
            print("[!] GOE메신저가 실행되지 않았습니다.")
            print("    메신저를 먼저 실행해 주세요.")
            return 1

        controller.connect()
        print("      연결 성공!")

        # 수신함 이동
        print("[2/5] 수신함으로 이동 중...")
        controller.navigate_to_inbox()
        controller.set_sort_unread_first()
        print("      완료!")

        # 안 읽은 쪽지 확인
        print("[3/5] 안 읽은 쪽지 확인 중...")
        unread_count = controller.get_unread_count()

        if unread_count <= 0:
            print("      안 읽은 쪽지가 없습니다.")
            controller.disconnect()
            return 0

        print(f"      안 읽은 쪽지: {unread_count}개")

        # 추출기 및 저장기 초기화
        extractor = MessageExtractor()
        saver = MessageSaver()
        db = MessageDatabase()
        importance_calc = ImportanceCalculator()

        # 쪽지 처리
        print(f"[4/5] 쪽지 처리 중...")
        processed = 0
        errors = []
        saved_files = []

        limit = args.limit if hasattr(args, 'limit') and args.limit else unread_count

        for i in range(min(limit, unread_count)):
            try:
                print(f"\n   [{i+1}/{min(limit, unread_count)}] 쪽지 열기...")
                msg_window = controller.open_first_unread()

                if not msg_window:
                    print("      건너뜀 (창 열기 실패)")
                    continue

                # 내용 추출
                content = extractor.extract_all(msg_window._window)
                print(f"      제목: {content.get('title', '제목 없음')[:30]}...")

                # 중요도 계산
                importance = importance_calc.calculate({
                    'title': content.get('title', ''),
                    'content': content.get('content', ''),
                    'deadline': content.get('deadline')
                })

                # 첨부파일 다운로드
                if download_attachments and msg_window.has_attachments():
                    print("      첨부파일 다운로드 중...")
                    msg_window.download_attachments()

                # Markdown 저장
                if save_markdown:
                    md_path = saver.save_as_markdown({
                        'title': content.get('title', ''),
                        'sender': content.get('sender', ''),
                        'affiliation': content.get('sender_dept', ''),
                        'received_date': content.get('date', ''),
                        'recipients': ', '.join(content.get('recipients', [])),
                        'content': content.get('content', ''),
                        'attachments': content.get('attachments', [])
                    })
                    saved_files.append(md_path)
                    print(f"      저장됨: {os.path.basename(md_path)}")

                # PDF 저장
                if save_pdf:
                    try:
                        pdf_path = saver.save_as_pdf(msg_window._window)
                        saved_files.append(pdf_path)
                        print(f"      PDF 저장됨: {os.path.basename(pdf_path)}")
                    except Exception as e:
                        print(f"      PDF 저장 실패: {e}")

                # 데이터베이스 저장
                message = create_message(
                    title=content.get('title', ''),
                    content=content.get('content', ''),
                    sender=content.get('sender', ''),
                    sender_dept=content.get('sender_dept', ''),
                    received_at=content.get('date', ''),
                    deadline=content.get('deadline'),
                    attachments=content.get('attachments', []),
                    grade=importance.get('grade', 'C'),
                    score=importance.get('score', 0),
                    starred=importance.get('auto_starred', False),
                    category=importance.get('main_category', 'information'),
                    task_group=importance.get('breakdown', {}).get('task_type', {}).get('reason', '기타')
                )
                db.add(message)

                # 창 닫기
                msg_window.close()
                processed += 1

            except Exception as e:
                logger.error(f"쪽지 처리 중 오류: {e}")
                errors.append(str(e))
                controller.close_message_window()

        # 연결 해제
        controller.disconnect()

        # 결과 출력
        print(f"\n[5/5] 처리 완료!")
        print("\n" + "-" * 40)
        print(f"  처리된 쪽지: {processed}개")
        print(f"  저장된 파일: {len(saved_files)}개")
        if errors:
            print(f"  오류: {len(errors)}건")
        print("-" * 40)

        return 0 if not errors else 1

    except MessengerNotRunningError:
        print("\n[!] GOE메신저가 실행되지 않았습니다.")
        print("    메신저를 먼저 실행하고 다시 시도해 주세요.")
        return 1

    except MessengerConnectionError as e:
        print(f"\n[!] 메신저 연결 실패: {e}")
        return 1

    except Exception as e:
        logger.exception(f"예상치 못한 오류: {e}")
        print(f"\n[!] 오류 발생: {e}")
        return 1


def cmd_list(args) -> int:
    """저장된 쪽지 목록 표시

    데이터베이스에 저장된 쪽지 목록을 표시합니다.

    Returns:
        종료 코드 (0: 성공)
    """
    from database import MessageDatabase
    from models import MessageFilter

    print("\n" + "=" * 60)
    print("  저장된 쪽지 목록")
    print("=" * 60 + "\n")

    db = MessageDatabase()

    # 필터 적용
    filter_obj = MessageFilter()

    if hasattr(args, 'status') and args.status:
        filter_obj.status = args.status
    if hasattr(args, 'starred') and args.starred:
        filter_obj.starred_only = True
    if hasattr(args, 'sender') and args.sender:
        filter_obj.sender = args.sender

    messages = db.search(filter_obj) if any([
        filter_obj.status, filter_obj.starred_only, filter_obj.sender
    ]) else db.get_all()

    # 개수 제한
    limit = args.limit if hasattr(args, 'limit') and args.limit else 20
    messages = messages[:limit]

    if not messages:
        print("저장된 쪽지가 없습니다.")
        return 0

    # 통계
    stats = db.get_stats()
    print(f"전체: {stats.total}개 | 미완료: {stats.pending}개 | "
          f"긴급: {stats.urgent}개 | 완료: {stats.completed}개\n")

    # 목록 출력
    print(f"{'번호':<4} {'상태':<6} {'중요':<3} {'제목':<30} {'발신자':<15} {'마감일':<12}")
    print("-" * 80)

    for i, msg in enumerate(messages, 1):
        # 상태 표시
        if msg.is_completed:
            status = "[완료]"
        elif msg.is_urgent:
            status = "[긴급]"
        else:
            status = "[대기]"

        # 중요 표시
        star = "*" if msg.starred else " "

        # 제목 (최대 28자)
        title = msg.title[:28] + "..." if len(msg.title) > 28 else msg.title

        # 발신자 (최대 13자)
        sender = msg.sender[:13] + ".." if len(msg.sender) > 13 else msg.sender

        # 마감일
        deadline = msg.deadline if msg.deadline else "-"
        if msg.d_day is not None:
            deadline = f"{deadline} (D-{msg.d_day})"

        print(f"{i:<4} {status:<6} {star:<3} {title:<30} {sender:<15} {deadline:<12}")

    print("-" * 80)
    print(f"\n총 {len(messages)}개 표시됨")

    return 0


def cmd_search(args) -> int:
    """쪽지 검색

    키워드로 저장된 쪽지를 검색합니다.

    Returns:
        종료 코드 (0: 성공)
    """
    from database import MessageDatabase
    from models import MessageFilter

    keyword = args.keyword

    print("\n" + "=" * 60)
    print(f"  검색: '{keyword}'")
    print("=" * 60 + "\n")

    db = MessageDatabase()

    # 검색 실행
    filter_obj = MessageFilter(query=keyword)

    if hasattr(args, 'sender') and args.sender:
        filter_obj.sender = args.sender
    if hasattr(args, 'date_from') and args.date_from:
        filter_obj.date_from = args.date_from
    if hasattr(args, 'date_to') and args.date_to:
        filter_obj.date_to = args.date_to

    results = db.search(filter_obj)

    if not results:
        print(f"'{keyword}' 관련 쪽지를 찾지 못했습니다.")
        return 0

    print(f"검색 결과: {len(results)}건\n")

    for i, msg in enumerate(results[:20], 1):
        # 상태 표시
        status = "[완료]" if msg.is_completed else ("[긴급]" if msg.is_urgent else "[대기]")
        star = "*" if msg.starred else " "

        print(f"{i}. {star} {status} {msg.title}")
        print(f"   발신: {msg.sender} | 수신: {msg.received_at or '-'}")
        if msg.deadline:
            print(f"   마감: {msg.deadline}")

        # 본문 미리보기
        preview = msg.content[:100].replace('\n', ' ') + "..." if len(msg.content) > 100 else msg.content.replace('\n', ' ')
        print(f"   내용: {preview}")
        print()

    return 0


def cmd_summary(args) -> int:
    """오늘의 쪽지 요약

    기한 중심으로 쪽지를 요약하여 표시합니다.

    Returns:
        종료 코드 (0: 성공)
    """
    from database import MessageDatabase
    from importance import ImportanceCalculator
    from grouping import DeadlineSummarizer

    print("\n" + "=" * 60)
    print(f"  오늘의 업무 요약 ({datetime.now().strftime('%Y-%m-%d')})")
    print("=" * 60 + "\n")

    db = MessageDatabase()

    # 통계
    stats = db.get_stats()
    print(f"[현황]")
    print(f"  신규: {stats.today_new}건 | 미완료: {stats.pending}건 | "
          f"긴급: {stats.urgent}건 | 완료: {stats.completed}건\n")

    # 긴급 업무
    urgent = db.get_urgent()
    if urgent:
        print("[긴급 업무] (D-2 이내)")
        print("-" * 40)
        for msg in urgent[:5]:
            star = "*" if msg.starred else " "
            d_day = f"D-{msg.d_day}" if msg.d_day is not None else "마감임박"
            print(f"  {star} [{d_day}] {msg.title}")
            print(f"       발신: {msg.sender}")
        print()

    # 이번 주 마감
    pending = db.get_pending()
    this_week = [m for m in pending if m.d_day is not None and 2 < m.d_day <= 7]
    if this_week:
        print("[이번 주 마감]")
        print("-" * 40)
        for msg in this_week[:5]:
            print(f"  [D-{msg.d_day}] {msg.title}")
        print()

    # 그룹별 현황
    group_stats = db.get_group_stats()
    if group_stats:
        print("[업무 그룹별 현황]")
        print("-" * 40)
        for gs in group_stats:
            icon = gs.get('icon', '')
            group = gs.get('group', '기타')
            total = gs.get('total', 0)
            pending_count = gs.get('pending', 0)
            urgent_count = gs.get('urgent', 0)
            print(f"  {icon} {group}: {pending_count}건 (긴급 {urgent_count}건)")
        print()

    # 완료율
    if stats.total > 0:
        completion_rate = int(stats.completed / stats.total * 100)
        bar_filled = int(completion_rate / 5)
        bar = "[" + "=" * bar_filled + " " * (20 - bar_filled) + "]"
        print(f"[진행률] {bar} {completion_rate}%\n")

    return 0


def cmd_complete(args) -> int:
    """쪽지 완료 처리

    지정한 쪽지를 완료 상태로 변경합니다.

    Returns:
        종료 코드 (0: 성공, 1: 실패)
    """
    from database import MessageDatabase

    message_id = args.id

    db = MessageDatabase()

    if db.mark_completed(message_id):
        print(f"완료 처리되었습니다: {message_id}")
        return 0
    else:
        print(f"쪽지를 찾을 수 없습니다: {message_id}")
        return 1


def cmd_star(args) -> int:
    """중요 표시 토글

    지정한 쪽지의 중요 표시를 토글합니다.

    Returns:
        종료 코드 (0: 성공, 1: 실패)
    """
    from database import MessageDatabase

    message_id = args.id

    db = MessageDatabase()

    if db.toggle_starred(message_id):
        msg = db.get(message_id)
        status = "중요 표시됨" if msg and msg.starred else "중요 표시 해제됨"
        print(f"{status}: {message_id}")
        return 0
    else:
        print(f"쪽지를 찾을 수 없습니다: {message_id}")
        return 1


def cmd_chat(args) -> int:
    """AI 채팅 질의

    자연어로 쪽지를 검색하고 정보를 얻습니다.

    Returns:
        종료 코드 (0: 성공)
    """
    from ai_chat import AIChatEngine
    from utils import MessageRepository

    query = args.query

    print("\n" + "=" * 60)
    print(f"  AI 채팅")
    print("=" * 60 + "\n")

    repo = MessageRepository()
    engine = AIChatEngine(repo)

    response = engine.process(query)

    print(f"[질문] {query}\n")
    print(f"[답변]\n{response['text']}\n")

    if response.get('suggestions'):
        print("[추천 질문]")
        for s in response['suggestions']:
            print(f"  - {s}")

    return 0


def cmd_gui(args) -> int:
    """GUI 대시보드 실행

    tkinter 기반의 GUI 대시보드를 실행합니다.

    Returns:
        종료 코드 (0: 성공)
    """
    import tkinter as tk
    from tkinter import messagebox

    # 설정 모듈 임포트
    from config import is_first_run, init_first_run, ConfigManager

    try:
        from settings_dialog import FirstRunDialog
        HAS_DIALOG = True
    except ImportError:
        HAS_DIALOG = False

    # 루트 윈도우 생성 (숨김)
    root = tk.Tk()
    root.withdraw()

    # 첫 실행 체크
    if is_first_run():
        init_first_run()

        if HAS_DIALOG:
            # 첫 실행 다이얼로그
            root.deiconify()
            dialog = FirstRunDialog(root)
            if not dialog.show():
                # 취소하면 종료
                root.destroy()
                return 0
            root.withdraw()

    # 설정 로드
    config = ConfigManager()

    # 메신저 경로 확인 (Windows만)
    if sys.platform == 'win32':
        messenger_path = config.get('messenger.path', '')
        if messenger_path and not os.path.exists(messenger_path):
            root.deiconify()
            messagebox.showwarning(
                "경고",
                f"GOE 메신저 경로를 찾을 수 없습니다:\n{messenger_path}\n\n"
                "설정에서 올바른 경로를 지정해주세요."
            )
            root.withdraw()

    # 메인 대시보드 실행
    root.destroy()  # 숨김 윈도우 제거

    try:
        from gui_dashboard import DashboardGUI
        app = DashboardGUI()
        app.root.mainloop()
    except ImportError as e:
        logger.error(f"GUI 모듈 로드 실패: {e}")
        error_root = tk.Tk()
        error_root.withdraw()
        messagebox.showerror(
            "오류",
            f"GUI 모듈을 로드할 수 없습니다:\n\n{str(e)}\n\n"
            "필요한 패키지를 설치해 주세요."
        )
        error_root.destroy()
        return 1
    except Exception as e:
        # 오류 발생 시 메시지 표시
        logger.exception(f"GUI 실행 오류: {e}")
        error_root = tk.Tk()
        error_root.withdraw()
        messagebox.showerror(
            "오류",
            f"프로그램 실행 중 오류가 발생했습니다:\n\n{str(e)}"
        )
        error_root.destroy()
        return 1

    return 0


def cmd_mcp(args) -> int:
    """MCP 서버 실행

    Claude Code 연동을 위한 MCP 서버를 실행합니다.

    Returns:
        종료 코드 (0: 성공)
    """
    import subprocess

    # mcp 서버 모듈 실행
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    try:
        print("MCP 서버 시작 중...")
        print("Claude Code에서 사용하려면 설정 파일을 확인하세요.")
        print("\nCtrl+C로 종료합니다.\n")

        result = subprocess.run(
            [sys.executable, '-m', 'mcp.server'],
            cwd=project_root
        )
        return result.returncode
    except KeyboardInterrupt:
        print("\nMCP 서버가 종료되었습니다.")
        return 0
    except Exception as e:
        logger.error(f"MCP 서버 실행 실패: {e}")
        print(f"[!] MCP 서버 실행 실패: {e}")
        return 1


def cmd_export(args) -> int:
    """쪽지 데이터 내보내기

    저장된 쪽지 데이터를 JSON 파일로 내보냅니다.

    Returns:
        종료 코드 (0: 성공, 1: 실패)
    """
    from database import MessageDatabase

    output_path = args.output

    db = MessageDatabase()

    if db.export_json(output_path):
        count = db.count()
        print(f"내보내기 완료: {output_path}")
        print(f"총 {count}개 쪽지가 저장되었습니다.")
        return 0
    else:
        print(f"내보내기 실패")
        return 1


def cmd_import(args) -> int:
    """쪽지 데이터 가져오기

    JSON 파일에서 쪽지 데이터를 가져옵니다.

    Returns:
        종료 코드 (0: 성공, 1: 실패)
    """
    from database import MessageDatabase

    input_path = args.input

    if not os.path.exists(input_path):
        print(f"파일을 찾을 수 없습니다: {input_path}")
        return 1

    db = MessageDatabase()

    count = db.import_json(input_path)
    if count > 0:
        print(f"가져오기 완료: {count}개 쪽지가 추가되었습니다.")
        return 0
    elif count == 0:
        print("새로 추가된 쪽지가 없습니다.")
        return 0
    else:
        print("가져오기 실패")
        return 1


def cmd_status(args) -> int:
    """시스템 상태 확인

    프로그램 설정 및 연결 상태를 확인합니다.

    Returns:
        종료 코드 (0: 성공)
    """
    from config import ConfigManager, get_data_folder, get_app_folder

    print("\n" + "=" * 60)
    print("  GOE 메신저 도우미 - 시스템 상태")
    print("=" * 60 + "\n")

    # 버전 정보
    config = ConfigManager()
    print(f"[버전]")
    print(f"  앱 이름: {config.get('app.name', 'GOE 메신저 도우미')}")
    print(f"  버전: {config.get('app.version', '1.0.0')}")
    print(f"  플랫폼: {sys.platform}")
    print(f"  Python: {sys.version.split()[0]}")
    print()

    # 경로 정보
    print(f"[경로]")
    print(f"  앱 폴더: {get_app_folder()}")
    print(f"  데이터 폴더: {get_data_folder()}")
    print(f"  메신저 경로: {config.get('messenger.path', '설정 안됨')}")
    print()

    # 모듈 상태
    print(f"[모듈 상태]")

    modules_status = []

    try:
        import pywinauto
        modules_status.append(("pywinauto", "설치됨"))
    except ImportError:
        modules_status.append(("pywinauto", "미설치 (Windows 자동화 불가)"))

    try:
        import pyautogui
        modules_status.append(("pyautogui", "설치됨"))
    except ImportError:
        modules_status.append(("pyautogui", "미설치"))

    try:
        import ttkbootstrap
        modules_status.append(("ttkbootstrap", "설치됨"))
    except ImportError:
        modules_status.append(("ttkbootstrap", "미설치 (기본 테마 사용)"))

    for name, status in modules_status:
        print(f"  {name}: {status}")
    print()

    # 메신저 연결 상태 (Windows만)
    if sys.platform == 'win32':
        print(f"[메신저 상태]")
        try:
            from messenger import GOEMessengerController
            controller = GOEMessengerController()
            if controller.is_running():
                print("  GOE메신저: 실행 중")
            else:
                print("  GOE메신저: 실행 안됨")
        except Exception as e:
            print(f"  GOE메신저: 확인 불가 ({e})")
        print()

    # 데이터베이스 상태
    print(f"[데이터베이스]")
    try:
        from database import MessageDatabase
        db = MessageDatabase()
        stats = db.get_stats()
        print(f"  총 쪽지: {stats.total}개")
        print(f"  미완료: {stats.pending}개")
        print(f"  완료: {stats.completed}개")
    except Exception as e:
        print(f"  상태 확인 실패: {e}")

    print()
    return 0


# ============================================================
# 메인 함수
# ============================================================

def create_parser() -> argparse.ArgumentParser:
    """CLI 파서 생성

    Returns:
        argparse.ArgumentParser 객체
    """
    parser = argparse.ArgumentParser(
        prog='gmas',
        description='GOE 메신저 도우미 - 경기교육통합메신저 자동화 프로그램',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  %(prog)s scan                    # 안 읽은 쪽지 스캔 및 저장
  %(prog)s list                    # 저장된 쪽지 목록
  %(prog)s search "생기부"          # 키워드 검색
  %(prog)s summary                 # 오늘의 요약
  %(prog)s gui                     # GUI 대시보드 실행
  %(prog)s chat "오늘 할 일 알려줘"  # AI 채팅

자세한 사용법: %(prog)s <command> --help
        """
    )

    # 전역 옵션
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='상세 로그 출력')
    parser.add_argument('--log-file', metavar='FILE',
                        help='로그 파일 경로')
    parser.add_argument('--version', action='version', version='%(prog)s 1.0.0')

    # 서브 명령어
    subparsers = parser.add_subparsers(dest='command', help='명령어')

    # scan: 안 읽은 쪽지 스캔
    scan_parser = subparsers.add_parser('scan', help='안 읽은 쪽지 스캔 및 저장')
    scan_parser.add_argument('--limit', '-n', type=int,
                             help='처리할 쪽지 수 제한')
    scan_parser.add_argument('--markdown', '-m', action='store_true', default=True,
                             help='Markdown으로 저장 (기본값)')
    scan_parser.add_argument('--pdf', '-p', action='store_true',
                             help='PDF로 저장')
    scan_parser.add_argument('--no-attachments', dest='attachments', action='store_false',
                             help='첨부파일 다운로드 안함')
    scan_parser.set_defaults(func=cmd_scan)

    # list: 쪽지 목록
    list_parser = subparsers.add_parser('list', help='저장된 쪽지 목록')
    list_parser.add_argument('--limit', '-n', type=int, default=20,
                             help='표시할 개수 (기본: 20)')
    list_parser.add_argument('--status', '-s', choices=['pending', 'completed'],
                             help='상태 필터')
    list_parser.add_argument('--starred', action='store_true',
                             help='중요 표시만')
    list_parser.add_argument('--sender', help='발신자 필터')
    list_parser.set_defaults(func=cmd_list)

    # search: 검색
    search_parser = subparsers.add_parser('search', help='쪽지 검색')
    search_parser.add_argument('keyword', help='검색어')
    search_parser.add_argument('--sender', help='발신자 필터')
    search_parser.add_argument('--date-from', metavar='YYYY-MM-DD',
                               help='시작일')
    search_parser.add_argument('--date-to', metavar='YYYY-MM-DD',
                               help='종료일')
    search_parser.set_defaults(func=cmd_search)

    # summary: 요약
    summary_parser = subparsers.add_parser('summary', help='오늘의 업무 요약')
    summary_parser.set_defaults(func=cmd_summary)

    # complete: 완료 처리
    complete_parser = subparsers.add_parser('complete', help='쪽지 완료 처리')
    complete_parser.add_argument('id', help='쪽지 ID')
    complete_parser.set_defaults(func=cmd_complete)

    # star: 중요 표시
    star_parser = subparsers.add_parser('star', help='중요 표시 토글')
    star_parser.add_argument('id', help='쪽지 ID')
    star_parser.set_defaults(func=cmd_star)

    # chat: AI 채팅
    chat_parser = subparsers.add_parser('chat', help='AI 채팅 질의')
    chat_parser.add_argument('query', help='질문')
    chat_parser.set_defaults(func=cmd_chat)

    # gui: GUI 실행
    gui_parser = subparsers.add_parser('gui', help='GUI 대시보드 실행')
    gui_parser.set_defaults(func=cmd_gui)

    # mcp: MCP 서버
    mcp_parser = subparsers.add_parser('mcp', help='MCP 서버 실행 (Claude Code 연동)')
    mcp_parser.set_defaults(func=cmd_mcp)

    # export: 내보내기
    export_parser = subparsers.add_parser('export', help='쪽지 데이터 내보내기')
    export_parser.add_argument('output', help='출력 파일 경로 (.json)')
    export_parser.set_defaults(func=cmd_export)

    # import: 가져오기
    import_parser = subparsers.add_parser('import', help='쪽지 데이터 가져오기')
    import_parser.add_argument('input', help='입력 파일 경로 (.json)')
    import_parser.set_defaults(func=cmd_import)

    # status: 상태 확인
    status_parser = subparsers.add_parser('status', help='시스템 상태 확인')
    status_parser.set_defaults(func=cmd_status)

    return parser


def main():
    """CLI 메인 함수"""
    parser = create_parser()
    args = parser.parse_args()

    # 로깅 설정
    setup_logging(
        verbose=args.verbose if hasattr(args, 'verbose') else False,
        log_file=args.log_file if hasattr(args, 'log_file') else None
    )

    # 명령어가 없으면 GUI 실행 (기본 동작)
    if args.command is None:
        # 인자 없이 실행시 GUI
        args.func = cmd_gui

    # 명령어 실행
    try:
        if hasattr(args, 'func'):
            exit_code = args.func(args)
            sys.exit(exit_code)
        else:
            parser.print_help()
            sys.exit(0)
    except KeyboardInterrupt:
        print("\n작업이 취소되었습니다.")
        sys.exit(130)
    except Exception as e:
        logger.exception(f"오류 발생: {e}")
        print(f"\n[!] 오류 발생: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
