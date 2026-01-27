"""
설정 및 경로 관리 모듈
- exe 배포 시 경로 문제 해결
- 기본 설정 내장
- 사용자 설정 자동 저장/로드
"""

import os
import sys
import yaml
from typing import Dict, Any, Optional


# ============================================================
# 기본 설정 (코드에 내장 - 별도 파일 필요 없음)
# ============================================================

DEFAULT_CONFIG = {
    'app': {
        'name': 'GOE 메신저 도우미',
        'version': '1.0.0'
    },
    'messenger': {
        'path': r'C:\Program Files (x86)\AtMessenger7',
        'check_interval': 30,  # 초
        'auto_save': True
    },
    'calendar': {
        'enabled': False,
        'calendar_id': 'primary'
    },
    'importance': {
        'auto_star_grades': ['S', 'A'],
        'show_notifications': True
    },
    'ui': {
        'theme': 'default',
        'window_size': [1200, 800]
    }
}


# ============================================================
# 경로 관리 (exe 배포 시에도 문제없음)
# ============================================================

def get_app_folder() -> str:
    """앱 실행 파일이 있는 폴더 (읽기 전용)
    
    개발 중: 스크립트 파일 위치
    exe 실행: exe 파일 위치
    """
    if getattr(sys, 'frozen', False):
        # PyInstaller로 패키징된 exe
        return os.path.dirname(sys.executable)
    else:
        # 개발 환경 (python으로 실행)
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_data_folder() -> str:
    """데이터 저장 폴더 (읽기/쓰기)
    
    위치: C:/Users/{사용자}/Documents/GOE메신저도우미/
    - 어디서 exe를 실행해도 같은 위치
    - 자동 생성됨
    """
    folder = os.path.join(
        os.path.expanduser('~'),
        'Documents',
        'GOE메신저도우미'
    )
    os.makedirs(folder, exist_ok=True)
    return folder


def get_config_path() -> str:
    """설정 파일 경로"""
    return os.path.join(get_data_folder(), 'config.yaml')


def get_token_path() -> str:
    """Google 인증 토큰 경로"""
    return os.path.join(get_data_folder(), 'google_token.json')


def get_db_path() -> str:
    """데이터베이스 경로"""
    return os.path.join(get_data_folder(), 'messages.db')


def get_attachments_folder() -> str:
    """첨부파일 저장 폴더"""
    folder = os.path.join(get_data_folder(), '첨부파일')
    os.makedirs(folder, exist_ok=True)
    return folder


def get_log_path() -> str:
    """로그 파일 경로"""
    return os.path.join(get_data_folder(), 'app.log')


# ============================================================
# 설정 관리 클래스
# ============================================================

class ConfigManager:
    """설정 관리자
    
    사용법:
        config = ConfigManager()
        
        # 읽기
        path = config.get('messenger.path')
        
        # 쓰기
        config.set('messenger.path', 'C:/새경로')
        config.save()
    """
    
    def __init__(self):
        self.config_path = get_config_path()
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """설정 로드 (없으면 기본값 사용)"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    user_config = yaml.safe_load(f) or {}
                # 기본값과 병합 (사용자 설정 우선)
                return self._merge_config(DEFAULT_CONFIG, user_config)
            except Exception as e:
                print(f"설정 로드 실패, 기본값 사용: {e}")
        
        return DEFAULT_CONFIG.copy()
    
    def _merge_config(self, default: Dict, user: Dict) -> Dict:
        """기본 설정과 사용자 설정 병합"""
        result = default.copy()
        for key, value in user.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_config(result[key], value)
            else:
                result[key] = value
        return result
    
    def get(self, key: str, default: Any = None) -> Any:
        """설정 값 읽기
        
        Args:
            key: 점(.)으로 구분된 키 (예: 'messenger.path')
            default: 없을 때 반환값
        
        Returns:
            설정 값
        """
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any) -> None:
        """설정 값 쓰기
        
        Args:
            key: 점(.)으로 구분된 키
            value: 저장할 값
        """
        keys = key.split('.')
        config = self.config
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value
    
    def save(self) -> bool:
        """설정 파일 저장"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(self.config, f, allow_unicode=True, default_flow_style=False)
            return True
        except Exception as e:
            print(f"설정 저장 실패: {e}")
            return False
    
    def reset(self) -> None:
        """설정 초기화"""
        self.config = DEFAULT_CONFIG.copy()
        self.save()
    
    def get_all(self) -> Dict[str, Any]:
        """전체 설정 반환"""
        return self.config.copy()


# ============================================================
# 첫 실행 체크
# ============================================================

def is_first_run() -> bool:
    """첫 실행 여부 확인"""
    return not os.path.exists(get_config_path())


def init_first_run() -> None:
    """첫 실행 시 초기화"""
    # 폴더 생성
    get_data_folder()
    get_attachments_folder()
    
    # 기본 설정 저장
    config = ConfigManager()
    config.save()
    
    print(f"✅ 초기 설정 완료!")
    print(f"   데이터 폴더: {get_data_folder()}")


# ============================================================
# 테스트
# ============================================================

if __name__ == "__main__":
    print("=" * 50)
    print("경로 정보")
    print("=" * 50)
    print(f"앱 폴더: {get_app_folder()}")
    print(f"데이터 폴더: {get_data_folder()}")
    print(f"설정 파일: {get_config_path()}")
    print(f"DB 파일: {get_db_path()}")
    print(f"첨부파일: {get_attachments_folder()}")
    
    print("\n" + "=" * 50)
    print("설정 테스트")
    print("=" * 50)
    
    config = ConfigManager()
    print(f"메신저 경로: {config.get('messenger.path')}")
    print(f"자동 저장: {config.get('messenger.auto_save')}")
    print(f"캘린더 활성화: {config.get('calendar.enabled')}")
    
    # 설정 변경 테스트
    config.set('messenger.path', r'D:\새경로\AtMessenger7')
    print(f"\n변경 후 경로: {config.get('messenger.path')}")
    
    print("\n첫 실행 여부:", is_first_run())
