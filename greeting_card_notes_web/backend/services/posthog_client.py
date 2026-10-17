"""
Server-side PostHog events.

Only the event name, the account id, and the note id are sent.
Email, names, questionnaire text, and note text are dropped.
If POSTHOG_API_KEY is unset, events are skipped.
"""

from __future__ import annotations

import os
from typing import Optional

import httpx

SAFE_PROPERTIES = {"note_id"}


def build_event(event: str, distinct_id: str, properties: Optional[dict] = None) -> dict:
    """
    Build a PostHog capture body with private fields removed.

    :param event: Event name.
    :param distinct_id: Account id. This is not an email address.
    :param properties: Extra fields. Only note_id is kept.
    :return: JSON body for the capture API.
    """
    safe = {}
    for key, value in (properties or {}).items():
        if key in SAFE_PROPERTIES and value:
            safe[key] = value
    safe["$process_person_profile"] = False
    safe["$ip"] = None
    return {
        "api_key": os.getenv("POSTHOG_API_KEY") or "",
        "event": event,
        "distinct_id": distinct_id,
        "properties": safe,
    }


def capture(event: str, distinct_id: str, properties: Optional[dict] = None) -> None:
    """
    Send one product event. Failures are logged and do not affect the note.

    :param event: Event name.
    :param distinct_id: Account id.
    :param properties: Extra fields. Private text is not sent.
    :return: None
    """
    api_key = os.getenv("POSTHOG_API_KEY")
    if not api_key or not distinct_id:
        return
    host = (os.getenv("POSTHOG_HOST") or "https://us.i.posthog.com").rstrip("/")
    body = build_event(event, distinct_id, properties)
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.post(f"{host}/capture/", json=body)
            response.raise_for_status()
    except Exception as exc:
        print(f"[POSTHOG] {event} was not sent: {exc}", flush=True)
