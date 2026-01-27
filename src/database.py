"""
데이터베이스 관리 모듈
- JSON 파일 기반 저장
- 메시지 CRUD 연산
- 검색 및 필터링
"""

import json
import os
import shutil
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable
from pathlib import Path

from .models import (
    Message, MessageFilter, DashboardStats,
    MessageStatus, MessageCategory, TaskGroup,
    create_message
)
from .config import get_data_folder


# ============================================================
# 데이터베이스 인터페이스 (추상)
# ============================================================

class DatabaseInterface:
    """데이터베이스 인터페이스 (다른 모듈에서 import)"""

    def add(self, message: Message) -> str:
        """메시지 추가, ID 반환"""
        raise NotImplementedError

    def get(self, message_id: str) -> Optional[Message]:
        """ID로 메시지 조회"""
        raise NotImplementedError

    def get_all(self) -> List[Message]:
        """모든 메시지 조회"""
        raise NotImplementedError

    def update(self, message: Message) -> bool:
        """메시지 업데이트"""
        raise NotImplementedError

    def delete(self, message_id: str) -> bool:
        """메시지 삭제"""
        raise NotImplementedError

    def search(self, filter_: MessageFilter) -> List[Message]:
        """필터로 검색"""
        raise NotImplementedError

    def get_stats(self) -> DashboardStats:
        """통계 조회"""
        raise NotImplementedError


# ============================================================
# JSON 파일 기반 데이터베이스
# ============================================================

class MessageDatabase(DatabaseInterface):
    """JSON 파일 기반 메시지 데이터베이스

    파일 구조:
        data/
        ├── messages.json      # 메시지 데이터
        ├── status.json        # 상태 정보 (완료/중요)
        └── backup/            # 백업 폴더
    """

    def __init__(self, data_folder: Optional[str] = None):
        self.data_folder = data_folder or get_data_folder()
        self.messages_file = os.path.join(self.data_folder, 'messages.json')
        self.status_file = os.path.join(self.data_folder, 'status.json')
        self.backup_folder = os.path.join(self.data_folder, 'backup')

        # 폴더 생성
        os.makedirs(self.data_folder, exist_ok=True)
        os.makedirs(self.backup_folder, exist_ok=True)

        # 데이터 로드
        self._messages: Dict[str, Dict] = {}
        self._load()

    # ==================== 파일 I/O ====================

    def _load(self) -> None:
        """데이터 파일 로드"""
        if os.path.exists(self.messages_file):
            try:
                with open(self.messages_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 리스트면 딕셔너리로 변환
                    if isinstance(data, list):
                        self._messages = {m['id']: m for m in data if 'id' in m}
                    else:
                        self._messages = data
            except (json.JSONDecodeError, Exception) as e:
                print(f"데이터 로드 실패: {e}")
                self._messages = {}

    def _save(self) -> None:
        """데이터 파일 저장"""
        try:
            # 백업 (기존 파일이 있으면)
            if os.path.exists(self.messages_file):
                backup_name = f"messages_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                backup_path = os.path.join(self.backup_folder, backup_name)
                shutil.copy2(self.messages_file, backup_path)
                self._cleanup_backups()

            # 저장
            with open(self.messages_file, 'w', encoding='utf-8') as f:
                json.dump(self._messages, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"데이터 저장 실패: {e}")

    def _cleanup_backups(self, keep: int = 10) -> None:
        """오래된 백업 파일 정리"""
        backups = sorted(Path(self.backup_folder).glob('messages_*.json'))
        for old_backup in backups[:-keep]:
            try:
                old_backup.unlink()
            except Exception:
                pass

    # ==================== CRUD 연산 ====================

    def add(self, message: Message) -> str:
        """메시지 추가

        Args:
            message: Message 객체

        Returns:
            추가된 메시지 ID
        """
        msg_dict = message.to_dict()
        msg_dict['created_at'] = datetime.now().isoformat()
        msg_dict['updated_at'] = msg_dict['created_at']

        self._messages[message.id] = msg_dict
        self._save()
        return message.id

    def get(self, message_id: str) -> Optional[Message]:
        """ID로 메시지 조회

        Args:
            message_id: 메시지 ID

        Returns:
            Message 객체 또는 None
        """
        data = self._messages.get(message_id)
        if data:
            return Message.from_dict(data)
        return None

    def get_all(self) -> List[Message]:
        """모든 메시지 조회 (최신순)

        Returns:
            Message 리스트
        """
        messages = [Message.from_dict(m) for m in self._messages.values()]
        # 수신일 기준 최신순 정렬
        messages.sort(key=lambda x: x.received_at or '', reverse=True)
        return messages

    def update(self, message: Message) -> bool:
        """메시지 업데이트

        Args:
            message: 업데이트할 Message 객체

        Returns:
            성공 여부
        """
        if message.id not in self._messages:
            return False

        msg_dict = message.to_dict()
        msg_dict['updated_at'] = datetime.now().isoformat()
        self._messages[message.id] = msg_dict
        self._save()
        return True

    def delete(self, message_id: str) -> bool:
        """메시지 삭제

        Args:
            message_id: 삭제할 메시지 ID

        Returns:
            성공 여부
        """
        if message_id in self._messages:
            del self._messages[message_id]
            self._save()
            return True
        return False

    # ==================== 상태 변경 ====================

    def mark_completed(self, message_id: str) -> bool:
        """완료 처리"""
        msg = self.get(message_id)
        if msg:
            msg.mark_completed()
            return self.update(msg)
        return False

    def mark_pending(self, message_id: str) -> bool:
        """대기 상태로 변경"""
        msg = self.get(message_id)
        if msg:
            msg.status = MessageStatus.PENDING.value
            msg.updated_at = datetime.now().isoformat()
            return self.update(msg)
        return False

    def toggle_starred(self, message_id: str) -> bool:
        """중요 표시 토글"""
        msg = self.get(message_id)
        if msg:
            msg.toggle_star()
            return self.update(msg)
        return False

    def set_starred(self, message_id: str, starred: bool) -> bool:
        """중요 표시 설정"""
        msg = self.get(message_id)
        if msg:
            msg.starred = starred
            msg.updated_at = datetime.now().isoformat()
            return self.update(msg)
        return False

    # ==================== 검색/필터 ====================

    def search(self, filter_: MessageFilter) -> List[Message]:
        """필터 조건으로 검색

        Args:
            filter_: MessageFilter 객체

        Returns:
            조건에 맞는 Message 리스트
        """
        messages = self.get_all()
        result = []

        for msg in messages:
            if self._matches_filter(msg, filter_):
                result.append(msg)

        return result

    def _matches_filter(self, msg: Message, f: MessageFilter) -> bool:
        """메시지가 필터 조건에 맞는지 확인"""
        # 검색어 (제목/본문)
        if f.query:
            query = f.query.lower()
            if query not in msg.title.lower() and query not in msg.content.lower():
                return False

        # 발신자
        if f.sender and f.sender.lower() not in msg.sender.lower():
            return False

        # 상태
        if f.status and msg.status != f.status:
            return False

        # 중요 표시만
        if f.starred_only and not msg.starred:
            return False

        # 대분류
        if f.category and msg.category != f.category:
            return False

        # 업무 그룹
        if f.task_group and msg.task_group != f.task_group:
            return False

        # 날짜 범위
        if f.date_from:
            if not msg.received_at or msg.received_at < f.date_from:
                return False
        if f.date_to:
            if not msg.received_at or msg.received_at > f.date_to:
                return False

        # 마감일 유무
        if f.has_deadline is not None:
            has_dl = bool(msg.deadline)
            if f.has_deadline != has_dl:
                return False

        # 중요도 등급
        if f.grade and msg.grade != f.grade:
            return False

        return True

    def find_by_title(self, title: str) -> List[Message]:
        """제목으로 검색"""
        return self.search(MessageFilter(query=title))

    def find_by_sender(self, sender: str) -> List[Message]:
        """발신자로 검색"""
        return self.search(MessageFilter(sender=sender))

    def get_urgent(self) -> List[Message]:
        """긴급 메시지 (D-2 이내, 미완료)"""
        messages = self.get_all()
        return [m for m in messages if m.is_urgent and not m.is_completed]

    def get_pending(self) -> List[Message]:
        """미완료 메시지"""
        return self.search(MessageFilter(status=MessageStatus.PENDING.value))

    def get_completed(self) -> List[Message]:
        """완료 메시지"""
        return self.search(MessageFilter(status=MessageStatus.COMPLETED.value))

    def get_starred(self) -> List[Message]:
        """중요 표시 메시지"""
        return self.search(MessageFilter(starred_only=True))

    def get_by_group(self, group: str) -> List[Message]:
        """업무 그룹별 조회"""
        return self.search(MessageFilter(task_group=group))

    def get_today(self) -> List[Message]:
        """오늘 수신된 메시지"""
        today = datetime.now().strftime('%Y-%m-%d')
        messages = self.get_all()
        return [m for m in messages if m.received_at and m.received_at.startswith(today)]

    # ==================== 통계 ====================

    def get_stats(self) -> DashboardStats:
        """대시보드 통계 조회"""
        messages = self.get_all()
        today = datetime.now().strftime('%Y-%m-%d')

        stats = DashboardStats(
            total=len(messages),
            pending=sum(1 for m in messages if m.status == MessageStatus.PENDING.value),
            in_progress=sum(1 for m in messages if m.status == MessageStatus.IN_PROGRESS.value),
            completed=sum(1 for m in messages if m.status == MessageStatus.COMPLETED.value),
            urgent=sum(1 for m in messages if m.is_urgent and not m.is_completed),
            starred=sum(1 for m in messages if m.starred),
            today_new=sum(1 for m in messages
                        if m.received_at and m.received_at.startswith(today))
        )
        return stats

    def get_group_stats(self) -> List[Dict[str, Any]]:
        """업무 그룹별 통계"""
        messages = self.get_all()
        groups = {}

        for msg in messages:
            group = msg.task_group
            if group not in groups:
                groups[group] = {'total': 0, 'pending': 0, 'urgent': 0}

            groups[group]['total'] += 1
            if not msg.is_completed:
                groups[group]['pending'] += 1
            if msg.is_urgent and not msg.is_completed:
                groups[group]['urgent'] += 1

        return [
            {
                'group': g,
                'icon': {'담임': '🎓', '제출': '📋', '회의': '📅',
                        '예산': '💰', '공지': '📢'}.get(g, '📌'),
                **stats
            }
            for g, stats in groups.items()
        ]

    # ==================== 유틸리티 ====================

    def count(self) -> int:
        """전체 메시지 수"""
        return len(self._messages)

    def exists(self, message_id: str) -> bool:
        """메시지 존재 여부"""
        return message_id in self._messages

    def clear(self) -> None:
        """모든 데이터 삭제 (주의!)"""
        self._messages = {}
        self._save()

    def export_json(self, filepath: str) -> bool:
        """JSON으로 내보내기"""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(list(self._messages.values()), f,
                         ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"내보내기 실패: {e}")
            return False

    def import_json(self, filepath: str) -> int:
        """JSON에서 가져오기"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            count = 0
            for item in data:
                if 'id' in item and item['id'] not in self._messages:
                    self._messages[item['id']] = item
                    count += 1

            self._save()
            return count
        except Exception as e:
            print(f"가져오기 실패: {e}")
            return 0


# ============================================================
# 상태 관리 (완료/중요 별도 저장)
# ============================================================

class StatusManager:
    """상태 정보 별도 관리

    messages.json은 원본 보존
    status.json에 상태 변경만 저장
    """

    def __init__(self, data_folder: Optional[str] = None):
        self.data_folder = data_folder or get_data_folder()
        self.status_file = os.path.join(self.data_folder, 'status.json')
        self._status: Dict[str, Dict] = {}
        self._load()

    def _load(self) -> None:
        """상태 파일 로드"""
        if os.path.exists(self.status_file):
            try:
                with open(self.status_file, 'r', encoding='utf-8') as f:
                    self._status = json.load(f)
            except Exception:
                self._status = {}

    def _save(self) -> None:
        """상태 파일 저장"""
        try:
            with open(self.status_file, 'w', encoding='utf-8') as f:
                json.dump(self._status, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"상태 저장 실패: {e}")

    def get_status(self, message_id: str) -> Dict[str, Any]:
        """메시지 상태 조회"""
        return self._status.get(message_id, {
            'status': MessageStatus.PENDING.value,
            'starred': False,
            'completed_at': None
        })

    def set_status(self, message_id: str, status: str) -> None:
        """상태 설정"""
        if message_id not in self._status:
            self._status[message_id] = {}

        self._status[message_id]['status'] = status
        if status == MessageStatus.COMPLETED.value:
            self._status[message_id]['completed_at'] = datetime.now().isoformat()
        self._save()

    def set_starred(self, message_id: str, starred: bool) -> None:
        """중요 표시 설정"""
        if message_id not in self._status:
            self._status[message_id] = {}
        self._status[message_id]['starred'] = starred
        self._save()


# ============================================================
# 전역 데이터베이스 인스턴스
# ============================================================

_db_instance: Optional[MessageDatabase] = None


def get_database() -> MessageDatabase:
    """데이터베이스 싱글톤 인스턴스"""
    global _db_instance
    if _db_instance is None:
        _db_instance = MessageDatabase()
    return _db_instance


def init_database(data_folder: Optional[str] = None) -> MessageDatabase:
    """데이터베이스 초기화 (경로 지정 가능)"""
    global _db_instance
    _db_instance = MessageDatabase(data_folder)
    return _db_instance


# ============================================================
# 테스트
# ============================================================

if __name__ == "__main__":
    import uuid
    from datetime import timedelta

    print("=== 데이터베이스 테스트 ===\n")

    # 테스트용 임시 폴더
    test_folder = os.path.join(get_data_folder(), 'test_db')
    os.makedirs(test_folder, exist_ok=True)

    db = MessageDatabase(test_folder)

    # 메시지 추가
    print("1. 메시지 추가")
    today = datetime.now()

    msg1 = create_message(
        title="생활기록부 최종 마감 안내",
        content="담임선생님께서는 1월 29일까지 나이스에 생기부를 제출해 주세요.",
        sender="교무기획부 김OO 부장",
        deadline=(today + timedelta(days=2)).strftime('%Y-%m-%d'),
        starred=True,
        task_group="담임"
    )
    db.add(msg1)
    print(f"   추가됨: {msg1.id[:8]}... - {msg1.title}")

    msg2 = create_message(
        title="2월 교직원 회의 안내",
        content="2월 5일 15시 시청각실에서 교직원 회의가 있습니다.",
        sender="교무기획부",
        category="information",
        task_group="회의"
    )
    db.add(msg2)
    print(f"   추가됨: {msg2.id[:8]}... - {msg2.title}")

    # 조회
    print("\n2. 전체 조회")
    all_msgs = db.get_all()
    for m in all_msgs:
        print(f"   {m.color_code} {m.title} ({m.sender})")

    # 통계
    print("\n3. 통계")
    stats = db.get_stats()
    print(f"   전체: {stats.total}, 미완료: {stats.pending}, 긴급: {stats.urgent}")

    # 검색
    print("\n4. 검색 (제목: 생기부)")
    results = db.find_by_title("생기부")
    for m in results:
        print(f"   {m.title}")

    # 완료 처리
    print("\n5. 완료 처리")
    db.mark_completed(msg1.id)
    updated = db.get(msg1.id)
    print(f"   {updated.title}: {updated.status}")

    # 정리
    print("\n6. 테스트 폴더 정리")
    db.clear()
    shutil.rmtree(test_folder, ignore_errors=True)
    print("   완료!")
