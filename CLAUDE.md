# CLAUDE.md - GOE Messenger Auto Saver

> 이 파일은 Claude 에이전트가 이 프로젝트를 이해하고 작업하기 위한 컨텍스트 문서입니다.

## 프로젝트 개요

**GOE Messenger Auto Saver (GMAS)**는 경기교육통합메신저의 안 읽은 쪽지를 자동으로 저장하고, **AI 기반 대시보드**를 통해 업무를 효율적으로 관리하는 Windows 자동화 프로그램입니다.

### 핵심 기능
1. 안 읽은 쪽지 자동 감지 및 저장 (MD/PDF)
2. 첨부파일 자동 다운로드
3. **⭐ 중요 쪽지 표시** (수동/자동)
4. **📊 대시보드** (현황, 긴급 대기열, 그룹 뷰)
5. **💬 AI 채팅 검색** (자연어 질의응답)
6. **📅 구글 캘린더 자동 연동**
7. **✅ 완료 처리 시스템** (대기열 자동 제거)
8. **📋 업무 그룹핑 & 중복 병합**
9. **Claude Code 연동** (CLI 자연어 명령)

### 사용자 인터페이스
```
┌─────────────────────────────────────────────────────────┐
│                    사용 방법                             │
├─────────────────────────────────────────────────────────┤
│  1. Claude Code (CLI) - 권장                            │
│     $ claude "오늘 온 쪽지 정리해줘"                     │
│     $ claude "생기부 관련 쪽지 찾아줘"                    │
│                                                         │
│  2. GUI 대시보드                                        │
│     $ python -m src.gui_dashboard                       │
│                                                         │
│  3. 웹 대시보드 (예정)                                   │
│     $ gmas serve --port 8080                            │
└─────────────────────────────────────────────────────────┘
```

---

## 기술 컨텍스트

### GOE메신저 정보
- **정식명칭**: 경기교육통합메신저 (AtMessenger7)
- **설치경로**: `C:\Program Files (x86)\AtMessenger7\`
- **데이터경로**: `C:\Users\{user}\AppData\Local\AtMessenger7`
- **기본 다운로드**: `문서\GOE메신저\Message 받은 파일`
- **첨부파일 제한**: 50MB, 서버 14일 보관

### UI 구조 (매뉴얼 기준)
```
┌─────────────────────────────────────────┐
│ 경기도교육청 메신저  [메뉴][설정][-][□][×]│
├────────┬────────────────────────────────┤
│ QUICK  │ [내목록][조직도][쪽지][대화] 🔍 │
│ MENU   ├────────────────────────────────┤
│        │ [쪽지작성] [알림][수신함][발신함] │
│        ├────────────────────────────────┤
│        │ 정렬: [읽지 않은 쪽지 우선순 ▼] │
│        ├────────────────────────────────┤
│        │ 📧 쪽지1 - 발신자1 - 날짜      │
│        │ 📧 쪽지2 - 발신자2 - 날짜      │
│        │ ...                            │
└────────┴────────────────────────────────┘
```

### 쪽지 읽기 창
```
┌─────────────────────────────────────┐
│ 쪽지 읽기                    [인쇄] │
├─────────────────────────────────────┤
│ 제목: {제목}                        │
│ 발신자: {이름} ({소속})             │
│ 첨부파일: [다운로드 ↓]              │
│   📎 파일명.hwp (100KB)             │
│ 수신자: {수신자 목록}               │
├─────────────────────────────────────┤
│ {본문 내용}                         │
│                                     │
├─────────────────────────────────────┤
│ [답장][전체회신][전달][삭제][닫기]  │
└─────────────────────────────────────┘
```

---

## 자동화 워크플로우

### 메인 시퀀스
```python
def main_workflow():
    # 1. 메신저 연결
    messenger = connect_to_goe_messenger()
    
    # 2. 쪽지함 이동
    click_menu("쪽지")
    click_button("수신함")
    
    # 3. 정렬 변경
    set_sort("읽지 않은 쪽지 우선순")
    
    # 4. 안 읽은 쪽지 처리
    while unread_exists():
        # 쪽지 열기
        double_click_first_unread()
        wait_for_window("쪽지 읽기")
        
        # 내용 추출
        content = extract_message_content()
        
        # 첨부파일 다운로드
        if has_attachments():
            click_download_button()
            wait_for_download()
        
        # 저장
        save_as_markdown(content)
        save_as_pdf()  # 인쇄 버튼 → Hancom PDF
        
        # 창 닫기
        close_message_window()
```

### 핵심 UI 조작
```python
# pywinauto + pyautogui 조합 사용

import pyautogui
from pywinauto import Application

# 1. 메신저 연결
app = Application(backend='uia').connect(title_re=".*경기도교육청 메신저.*")
main_window = app.top_window()

# 2. 메뉴 클릭 (이미지 인식 또는 좌표)
pyautogui.click(x, y)  # 쪽지 메뉴 위치

# 3. 버튼 클릭 (텍스트 기반)
main_window.child_window(title="수신함").click()

# 4. 다운로드 버튼 클릭
# 쪽지 읽기 창에서 첨부파일 영역의 다운로드 버튼 클릭
message_window.child_window(title="다운로드").click()
# 또는
pyautogui.click(download_button_position)
```

---

## MCP 에이전트 Tools

### 1. process_unread_messages
```json
{
  "name": "process_unread_messages",
  "description": "안 읽은 쪽지를 모두 처리하여 저장합니다",
  "parameters": {
    "save_markdown": {"type": "boolean", "default": true},
    "save_pdf": {"type": "boolean", "default": true},
    "download_attachments": {"type": "boolean", "default": true}
  },
  "returns": {
    "processed_count": "int",
    "saved_files": "list[str]",
    "errors": "list[str]"
  }
}
```

### 2. summarize_message
```json
{
  "name": "summarize_message",
  "description": "저장된 쪽지 내용을 요약합니다",
  "parameters": {
    "message_path": {"type": "string", "description": "쪽지 파일 경로"}
  },
  "returns": {
    "summary": "string",
    "key_points": "list[str]",
    "action_items": "list[str]"
  }
}
```

### 3. classify_message
```json
{
  "name": "classify_message",
  "description": "쪽지의 중요도와 카테고리를 분류합니다",
  "parameters": {
    "message_path": {"type": "string"}
  },
  "returns": {
    "importance": "high|medium|low",
    "urgency": "urgent|normal|low",
    "category": "업무|공지|회의|기타",
    "tags": "list[str]"
  }
}
```

### 4. search_messages
```json
{
  "name": "search_messages",
  "description": "저장된 쪽지를 검색합니다",
  "parameters": {
    "query": {"type": "string"},
    "date_from": {"type": "string", "format": "YYYY-MM-DD"},
    "date_to": {"type": "string", "format": "YYYY-MM-DD"},
    "sender": {"type": "string"}
  },
  "returns": {
    "results": "list[MessageInfo]"
  }
}
```

### 5. add_to_calendar
```json
{
  "name": "add_to_calendar",
  "description": "쪽지 기한을 구글 캘린더에 자동 등록합니다",
  "parameters": {
    "message_path": {"type": "string", "description": "쪽지 파일 경로"},
    "calendar_id": {"type": "string", "default": "primary"},
    "add_reminders": {"type": "boolean", "default": true}
  },
  "returns": {
    "event_id": "string",
    "event_link": "string",
    "reminders_set": "list[string]"
  }
}
```

### 6. calculate_importance
```json
{
  "name": "calculate_importance",
  "description": "학교업무 특수성을 반영하여 쪽지 중요도를 계산합니다",
  "parameters": {
    "message_path": {"type": "string"}
  },
  "returns": {
    "grade": "S|A|B|C|D",
    "score": "integer (0-100)",
    "breakdown": {
      "task_type": {"score": "int", "reason": "string"},
      "urgency": {"score": "int", "d_day": "int"},
      "sender": {"score": "int", "role": "string"},
      "impact": {"score": "int", "reason": "string"}
    },
    "color_code": "🔴|🟠|🟡|🟢|⚪"
  }
}
```

### 7. generate_action_process
```json
{
  "name": "generate_action_process",
  "description": "쪽지 내용을 분석하여 3단계 실행 프로세스를 생성합니다",
  "parameters": {
    "message_path": {"type": "string"}
  },
  "returns": {
    "task_type": "제출|담임|회의|협조|예산|공지",
    "process": [
      {"step": 1, "action": "string", "detail": "string"},
      {"step": 2, "action": "string", "detail": "string"},
      {"step": 3, "action": "string", "detail": "string"}
    ],
    "estimated_time": "string",
    "recommended_start": "string"
  }
}
```

### 8. generate_deadline_summary
```json
{
  "name": "generate_deadline_summary",
  "description": "기한 중심으로 쪽지들을 요약합니다",
  "parameters": {
    "date_range": {"type": "string", "default": "week"},
    "include_completed": {"type": "boolean", "default": false}
  },
  "returns": {
    "summary_date": "string",
    "urgent": "list[MessageSummary]",
    "this_week": "list[MessageSummary]",
    "upcoming": "list[MessageSummary]",
    "no_deadline": "list[MessageSummary]"
  }
}
```

---

## 프로젝트 구조

```
goe-messenger-auto-saver/
├── CLAUDE.md              # 이 파일 (에이전트 컨텍스트)
├── PRD.md                 # 제품 요구사항 문서
├── README.md              # 사용자 가이드
├── config.yaml            # 설정 파일
├── requirements.txt       # Python 의존성
│
├── src/
│   ├── __init__.py
│   ├── main.py            # CLI 엔트리포인트
│   ├── gui_dashboard.py   # 🆕 GUI 대시보드 (tkinter)
│   ├── messenger.py       # GOE메신저 UI 자동화
│   ├── extractor.py       # 쪽지 내용 추출
│   ├── saver.py           # 파일 저장 (MD/PDF)
│   ├── calendar_sync.py   # 🆕 구글 캘린더 연동
│   ├── importance.py      # 🆕 중요도 판단 시스템
│   ├── grouping.py        # 🆕 업무 그룹핑/중복 병합
│   ├── ai_chat.py         # 🆕 AI 채팅 검색
│   └── utils.py           # 유틸리티 함수
│
├── mcp/
│   ├── __init__.py
│   ├── server.py          # MCP 서버 (Claude Code 연동)
│   └── tools.py           # MCP 도구 정의
│
├── data/
│   ├── messages.json      # 저장된 쪽지 데이터
│   ├── status.json        # 완료/중요 상태
│   └── keywords.yaml      # 중요도 키워드 사전
│
├── assets/
│   └── images/            # UI 요소 이미지 (인식용)
│
└── tests/
    └── test_messenger.py
```

---

## Claude Code 연동

### MCP 서버 설정
```json
// ~/.claude/claude_desktop_config.json
{
  "mcpServers": {
    "goe-messenger": {
      "command": "python",
      "args": ["-m", "mcp.server"],
      "cwd": "C:/gmas",
      "env": {
        "GMAS_DATA_PATH": "C:/gmas/data"
      }
    }
  }
}
```

### Claude Code 사용 예시
```bash
# 기본 명령
$ claude "안 읽은 쪽지 몇 개야?"
→ check_unread_messages()

$ claude "오늘 온 쪽지 정리해줘"
→ process_unread_messages() + generate_deadline_summary()

$ claude "생기부 관련 쪽지 찾아줘"
→ search_messages(query="생기부")

$ claude "이번 주 마감 업무 알려줘"
→ generate_deadline_summary(date_range="week")

$ claude "생기부 마감 캘린더에 등록해줘"
→ add_to_calendar(message_id)

$ claude "출결 마감 완료 처리해"
→ mark_complete(message_id)
```

---

## 대시보드 시스템

### 대시보드 레이아웃
```
┌─────────────────────────────────────────────────────────────────────────┐
│  📬 GOE 업무 대시보드                    🔄 새로고침  ⚙️ 설정  💬 AI    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────────────┐  ┌──────────────────────────────────────────┐ │
│  │ 📊 오늘의 현황        │  │ 🔥 긴급 대기열 (완료 시 자동 제거)       │ │
│  │  신규: 5건           │  │  ⭐🔴 [D-0] 출결 마감        [완료]      │ │
│  │  긴급: 2건           │  │  ⭐🔴 [D-1] 생기부 제출      [완료]      │ │
│  │  완료: 12건          │  │    🔴 [D-2] 예산 품의        [완료]      │ │
│  │  ████████░░ 80%     │  └──────────────────────────────────────────┘ │
│  └──────────────────────┘                                               │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │ 📋 업무 그룹 (비슷한 업무 자동 분류, 중복 병합)                    │   │
│  │  🎓 담임업무 (3건)  │  📋 제출/보고 (2건)  │  📅 회의/연수 (1건)  │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │ 📜 쪽지 목록                          [전체][⭐중요][미완료][완료] │   │
│  │  ⭐ │ 상태 │ 제목              │ 발신자    │ 마감   │ 액션        │   │
│  │  ★  │ 🔴   │ 생기부 최종 마감   │ 교무기획부 │ D-2   │ [상세][완료] │   │
│  │  ☆  │ 🟡   │ 교육과정 계획     │ 교육과정부 │ D-7   │ [상세][완료] │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### 쪽지 상세 보기 (원본 + 요약 동시 표시)
```
┌─────────────────────────────────────────────────────────────┐
│ 📧 쪽지 상세                                                │
├─────────────────────────────────────────────────────────────┤
│  ⭐ 중요: [★ ON]    상태: 🔴 긴급    마감: D-2              │
├─────────────────────────────────────────────────────────────┤
│  📝 AI 요약                                                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ ■ 핵심: 생활기록부 최종 마감 (01/29까지)             │   │
│  │ ■ 3단계 실행:                                        │   │
│  │   1️⃣ 담당반 미입력 항목 확인                         │   │
│  │   2️⃣ 나이스 최종 입력                                │   │
│  │   3️⃣ 부장 검토 요청                                  │   │
│  │ ⏰ 예상 소요: 2시간                                   │   │
│  └─────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│  📜 원본 쪽지                              [펼치기/접기 ▼]  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 제목: 2학기 생활기록부 최종 마감 안내                 │   │
│  │ 발신: 교무기획부 김OO 부장                           │   │
│  │ 안녕하세요. 교무기획부입니다...                      │   │
│  └─────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│  [📅 캘린더 등록]  [✅ 완료 처리]  [닫기]                   │
└─────────────────────────────────────────────────────────────┘
```

---

## ⭐ 중요 쪽지 표시 시스템

### 중요 표시 방법
```python
# 1. 수동 표시
user_starred = True  # 사용자가 ☆ 클릭 → ★

# 2. 자동 표시 (S등급)
if importance_score >= 80:  # S등급
    auto_starred = True

# 3. 키워드 기반 자동 표시
auto_star_keywords = ["필수", "반드시", "마감", "긴급", "중요"]
if any(kw in message_content for kw in auto_star_keywords):
    auto_starred = True

# 4. 발신자 기반 자동 표시
auto_star_senders = ["교장", "교감"]
if any(sender in message_sender for sender in auto_star_senders):
    auto_starred = True
```

### 중요 표시 UI
```
목록 뷰:
★ 🔴 생기부 마감          D-2   ← 중요+긴급
★ 🔴 출결 마감            D-1   ← 중요+긴급
☆ 🟡 교육과정 계획        D-7   ← 일반
☆ 🟢 2월 회의 안내        -     ← 일반

필터:
[전체] [⭐ 중요만] [미완료] [완료]
```

---

## 완료 처리 시스템

### 완료 처리 흐름
```
[미완료] → [완료 버튼 클릭] → [확인 모달] → [완료 처리]
                                              │
                                              ├─ 긴급 대기열에서 제거
                                              ├─ 상태: ✅ 완료
                                              ├─ 완료 시각 기록
                                              └─ 통계 업데이트
```

### 상태 관리
```python
STATUS = {
    "pending": "⏳ 대기",      # 대기열에 표시
    "completed": "✅ 완료",     # 대기열에서 제거, 목록에서 회색
    "archived": "📦 보관"      # 숨김 처리
}
```

---

## 업무 그룹핑 & 중복 병합

### 자동 그룹핑
```python
GROUPS = {
    "담임": {"icon": "🎓", "keywords": ["생기부", "출결", "상담", "학부모"]},
    "제출": {"icon": "📋", "keywords": ["제출", "보고", "마감", "품의"]},
    "회의": {"icon": "📅", "keywords": ["회의", "연수", "참석"]},
    "예산": {"icon": "💰", "keywords": ["예산", "지출", "에듀파인"]},
    "공지": {"icon": "📢", "keywords": ["안내", "공지", "알림"]},
}
```

### 중복 병합
```python
def is_duplicate(msg1, msg2):
    """중복 판단"""
    # 1. 제목 유사도 > 80%
    # 2. 발신자 동일
    # 3. 수신 간격 < 24시간
    return similarity(msg1.title, msg2.title) > 0.8 \
           and msg1.sender == msg2.sender \
           and abs(msg1.date - msg2.date) < timedelta(hours=24)

# 병합 시 표시
"""
📋 교육과정 운영계획 제출 (2건 병합)
   ├ 원본: 교육과정 운영계획 안내 (01/25)
   └ 수정: 교육과정 계획 양식 변경 (01/26)
   📌 최종: 새 양식으로 02/03까지 제출
"""
```

---

## AI 채팅 검색

### 채팅 인터페이스
```
┌─────────────────────────────────────────────────────────────┐
│ 💬 AI 어시스턴트                                            │
├─────────────────────────────────────────────────────────────┤
│  👤 "생기부 관련 쪽지 찾아줘"                               │
│                                                             │
│  🤖 생기부 관련 쪽지 2건을 찾았습니다:                      │
│                                                             │
│     1. 생활기록부 최종 마감 안내 (01/27) 🔴                 │
│        └ 핵심: 세특, 행발, 창체 최종 점검                   │
│        └ 실행: 미입력확인 → 나이스입력 → 부장검토           │
│                                                             │
│  💡 추천 질문:                                              │
│     • "생기부 마감까지 해야 할 일 알려줘"                   │
│     • "생기부 관련 첨부파일 찾아줘"                         │
├─────────────────────────────────────────────────────────────┤
│  [입력창                                        ] [전송]    │
└─────────────────────────────────────────────────────────────┘
```

### 지원 질의 유형
| 유형 | 예시 | 응답 |
|------|------|------|
| 검색 | "예산 관련 쪽지 찾아줘" | 키워드 매칭 결과 |
| 질의 | "교육과정 계획 언제까지야?" | 마감일 정보 |
| 요약 | "오늘 쪽지 요약해줘" | 기한 중심 요약 |
| 가이드 | "생기부 제출 어떻게 해?" | 3단계 프로세스 |
| 우선순위 | "지금 뭐부터 해야 해?" | 긴급도 순 목록 |

---

## 핵심 코드 스니펫

### 메신저 연결
```python
from pywinauto import Application
from pywinauto.findwindows import ElementNotFoundError

def connect_messenger():
    try:
        app = Application(backend='uia').connect(
            title_re=".*경기도교육청 메신저.*",
            timeout=10
        )
        return app.top_window()
    except ElementNotFoundError:
        raise Exception("GOE메신저가 실행되지 않았습니다")
```

### 다운로드 버튼 클릭
```python
import pyautogui
import time

def download_attachment(message_window):
    """첨부파일 다운로드 버튼 클릭"""
    # 방법 1: 이미지 인식
    download_btn = pyautogui.locateOnScreen('assets/images/btn_download.png')
    if download_btn:
        pyautogui.click(pyautogui.center(download_btn))
        time.sleep(1)  # 다운로드 대기
        return True
    
    # 방법 2: 윈도우 컨트롤 접근
    try:
        message_window.child_window(title="다운로드", control_type="Button").click()
        time.sleep(1)
        return True
    except:
        return False
```

### PDF 저장 (인쇄)
```python
def save_as_pdf(message_window, output_path):
    """인쇄 버튼으로 PDF 저장"""
    # 인쇄 버튼 클릭
    message_window.child_window(title="인쇄", control_type="Button").click()
    time.sleep(0.5)
    
    # 인쇄 대화상자에서 Hancom PDF 선택
    print_dialog = Application(backend='uia').connect(title="인쇄")
    printer_combo = print_dialog.top_window().child_window(control_type="ComboBox")
    printer_combo.select("Hancom PDF")
    
    # 확인 클릭
    print_dialog.top_window().child_window(title="확인").click()
    
    # 저장 대화상자에서 파일명 입력
    time.sleep(1)
    save_dialog = Application(backend='uia').connect(title_re=".*저장.*")
    save_dialog.top_window().child_window(control_type="Edit").set_text(output_path)
    save_dialog.top_window().child_window(title="저장").click()
```

---

## 설정 (config.yaml)

```yaml
general:
  save_path: "D:/GOE_Archive"
  
automation:
  check_interval_minutes: 30
  click_delay_ms: 200
  
save_options:
  markdown: true
  pdf: true
  attachments: true
  
agent:
  enabled: true
  auto_summarize: true
  auto_classify: true
```

---

## 쪽지 대분류 시스템

### 📋 행동 vs 📢 정보
```
┌────────────────────────────┬────────────────────────────┐
│   📋 행동 필요 (Action)     │   📢 정보 제공 (Info)       │
│   "뭔가 해야 함"            │   "알아두면 됨"             │
├────────────────────────────┼────────────────────────────┤
│ • 제출/보고 마감            │ • 안내/공지                │
│ • 담임 업무 (생기부 등)     │ • 회의/행사 일정 안내       │
│ • 협조 요청                 │ • 정책/제도 변경 안내       │
│ • 예산 집행                 │ • 참고 자료 공유            │
├────────────────────────────┼────────────────────────────┤
│ → 긴급 대기열에 표시        │ → 정보 탭에 표시            │
│ → 마감일 캘린더 등록        │ → 일시 정보 캘린더 등록     │
│ → 완료 처리 필요            │ → 메타데이터 요약 저장      │
└────────────────────────────┴────────────────────────────┘
```

### 대분류 판단 코드
```python
ACTION_KEYWORDS = {
    '강한_행동': ['제출', '보고', '마감', '처리', '필수', '결재'],
    '담임_행동': ['생기부', '출결', '상담', '학부모', '성적'],
}

INFO_KEYWORDS = {
    '공지': ['안내', '공지', '알림', '참고', '공유'],
    '일정': ['예정', '계획', '일정', '개최'],
}

def determine_category(text):
    action_score = count_keywords(text, ACTION_KEYWORDS)
    info_score = count_keywords(text, INFO_KEYWORDS)
    return 'action' if action_score >= info_score else 'information'
```

---

## 중요도 판단 시스템 (80점 만점)

### 점수 체계 (발신자 점수 제외)
```
총점 = A(업무유형, 40점) + B(시급성, 25점) + C(영향범위, 15점)

A. 업무 유형 (40점)
├ 담임 업무: 40점 (생기부, 출결, 상담)
├ 제출/보고: 35점 (마감, 공문, 결재)
├ 협조 요청: 30점 (협조, 요청)
├ 예산/행정: 25점 (예산, 품의)
├ 회의/연수: 15점 (회의, 연수)
└ 공지/안내: 10점 (안내, 공지)

B. 시급성 (25점)
├ D-0: 25점
├ D-1: 20점
├ D-2~3: 15점
├ D-4~7: 8점
└ D-8+: 3점

C. 영향 범위 (15점)
├ 시스템 연계: 15점 (나이스, 에듀파인)
├ 학생 영향: 12점
├ 대외 업무: 10점
└ 일반: 5점

등급 (80점 만점):
├ S등급: 65점+ 🔴
├ A등급: 50-64 🟠
├ B등급: 35-49 🟡
├ C등급: 20-34 🟢
└ D등급: 0-19 ⚪
```

---

## 정보 쪽지 메타데이터 시스템

### 메타데이터 추출 흐름
```
[정보 쪽지 수신]
       │
       ▼
[AI 분석]
   ├── 핵심 내용 요약
   ├── 일시 추출 (날짜, 시간)
   ├── 장소 추출
   └── 기억할 사항 추출
       │
       ▼
[일시 정보 있음?]
   │
   ├─ Yes → [구글 캘린더 자동 등록]
   │         └ "2월 5일 15:00 교직원 회의"
   │
   └─ No → [메타데이터만 저장]
```

### 메타데이터 구조
```python
info_metadata = {
    'type': 'information',
    'title': '2월 교직원 회의 안내',
    'summary': {
        '핵심': '2025-02-05 15:00 시청각실 예정',
        '장소': '시청각실',
        '일시': '2025-02-05 15:00'
    },
    'remember': [
        '회의 자료 사전 검토 필요',
        '부서별 의견 준비'
    ],
    'tags': ['회의', '교직원'],
    'calendar_events': [{
        'summary': '2월 교직원 회의 안내',
        'date': '2025-02-05',
        'time': '15:00',
        'location': '시청각실',
        'reminders': [{'method': 'popup', 'minutes': 1440}]
    }],
    'has_calendar_event': True
}
```

### 일시 추출 패턴
```python
date_patterns = [
    r'(\d{1,2})월\s*(\d{1,2})일',      # 2월 5일
    r'(\d{4})[-./](\d{1,2})[-./](\d{1,2})',  # 2025-02-05
]

time_patterns = [
    r'(\d{1,2})[:\s시]\s*(\d{2})?분?',  # 15:00, 15시
    r'(오전|오후)\s*(\d{1,2})시',        # 오후 3시
]

location_patterns = [
    r'장소[:\s]*([^\n,]+)',
    r'(\w+(?:실|관|홀|센터))',
]
```

### MCP Tool: extract_info_metadata
```json
{
  "name": "extract_info_metadata",
  "description": "정보 쪽지에서 메타데이터 추출 및 캘린더 등록",
  "parameters": {
    "message_path": {"type": "string"}
  },
  "returns": {
    "type": "information",
    "summary": {...},
    "dates": [...],
    "location": "string",
    "remember": [...],
    "calendar_events": [...],
    "has_calendar_event": "boolean"
  }
}
```

---

## 에이전트 사용 예시 (업데이트)

### API 설정
```python
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/calendar']

def get_calendar_service():
    creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    return build('calendar', 'v3', credentials=creds)
```

### 이벤트 생성 코드
```python
def add_message_to_calendar(message: dict, calendar_id: str = 'primary'):
    """쪽지를 캘린더 이벤트로 등록"""
    service = get_calendar_service()
    
    # 중요도에 따른 색상
    importance = calculate_importance(message)
    color_map = {'S': '11', 'A': '6', 'B': '5', 'C': '10', 'D': '8'}
    
    # 3단계 프로세스 생성
    process = generate_action_process(message)
    process_text = "\n".join([
        f"{i+1}️⃣ {step['action']} - {step['detail']}"
        for i, step in enumerate(process['process'])
    ])
    
    event = {
        'summary': f"[{message['type']}] {message['title']}",
        'description': f"""
📬 GOE메신저 쪽지 자동 등록

■ 발신: {message['sender']}
■ 중요도: {importance['grade']}등급 ({importance['score']}점)

■ 실행 프로세스:
{process_text}

■ 원문 요약:
{message['summary']}
        """,
        'start': {'date': message['deadline']},
        'end': {'date': message['deadline']},
        'colorId': color_map.get(importance['grade'], '8'),
        'reminders': {
            'useDefault': False,
            'overrides': get_reminders(importance['grade'])
        }
    }
    
    return service.events().insert(
        calendarId=calendar_id, 
        body=event
    ).execute()

def get_reminders(grade: str) -> list:
    """중요도별 리마인더 설정"""
    reminders = {
        'S': [
            {'method': 'popup', 'minutes': 4320},   # D-3
            {'method': 'popup', 'minutes': 1440},   # D-1
            {'method': 'popup', 'minutes': 540},    # 당일 오전 9시
        ],
        'A': [
            {'method': 'popup', 'minutes': 1440},   # D-1
            {'method': 'popup', 'minutes': 60},     # 1시간 전
        ],
        'B': [{'method': 'popup', 'minutes': 1440}],
        'C': [{'method': 'popup', 'minutes': 540}],
        'D': []
    }
    return reminders.get(grade, [])
```

---

## 중요도 판단 시스템

### 키워드 사전
```python
IMPORTANCE_KEYWORDS = {
    'task_type': {
        '담임': {
            'score': 40,
            'keywords': ['생활기록부', '생기부', '출결', '결석', '학부모', '상담', 
                        '가정통신문', '성적', '세특', '행동발달', '창체', '담임', '학급']
        },
        '제출': {
            'score': 35,
            'keywords': ['제출', '보고', '마감', '기한', '까지', '필수', '반드시', 
                        '공문', '결재', '품의', '기안']
        },
        '부서': {
            'score': 30,
            'keywords': ['협조', '담당', '업무', '처리', '계획', '운영', '진행']
        },
        '협조': {
            'score': 25,
            'keywords': ['협조 요청', '부탁', '요청드립니다', '도움']
        },
        '회의': {
            'score': 20,
            'keywords': ['회의', '연수', '교육', '참석', '워크숍', '세미나']
        },
        '공지': {
            'score': 15,
            'keywords': ['안내', '공지', '알림', '참고', '전달']
        }
    },
    'sender_role': {
        '관리자': {'score': 20, 'keywords': ['교장', '교감']},
        '부장': {'score': 15, 'keywords': ['부장']},
        '행정': {'score': 12, 'keywords': ['행정실', '행정']},
        '담당': {'score': 10, 'keywords': ['담당']},
    },
    'system': {
        'score': 10,
        'keywords': ['나이스', 'NEIS', '에듀파인', 'K-에듀파인', '업로드', '입력']
    }
}
```

### 중요도 계산 로직
```python
import re
from datetime import datetime, timedelta

def calculate_importance(message: dict) -> dict:
    """학교업무 특수성 반영 중요도 계산"""
    content = message.get('content', '') + message.get('title', '')
    sender = message.get('sender', '')
    deadline = message.get('deadline')
    
    scores = {
        'task_type': {'score': 0, 'reason': ''},
        'urgency': {'score': 0, 'd_day': None},
        'sender': {'score': 0, 'role': ''},
        'impact': {'score': 0, 'reason': ''}
    }
    
    # A. 업무 유형 (40점)
    for task_type, info in IMPORTANCE_KEYWORDS['task_type'].items():
        if any(kw in content for kw in info['keywords']):
            if info['score'] > scores['task_type']['score']:
                scores['task_type'] = {'score': info['score'], 'reason': task_type}
    
    # B. 시급성 (30점)
    if deadline:
        d_day = (datetime.strptime(deadline, '%Y-%m-%d') - datetime.now()).days
        scores['urgency']['d_day'] = d_day
        if d_day <= 0:
            scores['urgency']['score'] = 30
        elif d_day == 1:
            scores['urgency']['score'] = 25
        elif d_day <= 3:
            scores['urgency']['score'] = 20
        elif d_day <= 7:
            scores['urgency']['score'] = 10
        else:
            scores['urgency']['score'] = 5
    
    # C. 발신자 (20점)
    for role, info in IMPORTANCE_KEYWORDS['sender_role'].items():
        if any(kw in sender for kw in info['keywords']):
            scores['sender'] = {'score': info['score'], 'role': role}
            break
    if scores['sender']['score'] == 0:
        scores['sender'] = {'score': 5, 'role': '일반'}
    
    # D. 영향 범위 (10점)
    if any(kw in content for kw in IMPORTANCE_KEYWORDS['system']['keywords']):
        scores['impact'] = {'score': 10, 'reason': '시스템 연계'}
    elif any(kw in content for kw in ['학생', '아이들', '우리반']):
        scores['impact'] = {'score': 8, 'reason': '학생 영향'}
    else:
        scores['impact'] = {'score': 5, 'reason': '일반'}
    
    # 총점 계산
    total = sum(s['score'] for s in scores.values())
    
    # 등급 산정
    if total >= 80:
        grade = 'S'
        color = '🔴'
    elif total >= 60:
        grade = 'A'
        color = '🟠'
    elif total >= 40:
        grade = 'B'
        color = '🟡'
    elif total >= 20:
        grade = 'C'
        color = '🟢'
    else:
        grade = 'D'
        color = '⚪'
    
    return {
        'grade': grade,
        'score': total,
        'breakdown': scores,
        'color_code': color
    }
```

---

## 3단계 실행 프로세스 생성

### 프로세스 템플릿
```python
ACTION_TEMPLATES = {
    '담임': {
        'base': ['학생/자료 확인', '나이스 입력', '검토 요청'],
        'details': {
            '생기부': ['담당반 미입력 항목 확인', '세특/행발/창체 최종 입력', '부장 검토 요청'],
            '출결': ['결석 학생 확인', '나이스 출결 처리', '담임 확인'],
            '상담': ['상담 일정 조율', '상담 실시 및 기록', '나이스 상담 입력'],
        }
    },
    '제출': {
        'base': ['양식 확인', '내용 작성', '제출 및 확인'],
        'details': {
            '공문': ['공문 내용 및 양식 확인', '기안문 작성', '결재 요청'],
            '보고서': ['양식 다운로드', '내용 작성 및 검토', '기한 내 제출'],
            '계획서': ['작년 자료 참고', '올해 계획 수립', '결재 및 제출'],
        }
    },
    '회의': {
        'base': ['일정 확인', '사전 준비', '참석'],
        'details': {
            '교직원회의': ['회의 시간/장소 확인', '안건 사전 검토', '참석 및 기록'],
            '연수': ['연수 신청/등록', '사전 자료 검토', '이수 및 결과 제출'],
        }
    },
    '협조': {
        'base': ['요청 내용 파악', '업무 처리', '완료 회신'],
        'details': {}
    },
    '예산': {
        'base': ['품의서 확인', '에듀파인 처리', '결재 확인'],
        'details': {}
    },
    '공지': {
        'base': ['내용 확인', '해당 시 일정 등록', '필요 시 공유'],
        'details': {}
    }
}
```

### 프로세스 생성 로직
```python
def generate_action_process(message: dict) -> dict:
    """쪽지 분석 → 3단계 실행 프로세스 생성"""
    content = message.get('content', '') + message.get('title', '')
    
    # 1. 업무 유형 식별
    task_type = identify_task_type(content)
    
    # 2. 세부 유형 식별
    sub_type = identify_sub_type(content, task_type)
    
    # 3. 템플릿 선택
    template = ACTION_TEMPLATES.get(task_type, ACTION_TEMPLATES['공지'])
    
    if sub_type and sub_type in template.get('details', {}):
        actions = template['details'][sub_type]
    else:
        actions = template['base']
    
    # 4. 구체화 (내용에서 추출한 정보로 보완)
    specific_info = extract_specific_info(content)
    
    process = []
    for i, action in enumerate(actions):
        detail = customize_action(action, specific_info, i)
        process.append({
            'step': i + 1,
            'action': action,
            'detail': detail
        })
    
    # 5. 예상 시간 및 권장 시작일
    estimated_time = estimate_time(task_type, sub_type)
    recommended_start = calculate_recommended_start(
        message.get('deadline'), 
        estimated_time
    )
    
    return {
        'task_type': task_type,
        'sub_type': sub_type,
        'process': process,
        'estimated_time': estimated_time,
        'recommended_start': recommended_start
    }

def identify_task_type(content: str) -> str:
    """내용에서 업무 유형 식별"""
    for task_type, info in IMPORTANCE_KEYWORDS['task_type'].items():
        if any(kw in content for kw in info['keywords']):
            return task_type
    return '공지'

def estimate_time(task_type: str, sub_type: str) -> str:
    """예상 소요 시간"""
    time_map = {
        '담임': {'생기부': '2-3시간', '출결': '30분', '상담': '1시간', 'default': '1시간'},
        '제출': {'공문': '1시간', '보고서': '2시간', '계획서': '3시간', 'default': '1시간'},
        '회의': {'default': '1-2시간'},
        '협조': {'default': '30분-1시간'},
        '예산': {'default': '30분'},
        '공지': {'default': '10분'}
    }
    type_times = time_map.get(task_type, {'default': '30분'})
    return type_times.get(sub_type, type_times['default'])
```

---

## 기한 중심 요약 생성

### 요약 생성 코드
```python
from datetime import datetime, timedelta

def generate_deadline_summary(messages: list, date_range: str = 'week') -> dict:
    """기한 중심으로 쪽지 요약"""
    today = datetime.now().date()
    
    categorized = {
        'urgent': [],      # D-0 ~ D-2 (🔴)
        'this_week': [],   # D-3 ~ D-7 (🟡)
        'upcoming': [],    # D-8+ (🟢)
        'no_deadline': []  # 기한 없음 (⚪)
    }
    
    for msg in messages:
        deadline = msg.get('deadline')
        importance = calculate_importance(msg)
        process = generate_action_process(msg)
        
        summary = {
            'title': msg['title'],
            'sender': msg['sender'],
            'deadline': deadline,
            'd_day': None,
            'importance': importance,
            'process_short': ' → '.join([p['action'] for p in process['process']]),
            'color': importance['color_code']
        }
        
        if not deadline:
            categorized['no_deadline'].append(summary)
            continue
        
        d_day = (datetime.strptime(deadline, '%Y-%m-%d').date() - today).days
        summary['d_day'] = d_day
        
        if d_day <= 2:
            categorized['urgent'].append(summary)
        elif d_day <= 7:
            categorized['this_week'].append(summary)
        else:
            categorized['upcoming'].append(summary)
    
    # 각 카테고리 내에서 D-day 순 정렬
    for key in ['urgent', 'this_week', 'upcoming']:
        categorized[key].sort(key=lambda x: x['d_day'] or 999)
    
    return {
        'summary_date': today.strftime('%Y-%m-%d'),
        **categorized
    }

def format_summary_markdown(summary: dict) -> str:
    """마크다운 형식 요약 출력"""
    output = f"# 📬 쪽지 요약 ({summary['summary_date']})\n\n"
    
    sections = [
        ('🔴 긴급 (D-0 ~ D-2)', 'urgent'),
        ('🟡 주의 (D-3 ~ D-7)', 'this_week'),
        ('🟢 예정 (D-8+)', 'upcoming'),
        ('⚪ 참고/공지', 'no_deadline')
    ]
    
    for title, key in sections:
        items = summary.get(key, [])
        if not items:
            continue
        
        output += f"## {title}\n"
        output += "| 마감 | 제목 | 발신자 | 실행 프로세스 |\n"
        output += "|------|------|--------|---------------|\n"
        
        for item in items:
            d_day = f"D-{item['d_day']}" if item['d_day'] is not None else "-"
            deadline = item['deadline'] or "-"
            output += f"| {deadline} ({d_day}) | {item['title'][:20]} | {item['sender']} | {item['process_short']} |\n"
        
        output += "\n"
    
    return output
```

---

## 에이전트 사용 예시 (확장)

## 에이전트 사용 예시 (확장)

### 기본 쪽지 처리
```
사용자: "안 읽은 쪽지 모두 저장해줘"

에이전트:
1. process_unread_messages() 호출
2. 처리 결과 반환:
   - 3개 쪽지 처리 완료
   - 저장 위치: D:/GOE_Archive/2025/01/27/
   - 첨부파일 5개 다운로드
```

### 기한 중심 요약
```
사용자: "이번 주 해야 할 일 정리해줘"

에이전트:
1. generate_deadline_summary(date_range="week") 호출
2. 결과:

📬 쪽지 요약 (2025-01-27)

🔴 긴급 (D-0 ~ D-2)
| 마감 | 제목 | 발신자 | 실행 프로세스 |
|------|------|--------|---------------|
| 01/29 (D-2) | 생기부 마감 | 교무기획부 | 점검→입력→검토요청 |

🟡 주의 (D-3 ~ D-7)
| 마감 | 제목 | 발신자 | 실행 프로세스 |
|------|------|--------|---------------|
| 02/03 (D-7) | 교육과정 계획 | 교육과정부 | 양식→작성→결재 |
```

### 중요도 분석
```
사용자: "오늘 온 쪽지 중에 급한 거 뭐야?"

에이전트:
1. search_messages(date_from="2025-01-27") 호출
2. 각 쪽지에 calculate_importance() 호출
3. S/A 등급 필터링
4. 결과:

🔴 S등급 (85점) - 생활기록부 최종 마감
  - 업무유형: 담임업무 (40점)
  - 시급성: D-2 (20점)
  - 발신자: 부장교사 (15점)
  - 영향범위: 나이스연계 (10점)
  
  📋 실행 프로세스:
  1️⃣ 담당반 생기부 미입력 항목 확인
  2️⃣ 나이스 최종 입력 및 자체 검토
  3️⃣ 부장선생님 검토 요청
```

### 구글 캘린더 등록
```
사용자: "생기부 마감 캘린더에 넣어줘"

에이전트:
1. search_messages(query="생기부 마감") 호출
2. add_to_calendar(message_path, add_reminders=True) 호출
3. 결과:

✅ 캘린더 등록 완료!

📅 [제출] 생활기록부 최종 마감
   일시: 2025-01-29
   색상: 🔴 빨강 (긴급)
   
⏰ 리마인더 설정:
   - D-3 (1/26) 알림
   - D-1 (1/28) 알림
   - 당일 오전 9시 알림
   
🔗 캘린더 링크: [열기]
```

### 3단계 프로세스 상세
```
사용자: "교육과정 운영계획 제출 어떻게 해야 해?"

에이전트:
1. search_messages(query="교육과정 운영계획") 호출
2. generate_action_process() 호출
3. 결과:

📋 교육과정 운영계획서 제출

■ 업무 유형: 제출 > 계획서
■ 마감: 2025-02-03 (D-7)
■ 예상 소요: 3시간

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1️⃣ 준비 단계
   └ 작년 운영계획서 참고 자료 확인
   └ 올해 교육과정 방향 검토
   └ 첨부된 양식 다운로드

2️⃣ 작성 단계
   └ 교과별 운영계획 수립
   └ 평가계획 포함
   └ 담당 부장 사전 협의

3️⃣ 제출 단계
   └ 최종 검토 및 수정
   └ 결재 요청 (담당→부장→교감)
   └ 기한 내 제출 확인

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⏰ 권장 시작일: 1/28 (여유 있게 D-6부터)
```

### 종합 워크플로우
```
사용자: "오늘 쪽지 정리하고 중요한 건 캘린더에 넣어줘"

에이전트 (자동 순차 실행):
1. process_unread_messages() - 안 읽은 쪽지 저장
2. generate_deadline_summary() - 기한별 정리
3. 각 쪽지에 calculate_importance() - 중요도 분석
4. S/A 등급에 add_to_calendar() - 캘린더 등록

결과:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📬 오늘의 쪽지 정리 완료

📥 저장: 5개 쪽지, 3개 첨부파일
📅 캘린더: 2개 일정 등록

🔴 긴급 (캘린더 등록됨)
├ 생기부 마감 (D-2) → 📅 등록
└ 출결 마감 (D-1) → 📅 등록

🟡 이번 주
├ 교육과정 계획 (D-7)
└ 예산 품의 (D-5)

🟢 참고
└ 2월 회의 안내
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 주의사항

1. **UI 변경 대응**: GOE메신저 업데이트 시 UI 요소 위치가 변경될 수 있음
   - assets/images/ 의 이미지 파일 업데이트 필요
   - config.yaml에서 좌표 조정 가능하도록 설계

2. **포그라운드 실행**: UI 자동화는 메신저 창이 보이는 상태에서만 동작

3. **보안**: 저장된 쪽지에 민감 정보가 포함될 수 있으므로 저장 폴더 접근 권한 관리 필요

4. **에러 복구**: 중단 시 마지막 처리 위치 저장하여 재개 가능

---

## 개발 우선순위

1. **P0 (필수)**
   - 메신저 연결 및 쪽지함 접근
   - 안 읽은 쪽지 식별
   - 다운로드 버튼 클릭
   - 마크다운 저장

2. **P1 (중요)**
   - PDF 저장
   - 설정 파일 지원
   - 로깅

3. **P2 (선택)**
   - MCP 에이전트 연동
   - 스케줄링
   - 시스템 트레이

---

*버전: 1.0*
*최종 수정: 2025-01-27*
