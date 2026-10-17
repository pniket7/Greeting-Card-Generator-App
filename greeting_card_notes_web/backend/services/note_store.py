"""
Save questionnaires, note versions, prompt bundles, model traces, and usefulness.
The service role key is used here. Callers must already have checked the owner.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from backend.prompts.reviewer_prompt import NOTE_REVIEWER_PROMPT
from backend.prompts.reviser_prompt import NOTE_REVISER_PROMPT
from backend.prompts.writer_prompt import NOTE_WRITER_PROMPT
from backend.services.gemini_client import DEFAULT_MODEL
from backend.services.supabase_rest import SupabaseError, request

REFINEMENTS_MAX = 2
PURGE_AFTER_DAYS = 30
REASON_TAGS = {
    "too_generic",
    "too_sentimental",
    "wrong_tone",
    "missed_point",
    "invented_detail",
    "strong",
}


def _first(rows: Any) -> Optional[dict]:
    if isinstance(rows, list) and rows:
        return rows[0]
    return None


def _rows(rows: Any) -> list:
    return rows if isinstance(rows, list) else []


def prompt_bundle_hash() -> str:
    """
    Hash the three prompt templates and the model name currently in code.

    :return: Hex sha256 digest.
    """
    payload = "\n---\n".join(
        [NOTE_WRITER_PROMPT, NOTE_REVIEWER_PROMPT, NOTE_REVISER_PROMPT, DEFAULT_MODEL]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def ensure_prompt_version() -> str:
    """
    Insert the current prompt bundle once. Later edits of the Python prompts
    create a new row. Existing rows are never updated.

    :return: prompt_version id.
    """
    digest = prompt_bundle_hash()
    existing = _first(
        request(
            "GET",
            "prompt_version",
            params={"content_hash": f"eq.{digest}", "select": "id"},
        )
    )
    if existing:
        return existing["id"]

    try:
        inserted = _first(
            request(
                "POST",
                "prompt_version",
                json={
                    "label": f"bundle {digest[:12]}",
                    "writer_prompt": NOTE_WRITER_PROMPT,
                    "reviewer_prompt": NOTE_REVIEWER_PROMPT,
                    "reviser_prompt": NOTE_REVISER_PROMPT,
                    "content_hash": digest,
                    "model": DEFAULT_MODEL,
                },
            )
        )
    except SupabaseError as exc:
        if exc.status_code != 409:
            raise
        inserted = _first(
            request(
                "GET",
                "prompt_version",
                params={"content_hash": f"eq.{digest}", "select": "id"},
            )
        )
    if not inserted:
        raise SupabaseError("Prompt version was not saved.")
    return inserted["id"]


def create_generating_input(owner_id: str, fields: dict) -> dict:
    """
    Insert a questionnaire and mark it generating.

    :param owner_id: auth.users id.
    :param fields: Column values for the questionnaire.
    :return: Inserted note_input row.
    """
    row = _first(
        request(
            "POST",
            "note_input",
            json={
                "owner_id": owner_id,
                "occasion_category": fields["occasion_category"],
                "specific_moment": fields["specific_moment"],
                "relationship": fields["relationship"],
                "relationship_closeness": fields["relationship_closeness"],
                "recipient_name": fields["recipient_name"],
                "sender_name": fields.get("sender_name") or "",
                "known_context": fields.get("known_context") or "",
                "user_override": fields.get("user_override") or "",
                "language": fields.get("language") or "English",
                "status": "generating",
            },
        )
    )
    if not row:
        raise SupabaseError("Questionnaire was not saved.")
    return row


def set_input_status(note_id: str, owner_id: str, status: str) -> None:
    """
    Set note_input.status for one owner.

    :param note_id: note_input id.
    :param owner_id: auth.users id.
    :param status: draft, generating, ready, failed, or deleted.
    :return: None
    """
    request(
        "PATCH",
        "note_input",
        params={"id": f"eq.{note_id}", "owner_id": f"eq.{owner_id}"},
        json={"status": status},
        prefer="return=minimal",
    )


def get_input(note_id: str, owner_id: str) -> Optional[dict]:
    """
    Load one questionnaire that this person still owns.

    :param note_id: note_input id.
    :param owner_id: auth.users id.
    :return: Row, or None when it is missing or deleted.
    """
    return _first(
        request(
            "GET",
            "note_input",
            params={
                "id": f"eq.{note_id}",
                "owner_id": f"eq.{owner_id}",
                "status": "neq.deleted",
                "select": "*",
            },
        )
    )


def revision_count(note_id: str) -> int:
    """
    Count AI rewrites already saved for one questionnaire.

    :param note_id: note_input id.
    :return: Number of note_output rows with source revision.
    """
    rows = _rows(
        request(
            "GET",
            "note_output",
            params={
                "note_input_id": f"eq.{note_id}",
                "source": "eq.revision",
                "select": "id",
            },
        )
    )
    return len(rows)


def _next_version_number(note_id: str) -> int:
    latest = _first(
        request(
            "GET",
            "note_output",
            params={
                "note_input_id": f"eq.{note_id}",
                "select": "version_number",
                "order": "version_number.desc",
                "limit": "1",
            },
        )
    )
    if not latest:
        return 1
    return int(latest["version_number"]) + 1


def _clear_final(note_id: str) -> None:
    request(
        "PATCH",
        "note_output",
        params={"note_input_id": f"eq.{note_id}", "is_final": "eq.true"},
        json={"is_final": False},
        prefer="return=minimal",
    )


def add_output(
    *,
    note_id: str,
    owner_id: str,
    source: str,
    content: str,
    revision_instruction: Optional[str] = None,
    input_snapshot: Optional[dict] = None,
    model: Optional[str] = None,
    prompt_version_id: Optional[str] = None,
    traces: Optional[list] = None,
) -> dict:
    """
    Save a new final version and an empty usefulness row.

    :param note_id: Parent note_input id.
    :param owner_id: auth.users id.
    :param source: generated, revision, or user_edit.
    :param content: Note text the person sees.
    :param revision_instruction: Rewrite instruction, when source is revision.
    :param input_snapshot: Answers sent to the model. Empty for a hand edit.
    :param model: Model name. Empty for a hand edit.
    :param prompt_version_id: Prompt bundle id. Empty for a hand edit.
    :param traces: Model trace rows to attach to this version.
    :return: Inserted note_output row.
    """
    inserted = _first(
        request(
            "POST",
            "note_output",
            json={
                "note_input_id": note_id,
                "owner_id": owner_id,
                "version_number": _next_version_number(note_id),
                "source": source,
                "content": content,
                "revision_instruction": revision_instruction,
                "input_snapshot": input_snapshot,
                "model": model,
                "prompt_version_id": prompt_version_id,
                "is_final": False,
            },
        )
    )
    if not inserted:
        raise SupabaseError("Note version was not saved.")
    _clear_final(note_id)
    request(
        "PATCH",
        "note_output",
        params={"id": f"eq.{inserted['id']}"},
        json={"is_final": True},
        prefer="return=minimal",
    )
    inserted["is_final"] = True

    request(
        "POST",
        "note_eval",
        json={"note_output_id": inserted["id"], "owner_id": owner_id},
    )

    if traces:
        payload = []
        for stage in traces:
            meta = stage.get("meta") or {}
            payload.append(
                {
                    "note_output_id": inserted["id"],
                    "note_input_id": note_id,
                    "event_type": stage.get("event_type") or "writer",
                    "prompt": stage.get("prompt") or "",
                    "response": stage.get("response") or "",
                    "parsed_note": stage.get("parsed_note") or "",
                    "verdict": meta.get("verdict"),
                    "failures": meta.get("failures"),
                    "meta": meta,
                }
            )
        request("POST", "note_trace", json=payload)

    return inserted


def list_notes(owner_id: str) -> list:
    """
    List this person's questionnaires, newest first, with a short preview.

    :param owner_id: auth.users id.
    :return: List of summary dicts.
    """
    inputs = _rows(
        request(
            "GET",
            "note_input",
            params={
                "owner_id": f"eq.{owner_id}",
                "status": "neq.deleted",
                "select": "id,recipient_name,occasion_category,specific_moment,status,updated_at",
                "order": "updated_at.desc",
            },
        )
    )
    finals = _rows(
        request(
            "GET",
            "note_output",
            params={
                "owner_id": f"eq.{owner_id}",
                "is_final": "eq.true",
                "select": "note_input_id,content",
            },
        )
    )
    preview_by_input = {row["note_input_id"]: row.get("content") or "" for row in finals}
    summaries = []
    for row in inputs:
        preview = " ".join((preview_by_input.get(row["id"]) or "").split())
        if len(preview) > 140:
            preview = preview[:137] + "..."
        summaries.append(
            {
                "id": row["id"],
                "recipient_name": row["recipient_name"],
                "occasion_category": row["occasion_category"],
                "specific_moment": row["specific_moment"],
                "status": row["status"],
                "updated_at": row["updated_at"],
                "preview": preview,
            }
        )
    return summaries


def _feedback_for(output_id: Optional[str], owner_id: str) -> Optional[dict]:
    if not output_id:
        return None
    row = _first(
        request(
            "GET",
            "note_eval",
            params={
                "note_output_id": f"eq.{output_id}",
                "owner_id": f"eq.{owner_id}",
                "select": "rating,reason_tag,copied_at",
            },
        )
    )
    if not row:
        return None
    return {
        "rating": row.get("rating"),
        "reason_tag": row.get("reason_tag"),
        "copied_at": row.get("copied_at"),
    }


def get_owned_note(note_id: str, owner_id: str) -> Optional[dict]:
    """
    Load one note for the result screen.

    :param note_id: note_input id.
    :param owner_id: auth.users id.
    :return: Note payload, or None when this person cannot see it.
    """
    note = get_input(note_id, owner_id)
    if not note:
        return None

    outputs = _rows(
        request(
            "GET",
            "note_output",
            params={
                "note_input_id": f"eq.{note_id}",
                "owner_id": f"eq.{owner_id}",
                "select": "id,source,content,version_number,is_final",
                "order": "version_number.asc",
            },
        )
    )
    original = next((row["content"] for row in outputs if row["source"] == "generated"), "")
    current = next((row for row in outputs if row.get("is_final")), None)
    if current is None and outputs:
        current = outputs[-1]

    return {
        "id": note["id"],
        "status": note["status"],
        "inputs": {
            "occasion_category": note["occasion_category"],
            "specific_moment": note["specific_moment"],
            "recipient_name": note["recipient_name"],
            "relationship": note["relationship"],
            "relationship_closeness": note["relationship_closeness"],
            "known_context": note["known_context"],
            "sender_name": note["sender_name"],
            "user_override": note["user_override"],
            "language": note["language"],
        },
        "original_note": original,
        "current_note": current["content"] if current else "",
        "output_id": current["id"] if current else None,
        "refinements_used": revision_count(note_id),
        "refinements_max": REFINEMENTS_MAX,
        "feedback": _feedback_for(current["id"] if current else None, owner_id),
    }


def soft_delete(note_id: str, owner_id: str) -> bool:
    """
    Mark a questionnaire deleted and set the purge time.

    :param note_id: note_input id.
    :param owner_id: auth.users id.
    :return: True when a row was updated.
    """
    now = datetime.now(timezone.utc)
    rows = request(
        "PATCH",
        "note_input",
        params={
            "id": f"eq.{note_id}",
            "owner_id": f"eq.{owner_id}",
            "status": "neq.deleted",
        },
        json={
            "status": "deleted",
            "deleted_at": now.isoformat(),
            "purge_after": (now + timedelta(days=PURGE_AFTER_DAYS)).isoformat(),
        },
    )
    return bool(rows)


def mark_copied(output_id: str, owner_id: str) -> bool:
    """
    Record the first time this version was copied.

    :param output_id: note_output id.
    :param owner_id: auth.users id.
    :return: True when the version belongs to this person.
    """
    owned = _first(
        request(
            "GET",
            "note_output",
            params={
                "id": f"eq.{output_id}",
                "owner_id": f"eq.{owner_id}",
                "select": "id",
            },
        )
    )
    if not owned:
        return "missing"

    existing = _first(
        request(
            "GET",
            "note_eval",
            params={
                "note_output_id": f"eq.{output_id}",
                "owner_id": f"eq.{owner_id}",
                "select": "id,copied_at",
            },
        )
    )
    if not existing:
        request(
            "POST",
            "note_eval",
            json={
                "note_output_id": output_id,
                "owner_id": owner_id,
                "copied_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return "recorded"
    if existing.get("copied_at"):
        return "already"
    request(
        "PATCH",
        "note_eval",
        params={"id": f"eq.{existing['id']}"},
        json={"copied_at": datetime.now(timezone.utc).isoformat()},
        prefer="return=minimal",
    )
    return "recorded"


def save_feedback(
    output_id: str,
    owner_id: str,
    rating: Optional[int],
    reason_tag: Optional[str],
) -> bool:
    """
    Save the person's rating and reason for one note version.

    :param output_id: note_output id.
    :param owner_id: auth.users id.
    :param rating: 1 to 5, or None to leave it unchanged when omitted by the caller.
    :param reason_tag: One of REASON_TAGS, or None.
    :return: True when the version belongs to this person.
    """
    owned = _first(
        request(
            "GET",
            "note_output",
            params={
                "id": f"eq.{output_id}",
                "owner_id": f"eq.{owner_id}",
                "select": "id",
            },
        )
    )
    if not owned:
        return False

    patch: dict[str, Any] = {}
    if rating is not None:
        patch["rating"] = rating
    if reason_tag is not None:
        patch["reason_tag"] = reason_tag

    existing = _first(
        request(
            "GET",
            "note_eval",
            params={
                "note_output_id": f"eq.{output_id}",
                "owner_id": f"eq.{owner_id}",
                "select": "id",
            },
        )
    )
    if not existing:
        request(
            "POST",
            "note_eval",
            json={"note_output_id": output_id, "owner_id": owner_id, **patch},
        )
        return True
    if patch:
        request(
            "PATCH",
            "note_eval",
            params={"id": f"eq.{existing['id']}"},
            json=patch,
            prefer="return=minimal",
        )
    return True


def _questionnaire_values(fields: dict) -> dict:
    return {
        "occasion_category": fields["occasion_category"],
        "specific_moment": fields["specific_moment"],
        "relationship": fields["relationship"],
        "relationship_closeness": fields["relationship_closeness"],
        "recipient_name": fields["recipient_name"],
        "sender_name": fields.get("sender_name") or "",
        "known_context": fields.get("known_context") or "",
        "user_override": fields.get("user_override") or "",
        "language": fields.get("language") or "English",
    }


def save_draft(owner_id: str, fields: dict, note_id: Optional[str] = None) -> Optional[dict]:
    """
    Insert a draft, or update a draft or failed questionnaire this person owns.

    :param owner_id: auth.users id.
    :param fields: Questionnaire fields.
    :param note_id: Existing note_input id, when updating.
    :return: The row, or None when the id is not an editable note for this person.
    """
    values = _questionnaire_values(fields)
    if not note_id:
        row = _first(
            request(
                "POST",
                "note_input",
                json={"owner_id": owner_id, "status": "draft", **values},
            )
        )
        if not row:
            raise SupabaseError("Draft was not saved.")
        return row

    rows = request(
        "PATCH",
        "note_input",
        params={
            "id": f"eq.{note_id}",
            "owner_id": f"eq.{owner_id}",
            "status": "in.(draft,failed)",
        },
        json=values,
    )
    return _first(rows)


def start_generation(owner_id: str, fields: dict, note_id: Optional[str] = None) -> Optional[dict]:
    """
    Mark a questionnaire generating. A new row is created when note_id is empty.
    An existing row is used only when this person owns it and it is still a draft or a failure.

    :param owner_id: auth.users id.
    :param fields: Questionnaire fields.
    :param note_id: Optional existing note_input id.
    :return: The generating row, or None when the existing id cannot be used.
    """
    values = _questionnaire_values(fields)
    if not note_id:
        return create_generating_input(owner_id, fields)

    rows = request(
        "PATCH",
        "note_input",
        params={
            "id": f"eq.{note_id}",
            "owner_id": f"eq.{owner_id}",
            "status": "in.(draft,failed)",
        },
        json={**values, "status": "generating"},
    )
    return _first(rows)


def purge_expired_notes() -> int:
    """
    Delete questionnaires whose purge time has passed. Child rows cascade.

    :return: Number of questionnaires deleted.
    """
    now = datetime.now(timezone.utc).isoformat()
    expired = _rows(
        request(
            "GET",
            "note_input",
            params={
                "status": "eq.deleted",
                "purge_after": f"lt.{now}",
                "select": "id",
            },
        )
    )
    if not expired:
        return 0
    id_list = ",".join(row["id"] for row in expired)
    request(
        "DELETE",
        "note_input",
        params={"id": f"in.({id_list})"},
        prefer="return=minimal",
    )
    return len(expired)


def list_for_review() -> list:
    """
    List notes for staff scoring. The sender's email is not selected.

    :return: Summary rows without owner email.
    """
    rows = _rows(
        request(
            "GET",
            "note_input",
            params={
                "status": "neq.deleted",
                "select": "id,recipient_name,occasion_category,specific_moment,relationship,status,updated_at",
                "order": "updated_at.desc",
            },
        )
    )
    return [
        {
            "id": row["id"],
            "recipient_name": row.get("recipient_name") or "",
            "occasion_category": row.get("occasion_category") or "",
            "specific_moment": row.get("specific_moment") or "",
            "relationship": row.get("relationship") or "",
            "status": row.get("status") or "",
            "updated_at": row.get("updated_at"),
        }
        for row in rows
    ]


def get_for_review(note_id: str) -> Optional[dict]:
    """
    Load one note for staff scoring, without the sender's email or account id.

    :param note_id: note_input id.
    :return: Review payload, or None when the note is missing.
    """
    note = _first(
        request(
            "GET",
            "note_input",
            params={
                "id": f"eq.{note_id}",
                "status": "neq.deleted",
                "select": "id,status,occasion_category,specific_moment,relationship,relationship_closeness,recipient_name,sender_name,known_context,user_override,language",
            },
        )
    )
    if not note:
        return None
    outputs = _rows(
        request(
            "GET",
            "note_output",
            params={
                "note_input_id": f"eq.{note_id}",
                "select": "id,source,content,version_number,is_final",
                "order": "version_number.asc",
            },
        )
    )
    eval_by_output = {}
    if outputs:
        id_list = ",".join(row["id"] for row in outputs)
        evals = _rows(
            request(
                "GET",
                "note_eval",
                params={
                    "note_output_id": f"in.({id_list})",
                    "select": "note_output_id,rating,reason_tag,copied_at,qa_score,qa_tags,qa_notes",
                },
            )
        )
        eval_by_output = {row["note_output_id"]: row for row in evals}
    versions = []
    for output in outputs:
        quality = eval_by_output.get(output["id"]) or {}
        versions.append(
            {
                "id": output["id"],
                "source": output["source"],
                "content": output["content"],
                "version_number": output["version_number"],
                "is_final": output["is_final"],
                "rating": quality.get("rating"),
                "reason_tag": quality.get("reason_tag"),
                "copied_at": quality.get("copied_at"),
                "qa_score": quality.get("qa_score"),
                "qa_tags": quality.get("qa_tags") or [],
                "qa_notes": quality.get("qa_notes") or "",
            }
        )
    return {
        "id": note["id"],
        "status": note["status"],
        "inputs": {
            "occasion_category": note["occasion_category"],
            "specific_moment": note["specific_moment"],
            "relationship": note["relationship"],
            "relationship_closeness": note["relationship_closeness"],
            "recipient_name": note["recipient_name"],
            "sender_name": note["sender_name"],
            "known_context": note["known_context"],
            "user_override": note["user_override"],
            "language": note["language"],
        },
        "versions": versions,
    }


def save_staff_qa(output_id: str, qa_score: Optional[int], qa_tags: Optional[list], qa_notes: Optional[str]) -> bool:
    """
    Write the staff score for one note version.

    :param output_id: note_output id.
    :param qa_score: Optional score from 1 to 5.
    :param qa_tags: Optional reason tags.
    :param qa_notes: Optional staff note.
    :return: True when the version exists.
    """
    output = _first(
        request(
            "GET",
            "note_output",
            params={"id": f"eq.{output_id}", "select": "id,owner_id"},
        )
    )
    if not output:
        return False
    patch: dict[str, Any] = {}
    if qa_score is not None:
        patch["qa_score"] = qa_score
    if qa_tags is not None:
        patch["qa_tags"] = qa_tags
    if qa_notes is not None:
        patch["qa_notes"] = qa_notes
    existing = _first(
        request(
            "GET",
            "note_eval",
            params={"note_output_id": f"eq.{output_id}", "select": "id"},
        )
    )
    if not existing:
        request(
            "POST",
            "note_eval",
            json={"note_output_id": output_id, "owner_id": output["owner_id"], **patch},
        )
        return True
    if patch:
        request(
            "PATCH",
            "note_eval",
            params={"id": f"eq.{existing['id']}"},
            json=patch,
            prefer="return=minimal",
        )
    return True
