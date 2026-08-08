"""
FastAPI Backend for "Rooting For You" Greeting Card Notes Web App.
Fully aligned with the Notion specification.
"""

from __future__ import annotations

import sys
import traceback
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

# Resolve path so `backend.*` imports work inside Docker (/app) and locally
APP_DIR = Path(__file__).resolve().parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from backend.services.note_pipeline import (
    generate_greeting_card_note,
    refine_greeting_card_note,
)
from backend.services.logging_service import log_generate_run, log_refine_run

app = FastAPI(
    title="Rooting For You - Notes API",
    description="Modern backend for generating personalized greeting card notes.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory session store (best-effort on free Render; client also sends inputs)
SESSIONS: Dict[str, Dict[str, Any]] = {}

api_router = APIRouter(prefix="/api")

FRONTEND_DIR = APP_DIR / "frontend"
INDEX_HTML = FRONTEND_DIR / "index.html"


class GenerateRequest(BaseModel):
    email: Optional[str] = Field("", description="User's email for saving the note (optional during testing)")
    newsletter_consent: bool = Field(False, description="Optional newsletter subscription")
    occasion_category: str = Field(..., description="celebrate, thank, or comfort")
    specific_moment: str = Field(..., description="Specific occasion like graduation, birthday, etc.")
    recipient_name: str = Field(..., description="Name of the recipient")
    relationship: str = Field(..., description="Relationship to the recipient")
    relationship_closeness: str = Field(..., description="formal, friendly, warm, close, or very_close")
    known_context: str = Field(..., description="Specific facts, details, or memories provided by user")
    sender_intent: Optional[str] = Field(None, description="Optional explicit intent")
    sender_feeling: Optional[str] = Field(None, description="Optional explicit feeling")
    sender_name: Optional[str] = Field("", description="Optional sign-off name")
    language: Optional[str] = Field("English", description="Target language")
    user_override: Optional[str] = Field("", description="Any special user override or custom guidance")


class RefineRequest(BaseModel):
    session_id: Optional[str] = Field(None, description="Session ID from generate (optional)")
    refinement_instruction: str = Field(..., description="Voice/detail refinement instruction")
    current_note: str = Field(..., description="The current note text to refine")
    refinements_used: int = Field(0, description="How many assisted refinements already used")
    # Card inputs are sent from the browser so refine works even if server memory was cleared
    occasion_category: str
    specific_moment: str
    recipient_name: str
    relationship: str
    relationship_closeness: str
    known_context: str
    sender_intent: Optional[str] = None
    sender_feeling: Optional[str] = None
    sender_name: Optional[str] = ""
    language: Optional[str] = "English"
    user_override: Optional[str] = ""


@api_router.get("/health")
async def health():
    """Simple health check used to verify the API is reachable."""
    return {"status": "ok"}


@api_router.post("/generate")
async def api_generate_note(req: GenerateRequest):
    """
    Generate a note using the multi-step write -> review -> revise pipeline.
    """
    print("\n[API] /api/generate received", flush=True)
    print(
        f"[API] email={req.email} category={req.occasion_category} "
        f"moment={req.specific_moment} recipient={req.recipient_name} "
        f"relationship={req.relationship} closeness={req.relationship_closeness}",
        flush=True,
    )
    print(f"[API] known_context={req.known_context}", flush=True)
    print(f"[API] user_override={req.user_override}", flush=True)

    try:
        result = generate_greeting_card_note(
            occasion_category=req.occasion_category,
            specific_moment=req.specific_moment,
            recipient_name=req.recipient_name,
            relationship=req.relationship,
            relationship_closeness=req.relationship_closeness,
            sender_intent=req.sender_intent,
            sender_feeling=req.sender_feeling,
            known_context=req.known_context,
            sender_name=req.sender_name,
            language=req.language,
            user_override=req.user_override,
            enable_review_loop=True,
        )

        session_id = str(uuid.uuid4())
        payload = req.model_dump() if hasattr(req, "model_dump") else req.dict()
        SESSIONS[session_id] = {
            "email": req.email,
            "newsletter_consent": req.newsletter_consent,
            "original_note": result["final_note"],
            "current_note": result["final_note"],
            "refinements_used": 0,
            "refinements_max": 2,
            "inputs": payload,
        }

        # Persist full debug log to Supabase (inputs + prompts + responses)
        try:
            log_generate_run(session_id, payload, result)
        except Exception as log_exc:
            print(f"[API] Supabase generate logging failed (non-fatal): {log_exc}", flush=True)

        print(
            f"[API] /api/generate success session_id={session_id} "
            f"verdict={result.get('verdict')} attempts={result.get('attempts')}",
            flush=True,
        )

        return {
            "session_id": session_id,
            "final_note": result["final_note"],
            "craft_notes": result["craft_notes"],
            "refinements_used": 0,
            "refinements_max": 2,
        }
    except Exception as e:
        print(f"[API] /api/generate FAILED: {e}", flush=True)
        print(traceback.format_exc(), flush=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Generation failed: {str(e)}",
        )


@api_router.post("/refine")
async def api_refine_note(req: RefineRequest):
    """
    Refine an existing note based on an instruction.
    Uses client-sent card inputs so refine still works if Render restarted
    and wiped the in-memory session store.
    """
    print(
        f"\n[API] /api/refine received session_id={req.session_id} "
        f"instruction={req.refinement_instruction} "
        f"refinements_used={req.refinements_used}",
        flush=True,
    )

    refinements_max = 2
    refinements_used = req.refinements_used
    original_note = req.current_note

    session = SESSIONS.get(req.session_id) if req.session_id else None
    if session:
        refinements_used = session["refinements_used"]
        original_note = session.get("original_note", req.current_note)
        print(f"[API] /api/refine using server session count={refinements_used}", flush=True)
    else:
        print(
            "[API] /api/refine session missing — continuing with client-sent inputs",
            flush=True,
        )

    if refinements_used >= refinements_max:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum limit of 2 assisted refinements has been reached for this note.",
        )

    try:
        before_note = req.current_note
        refine_result = refine_greeting_card_note(
            current_note=req.current_note,
            refinement_instruction=req.refinement_instruction,
            occasion_category=req.occasion_category,
            specific_moment=req.specific_moment,
            recipient_name=req.recipient_name,
            relationship=req.relationship,
            relationship_closeness=req.relationship_closeness,
            sender_intent=req.sender_intent,
            sender_feeling=req.sender_feeling,
            known_context=req.known_context,
            sender_name=req.sender_name,
            language=req.language,
            user_override=req.user_override,
        )
        refined_note = refine_result["final_note"]

        refinements_used += 1
        if session:
            session["refinements_used"] = refinements_used
            session["current_note"] = refined_note

        # Persist refine prompt/response to Supabase
        try:
            log_refine_run(
                req.session_id,
                req.refinement_instruction,
                before_note,
                refine_result,
                refinements_used,
            )
        except Exception as log_exc:
            print(f"[API] Supabase refine logging failed (non-fatal): {log_exc}", flush=True)

        print(
            f"[API] /api/refine success refinements_used={refinements_used}",
            flush=True,
        )

        return {
            "session_id": req.session_id,
            "original_note": original_note,
            "final_note": refined_note,
            "refinements_used": refinements_used,
            "refinements_max": refinements_max,
        }
    except Exception as e:
        print(f"[API] /api/refine FAILED: {e}", flush=True)
        print(traceback.format_exc(), flush=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Refinement failed: {str(e)}",
        )


@api_router.get("/session/{session_id}")
async def get_session(session_id: str):
    """Get the current state of a note session."""
    session = SESSIONS.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    return {
        "session_id": session_id,
        "original_note": session["original_note"],
        "current_note": session["current_note"],
        "refinements_used": session["refinements_used"],
        "refinements_max": session["refinements_max"],
    }


app.include_router(api_router)


@app.get("/")
async def serve_index():
    """Serve the editorial SPA homepage."""
    if not INDEX_HTML.exists():
        raise HTTPException(status_code=404, detail=f"Frontend missing at {INDEX_HTML}")
    return FileResponse(INDEX_HTML)


@app.get("/{full_path:path}")
async def serve_spa_or_asset(full_path: str):
    """
    Serve static frontend files. Never intercept /api/* routes
    (those are handled by api_router above).
    """
    # Defense-in-depth: never treat API paths as static files
    if full_path.startswith("api/") or full_path == "api":
        raise HTTPException(status_code=404, detail="API route not found.")

    candidate = FRONTEND_DIR / full_path
    if candidate.is_file():
        return FileResponse(candidate)

    # SPA fallback
    if INDEX_HTML.exists():
        return FileResponse(INDEX_HTML)

    raise HTTPException(status_code=404, detail="Not found.")
