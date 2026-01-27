"""
Test saver module
- MessageSaver
- Markdown generation
- Filename sanitization
- Path generation
"""

import pytest
import os
import tempfile
import shutil
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Import modules
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.saver import (
    MessageSaver,
    save_message,
    MARKDOWN_TEMPLATE,
    INVALID_FILENAME_CHARS
)


# ============================================================
# Sample Test Data
# ============================================================

SAMPLE_MESSAGE_DATA = {
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

SAMPLE_MESSAGE_NO_ATTACHMENTS = {
    'title': '간단한 공지',
    'sender': '행정실',
    'affiliation': '행정실',
    'received_date': '2025-01-27 14:00',
    'recipients': '전체 교직원',
    'content': '간단한 공지 내용입니다.',
    'attachments': []
}


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def temp_folder():
    """Create a temporary folder for tests"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def saver(temp_folder):
    """Create a MessageSaver instance with temporary storage"""
    return MessageSaver(base_path=temp_folder)


# ============================================================
# MessageSaver Initialization Tests
# ============================================================

class TestMessageSaverInit:
    """Test MessageSaver initialization"""

    def test_init_creates_folder(self, temp_folder):
        """Test that init creates the base folder"""
        base_path = os.path.join(temp_folder, 'new_folder')
        saver = MessageSaver(base_path=base_path)

        assert os.path.exists(base_path)

    def test_init_with_existing_folder(self, temp_folder):
        """Test init with existing folder"""
        saver = MessageSaver(base_path=temp_folder)

        assert saver.base_path == Path(temp_folder)


# ============================================================
# Markdown Generation Tests
# ============================================================

class TestMarkdownGeneration:
    """Test markdown generation"""

    def test_generate_markdown_basic(self, saver):
        """Test basic markdown generation"""
        markdown = saver._generate_markdown(SAMPLE_MESSAGE_DATA)

        assert SAMPLE_MESSAGE_DATA['title'] in markdown
        assert SAMPLE_MESSAGE_DATA['sender'] in markdown
        assert SAMPLE_MESSAGE_DATA['affiliation'] in markdown
        assert '마감일: 2025년 1월 29일' in markdown

    def test_generate_markdown_with_attachments(self, saver):
        """Test markdown includes attachments"""
        markdown = saver._generate_markdown(SAMPLE_MESSAGE_DATA)

        assert '생기부_점검표.hwp' in markdown
        assert '입력_매뉴얼.pdf' in markdown
        assert '52KB' in markdown

    def test_generate_markdown_no_attachments(self, saver):
        """Test markdown without attachments"""
        markdown = saver._generate_markdown(SAMPLE_MESSAGE_NO_ATTACHMENTS)

        assert '- 없음' in markdown

    def test_generate_markdown_structure(self, saver):
        """Test markdown has correct structure"""
        markdown = saver._generate_markdown(SAMPLE_MESSAGE_DATA)

        # Check headers
        assert '# ' in markdown  # Main title
        assert '## 본문' in markdown
        assert '## 첨부파일' in markdown

        # Check table
        assert '| 항목 | 내용 |' in markdown
        assert '| 발신자 |' in markdown

    def test_generate_markdown_footer(self, saver):
        """Test markdown includes footer"""
        markdown = saver._generate_markdown(SAMPLE_MESSAGE_DATA)

        assert '*저장일시:' in markdown
        assert 'GOE 메신저 도우미로 자동 저장됨' in markdown


# ============================================================
# Save As Markdown Tests
# ============================================================

class TestSaveAsMarkdown:
    """Test save_as_markdown method"""

    def test_save_as_markdown_basic(self, saver):
        """Test basic markdown save"""
        md_path = saver.save_as_markdown(SAMPLE_MESSAGE_DATA)

        assert os.path.exists(md_path)
        assert md_path.endswith('.md')

    def test_save_as_markdown_content(self, saver):
        """Test saved markdown content"""
        md_path = saver.save_as_markdown(SAMPLE_MESSAGE_DATA)

        with open(md_path, 'r', encoding='utf-8') as f:
            content = f.read()

        assert SAMPLE_MESSAGE_DATA['title'] in content
        assert SAMPLE_MESSAGE_DATA['content'][:50] in content

    def test_save_as_markdown_with_path(self, saver, temp_folder):
        """Test markdown save with specified path"""
        custom_path = os.path.join(temp_folder, 'custom', 'test.md')

        md_path = saver.save_as_markdown(SAMPLE_MESSAGE_DATA, path=custom_path)

        assert md_path == custom_path
        assert os.path.exists(custom_path)

    def test_save_as_markdown_creates_folders(self, saver, temp_folder):
        """Test that save creates necessary folders"""
        custom_path = os.path.join(temp_folder, 'a', 'b', 'c', 'test.md')

        md_path = saver.save_as_markdown(SAMPLE_MESSAGE_DATA, path=custom_path)

        assert os.path.exists(md_path)

    def test_save_as_markdown_korean_content(self, saver):
        """Test markdown save with Korean content"""
        korean_data = {
            'title': '한글 제목 테스트: 생활기록부 마감',
            'sender': '김철수',
            'affiliation': '교무기획부',
            'received_date': '2025-01-27',
            'recipients': '전체 교원',
            'content': '한글 본문입니다. 나이스에 생기부를 입력해 주세요.',
            'attachments': []
        }

        md_path = saver.save_as_markdown(korean_data)

        with open(md_path, 'r', encoding='utf-8') as f:
            content = f.read()

        assert '한글 제목 테스트' in content
        assert '나이스' in content

    def test_save_as_markdown_invalid_data(self, saver):
        """Test markdown save with invalid data"""
        with pytest.raises(ValueError):
            saver.save_as_markdown({})

        with pytest.raises(ValueError):
            saver.save_as_markdown({'content': 'no title'})


# ============================================================
# Filename Sanitization Tests
# ============================================================

class TestFilenameSanitization:
    """Test filename sanitization"""

    def test_sanitize_basic(self, saver):
        """Test basic filename sanitization"""
        result = saver.sanitize_filename('생기부_마감_안내.md')

        assert result == '생기부_마감_안내.md'

    def test_sanitize_removes_invalid_chars(self, saver):
        """Test removal of invalid characters"""
        result = saver.sanitize_filename('생기부/마감:안내?.md')

        assert '/' not in result
        assert ':' not in result
        assert '?' not in result

    def test_sanitize_preserves_extension(self, saver):
        """Test that extension is preserved"""
        result = saver.sanitize_filename('test<file>.pdf')

        assert result.endswith('.pdf')

    def test_sanitize_max_length(self, saver):
        """Test max length truncation"""
        long_name = 'a' * 100 + '.md'

        result = saver.sanitize_filename(long_name, max_length=20)

        # Stem should be max 20 chars
        stem = Path(result).stem
        assert len(stem) <= 20

    def test_sanitize_empty_string(self, saver):
        """Test handling empty string"""
        result = saver.sanitize_filename('')

        assert result == 'untitled'

    def test_sanitize_whitespace_handling(self, saver):
        """Test whitespace handling"""
        result = saver.sanitize_filename('  multiple   spaces  ')

        assert '  ' not in result  # No double spaces

    def test_sanitize_special_chars(self, saver):
        """Test various special characters"""
        result = saver.sanitize_filename('[긴급] 마감 ~12/31')

        assert result is not None
        assert len(result) > 0


# ============================================================
# Path Generation Tests
# ============================================================

class TestPathGeneration:
    """Test path generation"""

    def test_get_save_path_basic(self, saver):
        """Test basic path generation"""
        path = saver.get_save_path(SAMPLE_MESSAGE_DATA, extension='md')

        assert path.endswith('.md')
        assert '2025' in path  # Year from received_date

    def test_get_save_path_date_folders(self, saver):
        """Test path includes date folders"""
        path = saver.get_save_path(SAMPLE_MESSAGE_DATA, extension='md')

        # Should have YYYY/MM/DD structure
        assert '/2025/' in path or '\\2025\\' in path
        assert '/01/' in path or '\\01\\' in path
        assert '/27/' in path or '\\27\\' in path

    def test_get_save_path_pdf_extension(self, saver):
        """Test PDF extension"""
        path = saver.get_save_path(SAMPLE_MESSAGE_DATA, extension='pdf')

        assert path.endswith('.pdf')

    def test_get_save_path_no_received_date(self, saver):
        """Test path generation without received_date"""
        data = SAMPLE_MESSAGE_DATA.copy()
        data['received_date'] = ''

        path = saver.get_save_path(data, extension='md')

        # Should use current date
        today = datetime.now()
        assert str(today.year) in path

    def test_unique_path_generation(self, saver, temp_folder):
        """Test unique path generation for duplicates"""
        # Create a file
        test_path = Path(temp_folder) / 'test.md'
        test_path.write_text('test')

        # Get unique path
        unique = saver._get_unique_path(test_path)

        assert unique != test_path
        assert 'test(1)' in str(unique)

    def test_unique_path_multiple_duplicates(self, saver, temp_folder):
        """Test unique path with multiple duplicates"""
        # Create multiple files
        for i in ['', '(1)', '(2)']:
            path = Path(temp_folder) / f'test{i}.md'
            path.write_text('test')

        original = Path(temp_folder) / 'test.md'
        unique = saver._get_unique_path(original)

        assert 'test(3)' in str(unique)


# ============================================================
# Save Attachments Tests
# ============================================================

class TestSaveAttachments:
    """Test attachment saving"""

    def test_save_attachments_empty_list(self, saver):
        """Test saving empty attachment list"""
        result = saver.save_attachments([])

        assert result == []

    def test_save_attachments_no_downloaded_path(self, saver):
        """Test attachments without downloaded_path"""
        attachments = [
            {'name': 'test.hwp', 'size': '1KB'}
        ]

        result = saver.save_attachments(attachments)

        assert result == []

    def test_save_attachments_with_downloaded_file(self, saver, temp_folder):
        """Test saving attachments with actual files"""
        # Create a source file
        source_file = Path(temp_folder) / 'source' / 'original.hwp'
        source_file.parent.mkdir(parents=True, exist_ok=True)
        source_file.write_text('test content')

        attachments = [
            {
                'name': 'original.hwp',
                'size': '100B',
                'downloaded_path': str(source_file)
            }
        ]

        dest_folder = os.path.join(temp_folder, 'dest')
        result = saver.save_attachments(attachments, folder=dest_folder)

        assert len(result) == 1
        assert os.path.exists(result[0])


# ============================================================
# Convenience Function Tests
# ============================================================

class TestSaveMessageFunction:
    """Test save_message convenience function"""

    def test_save_message_md_only(self, temp_folder):
        """Test save_message with markdown only"""
        result = save_message(
            SAMPLE_MESSAGE_DATA,
            formats=['md'],
            base_path=temp_folder
        )

        assert 'md' in result
        assert result['md'] is not None
        assert os.path.exists(result['md'])

    def test_save_message_default_format(self, temp_folder):
        """Test save_message with default format (md)"""
        result = save_message(
            SAMPLE_MESSAGE_DATA,
            base_path=temp_folder
        )

        assert 'md' in result

    def test_save_message_pdf_path_only(self, temp_folder):
        """Test save_message PDF returns path only (no window)"""
        result = save_message(
            SAMPLE_MESSAGE_DATA,
            formats=['pdf'],
            base_path=temp_folder
        )

        # PDF requires window, so only path is returned
        assert 'pdf_path' in result


# ============================================================
# PDF Save Tests (Mocked)
# ============================================================

class TestSaveAsPDF:
    """Test PDF saving (with mocked Windows APIs)"""

    @patch('src.saver.PYWINAUTO_AVAILABLE', False)
    def test_save_as_pdf_no_pywinauto(self, saver):
        """Test PDF save without pywinauto raises error"""
        mock_window = Mock()

        with pytest.raises(RuntimeError) as exc_info:
            saver.save_as_pdf(mock_window)

        assert 'pywinauto' in str(exc_info.value).lower()

    @patch('src.saver.PYWINAUTO_AVAILABLE', True)
    @patch('src.saver.Application')
    def test_save_as_pdf_print_button_not_found(self, mock_app, saver):
        """Test PDF save when print button not found"""
        mock_window = Mock()
        mock_window.child_window.side_effect = Exception('Not found')
        mock_window.window_text.return_value = 'Test Title'

        with pytest.raises(RuntimeError) as exc_info:
            saver.save_as_pdf(mock_window)

        assert '인쇄 버튼' in str(exc_info.value) or 'PDF' in str(exc_info.value)


# ============================================================
# Edge Cases Tests
# ============================================================

class TestSaverEdgeCases:
    """Test edge cases"""

    def test_very_long_title(self, saver):
        """Test handling very long title"""
        data = SAMPLE_MESSAGE_DATA.copy()
        data['title'] = '가' * 200

        md_path = saver.save_as_markdown(data)

        # Should truncate filename
        filename = os.path.basename(md_path)
        assert len(filename) < 200

    def test_special_characters_in_title(self, saver):
        """Test handling special characters in title"""
        data = SAMPLE_MESSAGE_DATA.copy()
        data['title'] = '[긴급] 생기부/마감: 12월?'

        md_path = saver.save_as_markdown(data)

        assert os.path.exists(md_path)

    def test_empty_content(self, saver):
        """Test handling empty content"""
        data = {
            'title': '빈 내용 테스트',
            'sender': '발신자',
            'affiliation': '',
            'received_date': '',
            'recipients': '',
            'content': '',
            'attachments': []
        }

        md_path = saver.save_as_markdown(data)

        assert os.path.exists(md_path)

    def test_unicode_characters(self, saver):
        """Test handling unicode characters"""
        data = SAMPLE_MESSAGE_DATA.copy()
        data['title'] = '테스트 📋 이모지 포함'
        data['content'] = '본문에도 이모지 🎓 포함'

        md_path = saver.save_as_markdown(data)

        with open(md_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Emojis might be stripped from filename but should be in content
        assert os.path.exists(md_path)


# ============================================================
# Integration Tests
# ============================================================

class TestSaverIntegration:
    """Integration tests"""

    def test_full_save_workflow(self, temp_folder):
        """Test complete save workflow"""
        saver = MessageSaver(base_path=temp_folder)

        # Save message
        md_path = saver.save_as_markdown(SAMPLE_MESSAGE_DATA)

        # Verify file exists
        assert os.path.exists(md_path)

        # Verify content
        with open(md_path, 'r', encoding='utf-8') as f:
            content = f.read()

        assert SAMPLE_MESSAGE_DATA['title'] in content
        assert SAMPLE_MESSAGE_DATA['sender'] in content
        assert '마감일' in content

    def test_multiple_saves_unique_paths(self, temp_folder):
        """Test multiple saves create unique paths"""
        saver = MessageSaver(base_path=temp_folder)

        paths = []
        for _ in range(3):
            path = saver.save_as_markdown(SAMPLE_MESSAGE_DATA)
            paths.append(path)

        # All paths should be unique
        assert len(set(paths)) == 3

    def test_save_and_read_korean(self, temp_folder):
        """Test save and read Korean content"""
        saver = MessageSaver(base_path=temp_folder)

        korean_data = {
            'title': '한글 테스트 제목',
            'sender': '홍길동',
            'affiliation': '교무기획부',
            'received_date': '2025-01-27 09:00',
            'recipients': '전체 교원',
            'content': '''안녕하세요.

다음 사항을 안내드립니다:
1. 생활기록부 입력
2. 출결 처리
3. 성적 확인

감사합니다.''',
            'attachments': [{'name': '첨부파일.hwp', 'size': '100KB'}]
        }

        md_path = saver.save_as_markdown(korean_data)

        with open(md_path, 'r', encoding='utf-8') as f:
            content = f.read()

        assert '홍길동' in content
        assert '생활기록부' in content
        assert '첨부파일.hwp' in content
