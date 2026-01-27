"""
설정 다이얼로그
- GOE메신저 경로 설정
- Google 캘린더 연동
- 기타 옵션
"""

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Optional, Callable

from config import ConfigManager, get_data_folder


class SettingsDialog:
    """설정 다이얼로그
    
    사용법:
        dialog = SettingsDialog(parent_window)
        dialog.show()
    """
    
    def __init__(self, parent: tk.Tk, on_save: Optional[Callable] = None):
        self.parent = parent
        self.on_save = on_save
        self.config = ConfigManager()
        self.window: Optional[tk.Toplevel] = None
        
        # 설정 변수
        self.messenger_path = tk.StringVar()
        self.auto_save = tk.BooleanVar()
        self.check_interval = tk.IntVar()
        self.calendar_enabled = tk.BooleanVar()
        self.show_notifications = tk.BooleanVar()
    
    def show(self) -> None:
        """설정 창 표시"""
        if self.window and self.window.winfo_exists():
            self.window.lift()
            return
        
        self.window = tk.Toplevel(self.parent)
        self.window.title("⚙️ 설정")
        self.window.geometry("500x450")
        self.window.resizable(False, False)
        self.window.transient(self.parent)
        self.window.grab_set()
        
        # 현재 설정 로드
        self._load_current_settings()
        
        # UI 구성
        self._create_ui()
        
        # 창 중앙 배치
        self.window.update_idletasks()
        x = (self.window.winfo_screenwidth() - 500) // 2
        y = (self.window.winfo_screenheight() - 450) // 2
        self.window.geometry(f"+{x}+{y}")
    
    def _load_current_settings(self) -> None:
        """현재 설정 로드"""
        self.messenger_path.set(self.config.get('messenger.path', ''))
        self.auto_save.set(self.config.get('messenger.auto_save', True))
        self.check_interval.set(self.config.get('messenger.check_interval', 30))
        self.calendar_enabled.set(self.config.get('calendar.enabled', False))
        self.show_notifications.set(self.config.get('importance.show_notifications', True))
    
    def _create_ui(self) -> None:
        """UI 구성"""
        # 메인 프레임
        main_frame = ttk.Frame(self.window, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # === 메신저 설정 ===
        messenger_frame = ttk.LabelFrame(main_frame, text="📬 GOE 메신저", padding=10)
        messenger_frame.pack(fill=tk.X, pady=(0, 15))
        
        # 경로
        ttk.Label(messenger_frame, text="설치 경로:").pack(anchor=tk.W)
        path_frame = ttk.Frame(messenger_frame)
        path_frame.pack(fill=tk.X, pady=(2, 10))
        
        ttk.Entry(
            path_frame, 
            textvariable=self.messenger_path,
            width=45
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ttk.Button(
            path_frame,
            text="찾기",
            width=6,
            command=self._browse_messenger_path
        ).pack(side=tk.RIGHT, padx=(5, 0))
        
        # 자동 저장
        ttk.Checkbutton(
            messenger_frame,
            text="새 쪽지 자동 저장",
            variable=self.auto_save
        ).pack(anchor=tk.W)
        
        # 확인 간격
        interval_frame = ttk.Frame(messenger_frame)
        interval_frame.pack(fill=tk.X, pady=(5, 0))
        ttk.Label(interval_frame, text="확인 간격:").pack(side=tk.LEFT)
        ttk.Spinbox(
            interval_frame,
            from_=10,
            to=300,
            width=5,
            textvariable=self.check_interval
        ).pack(side=tk.LEFT, padx=5)
        ttk.Label(interval_frame, text="초").pack(side=tk.LEFT)
        
        # === 캘린더 설정 ===
        calendar_frame = ttk.LabelFrame(main_frame, text="📅 Google 캘린더", padding=10)
        calendar_frame.pack(fill=tk.X, pady=(0, 15))
        
        # 연동 상태
        self.calendar_status_label = ttk.Label(
            calendar_frame,
            text=self._get_calendar_status_text()
        )
        self.calendar_status_label.pack(anchor=tk.W)
        
        # 연동 버튼
        btn_frame = ttk.Frame(calendar_frame)
        btn_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.calendar_connect_btn = ttk.Button(
            btn_frame,
            text="연동하기" if not self.calendar_enabled.get() else "연동 해제",
            command=self._toggle_calendar
        )
        self.calendar_connect_btn.pack(side=tk.LEFT)
        
        ttk.Label(
            btn_frame,
            text="  브라우저에서 Google 로그인",
            foreground="gray"
        ).pack(side=tk.LEFT)
        
        # === 알림 설정 ===
        notify_frame = ttk.LabelFrame(main_frame, text="🔔 알림", padding=10)
        notify_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Checkbutton(
            notify_frame,
            text="중요 쪽지 알림 표시",
            variable=self.show_notifications
        ).pack(anchor=tk.W)
        
        # === 데이터 폴더 ===
        data_frame = ttk.LabelFrame(main_frame, text="📁 데이터 저장 위치", padding=10)
        data_frame.pack(fill=tk.X, pady=(0, 15))
        
        data_path = get_data_folder()
        ttk.Label(
            data_frame,
            text=data_path,
            foreground="gray"
        ).pack(anchor=tk.W)
        
        ttk.Button(
            data_frame,
            text="폴더 열기",
            command=lambda: os.startfile(data_path) if os.name == 'nt' else None
        ).pack(anchor=tk.W, pady=(5, 0))
        
        # === 버튼 ===
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(
            btn_frame,
            text="저장",
            command=self._save_settings
        ).pack(side=tk.RIGHT, padx=(5, 0))
        
        ttk.Button(
            btn_frame,
            text="취소",
            command=self.window.destroy
        ).pack(side=tk.RIGHT)
        
        ttk.Button(
            btn_frame,
            text="초기화",
            command=self._reset_settings
        ).pack(side=tk.LEFT)
    
    def _browse_messenger_path(self) -> None:
        """메신저 경로 찾기"""
        path = filedialog.askdirectory(
            title="GOE 메신저 설치 폴더 선택",
            initialdir=self.messenger_path.get() or "C:/Program Files (x86)"
        )
        if path:
            self.messenger_path.set(path)
    
    def _get_calendar_status_text(self) -> str:
        """캘린더 연동 상태 텍스트"""
        if self.calendar_enabled.get():
            return "✅ 연동됨 - 마감일이 캘린더에 자동 등록됩니다"
        return "❌ 연동 안 됨"
    
    def _toggle_calendar(self) -> None:
        """캘린더 연동 토글"""
        try:
            from calendar_sync import GoogleCalendarSync
            
            calendar = GoogleCalendarSync()
            
            if self.calendar_enabled.get():
                # 연동 해제
                if messagebox.askyesno("확인", "Google 캘린더 연동을 해제할까요?"):
                    calendar.disconnect()
                    self.calendar_enabled.set(False)
                    self.calendar_connect_btn.config(text="연동하기")
                    self.calendar_status_label.config(text=self._get_calendar_status_text())
            else:
                # 연동 시도
                messagebox.showinfo(
                    "안내",
                    "브라우저가 열리면 Google 계정으로 로그인해주세요."
                )
                if calendar.authenticate():
                    self.calendar_enabled.set(True)
                    self.calendar_connect_btn.config(text="연동 해제")
                    self.calendar_status_label.config(text=self._get_calendar_status_text())
                    messagebox.showinfo("완료", "Google 캘린더 연동이 완료되었습니다!")
                else:
                    messagebox.showerror("실패", "연동에 실패했습니다.")
                    
        except ImportError:
            messagebox.showerror(
                "오류",
                "Google API 라이브러리가 설치되지 않았습니다.\n\n"
                "pip install google-auth-oauthlib google-api-python-client"
            )
    
    def _save_settings(self) -> None:
        """설정 저장"""
        # 유효성 검사
        messenger_path = self.messenger_path.get()
        if messenger_path and not os.path.exists(messenger_path):
            if not messagebox.askyesno(
                "경고",
                f"경로가 존재하지 않습니다:\n{messenger_path}\n\n그래도 저장할까요?"
            ):
                return
        
        # 설정 저장
        self.config.set('messenger.path', messenger_path)
        self.config.set('messenger.auto_save', self.auto_save.get())
        self.config.set('messenger.check_interval', self.check_interval.get())
        self.config.set('calendar.enabled', self.calendar_enabled.get())
        self.config.set('importance.show_notifications', self.show_notifications.get())
        
        if self.config.save():
            messagebox.showinfo("완료", "설정이 저장되었습니다.")
            if self.on_save:
                self.on_save()
            self.window.destroy()
        else:
            messagebox.showerror("오류", "설정 저장에 실패했습니다.")
    
    def _reset_settings(self) -> None:
        """설정 초기화"""
        if messagebox.askyesno("확인", "모든 설정을 초기화할까요?"):
            self.config.reset()
            self._load_current_settings()
            messagebox.showinfo("완료", "설정이 초기화되었습니다.")


class FirstRunDialog:
    """첫 실행 설정 마법사"""
    
    def __init__(self, parent: tk.Tk):
        self.parent = parent
        self.config = ConfigManager()
        self.completed = False
    
    def show(self) -> bool:
        """첫 실행 다이얼로그 표시
        
        Returns:
            완료 여부
        """
        window = tk.Toplevel(self.parent)
        window.title("🎉 GOE 메신저 도우미 - 첫 실행 설정")
        window.geometry("450x350")
        window.resizable(False, False)
        window.transient(self.parent)
        window.grab_set()
        
        # 중앙 배치
        window.update_idletasks()
        x = (window.winfo_screenwidth() - 450) // 2
        y = (window.winfo_screenheight() - 350) // 2
        window.geometry(f"+{x}+{y}")
        
        # UI
        main_frame = ttk.Frame(window, padding=30)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(
            main_frame,
            text="🎉 환영합니다!",
            font=('맑은 고딕', 16, 'bold')
        ).pack(pady=(0, 10))
        
        ttk.Label(
            main_frame,
            text="GOE 메신저 도우미가 처음 실행되었습니다.\n"
                 "간단한 설정만 하면 바로 사용할 수 있어요.",
            justify=tk.CENTER
        ).pack(pady=(0, 20))
        
        # 메신저 경로
        ttk.Label(
            main_frame,
            text="GOE 메신저 설치 경로:",
            font=('맑은 고딕', 10, 'bold')
        ).pack(anchor=tk.W)
        
        self.path_var = tk.StringVar(value=r'C:\Program Files (x86)\AtMessenger7')
        path_frame = ttk.Frame(main_frame)
        path_frame.pack(fill=tk.X, pady=(5, 15))
        
        ttk.Entry(path_frame, textvariable=self.path_var, width=40).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(
            path_frame,
            text="찾기",
            command=lambda: self._browse_path(self.path_var)
        ).pack(side=tk.RIGHT, padx=(5, 0))
        
        # 캘린더 연동
        ttk.Label(
            main_frame,
            text="📅 Google 캘린더 연동 (선택):",
            font=('맑은 고딕', 10, 'bold')
        ).pack(anchor=tk.W, pady=(10, 5))
        
        ttk.Label(
            main_frame,
            text="마감일을 Google 캘린더에 자동으로 등록할 수 있어요.\n"
                 "나중에 설정에서 연동할 수 있습니다.",
            foreground="gray"
        ).pack(anchor=tk.W)
        
        # 버튼
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(30, 0))
        
        def on_start():
            self.config.set('messenger.path', self.path_var.get())
            self.config.save()
            self.completed = True
            window.destroy()
        
        ttk.Button(
            btn_frame,
            text="시작하기 🚀",
            command=on_start
        ).pack(side=tk.RIGHT)
        
        window.wait_window()
        return self.completed
    
    def _browse_path(self, var: tk.StringVar) -> None:
        """경로 찾기"""
        path = filedialog.askdirectory(
            title="GOE 메신저 설치 폴더 선택",
            initialdir=var.get() or "C:/Program Files (x86)"
        )
        if path:
            var.set(path)


# 테스트
if __name__ == "__main__":
    root = tk.Tk()
    root.title("설정 테스트")
    root.geometry("300x200")
    
    ttk.Button(
        root,
        text="설정 열기",
        command=lambda: SettingsDialog(root).show()
    ).pack(pady=50)
    
    root.mainloop()
