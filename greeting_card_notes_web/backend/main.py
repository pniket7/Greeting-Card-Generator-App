"""
FastAPI Backend for "Rooting For You" Greeting Card Notes Web App.
Fully aligned with the Notion specification.
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

# Resolve path to include the backend packages
APP_DIR = Path(__file__).resolve().parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

# Ensure internal modules can be imported
from backend.services.note_pipeline import (
    generate_greeting_card_note,
    refine_greeting_card_note,
)
from backend.services.card_image import note_as_text_bytes, render_card_png

app = FastAPI(
    title="Rooting For You - Notes API",
    description="Modern backend for generating personalized greeting card notes.",
    version="1.0.0",
)

# Enable CORS for frontend flexibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory session store for tracking assisted refinements
# In a production app, this would be SQLite/PostgreSQL/Redis
SESSIONS: Dict[str, Dict[str, Any]] = {}

class GenerateRequest(BaseModel):
    email: str = Field(..., description="User's email for saving the note")
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
    session_id: str = Field(..., description="Session ID returned during initial generation")
    refinement_instruction: str = Field(..., description="Instruction like 'Shorter', 'Warmer', or custom text")
    current_note: str = Field(..., description="The current note text to refine")

@app.post("/api/generate")
async def api_generate_note(req: GenerateRequest):
    """
    Generate a note using the multi-step write -> review -> revise pipeline.
    Creates a session to enforce the limit of 2 assisted refinements.
    """
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
        SESSIONS[session_id] = {
            "email": req.email,
            "newsletter_consent": req.newsletter_consent,
            "original_note": result["final_note"],
            "current_note": result["final_note"],
            "refinements_used": 0,
            "refinements_max": 2,
            "inputs": req.dict(),
        }

        return {
            "session_id": session_id,
            "final_note": result["final_note"],
            "craft_notes": result["craft_notes"],
            "refinements_used": 0,
            "refinements_max": 2,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Generation failed: {str(e)}",
        )

@app.post("/api/refine")
async def api_refine_note(req: RefineRequest):
    """
    Refine an existing note based on an instruction.
    Strictly enforces the limit of 2 assisted refinements per session.
    """
    session = SESSIONS.get(req.session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or expired.",
        )

    if session["refinements_used"] >= session["refinements_max"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum limit of 2 assisted refinements has been reached for this note.",
        )

    try:
        inputs = session["inputs"]
        refined_note = refine_greeting_card_note(
            current_note=req.current_note,
            refinement_instruction=req.refinement_instruction,
            occasion_category=inputs["occasion_category"],
            specific_moment=inputs["specific_moment"],
            recipient_name=inputs["recipient_name"],
            relationship=inputs["relationship"],
            relationship_closeness=inputs["relationship_closeness"],
            sender_intent=inputs["sender_intent"],
            sender_feeling=inputs["sender_feeling"],
            known_context=inputs["known_context"],
            sender_name=inputs["sender_name"],
            language=inputs["language"],
            user_override=inputs["user_override"],
        )

        session["refinements_used"] += 1
        session["current_note"] = refined_note

        return {
            "session_id": req.session_id,
            "original_note": session["original_note"],
            "final_note": refined_note,
            "refinements_used": session["refinements_used"],
            "refinements_max": session["refinements_max"],
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Refinement failed: {str(e)}",
        )

@app.get("/api/session/{session_id}")
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

# Serving the static frontend assets
FRONTEND_DIR = APP_DIR / "greeting_card_notes_web" / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
else:
    # Handle development or missing path gracefully by mounting relatively
    DEV_FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
    DEV_FRONTEND_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/", StaticFiles(directory=str(DEV_FRONTEND_DIR), html=True), name="frontend")
