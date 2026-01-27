"""
Google Calendar 연동 모듈
- OAuth 클라이언트 설정 내장 (배포 시 별도 파일 불필요)
- 사용자 토큰만 로컬에 저장
- 첫 사용 시 브라우저에서 로그인
"""

import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

try:
    from src.config import get_token_path, ConfigManager
except ImportError:
    from config import get_token_path, ConfigManager

# Google API 라이브러리 (없으면 기능 비활성화)
try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False
    print("⚠️ Google API 라이브러리 없음. 캘린더 기능 비활성화")


# ============================================================
# Google OAuth 설정 (코드에 내장 - 배포 시 별도 파일 불필요)
# ============================================================

# 이 정보는 공개해도 됨 (데스크톱 앱용 OAuth)
# 실제 배포 시 본인의 Google Cloud 프로젝트 정보로 교체
GOOGLE_CLIENT_CONFIG = {
    "installed": {
        "client_id": "YOUR_CLIENT_ID.apps.googleusercontent.com",
        "project_id": "goe-messenger-helper",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_secret": "YOUR_CLIENT_SECRET",
        "redirect_uris": ["http://localhost"]
    }
}

# 필요한 권한 범위
SCOPES = ['https://www.googleapis.com/auth/calendar.events']


# ============================================================
# Google Calendar 연동 클래스
# ============================================================

class GoogleCalendarSync:
    """Google Calendar 연동 관리자
    
    사용법:
        calendar = GoogleCalendarSync()
        
        # 연동 확인
        if not calendar.is_authenticated():
            calendar.authenticate()  # 브라우저 열림
        
        # 이벤트 등록
        calendar.create_event({
            'title': '생기부 마감',
            'date': '2025-01-29',
            'time': '17:00'
        })
    """
    
    def __init__(self):
        self.config = ConfigManager()
        self.token_path = get_token_path()
        self.credentials = None
        self.service = None
        
        if GOOGLE_API_AVAILABLE:
            self._load_credentials()
    
    def is_available(self) -> bool:
        """Google API 사용 가능 여부"""
        return GOOGLE_API_AVAILABLE
    
    def is_authenticated(self) -> bool:
        """인증 완료 여부"""
        return self.credentials is not None and self.credentials.valid
    
    def _load_credentials(self) -> None:
        """저장된 토큰 로드"""
        if os.path.exists(self.token_path):
            try:
                self.credentials = Credentials.from_authorized_user_file(
                    self.token_path, SCOPES
                )
                
                # 만료됐으면 갱신
                if self.credentials and self.credentials.expired and self.credentials.refresh_token:
                    self.credentials.refresh(Request())
                    self._save_credentials()
                
            except Exception as e:
                print(f"토큰 로드 실패: {e}")
                self.credentials = None
    
    def _save_credentials(self) -> None:
        """토큰 저장"""
        if self.credentials:
            with open(self.token_path, 'w') as f:
                f.write(self.credentials.to_json())
    
    def authenticate(self) -> bool:
        """Google 계정 인증 (브라우저 열림)
        
        Returns:
            성공 여부
        """
        if not GOOGLE_API_AVAILABLE:
            print("Google API 라이브러리가 설치되지 않았습니다.")
            return False
        
        try:
            flow = InstalledAppFlow.from_client_config(
                GOOGLE_CLIENT_CONFIG, SCOPES
            )
            self.credentials = flow.run_local_server(port=0)
            self._save_credentials()
            
            # 설정에 활성화 표시
            self.config.set('calendar.enabled', True)
            self.config.save()
            
            print("✅ Google 캘린더 연동 완료!")
            return True
            
        except Exception as e:
            print(f"❌ 인증 실패: {e}")
            return False
    
    def disconnect(self) -> None:
        """연동 해제"""
        if os.path.exists(self.token_path):
            os.remove(self.token_path)
        
        self.credentials = None
        self.service = None
        
        self.config.set('calendar.enabled', False)
        self.config.save()
        
        print("Google 캘린더 연동이 해제되었습니다.")
    
    def _get_service(self):
        """Calendar API 서비스 객체"""
        if not self.is_authenticated():
            return None
        
        if self.service is None:
            self.service = build('calendar', 'v3', credentials=self.credentials)
        
        return self.service
    
    def create_event(self, event_data: Dict[str, Any]) -> Optional[str]:
        """캘린더 이벤트 생성
        
        Args:
            event_data: {
                'title': str,           # 제목 (필수)
                'date': str,            # 날짜 YYYY-MM-DD (필수)
                'time': str,            # 시간 HH:MM (선택)
                'location': str,        # 장소 (선택)
                'description': str,     # 설명 (선택)
                'reminders': list,      # 알림 (선택)
                'color': str            # 색상 ID (선택)
            }
        
        Returns:
            생성된 이벤트 ID (실패 시 None)
        """
        service = self._get_service()
        if not service:
            print("캘린더 서비스 연결 실패")
            return None
        
        try:
            # 이벤트 구성
            event = {
                'summary': event_data['title'],
                'description': event_data.get('description', ''),
                'location': event_data.get('location', ''),
            }
            
            # 날짜/시간 설정
            date = event_data['date']
            time = event_data.get('time')
            
            if time:
                # 시간 있으면 datetime으로
                start_dt = f"{date}T{time}:00"
                end_dt = f"{date}T{int(time.split(':')[0])+1:02d}:{time.split(':')[1]}:00"
                event['start'] = {'dateTime': start_dt, 'timeZone': 'Asia/Seoul'}
                event['end'] = {'dateTime': end_dt, 'timeZone': 'Asia/Seoul'}
            else:
                # 시간 없으면 종일 이벤트
                event['start'] = {'date': date}
                event['end'] = {'date': date}
            
            # 알림 설정
            reminders = event_data.get('reminders', [
                {'method': 'popup', 'minutes': 1440},  # 1일 전
                {'method': 'popup', 'minutes': 60}     # 1시간 전
            ])
            event['reminders'] = {
                'useDefault': False,
                'overrides': reminders
            }
            
            # 색상 설정
            if 'color' in event_data:
                event['colorId'] = event_data['color']
            
            # 이벤트 생성
            calendar_id = self.config.get('calendar.calendar_id', 'primary')
            result = service.events().insert(
                calendarId=calendar_id,
                body=event
            ).execute()
            
            print(f"✅ 캘린더 등록: {event_data['title']}")
            return result.get('id')
            
        except Exception as e:
            print(f"❌ 캘린더 등록 실패: {e}")
            return None
    
    def create_deadline_event(self, message: Dict[str, Any]) -> Optional[str]:
        """마감일 이벤트 생성 (행동형 쪽지용)
        
        Args:
            message: {
                'title': str,
                'deadline': str (YYYY-MM-DD),
                'category': str,
                'process': list
            }
        """
        if not message.get('deadline'):
            return None
        
        # 마감일 기준 알림 설정
        reminders = [
            {'method': 'popup', 'minutes': 4320},   # D-3
            {'method': 'popup', 'minutes': 1440},   # D-1
            {'method': 'popup', 'minutes': 540},    # 당일 오전 9시
        ]
        
        description = f"""📋 행동 필요 쪽지

■ 업무: {message.get('category', '')}
■ 요약: {message.get('summary', '')}

■ 실행 프로세스:
{chr(10).join(f'  {i+1}. {p}' for i, p in enumerate(message.get('process', [])))}

---
GOE 메신저 도우미에서 자동 등록됨
"""
        
        return self.create_event({
            'title': f"🔴 [마감] {message['title'][:30]}",
            'date': message['deadline'],
            'description': description,
            'reminders': reminders,
            'color': '11'  # 빨간색
        })
    
    def create_info_event(self, message: Dict[str, Any]) -> Optional[str]:
        """정보 이벤트 생성 (정보형 쪽지용)
        
        Args:
            message: {
                'title': str,
                'event_date': str (YYYY-MM-DD),
                'event_time': str (HH:MM),
                'location': str,
                'remember': list
            }
        """
        if not message.get('event_date'):
            return None
        
        # 정보형은 알림 적게
        reminders = [
            {'method': 'popup', 'minutes': 1440},  # D-1
            {'method': 'popup', 'minutes': 60}     # 1시간 전
        ]
        
        remember_text = ""
        if message.get('remember'):
            remember_text = "\n■ 기억해야 할 것:\n" + \
                "\n".join(f"  • {r}" for r in message['remember'])
        
        description = f"""📢 정보/공지 쪽지

■ 장소: {message.get('location', '미정')}
{remember_text}

---
GOE 메신저 도우미에서 자동 등록됨
"""
        
        return self.create_event({
            'title': f"📢 {message['title'][:30]}",
            'date': message['event_date'],
            'time': message.get('event_time'),
            'location': message.get('location'),
            'description': description,
            'reminders': reminders,
            'color': '8'  # 회색 (참고용)
        })
    
    def get_upcoming_events(self, days: int = 7) -> List[Dict]:
        """다가오는 이벤트 조회"""
        service = self._get_service()
        if not service:
            return []
        
        try:
            now = datetime.utcnow().isoformat() + 'Z'
            end = (datetime.utcnow() + timedelta(days=days)).isoformat() + 'Z'
            
            calendar_id = self.config.get('calendar.calendar_id', 'primary')
            events_result = service.events().list(
                calendarId=calendar_id,
                timeMin=now,
                timeMax=end,
                maxResults=50,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            return events_result.get('items', [])
            
        except Exception as e:
            print(f"이벤트 조회 실패: {e}")
            return []


# ============================================================
# 테스트
# ============================================================

if __name__ == "__main__":
    print("=" * 50)
    print("Google Calendar 연동 테스트")
    print("=" * 50)
    
    calendar = GoogleCalendarSync()
    
    print(f"API 사용 가능: {calendar.is_available()}")
    print(f"인증 완료: {calendar.is_authenticated()}")
    print(f"토큰 경로: {get_token_path()}")
    
    if not calendar.is_available():
        print("\n⚠️ 다음 명령어로 라이브러리 설치:")
        print("pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client")
