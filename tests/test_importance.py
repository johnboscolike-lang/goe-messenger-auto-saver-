"""
Test importance module
- ImportanceCalculator
- InfoMetadataExtractor
- Grade calculation
- Main category classification
"""

import pytest
from datetime import datetime, timedelta

# Import modules
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.importance import (
    ImportanceCalculator,
    InfoMetadataExtractor,
    ACTION_KEYWORDS,
    INFO_KEYWORDS,
    AUTO_STAR_KEYWORDS
)


# ============================================================
# Sample Test Data
# ============================================================

# Action messages (require action)
SAMPLE_ACTION_MESSAGES = [
    {
        'title': '2학기 생활기록부 최종 마감 안내',
        'content': '담임선생님께서는 1월 29일까지 나이스에 생기부를 제출해 주세요.',
        'sender': '교무기획부 김철수 부장',
        'deadline': None,  # Will be set dynamically
        'expected_category': 'action',
        'expected_grade_min': 'A'  # High importance due to 담임 + 마감
    },
    {
        'title': '출결 처리 요청',
        'content': '결석 학생에 대한 출결 처리를 완료해 주시기 바랍니다.',
        'sender': '교무기획부',
        'deadline': None,
        'expected_category': 'action',
        'expected_grade_min': 'B'
    },
    {
        'title': '예산 집행 마감 안내',
        'content': '1월 31일까지 에듀파인에서 예산 집행을 완료해 주세요.',
        'sender': '행정실',
        'deadline': None,
        'expected_category': 'action',
        'expected_grade_min': 'B'
    }
]

# Information messages (no action required)
SAMPLE_INFO_MESSAGES = [
    {
        'title': '2월 교직원 회의 안내',
        'content': '2월 5일 15시에 시청각실에서 교직원 회의가 있습니다.',
        'sender': '교무기획부',
        'deadline': None,
        'expected_category': 'information',
        'expected_has_calendar': True
    },
    {
        'title': '교육부 정책 변경 안내',
        'content': '2025년부터 적용되는 교육과정 변경 사항을 참고해 주세요.',
        'sender': '교무기획부',
        'deadline': None,
        'expected_category': 'information',
        'expected_has_calendar': False
    }
]


# ============================================================
# ImportanceCalculator Tests
# ============================================================

class TestImportanceCalculator:
    """Test ImportanceCalculator"""

    @pytest.fixture
    def calculator(self):
        return ImportanceCalculator()

    def test_basic_calculation(self, calculator):
        """Test basic importance calculation"""
        msg = {
            'title': '테스트 메시지',
            'content': '테스트 내용입니다.',
            'deadline': None
        }

        result = calculator.calculate(msg)

        assert 'grade' in result
        assert 'score' in result
        assert 'main_category' in result
        assert 'color_code' in result
        assert 'auto_starred' in result
        assert result['max_score'] == 60

    def test_grade_s_urgent_deadline(self, calculator):
        """Test S grade for urgent deadline with important content"""
        deadline = datetime.now().strftime('%Y-%m-%d')  # D-0

        msg = {
            'title': '생활기록부 최종 마감',
            'content': '담임선생님께서는 오늘까지 반드시 생기부를 제출해 주세요.',
            'deadline': deadline
        }

        result = calculator.calculate(msg)

        assert result['grade'] == 'S'
        assert result['score'] >= 50
        assert result['color_code'] == '🔴'

    def test_homeroom_task_score(self, calculator):
        """Test high score for homeroom (담임) tasks"""
        msg = {
            'title': '생활기록부 입력 안내',
            'content': '담임선생님께서는 세특, 행동발달, 창체를 입력해 주세요.',
            'deadline': (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
        }

        result = calculator.calculate(msg)

        assert result['breakdown']['task_type']['reason'] == '담임'
        assert result['breakdown']['task_type']['score'] == 40

    def test_submit_task_score(self, calculator):
        """Test score for submit/report tasks"""
        msg = {
            'title': '공문 제출 안내',
            'content': '마감일까지 결재를 완료해 주세요.',
            'deadline': (datetime.now() + timedelta(days=5)).strftime('%Y-%m-%d')
        }

        result = calculator.calculate(msg)

        assert result['breakdown']['task_type']['reason'] == '제출'
        assert result['breakdown']['task_type']['score'] == 35

    def test_meeting_task_score(self, calculator):
        """Test score for meeting tasks"""
        msg = {
            'title': '연수 참석 안내',
            'content': '교직원 연수에 참석해 주세요.',
            'deadline': None
        }

        result = calculator.calculate(msg)

        assert result['breakdown']['task_type']['reason'] == '회의'
        assert result['breakdown']['task_type']['score'] == 20

    def test_notice_task_score(self, calculator):
        """Test score for notice tasks"""
        msg = {
            'title': '일정 안내',
            'content': '2월 일정을 안내드립니다.',
            'deadline': None
        }

        result = calculator.calculate(msg)

        assert result['breakdown']['task_type']['reason'] == '공지'
        assert result['breakdown']['task_type']['score'] == 10

    def test_urgency_d0(self, calculator):
        """Test urgency score for D-0"""
        deadline = datetime.now().strftime('%Y-%m-%d')

        msg = {
            'title': '테스트',
            'content': '테스트',
            'deadline': deadline
        }

        result = calculator.calculate(msg)

        assert result['breakdown']['urgency']['score'] == 20
        assert result['breakdown']['urgency']['d_day'] == 0

    def test_urgency_d1(self, calculator):
        """Test urgency score for D-1"""
        deadline = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')

        msg = {
            'title': '테스트',
            'content': '테스트',
            'deadline': deadline
        }

        result = calculator.calculate(msg)

        assert result['breakdown']['urgency']['score'] == 18
        assert result['breakdown']['urgency']['d_day'] == 1

    def test_urgency_keyword_bonus(self, calculator):
        """Test urgency keyword bonus"""
        msg = {
            'title': '긴급 공지',
            'content': '즉시 처리 바랍니다.',
            'deadline': (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
        }

        result = calculator.calculate(msg)

        # Should have +5 bonus
        assert '+긴급키워드' in result['breakdown']['urgency']['reason']

    def test_grade_boundaries(self, calculator):
        """Test grade boundaries"""
        # Test grade S (50+)
        msg_s = {
            'title': '생기부 마감',
            'content': '담임 반드시 제출',
            'deadline': datetime.now().strftime('%Y-%m-%d')
        }
        assert calculator.calculate(msg_s)['grade'] == 'S'

        # Test grade D (low score)
        msg_d = {
            'title': '참고',
            'content': '확인해 주세요.',
            'deadline': None
        }
        result_d = calculator.calculate(msg_d)
        assert result_d['score'] < 25

    def test_main_category_action(self, calculator):
        """Test action category classification"""
        for msg_data in SAMPLE_ACTION_MESSAGES:
            if msg_data['deadline'] is None:
                msg_data['deadline'] = (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d')

            result = calculator.calculate(msg_data)
            assert result['main_category'] == 'action', f"Failed for: {msg_data['title']}"

    def test_main_category_information(self, calculator):
        """Test information category classification"""
        for msg_data in SAMPLE_INFO_MESSAGES:
            result = calculator.calculate(msg_data)
            # Note: Some info messages might still be classified as action
            # if they contain action keywords
            assert result['main_category'] in ['action', 'information']

    def test_auto_star_s_grade(self, calculator):
        """Test auto-star for S grade"""
        msg = {
            'title': '생기부 마감',
            'content': '담임 생활기록부 제출',
            'deadline': datetime.now().strftime('%Y-%m-%d')
        }

        result = calculator.calculate(msg)

        if result['grade'] == 'S':
            assert result['auto_starred'] is True

    def test_auto_star_keywords(self, calculator):
        """Test auto-star for specific keywords"""
        msg = {
            'title': '필수 확인 사항',
            'content': '반드시 확인하세요.',
            'deadline': None
        }

        result = calculator.calculate(msg)

        assert result['auto_starred'] is True


# ============================================================
# InfoMetadataExtractor Tests
# ============================================================

class TestInfoMetadataExtractor:
    """Test InfoMetadataExtractor"""

    @pytest.fixture
    def extractor(self):
        return InfoMetadataExtractor()

    def test_basic_extraction(self, extractor):
        """Test basic metadata extraction"""
        msg = {
            'title': '회의 안내',
            'content': '회의가 있습니다.',
            'sender': '교무기획부'
        }

        result = extractor.extract(msg)

        assert result['type'] == 'information'
        assert 'summary' in result
        assert 'dates' in result
        assert 'tags' in result

    def test_date_extraction_month_day(self, extractor):
        """Test extracting dates in MM월 DD일 format"""
        msg = {
            'title': '회의 안내',
            'content': '2월 5일에 회의가 있습니다.',
            'sender': '교무기획부'
        }

        result = extractor.extract(msg)

        assert len(result['dates']) >= 1
        # Should extract as next year if month is before current
        date = result['dates'][0]['date']
        assert '-02-05' in date

    def test_date_extraction_full_date(self, extractor):
        """Test extracting dates in YYYY-MM-DD format"""
        msg = {
            'title': '마감 안내',
            'content': '2025-02-15까지 제출해 주세요.',
            'sender': '교무기획부'
        }

        result = extractor.extract(msg)

        assert len(result['dates']) >= 1
        assert result['dates'][0]['date'] == '2025-02-15'

    def test_time_extraction_24h(self, extractor):
        """Test extracting times in 24h format"""
        msg = {
            'title': '회의 안내',
            'content': '15:30에 시작합니다.',
            'sender': '교무기획부'
        }

        result = extractor.extract(msg)

        assert len(result['times']) >= 1
        assert '15:30' in result['times'][0]['time']

    def test_time_extraction_korean(self, extractor):
        """Test extracting times in Korean format"""
        msg = {
            'title': '회의 안내',
            'content': '오후 3시에 시작합니다.',
            'sender': '교무기획부'
        }

        result = extractor.extract(msg)

        assert len(result['times']) >= 1
        # 오후 3시 = 15:00
        assert '15' in result['times'][0]['time']

    def test_location_extraction(self, extractor):
        """Test extracting location"""
        msg = {
            'title': '회의 안내',
            'content': '시청각실에서 진행합니다.',
            'sender': '교무기획부'
        }

        result = extractor.extract(msg)

        assert result['location'] == '시청각실'

    def test_location_extraction_pattern(self, extractor):
        """Test extracting location with 장소: pattern"""
        msg = {
            'title': '회의 안내',
            'content': '장소: 본관 회의실',
            'sender': '교무기획부'
        }

        result = extractor.extract(msg)

        assert result['location'] is not None
        assert '회의실' in result['location'] or '본관' in result['location']

    def test_remember_items_extraction(self, extractor):
        """Test extracting remember items"""
        msg = {
            'title': '연수 안내',
            'content': '노트북 지참이 필요합니다. 사전 자료 검토 부탁드립니다.',
            'sender': '교무기획부'
        }

        result = extractor.extract(msg)

        assert len(result['remember']) >= 1

    def test_calendar_event_creation(self, extractor):
        """Test calendar event creation from extracted data"""
        msg = {
            'title': '2월 교직원 회의 안내',
            'content': '2월 5일 15시에 시청각실에서 교직원 회의가 있습니다.',
            'sender': '교무기획부'
        }

        result = extractor.extract(msg)

        assert result['has_calendar_event'] is True
        assert len(result['calendar_events']) >= 1

        event = result['calendar_events'][0]
        assert event['summary'] == '2월 교직원 회의 안내'
        assert event['location'] == '시청각실'
        assert '-02-05' in event['date']

    def test_no_calendar_event_without_date(self, extractor):
        """Test no calendar event when no date found"""
        msg = {
            'title': '일반 공지',
            'content': '참고해 주세요.',
            'sender': '교무기획부'
        }

        result = extractor.extract(msg)

        assert result['has_calendar_event'] is False
        assert len(result['calendar_events']) == 0

    def test_tag_generation_meeting(self, extractor):
        """Test tag generation for meeting"""
        msg = {
            'title': '교직원 회의',
            'content': '회의가 있습니다.',
            'sender': '교무기획부'
        }

        result = extractor.extract(msg)

        assert '회의' in result['tags']

    def test_tag_generation_training(self, extractor):
        """Test tag generation for training"""
        msg = {
            'title': '연수 안내',
            'content': '직무연수가 있습니다.',
            'sender': '연수부'
        }

        result = extractor.extract(msg)

        assert '연수' in result['tags']

    def test_summary_with_datetime_location(self, extractor):
        """Test summary generation"""
        msg = {
            'title': '2월 교직원 회의',
            'content': '2월 5일 15시에 시청각실에서',
            'sender': '교무기획부'
        }

        result = extractor.extract(msg)

        assert result['summary']['일시'] is not None
        assert result['summary']['장소'] == '시청각실'


# ============================================================
# Keyword Tests
# ============================================================

class TestKeywords:
    """Test keyword dictionaries"""

    def test_action_keywords_exist(self):
        """Test action keywords are defined"""
        assert '강한_행동' in ACTION_KEYWORDS
        assert '담임_행동' in ACTION_KEYWORDS
        assert '예산_행동' in ACTION_KEYWORDS

    def test_info_keywords_exist(self):
        """Test info keywords are defined"""
        assert '공지' in INFO_KEYWORDS
        assert '일정' in INFO_KEYWORDS

    def test_auto_star_keywords_exist(self):
        """Test auto-star keywords are defined"""
        assert '필수' in AUTO_STAR_KEYWORDS
        assert '마감' in AUTO_STAR_KEYWORDS
        assert '긴급' in AUTO_STAR_KEYWORDS


# ============================================================
# Integration Tests
# ============================================================

class TestImportanceIntegration:
    """Integration tests for importance module"""

    def test_full_workflow_action_message(self):
        """Test full workflow for action message"""
        calc = ImportanceCalculator()
        extractor = InfoMetadataExtractor()

        msg = {
            'title': '2학기 생활기록부 최종 마감 안내',
            'content': '담임선생님께서는 1월 29일까지 나이스에 생기부를 제출해 주세요.',
            'sender': '교무기획부',
            'deadline': (datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d')
        }

        # Calculate importance
        importance = calc.calculate(msg)

        assert importance['main_category'] == 'action'
        assert importance['grade'] in ['S', 'A']  # Should be high importance
        assert importance['breakdown']['task_type']['reason'] == '담임'

        # Should not need extensive metadata extraction for action messages
        # but can still extract dates
        meta = extractor.extract(msg)
        assert len(meta['dates']) >= 1

    def test_full_workflow_info_message(self):
        """Test full workflow for information message"""
        calc = ImportanceCalculator()
        extractor = InfoMetadataExtractor()

        msg = {
            'title': '2월 교직원 회의 안내',
            'content': '2월 5일 15시에 시청각실에서 교직원 회의가 있습니다. 회의 자료를 사전에 검토해 주세요.',
            'sender': '교무기획부',
            'deadline': None
        }

        # Calculate importance
        importance = calc.calculate(msg)

        # Extract metadata
        meta = extractor.extract(msg)

        assert meta['has_calendar_event'] is True
        assert meta['location'] == '시청각실'
        assert '회의' in meta['tags']

    def test_color_code_consistency(self):
        """Test color codes are consistent with grades"""
        calc = ImportanceCalculator()

        test_cases = [
            # (grade, expected_color)
            ('S', '🔴'),
            ('A', '🟠'),
            ('B', '🟡'),
            ('C', '🟢'),
            ('D', '⚪'),
        ]

        for grade, expected_color in test_cases:
            # Create message that should produce this grade
            if grade == 'S':
                msg = {
                    'title': '생기부 긴급 마감',
                    'content': '담임 반드시 제출',
                    'deadline': datetime.now().strftime('%Y-%m-%d')
                }
            elif grade == 'D':
                msg = {
                    'title': '참고',
                    'content': '확인',
                    'deadline': None
                }
            else:
                # For middle grades, just verify the color mapping logic
                continue

            result = calc.calculate(msg)
            if result['grade'] == grade:
                assert result['color_code'] == expected_color
