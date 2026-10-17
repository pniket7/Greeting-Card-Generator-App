"""
FastAPI backend for Rooting For You.

Accounts come from Supabase Auth. Notes, versions, prompts, traces, and
usefulness rows are stored in Postgres. The browser sends the auth token.
This API checks that the note belongs to that person.
"""

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

APP_DIR = Path(__file__).resolve().parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from backend.services.auth import fetch_auth_user
from backend.services.gemini_client import DEFAULT_MODEL
from backend.services.note_pipeline import (
    _normalize_card_inputs,
    generate_greeting_card_note,
    refine_greeting_card_note,
)
from backend.services.note_store import (
    REFINEMENTS_MAX,
    add_output,
    ensure_prompt_version,
    get_for_review,
    get_owned_note,
    list_for_review,
    list_notes,
    mark_copied,
    purge_expired_notes,
    revision_count,
    save_draft,
    save_feedback,
    save_staff_qa,
    set_input_status,
    soft_delete,
    start_generation,
)
from backend.services.posthog_client import capture
from backend.services.supabase_rest import SupabaseError, is_configured

app = FastAPI(
    title="Rooting For You - Notes API",
    description="Accounts, note versions, and usefulness for Rooting For You.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_router = APIRouter(prefix="/api")

FRONTEND_DIR = APP_DIR / "frontend"
INDEX_HTML = FRONTEND_DIR / "index.html"

ALLOWED_CATEGORIES = {"celebrate", "thank", "comfort"}
ALLOWED_CLOSENESS = {"formal", "friendly", "warm", "close", "very_close"}
REASON_TAGS = {
    "too_generic",
    "too_sentimental",
    "wrong_tone",
    "missed_point",
    "invented_detail",
    "strong",
}


class GenerateRequest(BaseModel):
    occasion_category: str
    specific_moment: str
    recipient_name: str = Field(..., min_length=1)
    relationship: str = Field(..., min_length=1)
    relationship_closeness: str
    known_context: str = ""
    sender_name: Optional[str] = ""
    language: Optional[str] = "English"
    user_override: Optional[str] = ""
    note_id: Optional[str] = None


class RefineRequest(BaseModel):
    refinement_instruction: str = Field(..., min_length=1)


class EditRequest(BaseModel):
    content: str = Field(..., min_length=1)


class FeedbackRequest(BaseModel):
    rating: Optional[int] = Field(None, ge=1, le=5)
    reason_tag: Optional[str] = None


class QaRequest(BaseModel):
    qa_score: Optional[int] = Field(None, ge=1, le=5)
    qa_tags: Optional[list[str]] = None
    qa_notes: Optional[str] = None


def _staff_ids() -> set:
    raw = os.getenv("STAFF_USER_IDS") or ""
    return {part.strip() for part in raw.split(",") if part.strip()}


def require_user(authorization: Optional[str] = Header(default=None)) -> dict:
    """
    Require a Supabase access token and return the auth user.

    :param authorization: Authorization header, expected as "Bearer <token>".
    :return: Auth user dict.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sign in required.")
    token = authorization.split(" ", 1)[1].strip()
    user = fetch_auth_user(token)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sign in required.")
    return user


def require_staff(user: dict = Depends(require_user)) -> dict:
    """
    Require a signed-in account listed in STAFF_USER_IDS.

    :param user: Auth user from require_user.
    :return: The same user.
    """
    if user["id"] not in _staff_ids():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Review access is not enabled for this account.")
    return user


def require_purge_secret(authorization: Optional[str] = Header(default=None)) -> None:
    """
    Require the cron secret. A browser session cannot call the purge job.

    :param authorization: Authorization header, expected as "Bearer <CRON_SECRET>".
    :return: None
    """
    secret = os.getenv("CRON_SECRET") or os.getenv("PURGE_SECRET")
    if not secret:
        raise HTTPException(status_code=503, detail="Purge is not configured.")
    if authorization != f"Bearer {secret}":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not allowed.")


def _pipeline_kwargs(fields: dict) -> dict:
    return {
        "occasion_category": fields["occasion_category"],
        "specific_moment": fields["specific_moment"],
        "recipient_name": fields["recipient_name"],
        "relationship": fields["relationship"],
        "relationship_closeness": fields["relationship_closeness"],
        "known_context": fields.get("known_context") or "",
        "sender_name": fields.get("sender_name") or "",
        "language": fields.get("language") or "English",
        "user_override": fields.get("user_override") or "",
    }


def _snapshot(fields: dict) -> dict:
    return {
        "raw": _pipeline_kwargs(fields),
        "normalized": _normalize_card_inputs(**_pipeline_kwargs(fields)),
    }


def _check_choice_fields(fields: dict) -> None:
    if fields["occasion_category"] not in ALLOWED_CATEGORIES:
        raise HTTPException(status_code=400, detail="Choose celebrate, thank, or comfort.")
    if fields["relationship_closeness"] not in ALLOWED_CLOSENESS:
        raise HTTPException(status_code=400, detail="Choose a relationship closeness.")
    if not str(fields.get("specific_moment") or "").strip():
        raise HTTPException(status_code=400, detail="Choose the moment.")


def _http_from_storage(exc: Exception) -> HTTPException:
    """
    Turn a storage or model failure into a short client error.

    :param exc: The caught exception.
    :return: HTTPException safe to show in the browser.
    """
    print(f"[API] request failed: {exc}", flush=True)
    print(traceback.format_exc(), flush=True)
    text = str(exc)
    if "refinement limit reached" in text:
        return HTTPException(
            status_code=400,
            detail="Maximum limit of 2 assisted refinements has been reached for this note.",
        )
    if "GOOGLE_API_KEY" in text:
        return HTTPException(status_code=500, detail="GOOGLE_API_KEY is not set on the server.")
    if isinstance(exc, SupabaseError):
        if not is_configured():
            return HTTPException(status_code=503, detail="Supabase is not configured on the server.")
        missing_table = "PGRST205" in text or "does not exist" in text or "schema cache" in text
        if missing_table:
            return HTTPException(
                status_code=503,
                detail="The new database tables are not created yet. Run supabase_schema.sql in the Supabase SQL editor.",
            )
        return HTTPException(status_code=500, detail="The note could not be saved.")
    return HTTPException(status_code=500, detail="The note could not be written. Try again.")


def _require_note(note_id: str, owner_id: str) -> dict:
    note = get_owned_note(note_id, owner_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found.")
    return note


@api_router.get("/health")
async def health():
    """Report that the API process is up."""
    return {"status": "ok"}


@api_router.get("/config")
async def public_config():
    """
    Return the public Supabase values the browser needs to sign in.
    The anon key is meant to be public. The service role key is not included.
    """
    supabase_url = os.getenv("SUPABASE_URL") or ""
    supabase_anon_key = os.getenv("SUPABASE_ANON_KEY") or ""
    return {
        "supabase_url": supabase_url,
        "supabase_anon_key": supabase_anon_key,
        "auth_configured": bool(supabase_url and supabase_anon_key),
    }


@api_router.get("/notes")
async def api_list_notes(user: dict = Depends(require_user)):
    """List the signed-in person's notes."""
    try:
        return {"notes": list_notes(user["id"])}
    except Exception as exc:
        raise _http_from_storage(exc) from exc


@api_router.get("/notes/{note_id}")
async def api_get_note(note_id: str, user: dict = Depends(require_user)):
    """Load one note owned by the signed-in person."""
    try:
        return _require_note(note_id, user["id"])
    except HTTPException:
        raise
    except Exception as exc:
        raise _http_from_storage(exc) from exc


@api_router.post("/notes/drafts")
async def api_create_draft(req: GenerateRequest, user: dict = Depends(require_user)):
    """Save a questionnaire before a note is written."""
    fields = req.model_dump() if hasattr(req, "model_dump") else req.dict()
    _check_choice_fields(fields)
    try:
        row = save_draft(user["id"], fields, note_id=None)
    except Exception as exc:
        raise _http_from_storage(exc) from exc
    capture("questionnaire_completed", user["id"], {"note_id": row["id"]})
    return {"note_id": row["id"], "status": row["status"]}


@api_router.patch("/notes/{note_id}")
async def api_update_draft(note_id: str, req: GenerateRequest, user: dict = Depends(require_user)):
    """Update a draft or a failed questionnaire owned by the signed-in person."""
    fields = req.model_dump() if hasattr(req, "model_dump") else req.dict()
    _check_choice_fields(fields)
    try:
        row = save_draft(user["id"], fields, note_id=note_id)
    except Exception as exc:
        raise _http_from_storage(exc) from exc
    if not row:
        raise HTTPException(status_code=404, detail="Note not found.")
    return {"note_id": row["id"], "status": row["status"]}


@api_router.post("/notes/generate")
async def api_generate_note(req: GenerateRequest, user: dict = Depends(require_user)):
    """
    Write one note and store the questionnaire, the version, and the model trace.
    """
    fields = req.model_dump() if hasattr(req, "model_dump") else req.dict()
    _check_choice_fields(fields)
    print(
        f"[API] /api/notes/generate user={user['id']} "
        f"category={fields['occasion_category']} moment={fields['specific_moment']}",
        flush=True,
    )

    note_row = None
    saved_output = False
    created_new = not fields.get("note_id")
    try:
        note_row = start_generation(user["id"], fields, note_id=fields.get("note_id"))
        if not note_row:
            raise HTTPException(status_code=404, detail="Note not found.")
        if created_new:
            capture("questionnaire_completed", user["id"], {"note_id": note_row["id"]})
        result = generate_greeting_card_note(**_pipeline_kwargs(fields), enable_review_loop=True)
        prompt_version_id = ensure_prompt_version()
        output = add_output(
            note_id=note_row["id"],
            owner_id=user["id"],
            source="generated",
            content=result["final_note"],
            input_snapshot=_snapshot(fields),
            model=DEFAULT_MODEL,
            prompt_version_id=prompt_version_id,
            traces=result.get("stage_logs") or [],
        )
        saved_output = True
        try:
            set_input_status(note_row["id"], user["id"], "ready")
        except Exception as status_exc:
            print(f"[API] note saved but status update failed: {status_exc}", flush=True)
        print(f"[API] /api/notes/generate saved note_id={note_row['id']}", flush=True)
        capture("note_generated", user["id"], {"note_id": note_row["id"]})
        return {
            "note_id": note_row["id"],
            "output_id": output["id"],
            "final_note": result["final_note"],
            "original_note": result["final_note"],
            "craft_notes": result.get("craft_notes") or "",
            "refinements_used": 0,
            "refinements_max": REFINEMENTS_MAX,
            "feedback": None,
        }
    except HTTPException:
        raise
    except Exception as exc:
        if note_row and not saved_output:
            try:
                set_input_status(note_row["id"], user["id"], "failed")
            except Exception as status_exc:
                print(f"[API] failed to mark note failed: {status_exc}", flush=True)
        raise _http_from_storage(exc) from exc


@api_router.post("/notes/{note_id}/refine")
async def api_refine_note(note_id: str, req: RefineRequest, user: dict = Depends(require_user)):
    """
    Rewrite the current note. The server counts AI rewrites. The cap is two.
    """
    try:
        current = _require_note(note_id, user["id"])
        if not current["current_note"]:
            raise HTTPException(status_code=400, detail="This note has no text to refine.")
        used = revision_count(note_id)
        if used >= REFINEMENTS_MAX:
            raise HTTPException(
                status_code=400,
                detail="Maximum limit of 2 assisted refinements has been reached for this note.",
            )

        fields = current["inputs"]
        refine_result = refine_greeting_card_note(
            current_note=current["current_note"],
            refinement_instruction=req.refinement_instruction,
            **_pipeline_kwargs(fields),
        )
        prompt_version_id = ensure_prompt_version()
        snapshot = _snapshot(fields)
        snapshot["refinement_instruction"] = req.refinement_instruction
        output = add_output(
            note_id=note_id,
            owner_id=user["id"],
            source="revision",
            content=refine_result["final_note"],
            revision_instruction=req.refinement_instruction,
            input_snapshot=snapshot,
            model=DEFAULT_MODEL,
            prompt_version_id=prompt_version_id,
            traces=[
                {
                    "event_type": "refine",
                    "prompt": refine_result.get("prompt") or "",
                    "response": refine_result.get("raw_response") or "",
                    "parsed_note": refine_result.get("final_note") or "",
                    "meta": {"instruction": req.refinement_instruction},
                }
            ],
        )
        saved = _require_note(note_id, user["id"])
        capture("revision_used", user["id"], {"note_id": note_id})
        return {
            "note_id": note_id,
            "output_id": output["id"],
            "original_note": saved["original_note"],
            "final_note": refine_result["final_note"],
            "refinements_used": saved["refinements_used"],
            "refinements_max": REFINEMENTS_MAX,
            "feedback": None,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise _http_from_storage(exc) from exc


@api_router.post("/notes/{note_id}/edits")
async def api_save_edit(note_id: str, req: EditRequest, user: dict = Depends(require_user)):
    """
    Save a hand edit as its own version. This does not count as an AI rewrite.
    """
    try:
        current = _require_note(note_id, user["id"])
        text = req.content.strip()
        if not text:
            raise HTTPException(status_code=400, detail="Note text cannot be empty.")
        if text == (current["current_note"] or "").strip():
            return {
                "note_id": note_id,
                "output_id": current["output_id"],
                "original_note": current["original_note"],
                "final_note": current["current_note"],
                "refinements_used": current["refinements_used"],
                "refinements_max": REFINEMENTS_MAX,
                "feedback": current["feedback"],
            }
        output = add_output(
            note_id=note_id,
            owner_id=user["id"],
            source="user_edit",
            content=text,
        )
        saved = _require_note(note_id, user["id"])
        return {
            "note_id": note_id,
            "output_id": output["id"],
            "original_note": saved["original_note"],
            "final_note": text,
            "refinements_used": saved["refinements_used"],
            "refinements_max": REFINEMENTS_MAX,
            "feedback": None,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise _http_from_storage(exc) from exc


@api_router.delete("/notes/{note_id}")
async def api_delete_note(note_id: str, user: dict = Depends(require_user)):
    """Soft-delete one note. The row is purged later from purge_after."""
    try:
        deleted = soft_delete(note_id, user["id"])
    except Exception as exc:
        raise _http_from_storage(exc) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Note not found.")
    return {"deleted": True}


@api_router.post("/outputs/{output_id}/copied")
async def api_mark_copied(output_id: str, user: dict = Depends(require_user)):
    """Record the first time this version was copied."""
    try:
        found = mark_copied(output_id, user["id"])
    except Exception as exc:
        raise _http_from_storage(exc) from exc
    if found == "missing":
        raise HTTPException(status_code=404, detail="Note not found.")
    if found == "recorded":
        capture("note_copied", user["id"], {"note_id": output_id})
    return {"copied": True}


@api_router.post("/outputs/{output_id}/feedback")
async def api_save_feedback(output_id: str, req: FeedbackRequest, user: dict = Depends(require_user)):
    """Save an optional rating and reason for this version."""
    if req.rating is None and not req.reason_tag:
        raise HTTPException(status_code=400, detail="Add a rating or a reason.")
    if req.reason_tag and req.reason_tag not in REASON_TAGS:
        raise HTTPException(status_code=400, detail="That reason is not one of the allowed tags.")
    try:
        found = save_feedback(output_id, user["id"], req.rating, req.reason_tag)
    except Exception as exc:
        raise _http_from_storage(exc) from exc
    if not found:
        raise HTTPException(status_code=404, detail="Note not found.")
    return {"saved": True}


@api_router.get("/review/access")
async def api_review_access(user: dict = Depends(require_user)):
    """Tell the signed-in person whether they can open the staff review screen."""
    return {"staff": user["id"] in _staff_ids()}


@api_router.get("/review/notes")
async def api_review_list(user: dict = Depends(require_staff)):
    """List notes for scoring. Email addresses are not included."""
    try:
        return {"notes": list_for_review()}
    except Exception as exc:
        raise _http_from_storage(exc) from exc


@api_router.get("/review/notes/{note_id}")
async def api_review_note(note_id: str, user: dict = Depends(require_staff)):
    """Load one note for scoring, without the sender's email."""
    try:
        note = get_for_review(note_id)
    except Exception as exc:
        raise _http_from_storage(exc) from exc
    if not note:
        raise HTTPException(status_code=404, detail="Note not found.")
    return note


@api_router.post("/review/outputs/{output_id}/qa")
async def api_save_qa(output_id: str, req: QaRequest, user: dict = Depends(require_staff)):
    """Save a staff score. The browser cannot write these fields with the anon key."""
    if req.qa_score is None and not req.qa_tags and req.qa_notes is None:
        raise HTTPException(status_code=400, detail="Add a score, a tag, or a note.")
    if req.qa_tags:
        unknown = [tag for tag in req.qa_tags if tag not in REASON_TAGS]
        if unknown:
            raise HTTPException(status_code=400, detail="That reason is not one of the allowed tags.")
    try:
        found = save_staff_qa(output_id, req.qa_score, req.qa_tags, req.qa_notes)
    except Exception as exc:
        raise _http_from_storage(exc) from exc
    if not found:
        raise HTTPException(status_code=404, detail="Note not found.")
    return {"saved": True}


@api_router.api_route("/internal/purge", methods=["GET", "POST"])
async def api_purge_expired(_authorized: None = Depends(require_purge_secret)):
    """Delete notes whose purge time has passed. Called by the daily cron."""
    try:
        purged = purge_expired_notes()
    except Exception as exc:
        raise _http_from_storage(exc) from exc
    return {"purged": purged}


app.include_router(api_router)


@app.get("/")
async def serve_index():
    """Serve the homepage."""
    if not INDEX_HTML.exists():
        raise HTTPException(status_code=404, detail=f"Frontend missing at {INDEX_HTML}")
    return FileResponse(INDEX_HTML)


@app.get("/{full_path:path}")
async def serve_spa_or_asset(full_path: str):
    """
    Serve static frontend files. API routes are registered above this catch-all.
    """
    if full_path.startswith("api/") or full_path == "api":
        raise HTTPException(status_code=404, detail="API route not found.")

    candidate = FRONTEND_DIR / full_path
    if candidate.is_file():
        return FileResponse(candidate)

    if INDEX_HTML.exists():
        return FileResponse(INDEX_HTML)

    raise HTTPException(status_code=404, detail="Not found.")
