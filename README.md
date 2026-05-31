# Audio JDM 모델 현황 대시보드

오디오SW PO 파트 구성원별 **Initiative** 현황을 Jira(TVPLAT)에서 조회하는 대시보드입니다.  
UI 레이아웃은 기존 Jira Dashboard(사이드바 + 헤더 + 섹션 카드)와 동일한 구조를 따릅니다.

## Tech Stack

| Layer | Stack |
|-------|-------|
| Backend | FastAPI (Python 3.12), jira (PyPI), MongoDB REST helper, OpenAI-compatible LiteLLM |
| Frontend | React 18 + Babel standalone (단일 SPA, vendor JS 로컬 서빙) |
| Run | uv, uvicorn (port **8200**) |

## Directory

```
.
├── main.py                 # uvicorn 진입점
├── hml.py                  # LgJira 래퍼
├── pyproject.toml
├── Dockerfile
└── wRE_dashboard/
    ├── backend/
    │   ├── main.py
    │   ├── jira_sync.py
    │   └── mongo_helper.py
    ├── frontend/
    │   ├── index.html
    │   ├── app.jsx
    │   └── vendor/
    └── run.py
```

## 구성원 (10명)

고석민, 윤필규, 박시형, 오제준, 이재철, 나택수, 조용승, 이홍순, 박윤규, 이마을

## 환경 변수

`.env.example` 참고:

- `JIRA_URL`, `CSR_JENKINS_ADMIN_ID`, `CSR_JENKINS_ADMIN_PWD`
- `AZURE_OPENAI_*` (향후 LLM 요약 확장용)
- `MONGO_API_BASE`, `MONGO_API_TOKEN`
- `GIT_PAGE_PASSWORD` (향후 Git Activity 페이지용)

## 로컬 실행

```bash
cd audio-jdm-dashboard
cp .env.example .env   # Jira 계정 입력

uv sync                # 또는: uv pip install -e .
python wRE_dashboard/run.py
```

브라우저: http://127.0.0.1:8200

## API

| Method | Path | 설명 |
|--------|------|------|
| GET | `/api/team-members` | 파트/구성원 목록 |
| POST | `/api/fetch-data` | Initiative 검색 시작 |
| GET | `/api/fetch-status` | 검색 진행률 |
| GET | `/api/dashboard-data` | 검색 결과 |
| POST | `/api/sync` | Jira → MongoDB 동기화 |
| GET | `/api/sync-info` | 마지막 동기화 정보 |

## Docker

```bash
docker build -t audio-jdm-dashboard .
docker run -p 8200:8200 --env-file .env audio-jdm-dashboard
```
