# GOE 메신저 도우미

경기교육통합메신저(GOE 메신저)의 쪽지를 자동으로 저장하고, AI 기반 중요도 분석을 통해 업무를 효율적으로 관리하는 Windows 자동화 프로그램입니다.

## 프로젝트 소개

GOE 메신저 도우미는 교사들의 행정 업무 부담을 줄이기 위해 개발되었습니다. 경기도교육청 통합메신저의 쪽지를 자동으로 백업하고, 중요도를 분석하여 우선순위를 제시합니다.

### 왜 필요한가요?

- GOE 메신저 첨부파일은 **14일 후 자동 삭제**됩니다
- 하루에 수십 개의 쪽지 중 **긴급한 업무**를 놓치기 쉽습니다
- 마감일 관리와 업무 추적이 번거롭습니다

### 해결책

- 안 읽은 쪽지 **자동 저장** (Markdown/PDF)
- 첨부파일 **자동 백업**
- AI 기반 **중요도 분석** 및 **업무 분류**
- Google 캘린더 **마감일 자동 등록**
- Claude Code 연동으로 **자연어 명령** 지원

---

## 주요 기능

### 1. 안 읽은 쪽지 자동 저장

- Markdown 형식으로 본문 저장
- PDF 형식으로 원본 저장 (인쇄 기능 활용)
- 첨부파일 자동 다운로드 및 백업

### 2. AI 기반 중요도 분석

| 등급 | 점수 | 색상 | 의미 |
|------|------|------|------|
| S | 50점 이상 | 빨강 | 즉시 처리 필요 |
| A | 40-49점 | 주황 | 우선 처리 |
| B | 25-39점 | 노랑 | 계획적 처리 |
| C | 10-24점 | 초록 | 여유 있게 처리 |
| D | 0-9점 | 흰색 | 참고용 |

**점수 산정 기준**:
- 업무 유형 (40점): 담임업무 > 제출/보고 > 협조요청 > 회의/연수 > 공지/안내
- 시급성 (20점): D-0(당일) > D-1 > D-2~3 > 이번 주 > 여유

### 3. 업무 분류 시스템

쪽지를 **행동(Action)**과 **정보(Info)**로 자동 분류합니다:

| 행동 필요 | 정보 제공 |
|-----------|-----------|
| 제출/보고 마감 | 안내/공지 |
| 담임 업무 (생기부 등) | 회의/행사 일정 |
| 협조 요청 | 정책/제도 변경 |
| 예산 집행 | 참고 자료 공유 |

### 4. Google 캘린더 연동

- 마감일 자동 등록
- 중요도별 리마인더 자동 설정
  - S등급: D-3, D-1, 당일 오전 알림
  - A등급: D-1, 1시간 전 알림
  - B등급: D-1 알림

### 5. Claude Code 연동 (MCP)

자연어 명령으로 쪽지를 관리할 수 있습니다:

```bash
# 예시 명령어
claude "오늘 온 쪽지 정리해줘"
claude "생기부 관련 쪽지 찾아줘"
claude "이번 주 마감 업무 알려줘"
claude "생기부 마감 캘린더에 등록해줘"
```

---

## 설치 방법

### 요구 사항

- Windows 10 이상
- Python 3.9 이상
- 경기교육통합메신저 (AtMessenger7) 설치

### 의존성 설치

```bash
# 저장소 클론
git clone https://github.com/your-repo/goe-messenger-auto-saver.git
cd goe-messenger-auto-saver

# 의존성 설치
pip install -r requirements.txt
```

### Google 캘린더 연동 설정 (선택)

1. [Google Cloud Console](https://console.cloud.google.com)에서 프로젝트 생성
2. Calendar API 활성화
3. OAuth 2.0 클라이언트 ID 생성
4. `credentials.json` 파일을 프로젝트 루트에 저장
5. 첫 실행 시 브라우저에서 인증

### Claude Code 연동 설정 (선택)

`~/.claude/claude_desktop_config.json` 파일에 다음 내용 추가:

```json
{
  "mcpServers": {
    "goe-messenger": {
      "command": "python",
      "args": ["-m", "mcp.server"],
      "cwd": "C:/path/to/goe-messenger-auto-saver",
      "env": {
        "GMAS_DATA_PATH": "C:/path/to/goe-messenger-auto-saver/data"
      }
    }
  }
}
```

---

## 사용 방법

### 1. GUI 대시보드 (권장)

```bash
python src/main.py
```

또는 빌드된 실행 파일:

```
GOE메신저도우미.exe
```

**대시보드 기능**:
- 오늘의 현황 (신규/긴급/완료 건수)
- 긴급 대기열 (D-day 순 정렬)
- 업무 그룹별 보기
- 쪽지 상세 보기 (원본 + AI 요약)
- 완료 처리 및 중요 표시

### 2. CLI 명령어

```bash
# 안 읽은 쪽지 처리
python -m src.main --process

# 특정 날짜 쪽지 검색
python -m src.main --search "생기부" --from 2025-01-01

# 마감 요약 생성
python -m src.main --summary week
```

### 3. Claude Code 연동

```bash
# 기본 질의
claude "안 읽은 쪽지 몇 개야?"

# 쪽지 처리
claude "오늘 온 쪽지 정리해줘"

# 검색
claude "생기부 관련 쪽지 찾아줘"

# 마감 관리
claude "이번 주 마감 업무 알려줘"

# 캘린더 등록
claude "생기부 마감 캘린더에 등록해줘"

# 완료 처리
claude "출결 마감 완료 처리해"
```

---

## 프로젝트 구조

```
goe-messenger-auto-saver/
├── CLAUDE.md              # Claude 에이전트 컨텍스트 문서
├── PRD.md                 # 제품 요구사항 문서
├── README.md              # 사용자 가이드 (이 파일)
├── config.yaml            # 설정 파일
├── requirements.txt       # Python 의존성
├── build.bat              # Windows 빌드 스크립트
│
├── src/
│   ├── __init__.py
│   ├── main.py            # CLI 엔트리포인트 / GUI 실행
│   ├── gui_dashboard.py   # GUI 대시보드 (tkinter)
│   ├── settings_dialog.py # 설정 다이얼로그
│   ├── config.py          # 설정/경로 관리
│   ├── messenger.py       # GOE메신저 UI 자동화
│   ├── extractor.py       # 쪽지 내용 추출
│   ├── saver.py           # 파일 저장 (MD/PDF)
│   ├── calendar_sync.py   # Google 캘린더 연동
│   ├── importance.py      # 중요도 판단 시스템
│   ├── grouping.py        # 업무 그룹핑/중복 병합
│   ├── ai_chat.py         # AI 채팅 검색
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
│   └── images/            # UI 요소 이미지 (자동화용)
│
└── tests/
    └── test_messenger.py  # 테스트 코드
```

---

## 설정 파일

### config.yaml

```yaml
general:
  # 쪽지 저장 경로
  save_path: "D:/GOE_Archive"
  # GOE 메신저 설치 경로
  messenger_path: "C:/Program Files (x86)/AtMessenger7"

automation:
  # 자동 확인 주기 (분)
  check_interval_minutes: 30
  # 클릭 간 대기 시간 (밀리초)
  click_delay_ms: 200

save_options:
  # Markdown 저장 여부
  markdown: true
  # PDF 저장 여부
  pdf: true
  # 첨부파일 다운로드 여부
  attachments: true

calendar:
  # 캘린더 연동 활성화
  enabled: false
  # 캘린더 ID (기본: primary)
  calendar_id: "primary"
  # 자동 리마인더 설정
  auto_reminders: true

agent:
  # MCP 에이전트 활성화
  enabled: true
  # 자동 요약 생성
  auto_summarize: true
  # 자동 분류
  auto_classify: true
```

### 데이터 저장 위치

```
C:\Users\{사용자}\Documents\GOE메신저도우미\
├── config.yaml        # 설정 파일
├── messages.db        # 쪽지 데이터베이스
├── google_token.json  # 캘린더 인증 토큰 (연동 시)
└── 첨부파일\          # 백업된 첨부파일
```

---

## 빌드 방법

### Windows 실행 파일 생성

```bash
# 빌드 스크립트 실행
build.bat

# 또는 직접 실행
pyinstaller --onefile --windowed --name "GOE메신저도우미" src/main.py
```

결과물: `dist/GOE메신저도우미.exe`

### 첫 실행 시 보안 경고

Windows Defender가 경고를 표시할 수 있습니다:

1. "Windows가 PC를 보호했습니다" 창에서
2. "추가 정보" 클릭
3. "실행" 버튼 클릭

이는 코드 서명이 없는 개인 개발 프로그램에서 일반적인 현상입니다.

---

## 주의사항

1. **포그라운드 실행**: UI 자동화는 메신저 창이 보이는 상태에서만 동작합니다.

2. **UI 변경 대응**: GOE 메신저 업데이트 시 UI 요소 위치가 변경될 수 있습니다.
   - `assets/images/` 폴더의 이미지 파일 업데이트 필요
   - `config.yaml`에서 좌표 조정 가능

3. **보안**: 저장된 쪽지에 민감 정보가 포함될 수 있으므로 저장 폴더 접근 권한을 관리하세요.

4. **에러 복구**: 프로그램 중단 시 마지막 처리 위치를 저장하여 재개가 가능합니다.

---

## 문의 및 기여

문제가 있거나 개선 제안이 있으시면 Issue를 등록해 주세요.

Pull Request도 환영합니다!

---

## 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다.

```
MIT License

Copyright (c) 2025

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

Made with care for teachers
