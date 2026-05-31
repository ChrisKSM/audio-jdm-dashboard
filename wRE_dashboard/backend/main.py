#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Audio JDM 모델 현황 대시보드 Backend
파트원별 Initiative → Epic → Story 계층 데이터 제공
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import threading
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
_DASHBOARD_DIR = os.path.dirname(_BACKEND_DIR)
_PROJECT_ROOT = os.path.dirname(_DASHBOARD_DIR)

sys.path.insert(0, _PROJECT_ROOT)
sys.path.insert(0, _BACKEND_DIR)

from hml import LgJira

import jira_sync

load_dotenv(dotenv_path=os.path.join(_PROJECT_ROOT, ".env"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Audio JDM Dashboard", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

JIRA_URL = os.getenv("JIRA_URL", "http://jira.lge.com/issue")
CSR_JENKINS_ADMIN_ID = os.getenv("CSR_JENKINS_ADMIN_ID", "")
CSR_JENKINS_ADMIN_PWD = os.getenv("CSR_JENKINS_ADMIN_PWD", "")

TEAM_PARTS: dict[str, dict[str, Any]] = {
    "audio_sw_po": {
        "name": "오디오SW PO 파트",
        "members": {
            "seokmin.koh": "고석민",
            "pilkyu.yoon": "윤필규",
            "sh12.park": "박시형",
            "jejun.oh": "오제준",
            "jaecheol.lee": "이재철",
            "taeksu.la": "나택수",
            "yongseung.cho": "조용승",
            "hongsoon.lee": "이홍순",
            "yoonkyu.park": "박윤규",
            "maeul.lee": "이마을",
        },
    }
}

TEAM_MEMBERS: dict[str, str] = {
    member_id: display
    for part in TEAM_PARTS.values()
    for member_id, display in part["members"].items()
}

_jira_connection: LgJira | None = None
_fetch_status: dict[str, Any] = {
    "running": False,
    "progress": 0,
    "total": 100,
    "current_task": "",
    "completed": False,
    "error": None,
    "data": None,
    "cancelled": False,
}
_fetch_lock = threading.Lock()

_sync_status: dict[str, Any] = {
    "running": False,
    "progress": 0,
    "current_task": "",
    "completed": False,
    "error": None,
    "count": 0,
}
_sync_lock = threading.Lock()


class StoryData(BaseModel):
    key: str
    summary: str
    status: str
    issue_type: str = "Story"
    assignee: str | None = None
    planned_sp: float | None = None
    sprint: str | None = None
    url: str


class EpicData(BaseModel):
    key: str
    summary: str
    status: str
    stories: list[StoryData] = Field(default_factory=list)
    url: str


class InitiativeData(BaseModel):
    key: str
    summary: str
    status: str
    epics: list[EpicData] = Field(default_factory=list)
    url: str
    status_color: str | None = None
    duedate: str | None = None


class PersonData(BaseModel):
    name: str
    display_name: str
    initiatives: list[InitiativeData] = Field(default_factory=list)


class DashboardData(BaseModel):
    persons: list[PersonData] = Field(default_factory=list)


class FetchRequest(BaseModel):
    members: list[str]
    source: str = "jira"
    quick: bool = True


class FetchStatus(BaseModel):
    running: bool
    progress: int
    total: int
    current_task: str
    completed: bool
    error: str | None = None


class SyncRequest(BaseModel):
    members: list[str] = Field(default_factory=list)
    full: bool = False


def get_jira() -> LgJira:
    global _jira_connection
    if _jira_connection is None:
        if not CSR_JENKINS_ADMIN_ID or not CSR_JENKINS_ADMIN_PWD:
            raise RuntimeError("Jira credentials not configured")
        logger.info("Connecting to Jira: %s", JIRA_URL)
        _jira_connection = LgJira(
            server=JIRA_URL,
            basic_auth=(CSR_JENKINS_ADMIN_ID, CSR_JENKINS_ADMIN_PWD),
        )
    return _jira_connection


def _issue_url(key: str) -> str:
    return f"{JIRA_URL.rstrip('/')}/browse/{key}"


def _status_text(value: Any) -> str:
    return str(value) if value is not None else ""


def _parse_status_color(fields: Any) -> str | None:
    raw = getattr(fields, "customfield_35917", None)
    if not raw:
        return None
    if hasattr(raw, "value"):
        return str(raw.value)
    return str(raw)


def update_fetch_status(**kwargs: Any) -> None:
    with _fetch_lock:
        _fetch_status.update(kwargs)


def _check_cancelled() -> bool:
    with _fetch_lock:
        if _fetch_status.get("cancelled"):
            _fetch_status["running"] = False
            _fetch_status["completed"] = True
            _fetch_status["error"] = "검색이 취소되었습니다."
            _fetch_status["cancelled"] = False
            return True
    return False


def _collect_epics_for_initiative(jira: LgJira, init_issue) -> list[Any]:
    epics: list[Any] = []
    links = getattr(init_issue.fields, "issuelinks", None) or []
    for link in links:
        linked = getattr(link, "outwardIssue", None) or getattr(link, "inwardIssue", None)
        if not linked:
            continue
        try:
            full_issue = jira.issue(
                linked.key,
                fields="summary,status,issuetype,issuelinks,customfield_10002,customfield_10005",
            )
            issue_type = _status_text(getattr(full_issue.fields, "issuetype", ""))
            if issue_type.lower() == "epic":
                epics.append(full_issue)
        except Exception as exc:
            logger.warning("Epic lookup failed (%s): %s", linked.key, exc)
    return epics


def _collect_stories_for_epic(jira: LgJira, epic_issue) -> list[StoryData]:
    stories: list[StoryData] = []
    links = getattr(epic_issue.fields, "issuelinks", None) or []
    for link in links:
        linked = getattr(link, "outwardIssue", None) or getattr(link, "inwardIssue", None)
        if not linked:
            continue
        try:
            story_issue = jira.issue(
                linked.key,
                fields="summary,status,issuetype,assignee,customfield_10002,customfield_10005",
            )
            issue_type = _status_text(getattr(story_issue.fields, "issuetype", ""))
            if issue_type.lower() not in ("story", "task"):
                continue
            assignee = None
            if getattr(story_issue.fields, "assignee", None):
                assignee = getattr(story_issue.fields.assignee, "name", None)
            stories.append(
                StoryData(
                    key=story_issue.key,
                    summary=story_issue.fields.summary or "",
                    status=_status_text(story_issue.fields.status),
                    issue_type=issue_type,
                    assignee=assignee,
                    planned_sp=getattr(story_issue.fields, "customfield_10002", None),
                    sprint=_status_text(getattr(story_issue.fields, "customfield_10005", None))[:80] or None,
                    url=_issue_url(story_issue.key),
                )
            )
        except Exception as exc:
            logger.warning("Story lookup failed (%s): %s", linked.key, exc)
    return stories


def fetch_data_background(members: list[str], source: str = "jira", quick: bool = True) -> None:
    global _fetch_status
    try:
        if source == "mongodb":
            update_fetch_status(progress=10, current_task="MongoDB 캐시 로드 중...")
            report = jira_sync.load_initiative_cache(members)
            if report:
                update_fetch_status(progress=100, current_task="완료", data=report, completed=True, running=False)
                return
            update_fetch_status(
                progress=100,
                completed=True,
                running=False,
                error="MongoDB에 Initiative 캐시가 없습니다. Jira 검색을 먼저 실행하세요.",
            )
            return

        jira = get_jira()
        member_list = ", ".join(members)
        jql = (
            f"project = TVPLAT AND issuetype = Initiative "
            f"AND created >= 2025-08-01 AND assignee in ({member_list}) "
            f'AND status NOT IN ("CLOSED", "DELIVERED", "DEFERRED")'
        )
        update_fetch_status(progress=5, current_task="Initiative 검색 중...")
        initiatives = jira.search_issues(
            jql,
            maxResults=500,
            fields="issuetype,summary,status,assignee,issuelinks,customfield_35917,duedate",
        )

        persons_dict = {
            member_id: PersonData(
                name=member_id,
                display_name=TEAM_MEMBERS.get(member_id, member_id),
                initiatives=[],
            )
            for member_id in members
        }

        total = len(initiatives)
        for idx, init_issue in enumerate(initiatives, start=1):
            if _check_cancelled():
                return

            assignee_name = None
            if getattr(init_issue.fields, "assignee", None):
                assignee_name = init_issue.fields.assignee.name
            if assignee_name not in persons_dict:
                continue

            init_data = InitiativeData(
                key=init_issue.key,
                summary=init_issue.fields.summary or "",
                status=_status_text(init_issue.fields.status),
                url=_issue_url(init_issue.key),
                status_color=_parse_status_color(init_issue.fields),
                duedate=getattr(init_issue.fields, "duedate", None),
            )

            if not quick:
                update_fetch_status(
                    progress=min(90, int((idx / max(total, 1)) * 85) + 5),
                    current_task=f"Initiative {idx}/{total}: {init_issue.key}",
                )
                for epic_issue in _collect_epics_for_initiative(jira, init_issue):
                    epic_data = EpicData(
                        key=epic_issue.key,
                        summary=epic_issue.fields.summary or "",
                        status=_status_text(epic_issue.fields.status),
                        url=_issue_url(epic_issue.key),
                        stories=_collect_stories_for_epic(jira, epic_issue),
                    )
                    init_data.epics.append(epic_data)

            persons_dict[assignee_name].initiatives.append(init_data)

        persons_list = list(persons_dict.values())
        dashboard = DashboardData(persons=persons_list)
        report_dump = dashboard.model_dump()

        try:
            jira_sync.save_initiative_cache(report_dump)
        except Exception as exc:
            logger.warning("Initiative cache save skipped: %s", exc)

        update_fetch_status(progress=100, current_task="완료", data=report_dump, completed=True, running=False)
        logger.info("Initiative search complete: %s items", total)

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Initiative search failed: %s", exc, exc_info=True)
        update_fetch_status(error=str(exc), completed=True, running=False)


def sync_background(members: list[str], full: bool = False) -> None:
    global _sync_status
    try:
        jira = get_jira()

        def progress(pct: int, task: str) -> None:
            with _sync_lock:
                _sync_status["progress"] = pct
                _sync_status["current_task"] = task

        if full:
            count = jira_sync.full_sync_issues(jira, members, JIRA_URL, progress)
        else:
            count = jira_sync.incremental_sync_issues(jira, members, JIRA_URL, progress)

        with _sync_lock:
            _sync_status.update(
                {
                    "running": False,
                    "completed": True,
                    "count": count,
                    "progress": 100,
                    "current_task": "동기화 완료",
                }
            )
    except Exception as exc:
        logger.error("Sync failed: %s", exc, exc_info=True)
        with _sync_lock:
            _sync_status.update(
                {"running": False, "completed": True, "error": str(exc), "current_task": "동기화 실패"}
            )


@app.get("/")
async def root():
    return FileResponse(os.path.join(_DASHBOARD_DIR, "frontend", "index.html"))


@app.get("/api/health")
async def health():
    return {"status": "ok", "title": "Audio JDM 모델 현황 대시보드"}


@app.get("/api/team-members")
async def get_team_members():
    return [
        {
            "part_id": part_id,
            "part_name": part_info["name"],
            "members": [
                {"id": member_id, "name": display_name}
                for member_id, display_name in part_info["members"].items()
            ],
        }
        for part_id, part_info in TEAM_PARTS.items()
    ]


@app.post("/api/fetch-data")
async def start_fetch_data(request: FetchRequest):
    global _fetch_status
    valid_members = [m for m in request.members if m in TEAM_MEMBERS]
    if not valid_members:
        raise HTTPException(status_code=400, detail="유효한 팀원이 없습니다.")

    if request.source == "jira" and (not CSR_JENKINS_ADMIN_ID or not CSR_JENKINS_ADMIN_PWD):
        raise HTTPException(status_code=500, detail="Jira credentials not configured (.env)")

    with _fetch_lock:
        if _fetch_status["running"]:
            raise HTTPException(status_code=409, detail="이미 검색이 진행 중입니다.")
        _fetch_status = {
            "running": True,
            "progress": 0,
            "total": 100,
            "current_task": "시작...",
            "completed": False,
            "error": None,
            "data": None,
            "cancelled": False,
        }

    thread = threading.Thread(
        target=fetch_data_background,
        args=(valid_members, request.source, request.quick),
        daemon=True,
    )
    thread.start()
    return {"status": "started", "members": valid_members, "source": request.source, "quick": request.quick}


@app.get("/api/fetch-status")
async def get_fetch_status():
    with _fetch_lock:
        return FetchStatus(
            running=_fetch_status["running"],
            progress=_fetch_status["progress"],
            total=_fetch_status["total"],
            current_task=_fetch_status["current_task"],
            completed=_fetch_status["completed"],
            error=_fetch_status.get("error"),
        )


@app.get("/api/dashboard-data")
async def get_dashboard_data():
    with _fetch_lock:
        if not _fetch_status["completed"]:
            raise HTTPException(status_code=404, detail="데이터가 아직 준비되지 않았습니다.")
        if _fetch_status["error"]:
            raise HTTPException(status_code=500, detail=_fetch_status["error"])
        return _fetch_status["data"]


@app.post("/api/cancel-search")
async def cancel_search():
    with _fetch_lock:
        if _fetch_status["running"]:
            _fetch_status["cancelled"] = True
    return {"status": "cancelling"}


@app.post("/api/sync")
async def start_sync(request: SyncRequest):
    global _sync_status
    members = [m for m in (request.members or list(TEAM_MEMBERS.keys())) if m in TEAM_MEMBERS]
    if not members:
        raise HTTPException(status_code=400, detail="유효한 팀원이 없습니다.")

    with _sync_lock:
        if _sync_status["running"]:
            raise HTTPException(status_code=409, detail="이미 동기화가 진행 중입니다.")
        _sync_status = {
            "running": True,
            "progress": 0,
            "current_task": "동기화 시작...",
            "completed": False,
            "error": None,
            "count": 0,
        }

    thread = threading.Thread(target=sync_background, args=(members, request.full), daemon=True)
    thread.start()
    return {"status": "started", "full": request.full, "members": members}


@app.get("/api/sync-status")
async def get_sync_status():
    with _sync_lock:
        return dict(_sync_status)


@app.get("/api/sync-info")
async def get_sync_info():
    """MongoDB 미설정/지연 시에도 UI가 멈추지 않도록 빠르게 fallback."""
    defaults = {
        "has_cache": False,
        "full_sync": None,
        "full_sync_count": 0,
        "incremental_sync": None,
        "incremental_count": 0,
    }
    try:
        return await asyncio.wait_for(asyncio.to_thread(jira_sync.get_last_sync_info), timeout=5.0)
    except Exception as exc:
        logger.warning("sync-info timeout/error, using defaults: %s", exc)
        return defaults


frontend_dir = os.path.join(_DASHBOARD_DIR, "frontend")
if os.path.isdir(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")
