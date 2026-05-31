#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MongoDB REST API helper — delivery-portal-db-watcher wrapper."""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)

MONGO_API_BASE = os.getenv(
    "MONGO_API_BASE",
    "https://delivery-portal-db-watcher.apps.hedej.lge.com",
)
MONGO_API_TOKEN = os.getenv("MONGO_API_TOKEN", "")

MAX_RETRIES = 3
RETRY_DELAY = 1


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {MONGO_API_TOKEN}",
        "Content-Type": "application/json",
    }


def _request(method: str, url: str, **kwargs) -> requests.Response | None:
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.request(
                method, url, headers=_headers(), timeout=30, **kwargs
            )
            if resp.status_code < 500:
                return resp
            logger.warning(
                "MongoDB API %s %s -> %s, retry %s/%s",
                method,
                url,
                resp.status_code,
                attempt + 1,
                MAX_RETRIES,
            )
        except requests.RequestException as exc:
            logger.warning(
                "MongoDB API request failed: %s, retry %s/%s",
                exc,
                attempt + 1,
                MAX_RETRIES,
            )
        if attempt < MAX_RETRIES - 1:
            time.sleep(RETRY_DELAY * (attempt + 1))
    return None


def _extract_data(resp_json: Any) -> Any:
    if isinstance(resp_json, dict) and "data" in resp_json:
        return resp_json["data"]
    return resp_json


def list_collections() -> list[str]:
    resp = _request("GET", f"{MONGO_API_BASE}/api/mongo-collections/")
    if resp and resp.status_code == 200:
        data = resp.json()
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("data", data.get("collections", []))
    return []


def create_collection(name: str) -> bool:
    resp = _request(
        "POST",
        f"{MONGO_API_BASE}/api/mongo-collections/",
        json={"collection_name": name},
    )
    return bool(resp and resp.status_code in (200, 201))


def ensure_collection(name: str) -> bool:
    if name in list_collections():
        return True
    return create_collection(name)


def get_all_documents(collection: str, use_cache: bool = False) -> list[dict]:
    params = {"use_cache": str(use_cache).lower()}
    resp = _request(
        "GET",
        f"{MONGO_API_BASE}/api/mongo-documents/{collection}/",
        params=params,
    )
    if resp and resp.status_code == 200:
        result = _extract_data(resp.json())
        return result if isinstance(result, list) else []
    return []


def query_documents(collection: str, query: dict, direct: bool = True) -> list[dict]:
    params = {"query": json.dumps(query), "direct": str(direct).lower()}
    resp = _request("GET", f"{MONGO_API_BASE}/api/{collection}", params=params)
    if resp and resp.status_code == 200:
        result = _extract_data(resp.json())
        return result if isinstance(result, list) else []
    return []


def insert_documents(collection: str, documents: list[dict]) -> bool:
    if not documents:
        return True
    batch_size = 100
    for i in range(0, len(documents), batch_size):
        batch = documents[i : i + batch_size]
        resp = _request(
            "POST",
            f"{MONGO_API_BASE}/api/mongo-documents/{collection}/",
            json={"documents": batch},
        )
        if not resp or resp.status_code not in (200, 201):
            return False
    return True


def update_document(collection: str, doc_id: str, updates: dict) -> bool:
    resp = _request(
        "PATCH",
        f"{MONGO_API_BASE}/api/mongo-documents/{collection}/{doc_id}",
        json=updates,
    )
    return bool(resp and resp.status_code == 200)


def delete_all_documents(collection: str) -> bool:
    resp = _request(
        "DELETE",
        f"{MONGO_API_BASE}/api/mongo-documents/{collection}/documents/",
    )
    return bool(resp and resp.status_code == 200)


def upsert_by_key(collection: str, key_field: str, documents: list[dict]) -> int:
    if not documents:
        return 0

    existing = get_all_documents(collection, use_cache=False)
    existing_map: dict[str, str] = {}
    for doc in existing:
        key = doc.get(key_field)
        doc_id = doc.get("_id")
        if key and doc_id:
            existing_map[key] = doc_id

    to_insert: list[dict] = []
    updated = 0

    for doc in documents:
        key_val = doc.get(key_field)
        if not key_val:
            continue
        if key_val in existing_map:
            if update_document(collection, existing_map[key_val], doc):
                updated += 1
        else:
            to_insert.append(doc)

    if to_insert and insert_documents(collection, to_insert):
        updated += len(to_insert)

    return updated
