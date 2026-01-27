"""
Test models module
- Message model
- Attachment model
- DashboardStats
- MessageFilter
"""

import pytest
from datetime import datetime, timedelta
import uuid

# Import models
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models import (
    Message, Attachment, ImportanceScore, ActionProcess,
    MessageStatus, ImportanceGrade, MessageCategory, TaskGroup,
    MessageFilter, DashboardStats,
    create_message, create_attachment,
    GRADE_COLORS, GROUP_ICONS
)


# ============================================================
# Sample Test Data
# ============================================================

SAMPLE_MESSAGE = {
    'title': '2학기 생활기록부 최종 마감 안내',
    'sender': '교무기획부 김철수 부장',
    'content': '담임선생님께서는 1월 29일까지 나이스에 생기부를 제출해 주세요.',
    'date': '2025-01-27',
    'deadline': '2025-01-29'
}

SAMPLE_MESSAGE_NO_DEADLINE = {
    'title': '2월 교직원 회의 안내',
    'sender': '교무기획부',
    'content': '2월 5일 15시에 교직원 회의가 있습니다.',
    'date': '2025-01-27',
    'deadline': None
}


# ============================================================
# Message Model Tests
# ============================================================

class TestMessage:
    """Message model tests"""

    def test_create_message_basic(self):
        """Test basic message creation with create_message helper"""
        msg = create_message(
            title=SAMPLE_MESSAGE['title'],
            content=SAMPLE_MESSAGE['content'],
            sender=SAMPLE_MESSAGE['sender']
        )

        assert msg.title == SAMPLE_MESSAGE['title']
        assert msg.content == SAMPLE_MESSAGE['content']
        assert msg.sender == SAMPLE_MESSAGE['sender']
        assert msg.id is not None
        assert len(msg.id) == 36  # UUID format
        assert msg.status == MessageStatus.PENDING.value
        assert msg.starred is False

    def test_create_message_with_deadline(self):
        """Test message creation with deadline"""
        msg = create_message(
            title=SAMPLE_MESSAGE['title'],
            content=SAMPLE_MESSAGE['content'],
            sender=SAMPLE_MESSAGE['sender'],
            deadline=SAMPLE_MESSAGE['deadline']
        )

        assert msg.deadline == '2025-01-29'

    def test_message_d_day_calculation(self):
        """Test D-day calculation"""
        # Set deadline to 2 days from now
        future_date = (datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d')

        msg = create_message(
            title='Test',
            content='Test content',
            sender='Sender',
            deadline=future_date
        )

        assert msg.d_day == 2

    def test_message_d_day_today(self):
        """Test D-day for today's deadline"""
        today = datetime.now().strftime('%Y-%m-%d')

        msg = create_message(
            title='Test',
            content='Test',
            sender='Sender',
            deadline=today
        )

        assert msg.d_day == 0

    def test_message_d_day_none(self):
        """Test D-day when no deadline"""
        msg = create_message(
            title='Test',
            content='Test',
            sender='Sender'
        )

        assert msg.d_day is None

    def test_message_is_urgent(self):
        """Test urgent detection (D-2 or less)"""
        # D-2 should be urgent
        deadline_d2 = (datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d')
        msg_urgent = create_message(
            title='Test', content='Test', sender='Sender',
            deadline=deadline_d2
        )
        assert msg_urgent.is_urgent is True

        # D-5 should not be urgent
        deadline_d5 = (datetime.now() + timedelta(days=5)).strftime('%Y-%m-%d')
        msg_not_urgent = create_message(
            title='Test', content='Test', sender='Sender',
            deadline=deadline_d5
        )
        assert msg_not_urgent.is_urgent is False

    def test_message_is_completed(self):
        """Test completion status check"""
        msg = create_message(
            title='Test', content='Test', sender='Sender'
        )

        assert msg.is_completed is False

        msg.mark_completed()
        assert msg.is_completed is True
        assert msg.status == MessageStatus.COMPLETED.value

    def test_message_toggle_star(self):
        """Test star toggle"""
        msg = create_message(
            title='Test', content='Test', sender='Sender'
        )

        assert msg.starred is False

        msg.toggle_star()
        assert msg.starred is True

        msg.toggle_star()
        assert msg.starred is False

    def test_message_color_code_urgent(self):
        """Test color code for urgent messages"""
        # Urgent (D-1)
        deadline = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        msg = create_message(
            title='Test', content='Test', sender='Sender',
            deadline=deadline
        )
        assert msg.color_code == '🔴'

    def test_message_color_code_this_week(self):
        """Test color code for this week messages"""
        # This week (D-5)
        deadline = (datetime.now() + timedelta(days=5)).strftime('%Y-%m-%d')
        msg = create_message(
            title='Test', content='Test', sender='Sender',
            deadline=deadline
        )
        assert msg.color_code == '🟡'

    def test_message_color_code_completed(self):
        """Test color code for completed messages"""
        msg = create_message(
            title='Test', content='Test', sender='Sender',
            deadline=(datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        )
        msg.mark_completed()
        assert msg.color_code == '✅'

    def test_message_to_dict(self):
        """Test message serialization to dict"""
        msg = create_message(
            title=SAMPLE_MESSAGE['title'],
            content=SAMPLE_MESSAGE['content'],
            sender=SAMPLE_MESSAGE['sender'],
            deadline=SAMPLE_MESSAGE['deadline'],
            starred=True
        )

        msg_dict = msg.to_dict()

        assert isinstance(msg_dict, dict)
        assert msg_dict['title'] == SAMPLE_MESSAGE['title']
        assert msg_dict['content'] == SAMPLE_MESSAGE['content']
        assert msg_dict['sender'] == SAMPLE_MESSAGE['sender']
        assert msg_dict['deadline'] == SAMPLE_MESSAGE['deadline']
        assert msg_dict['starred'] is True

    def test_message_from_dict(self):
        """Test message deserialization from dict"""
        msg_dict = {
            'id': str(uuid.uuid4()),
            'title': SAMPLE_MESSAGE['title'],
            'content': SAMPLE_MESSAGE['content'],
            'sender': SAMPLE_MESSAGE['sender'],
            'sender_dept': '교무기획부',
            'receivers': ['전체 교원'],
            'received_at': '2025-01-27T09:00:00',
            'deadline': SAMPLE_MESSAGE['deadline'],
            'status': 'pending',
            'starred': True,
            'category': 'action',
            'task_group': '담임',
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

        msg = Message.from_dict(msg_dict)

        assert msg.title == SAMPLE_MESSAGE['title']
        assert msg.starred is True
        assert msg.task_group == '담임'

    def test_message_grade_property(self):
        """Test grade property"""
        msg = create_message(
            title='Test', content='Test', sender='Sender'
        )

        # No importance set
        assert msg.grade == 'D'

        # Set importance
        msg.importance = {'grade': 'S', 'score': 55}
        assert msg.grade == 'S'


# ============================================================
# Attachment Model Tests
# ============================================================

class TestAttachment:
    """Attachment model tests"""

    def test_create_attachment_basic(self):
        """Test basic attachment creation"""
        att = create_attachment(
            filename='생기부_점검표_20250127.hwp',
            original_name='생기부_점검표.hwp'
        )

        assert att.filename == '생기부_점검표_20250127.hwp'
        assert att.original_name == '생기부_점검표.hwp'
        assert att.downloaded is False

    def test_create_attachment_with_size(self):
        """Test attachment with size"""
        att = create_attachment(
            filename='매뉴얼.pdf',
            original_name='매뉴얼.pdf',
            size=1024 * 52  # 52KB
        )

        assert att.size == 53248

    def test_attachment_to_dict(self):
        """Test attachment serialization"""
        att = Attachment(
            filename='test.hwp',
            original_name='원본.hwp',
            size=1024,
            downloaded=True,
            download_path='/path/to/file.hwp'
        )

        att_dict = att.to_dict()

        assert att_dict['filename'] == 'test.hwp'
        assert att_dict['downloaded'] is True
        assert att_dict['download_path'] == '/path/to/file.hwp'

    def test_attachment_from_dict(self):
        """Test attachment deserialization"""
        att_dict = {
            'filename': 'test.hwp',
            'original_name': '원본.hwp',
            'size': 2048,
            'downloaded': True,
            'download_path': '/downloads/test.hwp'
        }

        att = Attachment.from_dict(att_dict)

        assert att.filename == 'test.hwp'
        assert att.size == 2048


# ============================================================
# ImportanceScore Tests
# ============================================================

class TestImportanceScore:
    """ImportanceScore model tests"""

    def test_importance_score_basic(self):
        """Test ImportanceScore creation"""
        score = ImportanceScore(
            grade='S',
            score=55,
            main_category='action',
            color_code='🔴',
            auto_starred=True
        )

        assert score.grade == 'S'
        assert score.score == 55
        assert score.max_score == 60
        assert score.auto_starred is True

    def test_importance_score_to_dict(self):
        """Test ImportanceScore serialization"""
        score = ImportanceScore(
            grade='A',
            score=45,
            breakdown={'task_type': {'score': 35, 'reason': '담임'}}
        )

        score_dict = score.to_dict()

        assert score_dict['grade'] == 'A'
        assert 'breakdown' in score_dict


# ============================================================
# ActionProcess Tests
# ============================================================

class TestActionProcess:
    """ActionProcess model tests"""

    def test_action_process_basic(self):
        """Test ActionProcess creation"""
        process = ActionProcess(
            step=1,
            action='미입력 항목 확인',
            detail='나이스에서 생기부 미입력 학생 목록 확인'
        )

        assert process.step == 1
        assert process.action == '미입력 항목 확인'
        assert process.completed is False

    def test_action_process_to_dict(self):
        """Test ActionProcess serialization"""
        process = ActionProcess(
            step=2,
            action='입력',
            detail='세특 입력',
            completed=True
        )

        process_dict = process.to_dict()

        assert process_dict['step'] == 2
        assert process_dict['completed'] is True


# ============================================================
# MessageFilter Tests
# ============================================================

class TestMessageFilter:
    """MessageFilter model tests"""

    def test_filter_basic(self):
        """Test basic filter creation"""
        f = MessageFilter(query='생기부')

        assert f.query == '생기부'
        assert f.starred_only is False

    def test_filter_multiple_conditions(self):
        """Test filter with multiple conditions"""
        f = MessageFilter(
            query='마감',
            sender='교무기획부',
            status='pending',
            starred_only=True
        )

        assert f.query == '마감'
        assert f.sender == '교무기획부'
        assert f.status == 'pending'
        assert f.starred_only is True

    def test_filter_to_dict(self):
        """Test filter to_dict removes None values"""
        f = MessageFilter(
            query='테스트',
            sender=None,
            starred_only=False
        )

        f_dict = f.to_dict()

        assert 'query' in f_dict
        assert 'sender' not in f_dict  # None values excluded
        assert 'starred_only' not in f_dict  # False is falsy but included


# ============================================================
# DashboardStats Tests
# ============================================================

class TestDashboardStats:
    """DashboardStats model tests"""

    def test_stats_basic(self):
        """Test basic stats creation"""
        stats = DashboardStats(
            total=10,
            pending=5,
            completed=5
        )

        assert stats.total == 10
        assert stats.pending == 5

    def test_stats_completion_rate(self):
        """Test completion rate calculation"""
        stats = DashboardStats(
            total=10,
            completed=8
        )

        assert stats.completion_rate == 80.0

    def test_stats_completion_rate_zero_total(self):
        """Test completion rate with zero total"""
        stats = DashboardStats(total=0, completed=0)

        assert stats.completion_rate == 0.0

    def test_stats_to_dict(self):
        """Test stats serialization includes completion_rate"""
        stats = DashboardStats(
            total=20,
            pending=10,
            completed=8,
            urgent=2
        )

        stats_dict = stats.to_dict()

        assert 'completion_rate' in stats_dict
        assert stats_dict['completion_rate'] == 40.0


# ============================================================
# Enum Tests
# ============================================================

class TestEnums:
    """Enum value tests"""

    def test_message_status_values(self):
        """Test MessageStatus enum values"""
        assert MessageStatus.PENDING.value == 'pending'
        assert MessageStatus.COMPLETED.value == 'completed'
        assert MessageStatus.IN_PROGRESS.value == 'in_progress'
        assert MessageStatus.ARCHIVED.value == 'archived'

    def test_importance_grade_values(self):
        """Test ImportanceGrade enum values"""
        assert ImportanceGrade.S.value == 'S'
        assert ImportanceGrade.A.value == 'A'
        assert ImportanceGrade.B.value == 'B'
        assert ImportanceGrade.C.value == 'C'
        assert ImportanceGrade.D.value == 'D'

    def test_message_category_values(self):
        """Test MessageCategory enum values"""
        assert MessageCategory.ACTION.value == 'action'
        assert MessageCategory.INFORMATION.value == 'information'

    def test_task_group_values(self):
        """Test TaskGroup enum values"""
        assert TaskGroup.HOMEROOM.value == '담임'
        assert TaskGroup.SUBMIT.value == '제출'
        assert TaskGroup.MEETING.value == '회의'

    def test_grade_colors_mapping(self):
        """Test grade color mapping"""
        assert GRADE_COLORS[ImportanceGrade.S] == '🔴'
        assert GRADE_COLORS[ImportanceGrade.A] == '🟠'
        assert GRADE_COLORS[ImportanceGrade.D] == '⚪'

    def test_group_icons_mapping(self):
        """Test group icon mapping"""
        assert GROUP_ICONS[TaskGroup.HOMEROOM] == '🎓'
        assert GROUP_ICONS[TaskGroup.SUBMIT] == '📋'


# ============================================================
# Integration Tests
# ============================================================

class TestMessageIntegration:
    """Integration tests for Message model"""

    def test_full_message_workflow(self):
        """Test complete message lifecycle"""
        # Create
        msg = create_message(
            title='테스트 업무',
            content='테스트 내용입니다.',
            sender='테스트 발신자',
            deadline=(datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d')
        )

        # Check initial state
        assert msg.status == 'pending'
        assert msg.starred is False
        assert msg.is_completed is False

        # Star message
        msg.toggle_star()
        assert msg.starred is True

        # Complete message
        msg.mark_completed()
        assert msg.is_completed is True
        assert msg.color_code == '✅'

        # Serialize and deserialize
        msg_dict = msg.to_dict()
        restored = Message.from_dict(msg_dict)

        assert restored.title == msg.title
        assert restored.starred == msg.starred
        assert restored.is_completed == msg.is_completed
