"""
유틸리티 모듈
- SQLite 데이터베이스 관리
- 쪽지 CRUD 작업
- 검색 및 필터링
"""

import sqlite3
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

from config import get_db_path


# ============================================================
# 데이터베이스 스키마
# ============================================================

SCHEMA = """
-- 쪽지 테이블
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    sender TEXT NOT NULL,
    date TEXT NOT NULL,
    deadline TEXT,
    event_date TEXT,
    event_time TEXT,
    location TEXT,
    category TEXT DEFAULT '공지',
    main_type TEXT DEFAULT 'action',
    importance_grade TEXT DEFAULT 'C',
    importance_score INTEGER DEFAULT 0,
    starred INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending',
    summary TEXT,
    content TEXT,
    process TEXT,
    remember TEXT,
    attachments TEXT,
    calendar_registered INTEGER DEFAULT 0,
    merged_count INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- 상태 테이블 (완료/중요 등)
CREATE TABLE IF NOT EXISTS message_status (
    message_id INTEGER PRIMARY KEY,
    starred INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending',
    completed_at TEXT,
    FOREIGN KEY (message_id) REFERENCES messages(id)
);

-- 캘린더 이벤트 테이블
CREATE TABLE IF NOT EXISTS calendar_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER,
    event_id TEXT,
    event_date TEXT,
    event_time TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (message_id) REFERENCES messages(id)
);

-- 검색 인덱스
CREATE INDEX IF NOT EXISTS idx_messages_date ON messages(date);
CREATE INDEX IF NOT EXISTS idx_messages_deadline ON messages(deadline);
CREATE INDEX IF NOT EXISTS idx_messages_status ON messages(status);
CREATE INDEX IF NOT EXISTS idx_messages_category ON messages(category);
CREATE INDEX IF NOT EXISTS idx_messages_starred ON messages(starred);
"""


# ============================================================
# 데이터베이스 연결 관리
# ============================================================

class DatabaseManager:
    """SQLite 데이터베이스 관리자"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.db_path = get_db_path()
        self._connection = None
        self._initialized = True
        self._init_database()

    def _init_database(self) -> None:
        """데이터베이스 초기화"""
        try:
            conn = self.get_connection()
            conn.executescript(SCHEMA)
            conn.commit()
        except Exception as e:
            print(f"DB 초기화 오류: {e}")

    def get_connection(self) -> sqlite3.Connection:
        """데이터베이스 연결 반환"""
        if self._connection is None:
            self._connection = sqlite3.connect(
                self.db_path,
                check_same_thread=False
            )
            self._connection.row_factory = sqlite3.Row
        return self._connection

    def close(self) -> None:
        """연결 종료"""
        if self._connection:
            self._connection.close()
            self._connection = None


# ============================================================
# 쪽지 저장소
# ============================================================

class MessageRepository:
    """쪽지 데이터 저장소

    사용법:
        repo = MessageRepository()

        # 쪽지 추가
        msg_id = repo.add({
            'title': '생기부 마감',
            'sender': '교무부',
            'date': '2025-01-27',
            'deadline': '2025-01-29'
        })

        # 조회
        messages = repo.get_all()
        message = repo.get_by_id(1)

        # 검색
        results = repo.search('생기부')

        # 업데이트
        repo.update(1, {'status': 'completed'})

        # 삭제
        repo.delete(1)
    """

    def __init__(self):
        self.db = DatabaseManager()

    def add(self, message: Dict[str, Any]) -> int:
        """쪽지 추가

        Returns:
            생성된 쪽지 ID
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()

        # JSON 필드 처리
        process = json.dumps(message.get('process', []), ensure_ascii=False)
        remember = json.dumps(message.get('remember', []), ensure_ascii=False)
        attachments = json.dumps(message.get('attachments', []), ensure_ascii=False)

        # 중요도 정보
        importance = message.get('importance', {})

        cursor.execute("""
            INSERT INTO messages (
                title, sender, date, deadline, event_date, event_time,
                location, category, main_type, importance_grade, importance_score,
                starred, status, summary, content, process, remember,
                attachments, calendar_registered, merged_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            message.get('title', ''),
            message.get('sender', ''),
            message.get('date', datetime.now().strftime('%Y-%m-%d')),
            message.get('deadline'),
            message.get('event_date'),
            message.get('event_time'),
            message.get('location'),
            message.get('category', '공지'),
            message.get('main_type', 'action'),
            importance.get('grade', 'C'),
            importance.get('score', 0),
            1 if message.get('starred', False) else 0,
            message.get('status', 'pending'),
            message.get('summary', ''),
            message.get('content', ''),
            process,
            remember,
            attachments,
            1 if message.get('calendar_registered', False) else 0,
            message.get('merged_count', 1)
        ))

        conn.commit()
        return cursor.lastrowid

    def get_by_id(self, message_id: int) -> Optional[Dict[str, Any]]:
        """ID로 쪽지 조회"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM messages WHERE id = ?", (message_id,))
        row = cursor.fetchone()

        if row:
            return self._row_to_dict(row)
        return None

    def get_all(self, include_completed: bool = True) -> List[Dict[str, Any]]:
        """모든 쪽지 조회"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        if include_completed:
            cursor.execute("SELECT * FROM messages ORDER BY date DESC, id DESC")
        else:
            cursor.execute(
                "SELECT * FROM messages WHERE status != 'completed' ORDER BY date DESC, id DESC"
            )

        return [self._row_to_dict(row) for row in cursor.fetchall()]

    def get_pending(self) -> List[Dict[str, Any]]:
        """미완료 쪽지만 조회"""
        return self.get_all(include_completed=False)

    def get_starred(self) -> List[Dict[str, Any]]:
        """중요 표시된 쪽지 조회"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM messages WHERE starred = 1 ORDER BY date DESC")
        return [self._row_to_dict(row) for row in cursor.fetchall()]

    def get_by_category(self, category: str) -> List[Dict[str, Any]]:
        """카테고리별 쪽지 조회"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM messages WHERE category = ? ORDER BY date DESC",
            (category,)
        )
        return [self._row_to_dict(row) for row in cursor.fetchall()]

    def get_by_main_type(self, main_type: str) -> List[Dict[str, Any]]:
        """대분류별 쪽지 조회 (action/information)"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM messages WHERE main_type = ? ORDER BY date DESC",
            (main_type,)
        )
        return [self._row_to_dict(row) for row in cursor.fetchall()]

    def get_urgent(self, d_day_threshold: int = 2) -> List[Dict[str, Any]]:
        """긴급 쪽지 조회 (D-day 기준)"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        today = datetime.now().strftime('%Y-%m-%d')
        threshold_date = (datetime.now() + timedelta(days=d_day_threshold)).strftime('%Y-%m-%d')

        cursor.execute("""
            SELECT * FROM messages
            WHERE status != 'completed'
              AND deadline IS NOT NULL
              AND deadline <= ?
            ORDER BY deadline ASC
        """, (threshold_date,))

        return [self._row_to_dict(row) for row in cursor.fetchall()]

    def search(self, query: str, filters: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """쪽지 검색

        Args:
            query: 검색어 (제목, 발신자, 내용에서 검색)
            filters: {
                'date_from': 'YYYY-MM-DD',
                'date_to': 'YYYY-MM-DD',
                'sender': str,
                'category': str,
                'status': str
            }
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()

        sql = """
            SELECT * FROM messages
            WHERE (title LIKE ? OR sender LIKE ? OR content LIKE ? OR summary LIKE ?)
        """
        params = [f'%{query}%'] * 4

        filters = filters or {}

        if filters.get('date_from'):
            sql += " AND date >= ?"
            params.append(filters['date_from'])

        if filters.get('date_to'):
            sql += " AND date <= ?"
            params.append(filters['date_to'])

        if filters.get('sender'):
            sql += " AND sender LIKE ?"
            params.append(f'%{filters["sender"]}%')

        if filters.get('category'):
            sql += " AND category = ?"
            params.append(filters['category'])

        if filters.get('status'):
            sql += " AND status = ?"
            params.append(filters['status'])

        sql += " ORDER BY date DESC, id DESC"

        cursor.execute(sql, params)
        return [self._row_to_dict(row) for row in cursor.fetchall()]

    def update(self, message_id: int, updates: Dict[str, Any]) -> bool:
        """쪽지 업데이트"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        # JSON 필드 처리
        if 'process' in updates:
            updates['process'] = json.dumps(updates['process'], ensure_ascii=False)
        if 'remember' in updates:
            updates['remember'] = json.dumps(updates['remember'], ensure_ascii=False)
        if 'attachments' in updates:
            updates['attachments'] = json.dumps(updates['attachments'], ensure_ascii=False)

        # Boolean 필드 처리
        if 'starred' in updates:
            updates['starred'] = 1 if updates['starred'] else 0
        if 'calendar_registered' in updates:
            updates['calendar_registered'] = 1 if updates['calendar_registered'] else 0

        # 중요도 필드 처리
        if 'importance' in updates:
            importance = updates.pop('importance')
            updates['importance_grade'] = importance.get('grade', 'C')
            updates['importance_score'] = importance.get('score', 0)

        # updated_at 추가
        updates['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # SQL 생성
        set_clause = ', '.join(f'{k} = ?' for k in updates.keys())
        sql = f"UPDATE messages SET {set_clause} WHERE id = ?"

        cursor.execute(sql, list(updates.values()) + [message_id])
        conn.commit()

        return cursor.rowcount > 0

    def toggle_star(self, message_id: int) -> bool:
        """중요 표시 토글"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "UPDATE messages SET starred = 1 - starred, updated_at = ? WHERE id = ?",
            (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), message_id)
        )
        conn.commit()

        return cursor.rowcount > 0

    def mark_complete(self, message_id: int) -> bool:
        """완료 처리"""
        return self.update(message_id, {'status': 'completed'})

    def mark_pending(self, message_id: int) -> bool:
        """미완료로 변경"""
        return self.update(message_id, {'status': 'pending'})

    def delete(self, message_id: int) -> bool:
        """쪽지 삭제"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM messages WHERE id = ?", (message_id,))
        conn.commit()

        return cursor.rowcount > 0

    def get_stats(self) -> Dict[str, int]:
        """통계 조회"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        today = datetime.now().strftime('%Y-%m-%d')
        d2_threshold = (datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d')

        stats = {}

        # 전체
        cursor.execute("SELECT COUNT(*) FROM messages")
        stats['total'] = cursor.fetchone()[0]

        # 미완료
        cursor.execute("SELECT COUNT(*) FROM messages WHERE status = 'pending'")
        stats['pending'] = cursor.fetchone()[0]

        # 완료
        cursor.execute("SELECT COUNT(*) FROM messages WHERE status = 'completed'")
        stats['completed'] = cursor.fetchone()[0]

        # 중요
        cursor.execute("SELECT COUNT(*) FROM messages WHERE starred = 1")
        stats['starred'] = cursor.fetchone()[0]

        # 긴급 (D-2 이내)
        cursor.execute("""
            SELECT COUNT(*) FROM messages
            WHERE status = 'pending' AND deadline IS NOT NULL AND deadline <= ?
        """, (d2_threshold,))
        stats['urgent'] = cursor.fetchone()[0]

        # 행동 필요
        cursor.execute("""
            SELECT COUNT(*) FROM messages
            WHERE main_type = 'action' AND status = 'pending'
        """)
        stats['action'] = cursor.fetchone()[0]

        # 정보/공지
        cursor.execute("""
            SELECT COUNT(*) FROM messages
            WHERE main_type = 'information' AND status = 'pending'
        """)
        stats['information'] = cursor.fetchone()[0]

        # 오늘 수신
        cursor.execute("SELECT COUNT(*) FROM messages WHERE date = ?", (today,))
        stats['today'] = cursor.fetchone()[0]

        return stats

    def get_category_stats(self) -> Dict[str, Dict]:
        """카테고리별 통계"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        d2_threshold = (datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d')

        cursor.execute("""
            SELECT
                category,
                COUNT(*) as total,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN status = 'pending' AND deadline IS NOT NULL AND deadline <= ? THEN 1 ELSE 0 END) as urgent
            FROM messages
            GROUP BY category
        """, (d2_threshold,))

        stats = {}
        for row in cursor.fetchall():
            stats[row['category']] = {
                'total': row['total'],
                'pending': row['pending'],
                'urgent': row['urgent']
            }

        return stats

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Row를 딕셔너리로 변환"""
        d = dict(row)

        # JSON 필드 파싱
        for field in ['process', 'remember', 'attachments']:
            if d.get(field):
                try:
                    d[field] = json.loads(d[field])
                except json.JSONDecodeError:
                    d[field] = []
            else:
                d[field] = []

        # Boolean 변환
        d['starred'] = bool(d.get('starred'))
        d['calendar_registered'] = bool(d.get('calendar_registered'))

        # 중요도 필드 구조화
        d['importance'] = {
            'grade': d.pop('importance_grade', 'C'),
            'score': d.pop('importance_score', 0),
            'max_score': 60
        }

        return d

    def count(self) -> int:
        """전체 쪽지 수"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM messages")
        return cursor.fetchone()[0]

    def init_sample_data(self) -> None:
        """샘플 데이터 초기화 (테스트용)"""
        if self.count() > 0:
            return

        today = datetime.now()

        sample_messages = [
            {
                'title': '2학기 생활기록부 최종 마감 안내',
                'sender': '교무기획부 김OO 부장',
                'date': today.strftime('%Y-%m-%d'),
                'deadline': (today + timedelta(days=2)).strftime('%Y-%m-%d'),
                'category': '담임',
                'main_type': 'action',
                'importance': {'grade': 'S', 'score': 55},
                'starred': True,
                'status': 'pending',
                'summary': '생기부 세특, 행발, 창체 최종 점검 및 제출',
                'process': ['미입력 확인', '나이스 입력', '부장 검토'],
                'content': '안녕하세요. 교무기획부입니다.\n2학기 생활기록부 최종 마감일이 다가왔습니다.\n담임선생님께서는 1월 29일까지 모든 항목을 입력해 주시기 바랍니다.',
                'attachments': ['생기부_점검양식.hwp']
            },
            {
                'title': '출결 마감 안내',
                'sender': '교무기획부',
                'date': (today - timedelta(days=1)).strftime('%Y-%m-%d'),
                'deadline': (today + timedelta(days=1)).strftime('%Y-%m-%d'),
                'category': '담임',
                'main_type': 'action',
                'importance': {'grade': 'S', 'score': 58},
                'starred': True,
                'status': 'pending',
                'summary': '1월 출결 처리 마감',
                'process': ['결석 확인', '나이스 처리', '담임 확인'],
                'content': '1월 출결 마감일 안내드립니다. 미처리된 출결 건이 없도록 확인 부탁드립니다.',
                'attachments': []
            },
            {
                'title': '교육과정 운영계획서 제출 안내',
                'sender': '교육과정부 박OO',
                'date': (today - timedelta(days=2)).strftime('%Y-%m-%d'),
                'deadline': (today + timedelta(days=7)).strftime('%Y-%m-%d'),
                'category': '제출',
                'main_type': 'action',
                'importance': {'grade': 'A', 'score': 43},
                'starred': False,
                'status': 'pending',
                'summary': '2025 교육과정 운영계획 제출',
                'process': ['양식 확인', '계획 작성', '결재 요청'],
                'content': '교육과정 운영계획서 제출 안내드립니다. 첨부된 양식을 참고하여 작성해 주세요.',
                'attachments': ['운영계획_양식.hwp', '작년계획_참고.pdf']
            },
            {
                'title': '2월 교직원 회의 안내',
                'sender': '교무기획부',
                'date': (today - timedelta(days=3)).strftime('%Y-%m-%d'),
                'deadline': None,
                'event_date': (today + timedelta(days=9)).strftime('%Y-%m-%d'),
                'event_time': '15:00',
                'location': '시청각실',
                'category': '회의',
                'main_type': 'information',
                'importance': {'grade': 'C', 'score': 20},
                'starred': False,
                'status': 'pending',
                'summary': '2월 5일 15:00 시청각실에서 교직원 회의',
                'remember': ['회의 자료 사전 검토', '부서별 의견 준비'],
                'process': ['일정 확인', '자료 검토', '참석'],
                'content': '2월 교직원 회의 안내드립니다. 회의 자료를 사전에 검토해 주시기 바랍니다.',
                'attachments': [],
                'calendar_registered': True
            },
            {
                'title': '예산 집행 마감 안내',
                'sender': '행정실',
                'date': (today - timedelta(days=1)).strftime('%Y-%m-%d'),
                'deadline': (today + timedelta(days=5)).strftime('%Y-%m-%d'),
                'category': '제출',
                'main_type': 'action',
                'importance': {'grade': 'B', 'score': 38},
                'starred': False,
                'status': 'completed',
                'summary': '1월 예산 집행 마감',
                'process': ['품의 확인', '에듀파인', '결재'],
                'content': '1월 예산 집행 마감 안내드립니다.',
                'attachments': []
            },
            {
                'title': '학교폭력예방교육 자료 공유',
                'sender': '생활인권부',
                'date': (today - timedelta(days=2)).strftime('%Y-%m-%d'),
                'deadline': None,
                'category': '공지',
                'main_type': 'information',
                'importance': {'grade': 'D', 'score': 10},
                'starred': False,
                'status': 'pending',
                'summary': '학교폭력예방교육 참고 자료',
                'remember': ['학급별 교육 시 활용'],
                'process': ['자료 확인', '필요시 활용'],
                'content': '학교폭력예방교육 자료 공유합니다. 학급별 교육 시 활용해 주세요.',
                'attachments': ['예방교육자료.pptx']
            }
        ]

        for msg in sample_messages:
            self.add(msg)

        print(f"샘플 데이터 {len(sample_messages)}건 추가됨")


# ============================================================
# 유틸리티 함수
# ============================================================

def get_d_day(deadline: Optional[str]) -> int:
    """D-day 계산

    Args:
        deadline: 마감일 (YYYY-MM-DD)

    Returns:
        D-day (음수면 지남, 양수면 남음)
    """
    if not deadline:
        return 999

    try:
        deadline_date = datetime.strptime(deadline, '%Y-%m-%d')
        return (deadline_date - datetime.now()).days
    except ValueError:
        return 999


def format_d_day(deadline: Optional[str]) -> str:
    """D-day 포맷팅

    Args:
        deadline: 마감일 (YYYY-MM-DD)

    Returns:
        "D-2", "D-0", "D+1" 등
    """
    d_day = get_d_day(deadline)

    if d_day == 999:
        return "-"
    elif d_day > 0:
        return f"D-{d_day}"
    elif d_day == 0:
        return "D-Day"
    else:
        return f"D+{abs(d_day)}"


def get_status_emoji(message: Dict[str, Any]) -> str:
    """상태 이모지 반환"""
    if message.get('status') == 'completed':
        return "완료"

    d_day = get_d_day(message.get('deadline'))

    if d_day <= 0:
        return "지남"
    elif d_day <= 2:
        return "긴급"
    elif d_day <= 7:
        return "주의"
    else:
        return "여유"


def get_status_color(message: Dict[str, Any]) -> str:
    """상태 색상 코드 반환"""
    if message.get('status') == 'completed':
        return "#6c757d"  # 회색

    d_day = get_d_day(message.get('deadline'))

    if d_day <= 0:
        return "#dc3545"  # 빨강
    elif d_day <= 2:
        return "#dc3545"  # 빨강
    elif d_day <= 7:
        return "#ffc107"  # 노랑
    else:
        return "#28a745"  # 초록


# ============================================================
# 테스트
# ============================================================

if __name__ == "__main__":
    print("=" * 50)
    print("데이터베이스 테스트")
    print("=" * 50)

    repo = MessageRepository()

    # 샘플 데이터 초기화
    repo.init_sample_data()

    # 통계
    stats = repo.get_stats()
    print(f"\n통계: {stats}")

    # 전체 조회
    messages = repo.get_all()
    print(f"\n전체 쪽지: {len(messages)}건")

    for msg in messages[:3]:
        print(f"  - {msg['title']} ({msg['status']})")

    # 검색
    results = repo.search('생기부')
    print(f"\n'생기부' 검색 결과: {len(results)}건")

    # 긴급 쪽지
    urgent = repo.get_urgent()
    print(f"\n긴급 쪽지: {len(urgent)}건")

    # 카테고리별 통계
    cat_stats = repo.get_category_stats()
    print(f"\n카테고리별 통계: {cat_stats}")
