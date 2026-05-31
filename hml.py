#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""사내 Jira 래퍼 — python-jira 기반 LgJira."""

from __future__ import annotations

from jira import JIRA


class LgJira:
    """LG Jira REST API thin wrapper."""

    def __init__(self, server: str, basic_auth: tuple[str, str]):
        self.server = server.rstrip("/")
        self._client = JIRA(server=self.server, basic_auth=basic_auth)

    def search_issues(self, jql: str, maxResults: int = 500, fields: str | None = None):
        return self._client.search_issues(jql, maxResults=maxResults, fields=fields)

    def issue(self, key: str, fields: str | None = None):
        return self._client.issue(key, fields=fields)
