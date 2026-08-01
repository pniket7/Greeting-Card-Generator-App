"""
Generate -> review -> revise pipeline for greeting-card notes.
"""

from greeting_card_notes.prompts.writer_prompt import NOTE_WRITER_PROMPT
from greeting_card_notes.prompts.reviewer_prompt import NOTE_REVIEWER_PROMPT
from greeting_card_notes.prompts.reviser_prompt import NOTE_REVISER_PROMPT
from greeting_card_notes.services.gemini_client import DEFAULT_MODEL, generate_text
from greeting_card_notes.services.parsers import (
    format_failures_for_reviser,
    parse_craft_or_revision_notes,
    parse_final_note,
    parse_review,
)

MAX_REVIEW_LOOPS = 1


def _normalize_card_inputs(
    occasion,
    recipient_name,
    relationship,
    years_known,
    tone,
    length_preference,
    personal_details,
    sender_name="",
    language="English",
    additional_guidance="",
):
    """
    Normalize card request fields before prompt formatting.

    :param occasion: The card occasion.
    :param recipient_name: The recipient name.
    :param relationship: The relationship to the recipient.
    :param years_known: How long the sender has known the recipient.
    :param tone: The requested tone.
    :param length_preference: Short, Medium, or Long.
    :param personal_details: Personal details that should ground the note.
    :param sender_name: Optional sender name for sign-off.
    :param language: Output language for the note.
    :param additional_guidance: Optional extra writing guidance.
    :return: Dict of normalized fields for prompt formatting.
    """
    # Normalize empty / missing fields into prompt-safe defaults
    return {
        "occasion": occasion or "Not specified",
        "recipient_name": recipient_name or "Not specified",
        "relationship": relationship or "Not specified",
        "years_known": years_known or "Not specified",
        "tone": tone or "Warm and sincere",
        "length_preference": length_preference or "Medium",
        "sender_name": sender_name.strip() if sender_name and str(sender_name).strip() else "Not provided",
        "language": language or "English",
        "personal_details": (
            personal_details.strip()
            if personal_details and str(personal_details).strip()
            else "No specific personal details provided."
        ),
        "additional_guidance": (
            additional_guidance.strip()
            if additional_guidance and str(additional_guidance).strip()
            else "None"
        ),
    }


def generate_writer_note(
    occasion,
    recipient_name,
    relationship,
    years_known,
    tone,
    length_preference,
    personal_details,
    sender_name="",
    language="English",
    additional_guidance="",
    model=DEFAULT_MODEL,
):
    """
    Generate an initial greeting-card note draft from the writer prompt.

    :param occasion: The card occasion.
    :param recipient_name: The recipient name.
    :param relationship: The relationship to the recipient.
    :param years_known: How long the sender has known the recipient.
    :param tone: The requested tone.
    :param length_preference: Short, Medium, or Long.
    :param personal_details: Personal details that should ground the note.
    :param sender_name: Optional sender name for sign-off.
    :param language: Output language for the note.
    :param additional_guidance: Optional extra writing guidance.
    :param model: The Gemini model to use.
    :return: Dict with draft_note, craft_notes, and raw_response.
    """
    # Normalize inputs for prompt formatting
    inputs = _normalize_card_inputs(
        occasion,
        recipient_name,
        relationship,
        years_known,
        tone,
        length_preference,
        personal_details,
        sender_name=sender_name,
        language=language,
        additional_guidance=additional_guidance,
    )

    # Format the writer prompt
    prompt = NOTE_WRITER_PROMPT.format(
        occasion=inputs["occasion"],
        recipient_name=inputs["recipient_name"],
        relationship=inputs["relationship"],
        years_known=inputs["years_known"],
        tone=inputs["tone"],
        length_preference=inputs["length_preference"],
        sender_name=inputs["sender_name"],
        language=inputs["language"],
        personal_details=inputs["personal_details"],
        additional_guidance=inputs["additional_guidance"],
    )

    # Run the writer agent
    response = generate_text(prompt, model=model, temperature=0.8)

    # Parse writer output
    draft_note = parse_final_note(response)
    craft_notes = parse_craft_or_revision_notes(response)

    return {
        "draft_note": draft_note,
        "craft_notes": craft_notes,
        "raw_response": response,
    }


def review_greeting_card_note(
    draft_note,
    occasion,
    recipient_name,
    relationship,
    years_known,
    tone,
    length_preference,
    personal_details,
    sender_name="",
    language="English",
    additional_guidance="",
    model=DEFAULT_MODEL,
):
    """
    Review a drafted greeting-card note against quality criteria.

    :param draft_note: The drafted note text to review.
    :param occasion: The card occasion.
    :param recipient_name: The recipient name.
    :param relationship: The relationship to the recipient.
    :param years_known: How long the sender has known the recipient.
    :param tone: The requested tone.
    :param length_preference: Short, Medium, or Long.
    :param personal_details: Personal details that should ground the note.
    :param sender_name: Optional sender name for sign-off.
    :param language: Output language for the note.
    :param additional_guidance: Optional extra writing guidance.
    :param model: The Gemini model to use.
    :return: Dict with verdict, failures, evaluation_breakdown, and raw_response.
    """
    # Normalize inputs for prompt formatting
    inputs = _normalize_card_inputs(
        occasion,
        recipient_name,
        relationship,
        years_known,
        tone,
        length_preference,
        personal_details,
        sender_name=sender_name,
        language=language,
        additional_guidance=additional_guidance,
    )

    # Format the reviewer prompt
    prompt = NOTE_REVIEWER_PROMPT.format(
        occasion=inputs["occasion"],
        recipient_name=inputs["recipient_name"],
        relationship=inputs["relationship"],
        years_known=inputs["years_known"],
        tone=inputs["tone"],
        length_preference=inputs["length_preference"],
        sender_name=inputs["sender_name"],
        language=inputs["language"],
        personal_details=inputs["personal_details"],
        additional_guidance=inputs["additional_guidance"],
        draft_note=draft_note or "",
    )

    # Run the reviewer agent
    response = generate_text(prompt, model=model, temperature=0.2)

    # Parse reviewer output
    review = parse_review(response)
    return {
        "verdict": review["verdict"],
        "failures": review["failures"],
        "evaluation_breakdown": review["evaluation_breakdown"],
        "raw_response": response,
    }


def revise_greeting_card_note(
    draft_note,
    review_feedback,
    occasion,
    recipient_name,
    relationship,
    years_known,
    tone,
    length_preference,
    personal_details,
    sender_name="",
    language="English",
    additional_guidance="",
    model=DEFAULT_MODEL,
):
    """
    Revise a greeting-card note using reviewer failure feedback.

    :param draft_note: The current drafted note text.
    :param review_feedback: Formatted failure feedback from the reviewer.
    :param occasion: The card occasion.
    :param recipient_name: The recipient name.
    :param relationship: The relationship to the recipient.
    :param years_known: How long the sender has known the recipient.
    :param tone: The requested tone.
    :param length_preference: Short, Medium, or Long.
    :param personal_details: Personal details that should ground the note.
    :param sender_name: Optional sender name for sign-off.
    :param language: Output language for the note.
    :param additional_guidance: Optional extra writing guidance.
    :param model: The Gemini model to use.
    :return: Dict with revised_note, revision_summary, and raw_response.
    """
    # Normalize inputs for prompt formatting
    inputs = _normalize_card_inputs(
        occasion,
        recipient_name,
        relationship,
        years_known,
        tone,
        length_preference,
        personal_details,
        sender_name=sender_name,
        language=language,
        additional_guidance=additional_guidance,
    )

    # Format the reviser prompt
    prompt = NOTE_REVISER_PROMPT.format(
        occasion=inputs["occasion"],
        recipient_name=inputs["recipient_name"],
        relationship=inputs["relationship"],
        years_known=inputs["years_known"],
        tone=inputs["tone"],
        length_preference=inputs["length_preference"],
        sender_name=inputs["sender_name"],
        language=inputs["language"],
        personal_details=inputs["personal_details"],
        additional_guidance=inputs["additional_guidance"],
        draft_note=draft_note or "",
        review_feedback=review_feedback or "No feedback provided.",
    )

    # Run the reviser agent
    response = generate_text(prompt, model=model, temperature=0.6)

    # Parse reviser output
    revised_note = parse_final_note(response)
    revision_summary = parse_craft_or_revision_notes(response)

    return {
        "revised_note": revised_note,
        "revision_summary": revision_summary,
        "raw_response": response,
    }


def generate_greeting_card_note(
    occasion,
    recipient_name,
    relationship,
    years_known,
    tone,
    length_preference,
    personal_details,
    sender_name="",
    language="English",
    additional_guidance="",
    model=DEFAULT_MODEL,
    enable_review_loop=True,
    max_review_loops=MAX_REVIEW_LOOPS,
):
    """
    Generate a personal greeting-card note using a write -> review -> revise loop.

    :param occasion: The card occasion.
    :param recipient_name: The recipient name.
    :param relationship: The relationship to the recipient.
    :param years_known: How long the sender has known the recipient.
    :param tone: The requested tone.
    :param length_preference: Short, Medium, or Long.
    :param personal_details: Personal details that should ground the note.
    :param sender_name: Optional sender name for sign-off.
    :param language: Output language for the note.
    :param additional_guidance: Optional extra writing guidance.
    :param model: The Gemini model to use.
    :param enable_review_loop: Whether to run the review -> revise loop.
    :param max_review_loops: Maximum number of review attempts.
    :return: Dict with final_note, verdict, attempts, craft_notes, and review_history.
    """
    # Generate the initial draft
    writer_result = generate_writer_note(
        occasion,
        recipient_name,
        relationship,
        years_known,
        tone,
        length_preference,
        personal_details,
        sender_name=sender_name,
        language=language,
        additional_guidance=additional_guidance,
        model=model,
    )
    current_note = writer_result["draft_note"]
    craft_notes = writer_result["craft_notes"]

    # Optionally skip review loop for faster prototyping
    if not enable_review_loop:
        return {
            "final_note": current_note,
            "verdict": "SKIPPED_REVIEW",
            "attempts": 1,
            "craft_notes": craft_notes,
            "review_history": [],
            "writer_raw": writer_result["raw_response"],
            "last_reviser_raw": "",
        }

    # Run review -> revise until PASS or max loops reached
    review_history = []
    last_reviser_raw = ""
    final_verdict = "FAIL"

    for attempt in range(1, max_review_loops + 1):
        # Review the current note
        review_result = review_greeting_card_note(
            current_note,
            occasion,
            recipient_name,
            relationship,
            years_known,
            tone,
            length_preference,
            personal_details,
            sender_name=sender_name,
            language=language,
            additional_guidance=additional_guidance,
            model=model,
        )
        review_history.append(
            {
                "attempt": attempt,
                "verdict": review_result["verdict"],
                "failures": review_result["failures"],
                "raw": review_result["raw_response"],
            }
        )
        final_verdict = review_result["verdict"]

        # Stop early on PASS
        if review_result["verdict"] == "PASS":
            break

        # Revise based on reviewer failures (one revise per failed review attempt)
        feedback = format_failures_for_reviser(review_result["failures"])
        reviser_result = revise_greeting_card_note(
            current_note,
            feedback,
            occasion,
            recipient_name,
            relationship,
            years_known,
            tone,
            length_preference,
            personal_details,
            sender_name=sender_name,
            language=language,
            additional_guidance=additional_guidance,
            model=model,
        )
        current_note = reviser_result["revised_note"]
        last_reviser_raw = reviser_result["raw_response"]
        if reviser_result["revision_summary"]:
            craft_notes = reviser_result["revision_summary"]

    return {
        "final_note": current_note,
        "verdict": final_verdict,
        "attempts": len(review_history),
        "craft_notes": craft_notes,
        "review_history": review_history,
        "writer_raw": writer_result["raw_response"],
        "last_reviser_raw": last_reviser_raw,
    }


def refine_greeting_card_note(
    current_note,
    refinement_instruction,
    occasion,
    recipient_name,
    relationship,
    years_known,
    tone,
    length_preference,
    personal_details,
    sender_name="",
    language="English",
    additional_guidance="",
    model=DEFAULT_MODEL,
):
    """
    Quickly refine an existing note (shorter / warmer / etc.) without a full review loop.

    :param current_note: The existing note text to rewrite.
    :param refinement_instruction: The refinement instruction to apply.
    :param occasion: The card occasion.
    :param recipient_name: The recipient name.
    :param relationship: The relationship to the recipient.
    :param years_known: How long the sender has known the recipient.
    :param tone: The requested tone.
    :param length_preference: Short, Medium, or Long.
    :param personal_details: Personal details that should ground the note.
    :param sender_name: Optional sender name for sign-off.
    :param language: Output language for the note.
    :param additional_guidance: Optional extra writing guidance.
    :param model: The Gemini model to use.
    :return: The refined copy-ready note text.
    """
    # Build combined guidance that includes the existing draft and refinement ask
    combined_guidance = (
        f"{additional_guidance}\n\n"
        f"Refinement instruction for this rewrite: {refinement_instruction}\n\n"
        f"Rewrite the following existing draft according to the refinement instruction. "
        f"Keep factual grounding and occasion fit.\n\n"
        f"<existing_draft>\n{current_note}\n</existing_draft>"
    ).strip()

    # Reuse the writer path for a single-pass refinement
    writer_result = generate_writer_note(
        occasion,
        recipient_name,
        relationship,
        years_known,
        tone,
        length_preference,
        personal_details,
        sender_name=sender_name,
        language=language,
        additional_guidance=combined_guidance,
        model=model,
    )
    return writer_result["draft_note"]
