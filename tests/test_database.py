"""
Test database module
- MessageDatabase CRUD operations
- Search and filtering
- Statistics
"""

import pytest
import os
import tempfile
import shutil
from datetime import datetime, timedelta
import json

# Import modules
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import MessageDatabase, StatusManager, init_database
from src.models import (
    Message, MessageFilter, MessageStatus,
    create_message
)


# ============================================================
# Sample Test Data
# ============================================================

SAMPLE_MESSAGES = [
    {
        'title': '2학기 생활기록부 최종 마감 안내',
        'sender': '교무기획부 김철수 부장',
        'content': '담임선생님께서는 1월 29일까지 나이스에 생기부를 제출해 주세요.',
        'deadline': None,  # Will be set dynamically
        'task_group': '담임',
        'starred': True
    },
    {
        'title': '2월 교직원 회의 안내',
        'sender': '교무기획부',
        'content': '2월 5일 15시에 교직원 회의가 있습니다.',
        'deadline': None,
        'task_group': '회의',
        'starred': False
    },
    {
        'title': '예산 집행 마감 안내',
        'sender': '행정실',
        'content': '1월 31일까지 예산 집행을 완료해 주세요.',
        'deadline': None,
        'task_group': '예산',
        'starred': False
    }
]


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def temp_data_folder():
    """Create a temporary data folder for tests"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def db(temp_data_folder):
    """Create a MessageDatabase instance with temporary storage"""
    return MessageDatabase(data_folder=temp_data_folder)


@pytest.fixture
def populated_db(db):
    """Create a database with sample messages"""
    today = datetime.now()

    for i, msg_data in enumerate(SAMPLE_MESSAGES):
        deadline = (today + timedelta(days=i+1)).strftime('%Y-%m-%d')
        msg = create_message(
            title=msg_data['title'],
            content=msg_data['content'],
            sender=msg_data['sender'],
            deadline=deadline,
            task_group=msg_data['task_group'],
            starred=msg_data['starred']
        )
        db.add(msg)

    return db


# ============================================================
# Basic CRUD Tests
# ============================================================

class TestMessageDatabaseCRUD:
    """Test basic CRUD operations"""

    def test_add_message(self, db):
        """Test adding a message"""
        msg = create_message(
            title='테스트 메시지',
            content='테스트 내용',
            sender='테스트 발신자'
        )

        msg_id = db.add(msg)

        assert msg_id == msg.id
        assert db.count() == 1

    def test_add_multiple_messages(self, db):
        """Test adding multiple messages"""
        for i in range(5):
            msg = create_message(
                title=f'메시지 {i}',
                content=f'내용 {i}',
                sender='발신자'
            )
            db.add(msg)

        assert db.count() == 5

    def test_get_message(self, db):
        """Test retrieving a message by ID"""
        msg = create_message(
            title='조회 테스트',
            content='테스트 내용',
            sender='발신자'
        )
        db.add(msg)

        retrieved = db.get(msg.id)

        assert retrieved is not None
        assert retrieved.id == msg.id
        assert retrieved.title == '조회 테스트'

    def test_get_nonexistent_message(self, db):
        """Test retrieving non-existent message returns None"""
        result = db.get('nonexistent-id')
        assert result is None

    def test_get_all_messages(self, populated_db):
        """Test retrieving all messages"""
        messages = populated_db.get_all()

        assert len(messages) == 3
        assert all(isinstance(m, Message) for m in messages)

    def test_update_message(self, db):
        """Test updating a message"""
        msg = create_message(
            title='원본 제목',
            content='원본 내용',
            sender='발신자'
        )
        db.add(msg)

        # Modify and update
        msg.title = '수정된 제목'
        msg.starred = True
        result = db.update(msg)

        assert result is True

        # Verify update
        updated = db.get(msg.id)
        assert updated.title == '수정된 제목'
        assert updated.starred is True

    def test_update_nonexistent_message(self, db):
        """Test updating non-existent message returns False"""
        msg = create_message(
            title='테스트',
            content='테스트',
            sender='발신자'
        )
        # Don't add to db

        result = db.update(msg)
        assert result is False

    def test_delete_message(self, db):
        """Test deleting a message"""
        msg = create_message(
            title='삭제 테스트',
            content='삭제될 내용',
            sender='발신자'
        )
        db.add(msg)
        assert db.count() == 1

        result = db.delete(msg.id)

        assert result is True
        assert db.count() == 0
        assert db.get(msg.id) is None

    def test_delete_nonexistent_message(self, db):
        """Test deleting non-existent message returns False"""
        result = db.delete('nonexistent-id')
        assert result is False

    def test_exists(self, db):
        """Test checking if message exists"""
        msg = create_message(
            title='존재 확인',
            content='테스트',
            sender='발신자'
        )
        db.add(msg)

        assert db.exists(msg.id) is True
        assert db.exists('nonexistent-id') is False

    def test_clear(self, populated_db):
        """Test clearing all messages"""
        assert populated_db.count() == 3

        populated_db.clear()

        assert populated_db.count() == 0


# ============================================================
# Status Change Tests
# ============================================================

class TestMessageDatabaseStatus:
    """Test status change operations"""

    def test_mark_completed(self, db):
        """Test marking message as completed"""
        msg = create_message(
            title='완료 테스트',
            content='테스트',
            sender='발신자'
        )
        db.add(msg)

        result = db.mark_completed(msg.id)

        assert result is True
        updated = db.get(msg.id)
        assert updated.status == MessageStatus.COMPLETED.value

    def test_mark_pending(self, db):
        """Test marking message as pending"""
        msg = create_message(
            title='대기 테스트',
            content='테스트',
            sender='발신자'
        )
        msg.status = MessageStatus.COMPLETED.value
        db.add(msg)

        result = db.mark_pending(msg.id)

        assert result is True
        updated = db.get(msg.id)
        assert updated.status == MessageStatus.PENDING.value

    def test_toggle_starred(self, db):
        """Test toggling starred status"""
        msg = create_message(
            title='중요 테스트',
            content='테스트',
            sender='발신자'
        )
        db.add(msg)

        # Toggle on
        db.toggle_starred(msg.id)
        assert db.get(msg.id).starred is True

        # Toggle off
        db.toggle_starred(msg.id)
        assert db.get(msg.id).starred is False

    def test_set_starred(self, db):
        """Test setting starred status directly"""
        msg = create_message(
            title='중요 설정 테스트',
            content='테스트',
            sender='발신자'
        )
        db.add(msg)

        db.set_starred(msg.id, True)
        assert db.get(msg.id).starred is True

        db.set_starred(msg.id, False)
        assert db.get(msg.id).starred is False


# ============================================================
# Search and Filter Tests
# ============================================================

class TestMessageDatabaseSearch:
    """Test search and filter operations"""

    def test_search_by_query(self, populated_db):
        """Test searching by query string"""
        filter_ = MessageFilter(query='생기부')
        results = populated_db.search(filter_)

        assert len(results) == 1
        assert '생기부' in results[0].title

    def test_search_by_sender(self, populated_db):
        """Test searching by sender"""
        filter_ = MessageFilter(sender='행정실')
        results = populated_db.search(filter_)

        assert len(results) == 1
        assert results[0].sender == '행정실'

    def test_search_by_status(self, populated_db):
        """Test searching by status"""
        # Mark one as completed
        messages = populated_db.get_all()
        populated_db.mark_completed(messages[0].id)

        filter_ = MessageFilter(status=MessageStatus.PENDING.value)
        results = populated_db.search(filter_)

        assert len(results) == 2

    def test_search_starred_only(self, populated_db):
        """Test searching starred messages only"""
        filter_ = MessageFilter(starred_only=True)
        results = populated_db.search(filter_)

        assert len(results) == 1
        assert results[0].starred is True

    def test_search_by_task_group(self, populated_db):
        """Test searching by task group"""
        filter_ = MessageFilter(task_group='담임')
        results = populated_db.search(filter_)

        assert len(results) == 1
        assert results[0].task_group == '담임'

    def test_find_by_title(self, populated_db):
        """Test find_by_title helper"""
        results = populated_db.find_by_title('회의')

        assert len(results) == 1
        assert '회의' in results[0].title

    def test_find_by_sender(self, populated_db):
        """Test find_by_sender helper"""
        results = populated_db.find_by_sender('교무기획부')

        # Both messages from 교무기획부
        assert len(results) == 2

    def test_get_urgent(self, populated_db):
        """Test getting urgent messages"""
        # D-1 should be urgent
        results = populated_db.get_urgent()

        assert len(results) >= 1
        assert all(m.is_urgent for m in results)

    def test_get_pending(self, populated_db):
        """Test getting pending messages"""
        results = populated_db.get_pending()

        assert len(results) == 3
        assert all(m.status == MessageStatus.PENDING.value for m in results)

    def test_get_completed(self, populated_db):
        """Test getting completed messages"""
        messages = populated_db.get_all()
        populated_db.mark_completed(messages[0].id)

        results = populated_db.get_completed()

        assert len(results) == 1

    def test_get_starred(self, populated_db):
        """Test getting starred messages"""
        results = populated_db.get_starred()

        assert len(results) == 1
        assert results[0].starred is True

    def test_get_by_group(self, populated_db):
        """Test getting messages by group"""
        results = populated_db.get_by_group('회의')

        assert len(results) == 1
        assert results[0].task_group == '회의'


# ============================================================
# Statistics Tests
# ============================================================

class TestMessageDatabaseStats:
    """Test statistics operations"""

    def test_get_stats(self, populated_db):
        """Test getting dashboard statistics"""
        stats = populated_db.get_stats()

        assert stats.total == 3
        assert stats.pending == 3
        assert stats.completed == 0
        assert stats.starred == 1

    def test_get_stats_with_completed(self, populated_db):
        """Test stats after completing messages"""
        messages = populated_db.get_all()
        populated_db.mark_completed(messages[0].id)
        populated_db.mark_completed(messages[1].id)

        stats = populated_db.get_stats()

        assert stats.total == 3
        assert stats.pending == 1
        assert stats.completed == 2

    def test_get_stats_urgent(self, populated_db):
        """Test urgent count in stats"""
        stats = populated_db.get_stats()

        # At least one should be urgent (D-1)
        assert stats.urgent >= 1

    def test_get_group_stats(self, populated_db):
        """Test group statistics"""
        group_stats = populated_db.get_group_stats()

        assert isinstance(group_stats, list)
        assert len(group_stats) == 3  # 담임, 회의, 예산

        # Find 담임 group
        homeroom = next((g for g in group_stats if g['group'] == '담임'), None)
        assert homeroom is not None
        assert homeroom['total'] == 1
        assert homeroom['icon'] == '🎓'


# ============================================================
# File I/O Tests
# ============================================================

class TestMessageDatabaseIO:
    """Test file I/O operations"""

    def test_data_persists(self, temp_data_folder):
        """Test data persists between instances"""
        # Create and add message
        db1 = MessageDatabase(data_folder=temp_data_folder)
        msg = create_message(
            title='영속성 테스트',
            content='테스트',
            sender='발신자'
        )
        db1.add(msg)

        # Create new instance (should load from file)
        db2 = MessageDatabase(data_folder=temp_data_folder)

        assert db2.count() == 1
        assert db2.get(msg.id) is not None

    def test_export_json(self, populated_db, temp_data_folder):
        """Test JSON export"""
        export_path = os.path.join(temp_data_folder, 'export.json')

        result = populated_db.export_json(export_path)

        assert result is True
        assert os.path.exists(export_path)

        # Verify content
        with open(export_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        assert len(data) == 3

    def test_import_json(self, db, temp_data_folder):
        """Test JSON import"""
        # Create export file
        export_data = [
            {
                'id': 'import-test-1',
                'title': '가져오기 테스트 1',
                'content': '내용 1',
                'sender': '발신자',
                'sender_dept': '',
                'receivers': [],
                'received_at': '2025-01-27T09:00:00',
                'deadline': None,
                'status': 'pending',
                'starred': False,
                'category': 'action',
                'task_group': '공지',
                'importance': None,
                'process': [],
                'attachments': [],
                'md_path': None,
                'pdf_path': None,
                'metadata': {},
                'merged_count': 1,
                'merged_from': [],
                'calendar_event_id': None,
                'created_at': '2025-01-27T09:00:00',
                'updated_at': '2025-01-27T09:00:00'
            },
            {
                'id': 'import-test-2',
                'title': '가져오기 테스트 2',
                'content': '내용 2',
                'sender': '발신자',
                'sender_dept': '',
                'receivers': [],
                'received_at': '2025-01-27T09:00:00',
                'deadline': None,
                'status': 'pending',
                'starred': False,
                'category': 'action',
                'task_group': '공지',
                'importance': None,
                'process': [],
                'attachments': [],
                'md_path': None,
                'pdf_path': None,
                'metadata': {},
                'merged_count': 1,
                'merged_from': [],
                'calendar_event_id': None,
                'created_at': '2025-01-27T09:00:00',
                'updated_at': '2025-01-27T09:00:00'
            }
        ]

        import_path = os.path.join(temp_data_folder, 'import.json')
        with open(import_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f)

        # Import
        count = db.import_json(import_path)

        assert count == 2
        assert db.count() == 2
        assert db.get('import-test-1') is not None


# ============================================================
# StatusManager Tests
# ============================================================

class TestStatusManager:
    """Test StatusManager operations"""

    def test_status_manager_basic(self, temp_data_folder):
        """Test basic status manager operations"""
        manager = StatusManager(data_folder=temp_data_folder)

        # Get default status
        status = manager.get_status('test-id')
        assert status['status'] == 'pending'
        assert status['starred'] is False

    def test_status_manager_set_status(self, temp_data_folder):
        """Test setting status"""
        manager = StatusManager(data_folder=temp_data_folder)

        manager.set_status('test-id', 'completed')
        status = manager.get_status('test-id')

        assert status['status'] == 'completed'
        assert 'completed_at' in status

    def test_status_manager_set_starred(self, temp_data_folder):
        """Test setting starred"""
        manager = StatusManager(data_folder=temp_data_folder)

        manager.set_starred('test-id', True)
        status = manager.get_status('test-id')

        assert status['starred'] is True

    def test_status_manager_persists(self, temp_data_folder):
        """Test status persists between instances"""
        manager1 = StatusManager(data_folder=temp_data_folder)
        manager1.set_status('test-id', 'completed')
        manager1.set_starred('test-id', True)

        manager2 = StatusManager(data_folder=temp_data_folder)
        status = manager2.get_status('test-id')

        assert status['status'] == 'completed'
        assert status['starred'] is True


# ============================================================
# Edge Cases
# ============================================================

class TestMessageDatabaseEdgeCases:
    """Test edge cases and error handling"""

    def test_empty_database(self, db):
        """Test operations on empty database"""
        assert db.count() == 0
        assert db.get_all() == []
        assert db.get_urgent() == []

        stats = db.get_stats()
        assert stats.total == 0
        assert stats.completion_rate == 0.0

    def test_korean_content(self, db):
        """Test handling Korean content"""
        msg = create_message(
            title='한글 제목 테스트: 생활기록부',
            content='한글 본문: 나이스에 생기부를 입력해 주세요.',
            sender='교무기획부 김철수'
        )
        db.add(msg)

        retrieved = db.get(msg.id)

        assert retrieved.title == '한글 제목 테스트: 생활기록부'
        assert '나이스' in retrieved.content

    def test_special_characters_in_content(self, db):
        """Test handling special characters"""
        msg = create_message(
            title='특수문자: [긴급] 마감 ~12/31',
            content='URL: https://example.com?param=value&test=1',
            sender='발신자 <test@email.com>'
        )
        db.add(msg)

        retrieved = db.get(msg.id)

        assert retrieved.title == '특수문자: [긴급] 마감 ~12/31'

    def test_long_content(self, db):
        """Test handling long content"""
        long_content = '가' * 10000  # 10,000 characters

        msg = create_message(
            title='긴 내용 테스트',
            content=long_content,
            sender='발신자'
        )
        db.add(msg)

        retrieved = db.get(msg.id)

        assert len(retrieved.content) == 10000
