"""Minimal Notion REST client + property extractors.

Rate limits (429) are aggressive on collection queries — space calls and batch.
This client paginates the data-source query and is meant to be driven by the sync
worker on a 2-minute incremental cadence (filter by last_edited_time), NOT to dump
all 606 rows every tick.
"""
from __future__ import annotations

from datetime import date, datetime

import httpx

from .config import settings


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.notion_token}",
        "Notion-Version": settings.notion_version,
        "Content-Type": "application/json",
    }


async def query_database(database_id: str, start_cursor: str | None = None,
                         since: datetime | None = None) -> dict:
    """One page of a database query, optionally filtered to rows edited since `since`."""
    body: dict = {"page_size": 100}
    if start_cursor:
        body["start_cursor"] = start_cursor
    if since is not None:
        body["filter"] = {
            "timestamp": "last_edited_time",
            "last_edited_time": {"on_or_after": since.astimezone().isoformat()},
        }
        body["sorts"] = [{"timestamp": "last_edited_time", "direction": "ascending"}]
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{settings.notion_api_base}/databases/{database_id}/query",
            headers=_headers(), json=body,
        )
        resp.raise_for_status()
        return resp.json()


async def iter_pages(database_id: str, since: datetime | None = None):
    """Yield every page across pagination for an (optionally incremental) query."""
    cursor = None
    while True:
        data = await query_database(database_id, start_cursor=cursor, since=since)
        for page in data.get("results", []):
            yield page
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")


# --- property extractors -----------------------------------------------------
# Notion returns richly-typed property blobs; these pull the scalar we store.

def prop_title(props: dict, key: str) -> str | None:
    arr = (props.get(key) or {}).get("title") or []
    return "".join(t.get("plain_text", "") for t in arr) or None


def prop_select(props: dict, key: str) -> str | None:
    sel = (props.get(key) or {}).get("select")
    return sel.get("name") if sel else None


def prop_status(props: dict, key: str) -> str | None:
    st = (props.get(key) or {}).get("status")
    return st.get("name") if st else None


def prop_number(props: dict, key: str) -> float | None:
    return (props.get(key) or {}).get("number")


def prop_person_id(props: dict, key: str) -> str | None:
    people = (props.get(key) or {}).get("people") or []
    return people[0].get("id") if people else None


def prop_relation_id(props: dict, key: str) -> str | None:
    rel = (props.get(key) or {}).get("relation") or []
    return rel[0].get("id") if rel else None


def prop_date(props: dict, key: str) -> datetime | None:
    d = (props.get(key) or {}).get("date")
    if not d or not d.get("start"):
        return None
    return _parse_ts(d["start"])


def prop_created_or_edited(page: dict, which: str) -> datetime | None:
    val = page.get(which)  # 'created_time' | 'last_edited_time'
    return _parse_ts(val) if val else None


def _parse_ts(raw: str) -> datetime:
    # Notion may hand back a trailing 'Z'; datetime.fromisoformat handles offsets
    # in 3.11+, but normalize 'Z' -> '+00:00' for older interpreters too.
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


def _parse_date(raw: str | None) -> date | None:
    if not raw:
        return None
    return _parse_ts(raw).date()
