# 해외 언론 속 한국 (korea-news-watch)

미국·일본·중국·베트남 주요 매체의 **한국 관련 기사**를 매일 아침 7시(한국시간)에 모아서
한국어 제목, 3줄 요약, "한국 내 이슈 가능성" 점수(1~5)를 붙여 보여주는 웹사이트입니다.

- 기사 본문은 저장하지 않습니다. 제목, 요약, 원문 링크만 보여줍니다.
- **두 가지 모드**가 있고, API 키가 있는지에 따라 자동으로 정해집니다.
  - **무료 모드 (기본, 0원):** 무료 번역기(Google 번역 → 안 되면 MyMemory)로 제목과 RSS 소개문을 번역합니다.
    점수는 제목 키워드와 여러 나라 동시 보도 여부로 매기는 규칙 점수입니다(`scripts/free_mode.py`).
  - **Claude 모드 (선택, 월 $1 안팎):** GitHub Secrets에 `ANTHROPIC_API_KEY`를 등록하면 그 뒤로 들어오는 기사부터
    Claude Haiku 5.5(`claude-haiku-5-5`)가 3줄 요약과 이슈 점수, 이유를 만듭니다. 비용은 배치 처리로 50% 할인됩니다.
- 요약은 **제목과 RSS 소개문**만 보고 만듭니다. 본문 전체를 요약한 것은 아닙니다.

---

## 처음 한 번만 하는 설정 (약 20분)

### 1단계: GitHub 저장소 만들기
1. https://github.com 에 가입하고 로그인합니다.
2. 오른쪽 위 **+** → **New repository**를 누릅니다.
3. Repository name에 `korea-news-watch`를 입력하고 **Public**을 선택한 뒤 **Create repository**를 누릅니다.
   (Public이어야 GitHub Pages와 Actions를 무료로 쓸 수 있습니다.)

### 2단계: 파일 올리기
1. 새 저장소 화면에서 **uploading an existing file** 링크를 누릅니다.
2. 바탕화면의 `korea-news-watch` 폴더를 열고 **안의 내용 전부**(`.github`, `docs`, `scripts`, `README.md` 등)를
   선택(Ctrl+A)해서 브라우저 업로드 창으로 끌어다 놓습니다.
   - `.github` 폴더가 꼭 같이 올라가야 자동 실행이 됩니다.
3. 아래 **Commit changes**를 누릅니다.

> 3~4단계는 **Claude 모드를 쓸 때만** 필요합니다. 무료 모드로 쓸 거라면 건너뛰고 5단계로 가세요.

### 3단계: Claude API 키 만들기
1. https://console.anthropic.com 에 가입하고 로그인합니다.
2. **Billing**에서 크레딧을 충전합니다(최소 금액이면 충분합니다).
   - **Limits**에서 월 사용 한도를 낮게(예: $5) 정해두면 안심할 수 있습니다.
3. **API Keys** → **Create Key** → 이름(예: `korea-news`)을 입력하고 만든 다음, 키를 복사합니다.
   - 키는 이 화면에서 **한 번만** 보입니다. 다른 사람이나 채팅창에 절대 붙여넣지 마세요.

### 4단계: API 키를 GitHub Secrets에 저장하기
1. 저장소에서 **Settings** → 왼쪽 **Secrets and variables** → **Actions**로 갑니다.
2. **New repository secret**을 누릅니다.
3. Name: `ANTHROPIC_API_KEY`, Secret: (복사한 키)를 넣고 **Add secret**을 누릅니다.

### 5단계: GitHub Pages 켜기
1. **Settings** → 왼쪽 **Pages**로 갑니다.
2. Source: **Deploy from a branch**, Branch: **main**, 폴더: **/docs**로 맞추고 **Save**를 누릅니다.
3. 1~2분 뒤 위쪽에 사이트 주소가 나타납니다: `https://<내 아이디>.github.io/korea-news-watch/`

### 6단계: 첫 실행 (수동)
1. 저장소 위쪽 **Actions** 탭 → 왼쪽 **Daily Korea news** → 오른쪽 **Run workflow** → 초록 버튼을 누릅니다.
2. 몇 분에서 수십 분 뒤 초록 체크(✓)가 뜨면 성공입니다. 사이트를 새로고침하면 기사가 보입니다.
   - 빨간 X가 뜨면 그 실행을 눌러 로그를 확인합니다(그대로 복사해서 Claude에게 물어보면 됩니다).

이후로는 **매일 오전 7시 무렵 자동 실행**됩니다. GitHub 사정에 따라 몇 분에서 수십 분 늦어질 수 있습니다.
(참고: 저장소에 60일 동안 아무 활동이 없으면 GitHub가 예약 실행을 멈춥니다. 이 프로젝트는 매일 커밋하므로 보통 문제없습니다.)

---

## 동작 방식

```
RSS 피드 (scripts/feeds.py)
   ↓  한국 키워드 필터 + URL·제목 중복 제외 (scripts/collect.py)
AI 대기열 (data/queue.json)
   ↓  Claude 배치 처리: 번역·3줄 요약·점수 (scripts/summarize.py)
기사 기록 (docs/articles.json)  ←  웹사이트(docs/index.html)가 이 파일을 읽어 표시
```

| 파일 | 역할 |
|---|---|
| `scripts/feeds.py` | 매체 목록과 키워드. **매체를 추가/삭제하려면 이 파일만 고치세요** |
| `scripts/main.py` | 전체 순서 실행. 한 번에 AI 처리 최대 200건, 기록 보관 90일 |
| `docs/articles.json` | 기사 기록(제목, 요약, 점수, 링크) |
| `data/queue.json` | AI 처리를 기다리는 기사(처리되면 삭제) |
| `.github/workflows/daily.yml` | 매일 자동 실행 설정 |

## 자주 묻는 것
- **API 키가 없으면?** 수집만 하고 원문 제목만 보여줍니다(“AI 요약 대기 중”). 키를 등록하면 다음 실행 때 밀린 기사부터 처리합니다.
- **비용 확인은?** console.anthropic.com → **Usage**에서 볼 수 있습니다.
- **실행 시각 바꾸기:** `daily.yml`의 `cron: "0 22 * * *"`를 고칩니다. UTC 기준이라 한국시간에서 9시간을 빼야 합니다.
