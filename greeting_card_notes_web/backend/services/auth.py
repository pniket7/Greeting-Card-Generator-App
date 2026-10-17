"""
Verify a Supabase Auth access token by asking Supabase who it belongs to.
"""

from __future__ import annotations

import os
from typing import Optional

import httpx


def fetch_auth_user(access_token: str) -> Optional[dict]:
    """
    Resolve a bearer token to the Supabase auth user.

    :param access_token: The access token from supabase.auth.
    :return: User dict with id and email, or None when the token is rejected.
    """
    base_url = (os.getenv("SUPABASE_URL") or "").rstrip("/")
    api_key = os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not base_url or not api_key or not access_token:
        return None

    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.get(
                f"{base_url}/auth/v1/user",
                headers={
                    "apikey": api_key,
                    "Authorization": f"Bearer {access_token}",
                },
            )
    except httpx.HTTPError:
        return None

    if response.status_code != 200:
        return None

    body = response.json()
    if not isinstance(body, dict) or not body.get("id"):
        return None
    return body
