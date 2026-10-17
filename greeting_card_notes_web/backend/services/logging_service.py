"""
Legacy logger for note_sessions and note_events.

The app no longer calls this module. New writes go through note_store.py.
Left here so the old table shape is still documented in code.

Requires env:
  SUPABASE_URL
  SUPABASE_SERVICE_ROLE_KEY

If unset, logging is skipped and the app still runs normally.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import httpx


def is_logging_configured():
    """
    Check whether Supabase logging credentials are present.

    :return: True if URL and service role key are set.
    """
    return bool(os.getenv("SUPABASE_URL")) and bool(os.getenv("SUPABASE_SERVICE_ROLE_KEY"))


def _headers():
    """
    Build Supabase REST headers using the service role key.

    :return: Dict of HTTP headers.
    """
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _base_url():
    """
    Normalize the Supabase project URL.

    :return: Base URL without trailing slash.
    """
    return (os.getenv("SUPABASE_URL") or "").rstrip("/")


def create_note_session(session_row):
    """
    Insert one note_sessions row and return the inserted record.

    :param session_row: Dict matching note_sessions columns.
    :return: Inserted row dict, or None if logging is disabled/failed.
    """
    if not is_logging_configured():
        print("[SUPABASE] Skipping session log — SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set", flush=True)
        return None

    url = f"{_base_url()}/rest/v1/note_sessions"
    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.post(url, headers=_headers(), json=session_row)
            response.raise_for_status()
            rows = response.json()
            inserted = rows[0] if isinstance(rows, list) and rows else rows
            print(f"[SUPABASE] note_sessions inserted id={inserted.get('id')}", flush=True)
            return inserted
    except Exception as exc:
        print(f"[SUPABASE] Failed to insert note_sessions: {exc}", flush=True)
        return None


def update_note_session(session_id, patch):
    """
    Patch fields on an existing note_sessions row.

    :param session_id: UUID string of the session.
    :param patch: Dict of columns to update.
    :return: True on success, False otherwise.
    """
    if not is_logging_configured() or not session_id:
        return False

    url = f"{_base_url()}/rest/v1/note_sessions"
    params = {"id": f"eq.{session_id}"}
    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.patch(url, headers=_headers(), params=params, json=patch)
            response.raise_for_status()
            print(f"[SUPABASE] note_sessions updated id={session_id}", flush=True)
            return True
    except Exception as exc:
        print(f"[SUPABASE] Failed to update note_sessions: {exc}", flush=True)
        return False


def insert_note_events(events):
    """
    Insert one or more note_events rows (prompt/response debug traces).

    :param events: List of event dicts matching note_events columns.
    :return: Number of events inserted, or 0 on failure/skip.
    """
    if not is_logging_configured():
        return 0
    if not events:
        return 0

    url = f"{_base_url()}/rest/v1/note_events"
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(url, headers=_headers(), json=events)
            response.raise_for_status()
            print(f"[SUPABASE] note_events inserted count={len(events)}", flush=True)
            return len(events)
    except Exception as exc:
        print(f"[SUPABASE] Failed to insert note_events: {exc}", flush=True)
        return 0


def log_generate_run(session_id, request_payload, pipeline_result):
    """
    Persist a full generate run: session summary + stage prompt/response events.

    :param session_id: Client/server session UUID (also used as note_sessions.id).
    :param request_payload: Original API request fields.
    :param pipeline_result: Dict returned by generate_greeting_card_note.
    :return: None
    """
    session_row = {
        "id": session_id,
        "email": request_payload.get("email") or "",
        "newsletter_consent": bool(request_payload.get("newsletter_consent") or False),
        "occasion_category": request_payload.get("occasion_category") or "",
        "specific_moment": request_payload.get("specific_moment") or "",
        "recipient_name": request_payload.get("recipient_name") or "",
        "relationship": request_payload.get("relationship") or "",
        "relationship_closeness": request_payload.get("relationship_closeness") or "",
        "known_context": request_payload.get("known_context") or "",
        "user_override": request_payload.get("user_override") or "",
        "sender_name": request_payload.get("sender_name") or "",
        "language": request_payload.get("language") or "English",
        "final_note": pipeline_result.get("final_note") or "",
        "craft_notes": pipeline_result.get("craft_notes") or "",
        "verdict": pipeline_result.get("verdict") or "",
        "attempts": pipeline_result.get("attempts") or 0,
        "refinements_used": 0,
    }
    create_note_session(session_row)

    events = []
    for stage in pipeline_result.get("stage_logs") or []:
        events.append(
            {
                "session_id": session_id,
                "event_type": stage.get("event_type") or "unknown",
                "prompt": stage.get("prompt") or "",
                "response": stage.get("response") or "",
                "parsed_note": stage.get("parsed_note") or "",
                "meta": stage.get("meta") or {},
            }
        )
    insert_note_events(events)


def log_refine_run(session_id, instruction, before_note, refine_result, refinements_used):
    """
    Persist a refine step: update session counters and insert refine event.

    :param session_id: Existing note session UUID.
    :param instruction: Refinement instruction text.
    :param before_note: Note text before refinement.
    :param refine_result: Dict with final_note, prompt, raw_response.
    :param refinements_used: Updated assisted-refinement count.
    :return: None
    """
    if session_id:
        update_note_session(
            session_id,
            {
                "final_note": refine_result.get("final_note") or "",
                "refinements_used": refinements_used,
            },
        )

    insert_note_events(
        [
            {
                "session_id": session_id,
                "event_type": "refine",
                "prompt": refine_result.get("prompt") or "",
                "response": refine_result.get("raw_response") or "",
                "parsed_note": refine_result.get("final_note") or "",
                "meta": {
                    "instruction": instruction,
                    "before_note": before_note,
                    "refinements_used": refinements_used,
                },
            }
        ]
    )
