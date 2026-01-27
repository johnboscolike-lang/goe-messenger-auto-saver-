"""
GOE Messenger Auto Saver - 대시보드 GUI
tkinter + ttkbootstrap 기반 모던 UI
- 실제 SQLite DB 연동
"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from typing import Dict, Any, List, Optional

# ttkbootstrap 없을 경우 대비
try:
    import ttkbootstrap as tb
    from ttkbootstrap.constants import *
    USE_BOOTSTRAP = True
except ImportError:
    USE_BOOTSTRAP = False
    print("ttkbootstrap 미설치. 기본 테마 사용.")

# 내부 모듈
from utils import (
    MessageRepository, get_d_day, format_d_day,
    get_status_emoji, get_status_color
)
from ai_chat import AIChatEngine
from importance import ImportanceCalculator
from grouping import MessageGrouper, DeadlineSummarizer, TASK_GROUPS


class DashboardGUI:
    """메인 대시보드 GUI - DB 연동 버전"""

    # 색상 정의
    COLORS = {
        "urgent": "#dc3545",      # 빨강
        "warning": "#ffc107",     # 노랑
        "normal": "#28a745",      # 초록
        "muted": "#6c757d",       # 회색
        "primary": "#0d6efd",     # 파랑
        "star": "#ffc107",        # 별 노랑
        "bg": "#f8f9fa",          # 배경
        "card": "#ffffff",        # 카드 배경
    }

    CATEGORY_ICONS = {
        "담임": "Teach",
        "제출": "Submit",
        "회의": "Meet",
        "예산": "Budget",
        "공지": "Notice",
    }

    def __init__(self):
        # 메인 윈도우
        if USE_BOOTSTRAP:
            self.root = tb.Window(themename="flatly")
        else:
            self.root = tk.Tk()

        self.root.title("GOE 업무 대시보드")
        self.root.geometry("1200x800")
        self.root.minsize(900, 600)

        # DB 연동
        self.repo = MessageRepository()
        self.repo.init_sample_data()  # 첫 실행 시 샘플 데이터

        # AI 엔진
        self.ai_engine = AIChatEngine(self.repo)

        # 그룹핑/요약
        self.grouper = MessageGrouper()
        self.summarizer = DeadlineSummarizer()

        # 상태
        self.filter_status = "all"  # all, pending, completed, starred, action, information
        self.messages: List[Dict[str, Any]] = []

        # UI 구성
        self._create_header()
        self._create_main_content()
        self._create_status_bar()

        # 초기 데이터 로드
        self._refresh_data()

    def _load_messages(self) -> List[Dict[str, Any]]:
        """DB에서 쪽지 로드"""
        return self.repo.get_all()

    def _create_header(self):
        """상단 헤더 생성"""
        header = ttk.Frame(self.root, padding=10)
        header.pack(fill=tk.X)

        # 제목
        title = ttk.Label(header, text="GOE 업무 대시보드",
                         font=("맑은 고딕", 18, "bold"))
        title.pack(side=tk.LEFT)

        # 오른쪽 버튼들
        btn_frame = ttk.Frame(header)
        btn_frame.pack(side=tk.RIGHT)

        ttk.Button(btn_frame, text="새로고침",
                  command=self._refresh_data).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="설정",
                  command=self._show_settings).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="AI 채팅",
                  command=self._show_ai_chat).pack(side=tk.LEFT, padx=5)

    def _create_main_content(self):
        """메인 컨텐츠 영역"""
        main = ttk.Frame(self.root, padding=10)
        main.pack(fill=tk.BOTH, expand=True)

        # 왼쪽 패널 (현황 + 긴급 대기열)
        left_panel = ttk.Frame(main, width=350)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        left_panel.pack_propagate(False)

        self._create_status_card(left_panel)
        self._create_urgent_queue(left_panel)
        self._create_group_view(left_panel)

        # 오른쪽 패널 (쪽지 목록)
        right_panel = ttk.Frame(main)
        right_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._create_message_list(right_panel)

    def _create_status_card(self, parent):
        """오늘의 현황 카드"""
        card = ttk.LabelFrame(parent, text="오늘의 현황", padding=15)
        card.pack(fill=tk.X, pady=(0, 10))

        # 통계
        stats_frame = ttk.Frame(card)
        stats_frame.pack(fill=tk.X)

        self.stat_labels = {}

        for label_text in ["행동 필요", "정보/공지", "긴급 (D-2)", "처리 완료"]:
            frame = ttk.Frame(stats_frame)
            frame.pack(fill=tk.X, pady=2)
            ttk.Label(frame, text=label_text).pack(side=tk.LEFT)
            lbl = ttk.Label(frame, text="0건", font=("맑은 고딕", 10, "bold"))
            lbl.pack(side=tk.RIGHT)
            self.stat_labels[label_text] = lbl

        # 진행률 바
        ttk.Separator(card, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

        progress_frame = ttk.Frame(card)
        progress_frame.pack(fill=tk.X)

        self.progress_label = ttk.Label(progress_frame, text="진행률: 0%")
        self.progress_label.pack(side=tk.LEFT)

        if USE_BOOTSTRAP:
            self.progress_bar = tb.Progressbar(
                progress_frame, value=0,
                bootstyle="success-striped"
            )
        else:
            self.progress_bar = ttk.Progressbar(
                progress_frame, value=0
            )
        self.progress_bar.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(10, 0))

    def _create_urgent_queue(self, parent):
        """긴급 대기열"""
        card = ttk.LabelFrame(parent, text="긴급 대기열", padding=10)
        card.pack(fill=tk.X, pady=(0, 10))

        self.urgent_frame = ttk.Frame(card)
        self.urgent_frame.pack(fill=tk.X)

    def _update_urgent_queue(self):
        """긴급 대기열 업데이트"""
        # 기존 위젯 삭제
        for widget in self.urgent_frame.winfo_children():
            widget.destroy()

        # 긴급 쪽지 필터링 (D-2 이하, pending만)
        urgent_messages = self.repo.get_urgent(d_day_threshold=2)

        if not urgent_messages:
            ttk.Label(self.urgent_frame, text="긴급 업무가 없습니다",
                     foreground=self.COLORS["muted"]).pack(pady=10)
            return

        for msg in urgent_messages[:5]:  # 최대 5개
            self._create_urgent_item(self.urgent_frame, msg)

    def _create_urgent_item(self, parent, msg):
        """긴급 대기열 아이템"""
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.X, pady=3)

        d_day = get_d_day(msg.get('deadline'))
        star = "[*]" if msg.get('starred') else ""

        # D-day 라벨
        d_label = ttk.Label(frame, text=f"{star}[긴급] [D-{d_day}]",
                           font=("맑은 고딕", 9, "bold"))
        d_label.pack(side=tk.LEFT)

        # 제목
        title = msg["title"][:15] + "..." if len(msg["title"]) > 15 else msg["title"]
        ttk.Label(frame, text=title).pack(side=tk.LEFT, padx=5)

        # 완료 버튼
        btn = ttk.Button(frame, text="완료", width=5,
                        command=lambda m=msg: self._mark_complete(m))
        btn.pack(side=tk.RIGHT)

    def _create_group_view(self, parent):
        """업무 그룹 뷰"""
        card = ttk.LabelFrame(parent, text="업무 그룹", padding=10)
        card.pack(fill=tk.BOTH, expand=True)

        self.group_frame = ttk.Frame(card)
        self.group_frame.pack(fill=tk.BOTH, expand=True)

    def _update_group_view(self):
        """업무 그룹 업데이트"""
        for widget in self.group_frame.winfo_children():
            widget.destroy()

        # 카테고리별 통계
        cat_stats = self.repo.get_category_stats()

        if not cat_stats:
            ttk.Label(self.group_frame, text="업무가 없습니다",
                     foreground=self.COLORS["muted"]).pack(pady=10)
            return

        for cat, info in cat_stats.items():
            icon = self.CATEGORY_ICONS.get(cat, "기타")
            frame = ttk.Frame(self.group_frame)
            frame.pack(fill=tk.X, pady=2)

            pending = info.get('pending', 0)
            urgent = info.get('urgent', 0)

            label_text = f"[{icon}] {cat} ({pending}건"
            if urgent > 0:
                label_text += f", 긴급 {urgent}건"
            label_text += ")"

            ttk.Label(frame, text=label_text, font=("맑은 고딕", 10)).pack(side=tk.LEFT)

    def _create_message_list(self, parent):
        """쪽지 목록"""
        # 필터 버튼
        filter_frame = ttk.Frame(parent)
        filter_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(filter_frame, text="쪽지 목록",
                 font=("맑은 고딕", 12, "bold")).pack(side=tk.LEFT)

        # 필터 버튼들
        btn_frame = ttk.Frame(filter_frame)
        btn_frame.pack(side=tk.RIGHT)

        for text, status in [("전체", "all"), ("행동", "action"), ("정보", "information"),
                            ("중요", "starred"), ("미완료", "pending"), ("완료", "completed")]:
            btn = ttk.Button(btn_frame, text=text, width=6,
                           command=lambda s=status: self._set_filter(s))
            btn.pack(side=tk.LEFT, padx=2)

        # 검색창
        search_frame = ttk.Frame(parent)
        search_frame.pack(fill=tk.X, pady=(0, 10))

        self.search_var = tk.StringVar()
        self.search_var.trace("w", self._on_search)

        ttk.Label(search_frame, text="검색:").pack(side=tk.LEFT)
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=40)
        search_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        # 목록 (Treeview)
        columns = ("star", "type", "status", "title", "sender", "deadline", "category")

        self.tree = ttk.Treeview(parent, columns=columns, show="headings", height=15)

        self.tree.heading("star", text="중요")
        self.tree.heading("type", text="분류")
        self.tree.heading("status", text="상태")
        self.tree.heading("title", text="제목")
        self.tree.heading("sender", text="발신자")
        self.tree.heading("deadline", text="마감/일시")
        self.tree.heading("category", text="업무")

        self.tree.column("star", width=40, anchor=tk.CENTER)
        self.tree.column("type", width=50, anchor=tk.CENTER)
        self.tree.column("status", width=50, anchor=tk.CENTER)
        self.tree.column("title", width=280)
        self.tree.column("sender", width=120)
        self.tree.column("deadline", width=100, anchor=tk.CENTER)
        self.tree.column("category", width=60, anchor=tk.CENTER)

        # 스크롤바
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 더블클릭 이벤트
        self.tree.bind("<Double-1>", self._on_message_double_click)

        # 우클릭 메뉴
        self.context_menu = tk.Menu(self.tree, tearoff=0)
        self.context_menu.add_command(label="중요 표시 토글", command=self._toggle_star)
        self.context_menu.add_command(label="완료 처리", command=self._mark_selected_complete)
        self.context_menu.add_command(label="캘린더 등록", command=self._add_to_calendar)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="상세 보기", command=self._show_detail)

        self.tree.bind("<Button-3>", self._show_context_menu)

    def _create_status_bar(self):
        """상태 바"""
        status = ttk.Frame(self.root, padding=5)
        status.pack(fill=tk.X, side=tk.BOTTOM)

        self.status_label = ttk.Label(status, text="준비됨")
        self.status_label.pack(side=tk.LEFT)

        ttk.Label(status, text="GOE Messenger Auto Saver v1.0").pack(side=tk.RIGHT)

    def _refresh_data(self):
        """데이터 새로고침 (DB에서 로드)"""
        self.messages = self._load_messages()

        self._update_urgent_queue()
        self._update_group_view()
        self._update_message_list()
        self._update_stats()
        self.status_label.config(text=f"마지막 업데이트: {datetime.now().strftime('%H:%M:%S')}")

    def _update_message_list(self):
        """메시지 목록 업데이트"""
        # 기존 항목 삭제
        for item in self.tree.get_children():
            self.tree.delete(item)

        # 필터링
        filtered = self.messages
        search_text = self.search_var.get().lower()

        if self.filter_status == "starred":
            filtered = [m for m in filtered if m.get("starred")]
        elif self.filter_status == "pending":
            filtered = [m for m in filtered if m.get("status") == "pending"]
        elif self.filter_status == "completed":
            filtered = [m for m in filtered if m.get("status") == "completed"]
        elif self.filter_status == "action":
            filtered = [m for m in filtered if m.get("main_type") == "action"]
        elif self.filter_status == "information":
            filtered = [m for m in filtered if m.get("main_type") == "information"]

        if search_text:
            filtered = [m for m in filtered
                       if search_text in m.get("title", "").lower()
                       or search_text in m.get("sender", "").lower()
                       or search_text in m.get("summary", "").lower()]

        # 정렬 (긴급도 순)
        filtered.sort(key=lambda x: (
            x.get("status") == "completed",  # 완료는 뒤로
            get_d_day(x.get("deadline")) if x.get("deadline") else 999
        ))

        # 목록에 추가
        for msg in filtered:
            star = "*" if msg.get("starred") else ""
            main_type = "[행동]" if msg.get("main_type") == "action" else "[정보]"
            status = self._get_status_text(msg)

            # 행동 쪽지는 마감일, 정보 쪽지는 일시
            if msg.get("main_type") == "action":
                deadline = self._format_deadline(msg)
            else:
                event_date = msg.get("event_date", "")
                event_time = msg.get("event_time", "")
                deadline = f"{event_date} {event_time}".strip() if event_date else "-"

            category = self.CATEGORY_ICONS.get(msg.get("category", ""), "기타")

            self.tree.insert("", tk.END, iid=msg["id"], values=(
                star, main_type, status, msg.get("title", ""),
                msg.get("sender", ""), deadline, category
            ), tags=(msg.get("status", "pending"),))

        # 완료 항목 회색 처리
        self.tree.tag_configure("completed", foreground=self.COLORS["muted"])

    def _update_stats(self):
        """통계 업데이트 (DB에서 조회)"""
        stats = self.repo.get_stats()

        self.stat_labels["행동 필요"].config(text=f"{stats.get('action', 0)}건")
        self.stat_labels["정보/공지"].config(text=f"{stats.get('information', 0)}건")
        self.stat_labels["긴급 (D-2)"].config(text=f"{stats.get('urgent', 0)}건")
        self.stat_labels["처리 완료"].config(text=f"{stats.get('completed', 0)}건")

        total = stats.get('total', 0)
        completed = stats.get('completed', 0)
        progress_pct = int((completed / total) * 100) if total > 0 else 0

        self.progress_label.config(text=f"진행률: {progress_pct}%")
        self.progress_bar.config(value=progress_pct)

    def _get_status_text(self, msg):
        """상태 텍스트"""
        if msg.get("status") == "completed":
            return "[완료]"
        d_day = get_d_day(msg.get("deadline"))
        if d_day <= 0:
            return "[지남]"
        elif d_day <= 2:
            return "[긴급]"
        elif d_day <= 7:
            return "[주의]"
        else:
            return "[여유]"

    def _format_deadline(self, msg):
        """마감일 포맷"""
        deadline = msg.get("deadline")
        if not deadline:
            return "-"
        d_day = get_d_day(deadline)
        date_str = deadline[5:] if len(deadline) >= 10 else deadline  # MM-DD
        return f"{date_str} (D-{d_day})"

    def _set_filter(self, status):
        """필터 설정"""
        self.filter_status = status
        self._update_message_list()

    def _on_search(self, *args):
        """검색 이벤트"""
        self._update_message_list()

    def _on_message_double_click(self, event):
        """메시지 더블클릭"""
        self._show_detail()

    def _show_context_menu(self, event):
        """우클릭 메뉴"""
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)

    def _toggle_star(self):
        """중요 표시 토글 (DB 업데이트)"""
        selected = self.tree.selection()
        if not selected:
            return

        msg_id = int(selected[0])
        self.repo.toggle_star(msg_id)
        self._refresh_data()

    def _mark_complete(self, msg):
        """완료 처리 (DB 업데이트)"""
        if messagebox.askyesno("완료 확인", f"'{msg['title']}'을(를) 완료 처리하시겠습니까?"):
            self.repo.mark_complete(msg['id'])
            self._refresh_data()

    def _mark_selected_complete(self):
        """선택 항목 완료 처리"""
        selected = self.tree.selection()
        if not selected:
            return

        msg_id = int(selected[0])
        msg = self.repo.get_by_id(msg_id)
        if msg:
            self._mark_complete(msg)

    def _add_to_calendar(self):
        """캘린더 등록"""
        selected = self.tree.selection()
        if not selected:
            return

        msg_id = int(selected[0])
        msg = self.repo.get_by_id(msg_id)

        if msg:
            try:
                from calendar_sync import GoogleCalendarSync

                calendar = GoogleCalendarSync()
                if calendar.is_authenticated():
                    if msg.get('main_type') == 'action':
                        event_id = calendar.create_deadline_event(msg)
                    else:
                        event_id = calendar.create_info_event(msg)

                    if event_id:
                        self.repo.update(msg_id, {'calendar_registered': True})
                        messagebox.showinfo("캘린더 등록",
                            f"'{msg['title']}' 일정이 구글 캘린더에 등록되었습니다.")
                        self._refresh_data()
                    else:
                        messagebox.showerror("오류", "캘린더 등록에 실패했습니다.")
                else:
                    messagebox.showwarning("알림",
                        "Google 캘린더가 연동되어 있지 않습니다.\n설정에서 연동해 주세요.")
            except ImportError:
                messagebox.showinfo("캘린더 등록",
                    f"'{msg['title']}' 일정\n마감: {msg.get('deadline', '없음')}\n\n"
                    "(Google API 미설치 - 시뮬레이션)")

    def _show_detail(self):
        """상세 보기 팝업"""
        selected = self.tree.selection()
        if not selected:
            return

        msg_id = int(selected[0])
        msg = self.repo.get_by_id(msg_id)

        if not msg:
            return

        # 상세 보기 창
        detail_window = tk.Toplevel(self.root)
        detail_window.title(f"쪽지 상세: {msg['title'][:30]}")
        detail_window.geometry("650x750")
        detail_window.transient(self.root)

        # 내용
        main_frame = ttk.Frame(detail_window, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 헤더
        header = ttk.Frame(main_frame)
        header.pack(fill=tk.X, pady=(0, 10))

        # 대분류 표시
        main_type = msg.get("main_type", "action")
        type_text = "[행동 필요]" if main_type == "action" else "[정보 제공]"
        star_text = "[* 중요]" if msg.get("starred") else "[일반]"
        status_text = self._get_status_text(msg)
        deadline_text = f"마감: {msg.get('deadline', '없음')}" if main_type == "action" else ""

        ttk.Label(header, text=f"{type_text}  |  {star_text}  {status_text}  {deadline_text}",
                 font=("맑은 고딕", 10)).pack(side=tk.LEFT)

        # 중요 표시 버튼
        star_btn = ttk.Button(header, text="중요 토글",
                             command=lambda: self._toggle_star_detail(msg, detail_window))
        star_btn.pack(side=tk.RIGHT)

        ttk.Separator(main_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

        # AI 요약
        summary_frame = ttk.LabelFrame(main_frame, text="AI 요약", padding=10)
        summary_frame.pack(fill=tk.X, pady=(0, 10))

        summary_text = msg.get('summary', '요약 정보 없음')
        ttk.Label(summary_frame, text=f"핵심: {summary_text}",
                 wraplength=600).pack(anchor=tk.W)

        # 행동 쪽지: 3단계 실행 프로세스
        if main_type == "action":
            ttk.Label(summary_frame, text="\n3단계 실행:",
                     font=("맑은 고딕", 9, "bold")).pack(anchor=tk.W)

            process = msg.get("process", [])
            for i, step in enumerate(process, 1):
                ttk.Label(summary_frame, text=f"  {i}. {step}").pack(anchor=tk.W)
        else:
            # 정보 쪽지: 일시/장소, 기억사항
            if msg.get("event_date"):
                event_info = f"{msg.get('event_date', '')} {msg.get('event_time', '')}"
                if msg.get("location"):
                    event_info += f" @ {msg['location']}"
                ttk.Label(summary_frame, text=f"\n일시/장소: {event_info}",
                         font=("맑은 고딕", 9)).pack(anchor=tk.W)

            remember = msg.get("remember", [])
            if remember:
                ttk.Label(summary_frame, text="\n기억해야 할 사항:",
                         font=("맑은 고딕", 9, "bold")).pack(anchor=tk.W)
                for item in remember:
                    ttk.Label(summary_frame, text=f"  - {item}").pack(anchor=tk.W)

            if msg.get("calendar_registered"):
                ttk.Label(summary_frame, text="\n[캘린더 등록됨]",
                         foreground=self.COLORS["normal"]).pack(anchor=tk.W)

        # 원본 쪽지
        content_frame = ttk.LabelFrame(main_frame, text="원본 쪽지", padding=10)
        content_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        info_text = f"제목: {msg.get('title', '')}\n발신: {msg.get('sender', '')}\n수신: {msg.get('date', '')}\n"
        ttk.Label(content_frame, text=info_text).pack(anchor=tk.W)

        ttk.Separator(content_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)

        content_text = tk.Text(content_frame, height=8, wrap=tk.WORD)
        content_text.insert(tk.END, msg.get("content", ""))
        content_text.config(state=tk.DISABLED)
        content_text.pack(fill=tk.BOTH, expand=True)

        # 첨부파일
        attachments = msg.get("attachments", [])
        if attachments:
            attach_frame = ttk.LabelFrame(main_frame, text="첨부파일", padding=10)
            attach_frame.pack(fill=tk.X, pady=(0, 10))

            for att in attachments:
                ttk.Label(attach_frame, text=f"  - {att}").pack(anchor=tk.W)

        # 버튼
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X)

        # 캘린더 등록 버튼
        if not msg.get("calendar_registered"):
            ttk.Button(btn_frame, text="캘린더 등록",
                      command=lambda: self._register_calendar_from_detail(msg, detail_window)).pack(side=tk.LEFT, padx=5)

        # 행동 쪽지만 완료 처리 버튼
        if main_type == "action" and msg.get("status") != "completed":
            ttk.Button(btn_frame, text="완료 처리",
                      command=lambda: [self._mark_complete(msg), detail_window.destroy()]).pack(side=tk.LEFT, padx=5)

        ttk.Button(btn_frame, text="닫기",
                  command=detail_window.destroy).pack(side=tk.RIGHT, padx=5)

    def _register_calendar_from_detail(self, msg, window):
        """상세창에서 캘린더 등록"""
        self._select_message_by_id(msg['id'])
        self._add_to_calendar()
        window.destroy()
        self._show_detail()

    def _select_message_by_id(self, msg_id):
        """ID로 트리뷰 항목 선택"""
        for item in self.tree.get_children():
            if int(item) == msg_id:
                self.tree.selection_set(item)
                break

    def _toggle_star_detail(self, msg, window):
        """상세창에서 중요 표시 토글"""
        self.repo.toggle_star(msg['id'])
        self._refresh_data()
        window.destroy()
        self._select_message_by_id(msg['id'])
        self._show_detail()

    def _show_settings(self):
        """설정 창 - SettingsDialog 사용"""
        try:
            from settings_dialog import SettingsDialog
            dialog = SettingsDialog(self.root, on_save=self._on_settings_saved)
            dialog.show()
        except ImportError:
            self._show_settings_basic()

    def _on_settings_saved(self):
        """설정 저장 후 콜백"""
        self._refresh_data()

    def _show_settings_basic(self):
        """기본 설정 창 (settings_dialog 없을 때)"""
        settings_window = tk.Toplevel(self.root)
        settings_window.title("설정")
        settings_window.geometry("400x300")
        settings_window.transient(self.root)

        frame = ttk.Frame(settings_window, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="설정", font=("맑은 고딕", 14, "bold")).pack(anchor=tk.W)
        ttk.Separator(frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

        # 자동 스캔
        auto_scan = tk.BooleanVar(value=True)
        ttk.Checkbutton(frame, text="자동 스캔 활성화",
                       variable=auto_scan).pack(anchor=tk.W, pady=5)

        # 스캔 간격
        interval_frame = ttk.Frame(frame)
        interval_frame.pack(fill=tk.X, pady=5)
        ttk.Label(interval_frame, text="스캔 간격 (분):").pack(side=tk.LEFT)
        ttk.Entry(interval_frame, width=10).pack(side=tk.RIGHT)

        # S등급 자동 중요 표시
        auto_star = tk.BooleanVar(value=True)
        ttk.Checkbutton(frame, text="S등급 자동 중요 표시",
                       variable=auto_star).pack(anchor=tk.W, pady=5)

        ttk.Button(frame, text="저장",
                  command=settings_window.destroy).pack(pady=20)

    def _show_ai_chat(self):
        """AI 채팅 창"""
        chat_window = tk.Toplevel(self.root)
        chat_window.title("AI 어시스턴트")
        chat_window.geometry("500x600")
        chat_window.transient(self.root)

        frame = ttk.Frame(chat_window, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        # 채팅 영역
        chat_frame = ttk.Frame(frame)
        chat_frame.pack(fill=tk.BOTH, expand=True)

        self.chat_text = tk.Text(chat_frame, wrap=tk.WORD, state=tk.DISABLED)
        self.chat_text.pack(fill=tk.BOTH, expand=True)

        # 초기 메시지
        suggestions = self.ai_engine.get_suggestions()
        welcome_msg = ("안녕하세요! GOE 업무 어시스턴트입니다.\n"
                      "무엇을 도와드릴까요?\n\n"
                      "예시:\n")
        for s in suggestions[:4]:
            welcome_msg += f"  - '{s}'\n"

        self._add_chat_message("[AI]", welcome_msg)

        # 입력 영역
        input_frame = ttk.Frame(frame)
        input_frame.pack(fill=tk.X, pady=(10, 0))

        self.chat_input = ttk.Entry(input_frame)
        self.chat_input.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.chat_input.bind("<Return>", self._on_chat_send)

        ttk.Button(input_frame, text="전송",
                  command=self._on_chat_send).pack(side=tk.RIGHT)

    def _add_chat_message(self, sender, message):
        """채팅 메시지 추가"""
        self.chat_text.config(state=tk.NORMAL)
        self.chat_text.insert(tk.END, f"\n{sender} {message}\n")
        self.chat_text.config(state=tk.DISABLED)
        self.chat_text.see(tk.END)

    def _on_chat_send(self, event=None):
        """채팅 전송 (AI 엔진 사용)"""
        message = self.chat_input.get().strip()
        if not message:
            return

        self._add_chat_message("[나]", message)
        self.chat_input.delete(0, tk.END)

        # AI 엔진으로 응답 생성
        response = self.ai_engine.process(message)
        self.root.after(300, lambda: self._add_chat_message("[AI]", response['text']))

        # 추천 질문 표시
        if response.get('suggestions'):
            suggestions_text = "\n추천 질문:\n"
            for s in response['suggestions']:
                if s:
                    suggestions_text += f"  - {s}\n"
            self.root.after(500, lambda: self._add_chat_message("", suggestions_text))

    def run(self):
        """앱 실행"""
        self.root.mainloop()


# main.py에서 사용하는 alias
GOEMessengerDashboard = DashboardGUI


def main():
    app = DashboardGUI()
    app.run()


if __name__ == "__main__":
    main()
