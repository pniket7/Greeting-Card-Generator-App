"""
Small PostgREST client. Uses the service role key. Never send that key to the browser.
"""

from __future__ import annotations

import os
from typing import Any, Optional

import httpx


class SupabaseError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


def is_configured() -> bool:
    return bool(os.getenv("SUPABASE_URL")) and bool(os.getenv("SUPABASE_SERVICE_ROLE_KEY"))


def _base_url() -> str:
    return (os.getenv("SUPABASE_URL") or "").rstrip("/")


def _headers(prefer: str) -> dict:
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or ""
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": prefer,
    }


def request(
    method: str,
    table: str,
    *,
    params: Optional[dict] = None,
    json: Any = None,
    prefer: str = "return=representation",
) -> Any:
    """
    Call one PostgREST endpoint and return the parsed JSON body.

    :param method: HTTP method.
    :param table: Table name under /rest/v1/.
    :param params: Query string, including PostgREST filters.
    :param json: JSON body for insert, update, or upsert.
    :param prefer: PostgREST Prefer header.
    :return: Parsed JSON, or None when the response has no body.
    """
    if not is_configured():
        raise SupabaseError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required.")

    url = f"{_base_url()}/rest/v1/{table}"
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.request(
                method,
                url,
                headers=_headers(prefer),
                params=params,
                json=json,
            )
    except httpx.HTTPError as exc:
        raise SupabaseError(f"Supabase request failed: {exc}") from exc

    if response.status_code >= 400:
        detail = (response.text or "").strip()
        raise SupabaseError(detail or f"Supabase HTTP {response.status_code}", response.status_code)

    if response.status_code == 204 or not response.content:
        return None
    return response.json()
