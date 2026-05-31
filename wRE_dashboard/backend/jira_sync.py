#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Jira <-> MongoDB sync for Audio JDM dashboard."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from typing import Any, Callable

import mongo_helper as mdb

logger = logging.getLogger(__name__)

COLL_ISSUES = "jdm_jira_issues"
COLL_EPIC_INIT = "jdm_epic_init_map"
COLL_SYNC_META = "jdm_sync_meta"
COLL_INITIATIVE_CACHE = "jdm_initiative_cache"


def get_sync_meta(sync_type: str) -> dict | None:
    docs = mdb.query_documents(COLL_SYNC_META, {"sync_type": sync_type})
    return docs[0] if docs else None


def update_sync_meta(sync_type: str, **kwargs: Any) -> None:
    meta = get_sync_meta(sync_type)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data = {"sync_type": sync_type, "last_sync": now, **kwargs}
    if meta and meta.get("_id"):
        mdb.update_document(COLL_SYNC_META, meta["_id"], data)
    else:
        mdb.insert_documents(COLL_SYNC_META, [data])


def issue_to_doc(issue, jira_url: str) -> dict:
    fields = issue.fields

    assignee = ""
    assignee_display = ""
    if getattr(fields, "assignee", None):
        assignee = getattr(fields.assignee, "name", "") or getattr(fields.assignee, "key", "")
        assignee_display = getattr(fields.assignee, "displayName", "") or ""

    status = fields.status.name if getattr(fields, "status", None) else ""
    issue_type = fields.issuetype.name if getattr(fields, "issuetype", None) else ""

    sprint_raw = ""
    sprint_field = getattr(fields, "customfield_10005", None)
    if sprint_field:
        sprint_raw = (
            "|".join(str(s) for s in sprint_field)
            if isinstance(sprint_field, list)
            else str(sprint_field)
        )

    epic_link = getattr(fields, "customfield_11579", None) or ""
    planned_sp = getattr(fields, "customfield_10002", None)
    actual_sp = getattr(fields, "story_points", None)
    description = getattr(fields, "description", None) or ""

    issuelinks_data: list[dict] = []
    if getattr(fields, "issuelinks", None):
        for link in fields.issuelinks:
            link_info: dict[str, str] = {}
            link_type = getattr(link, "type", None)
            if link_type:
                link_info["type_name"] = getattr(link_type, "name", "")
                link_info["type_inward"] = getattr(link_type, "inward", "")
                link_info["type_outward"] = getattr(link_type, "outward", "")
            if getattr(link, "outwardIssue", None):
                oi = link.outwardIssue
                link_info["direction"] = "outward"
                link_info["issue_key"] = oi.key
                link_info["issue_summary"] = (
                    getattr(oi.fields, "summary", "") if hasattr(oi, "fields") else ""
                )
            elif getattr(link, "inwardIssue", None):
                ii = link.inwardIssue
                link_info["direction"] = "inward"
                link_info["issue_key"] = ii.key
                link_info["issue_summary"] = (
                    getattr(ii.fields, "summary", "") if hasattr(ii, "fields") else ""
                )
            if link_info:
                issuelinks_data.append(link_info)

    base = jira_url.rstrip("/")
    return {
        "key": issue.key,
        "issue_type": issue_type,
        "summary": fields.summary or "",
        "status": status,
        "assignee": assignee,
        "assignee_display": assignee_display,
        "description": description,
        "sprint_raw": sprint_raw,
        "epic_link": epic_link,
        "planned_sp": planned_sp,
        "actual_sp": actual_sp or 0,
        "worklog_hours": 0,
        "issuelinks": issuelinks_data,
        "url": f"{base}/browse/{issue.key}",
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def full_sync_issues(
    jira,
    members: list[str],
    jira_url: str,
    progress_callback: Callable[[int, str], None] | None = None,
) -> int:
    t_start = time.time()
    total_synced = 0
    member_list = ", ".join(members)

    if progress_callback:
        progress_callback(5, "Story 전체 동기화 중...")

    story_jql = (
        f"project = TVPLAT AND issuetype in (Story, Task) "
        f"AND created >= 2026-01-01 AND assignee IN ({member_list})"
    )
    try:
        stories = jira.search_issues(
            story_jql,
            maxResults=1000,
            fields="issuetype,summary,status,assignee,description,customfield_10005,customfield_11579,customfield_10002",
        )
    except Exception as exc:
        logger.error("Story sync failed: %s", exc)
        stories = []

    story_docs = [issue_to_doc(s, jira_url) for s in stories]
    if story_docs:
        mdb.delete_all_documents(COLL_ISSUES)
        mdb.insert_documents(COLL_ISSUES, story_docs)
        total_synced += len(story_docs)

    if progress_callback:
        progress_callback(40, "Initiative 전체 동기화 중...")

    init_jql = (
        f"project = TVPLAT AND issuetype = Initiative "
        f"AND created >= 2025-12-01 AND assignee in ({member_list}) "
        f'AND status NOT IN ("CLOSED", "DELIVERED", "DEFERRED")'
    )
    try:
        initiatives = jira.search_issues(
            init_jql,
            maxResults=500,
            fields="issuetype,summary,status,assignee,issuelinks,customfield_10002,customfield_10005",
        )
    except Exception as exc:
        logger.error("Initiative sync failed: %s", exc)
        initiatives = []

    init_docs = [issue_to_doc(i, jira_url) for i in initiatives]
    if init_docs:
        mdb.insert_documents(COLL_ISSUES, init_docs)
        total_synced += len(init_docs)

    epic_init_maps: list[dict] = []
    for init_doc in init_docs:
        for link in init_doc.get("issuelinks", []):
            if (
                link.get("type_outward") == "is published by"
                and link.get("direction") == "outward"
            ):
                epic_key = link.get("issue_key")
                if epic_key:
                    epic_init_maps.append(
                        {
                            "epic_key": epic_key,
                            "init_key": init_doc["key"],
                            "init_summary": init_doc["summary"],
                            "init_status": init_doc["status"],
                            "init_assignee": init_doc.get("assignee", ""),
                            "init_assignee_display": init_doc.get("assignee_display", ""),
                            "init_url": init_doc["url"],
                        }
                    )

    if epic_init_maps:
        mdb.delete_all_documents(COLL_EPIC_INIT)
        mdb.insert_documents(COLL_EPIC_INIT, epic_init_maps)

    update_sync_meta(
        "full_sync",
        issue_count=total_synced,
        duration=round(time.time() - t_start, 1),
    )
    return total_synced


def incremental_sync_issues(
    jira,
    members: list[str],
    jira_url: str,
    progress_callback: Callable[[int, str], None] | None = None,
) -> int:
    t_start = time.time()
    meta = get_sync_meta("full_sync")
    if not meta or not meta.get("last_sync"):
        return full_sync_issues(jira, members, jira_url, progress_callback)

    last_sync = meta["last_sync"]
    try:
        last_dt = datetime.strptime(last_sync, "%Y-%m-%d %H:%M:%S") - timedelta(minutes=5)
        jql_date = last_dt.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        jql_date = last_sync[:16]

    member_list = ", ".join(members)
    jql = (
        f"project = TVPLAT AND issuetype IN (Story, Initiative) "
        f"AND assignee IN ({member_list}) AND updated >= \"{jql_date}\""
    )
    try:
        updated_issues = jira.search_issues(
            jql,
            maxResults=500,
            fields="issuetype,summary,status,assignee,description,customfield_10005,customfield_11579,customfield_10002,issuelinks",
        )
    except Exception as exc:
        logger.error("Incremental sync failed: %s", exc)
        return 0

    if not updated_issues:
        update_sync_meta("incremental_sync", issue_count=0, duration=round(time.time() - t_start, 1))
        return 0

    updated_docs = [issue_to_doc(i, jira_url) for i in updated_issues]
    count = mdb.upsert_by_key(COLL_ISSUES, "key", updated_docs)
    update_sync_meta("incremental_sync", issue_count=count, duration=round(time.time() - t_start, 1))
    return count


def get_last_sync_info() -> dict:
    defaults = {
        "has_cache": False,
        "full_sync": None,
        "full_sync_count": 0,
        "incremental_sync": None,
        "incremental_count": 0,
    }
    try:
        full = get_sync_meta("full_sync")
        incr = get_sync_meta("incremental_sync")
        return {
            "has_cache": full is not None and full.get("last_sync") is not None,
            "full_sync": full.get("last_sync") if full else None,
            "full_sync_count": full.get("issue_count", 0) if full else 0,
            "incremental_sync": incr.get("last_sync") if incr else None,
            "incremental_count": incr.get("issue_count", 0) if incr else 0,
        }
    except Exception as exc:
        logger.warning("get_last_sync_info fallback: %s", exc)
        return defaults


def save_initiative_cache(report_data: dict) -> None:
    mdb.ensure_collection(COLL_INITIATIVE_CACHE)
    existing = mdb.query_documents(COLL_INITIATIVE_CACHE, {"cache_key": "initiative_report"})
    payload = {
        "cache_key": "initiative_report",
        "report_data": report_data,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    if existing and existing[0].get("_id"):
        mdb.update_document(COLL_INITIATIVE_CACHE, existing[0]["_id"], payload)
    else:
        mdb.insert_documents(COLL_INITIATIVE_CACHE, [payload])


def load_initiative_cache(members: list[str]) -> dict | None:
    cached = mdb.query_documents(COLL_INITIATIVE_CACHE, {"cache_key": "initiative_report"})
    if not cached:
        cached = mdb.get_all_documents(COLL_INITIATIVE_CACHE)
    if not cached or not cached[0].get("report_data"):
        return None
    report = cached[0]["report_data"]
    members_set = set(members)
    if "persons" in report:
        report = {
            **report,
            "persons": [p for p in report["persons"] if p.get("name") in members_set],
        }
    return report
