"""
Generate -> review -> revise pipeline for greeting-card notes.
Supports Notion structured inputs, rules, and training examples.
"""

from ..prompts.writer_prompt import NOTE_WRITER_PROMPT
from ..prompts.reviewer_prompt import NOTE_REVIEWER_PROMPT
from ..prompts.reviser_prompt import NOTE_REVISER_PROMPT
from .gemini_client import DEFAULT_MODEL, generate_text
from .parsers import (
    format_failures_for_reviser,
    parse_craft_or_revision_notes,
    parse_final_note,
    parse_review,
)
from .occasion_metadata import get_moment_defaults, CATEGORIES, CLOSENESS_LEVELS, INTENTS, FEELINGS

MAX_REVIEW_LOOPS = 1


def _log_section(title, content=""):
    """
    Print a clearly marked section to stdout so Render / local logs show pipeline progress.

    :param title: Section title shown in the log banner.
    :param content: Optional body text to print under the banner.
    :return: None
    """
    # Use flush=True so logs appear immediately in Render
    banner = f"\n{'=' * 80}\n[{title}]\n{'=' * 80}"
    print(banner, flush=True)
    if content is not None and str(content).strip() != "":
        print(content, flush=True)
        print(f"{'-' * 80}\n", flush=True)


def _normalize_card_inputs(
    occasion_category=None,
    specific_moment=None,
    recipient_name=None,
    relationship=None,
    relationship_closeness=None,
    sender_intent=None,
    sender_feeling=None,
    known_context=None,
    sender_name="",
    language="English",
    user_override=None,
    # Legacy parameters mapping
    occasion=None,
    tone=None,
    length_preference=None,
    personal_details=None,
    additional_guidance=None,
):
    """
    Normalize card request fields into Notion structured schema, supporting both
    new structured parameters and legacy inputs.
    """
    # 1. Resolve Occasion Category (celebrate, thank, comfort)
    resolved_category = (occasion_category or "").strip().lower()
    if not resolved_category and occasion:
        occ_str = str(occasion).strip().lower()
        if any(x in occ_str for x in ["birthday", "congratulation", "anniversary", "custom", "celebrate"]):
            resolved_category = "celebrate"
        elif any(x in occ_str for x in ["thank"]):
            resolved_category = "thank"
        elif any(x in occ_str for x in ["well", "condolence", "sympathy", "comfort"]):
            resolved_category = "comfort"
    
    if resolved_category not in CATEGORIES:
        resolved_category = "celebrate"

    # 2. Resolve Specific Moment
    resolved_moment = (specific_moment or "").strip().lower()
    if not resolved_moment and occasion:
        occ_str = str(occasion).strip().lower()
        if "birthday" in occ_str:
            resolved_moment = "birthday"
        elif "congratulation" in occ_str:
            resolved_moment = "promotion"  # sensible default
        elif "thank" in occ_str:
            resolved_moment = "thank_you"
        elif "well" in occ_str:
            resolved_moment = "get_well"
        elif "sympathy" in occ_str or "condolence" in occ_str:
            resolved_moment = "condolences"
        elif "anniversary" in occ_str:
            resolved_moment = "anniversary"
        else:
            resolved_moment = "other"
            
    if not resolved_moment:
        resolved_moment = "birthday"

    # 3. Resolve Relationship Closeness (formal, friendly, warm, close, very_close)
    resolved_closeness = (relationship_closeness or "").strip().lower()
    if not resolved_closeness and tone:
        tone_str = str(tone).strip().lower()
        if any(x in tone_str for x in ["formal", "respectful"]):
            resolved_closeness = "formal"
        elif any(x in tone_str for x in ["casual", "friendly"]):
            resolved_closeness = "friendly"
        elif any(x in tone_str for x in ["warm", "sincere"]):
            resolved_closeness = "warm"
        elif any(x in tone_str for x in ["heartfelt", "emotional"]):
            resolved_closeness = "close"
        elif any(x in tone_str for x in ["deep", "intimate", "very close"]):
            resolved_closeness = "very_close"

    if resolved_closeness not in CLOSENESS_LEVELS:
        resolved_closeness = "warm"

    # 4. Resolve Relationship Type
    resolved_relationship = (relationship or "Friend").strip()

    # 5. Resolve Intent & Feeling using Occasion Metadata defaults
    metadata = get_moment_defaults(resolved_moment)
    if metadata:
        resolved_intent = sender_intent or metadata["default_intent"]
        resolved_feeling = sender_feeling or metadata["default_feeling"]
    else:
        # Generic defaults based on category if moment is not in metadata
        if resolved_category == "celebrate":
            resolved_intent = sender_intent or "share_the_happiness"
            resolved_feeling = sender_feeling or "warm"
        elif resolved_category == "thank":
            resolved_intent = sender_intent or "share_the_happiness"
            resolved_feeling = sender_feeling or "warm"
        else:  # comfort
            resolved_intent = sender_intent or "mark_the_milestone"
            resolved_feeling = sender_feeling or "reflective"

    # 6. Resolve Context and Overrides
    resolved_context = (known_context or personal_details or "").strip()
    if not resolved_context:
        resolved_context = "No specific personal details provided."

    resolved_override = (user_override or additional_guidance or "").strip()
    if not resolved_override:
        resolved_override = "None"

    return {
        "occasion_category": CATEGORIES[resolved_category],
        "specific_moment": resolved_moment.replace("_", " ").title(),
        "recipient_name": (recipient_name or "Recipient").strip(),
        "relationship": resolved_relationship,
        "relationship_closeness": CLOSENESS_LEVELS[resolved_closeness],
        "sender_intent": INTENTS.get(resolved_intent, resolved_intent.replace("_", " ").title()),
        "sender_feeling": FEELINGS.get(resolved_feeling, resolved_feeling.replace("_", " ").title()),
        "sender_name": sender_name.strip() if sender_name and str(sender_name).strip() else "Not provided",
        "language": language or "English",
        "known_context": resolved_context,
        "user_override": resolved_override,
    }


def generate_writer_note(
    occasion_category=None,
    specific_moment=None,
    recipient_name=None,
    relationship=None,
    relationship_closeness=None,
    sender_intent=None,
    sender_feeling=None,
    known_context=None,
    sender_name="",
    language="English",
    user_override=None,
    model=DEFAULT_MODEL,
    # Legacy fallbacks
    occasion=None,
    tone=None,
    length_preference=None,
    personal_details=None,
    additional_guidance=None,
):
    """
    Generate an initial greeting-card note draft from the writer prompt.
    """
    inputs = _normalize_card_inputs(
        occasion_category=occasion_category,
        specific_moment=specific_moment,
        recipient_name=recipient_name,
        relationship=relationship,
        relationship_closeness=relationship_closeness,
        sender_intent=sender_intent,
        sender_feeling=sender_feeling,
        known_context=known_context,
        sender_name=sender_name,
        language=language,
        user_override=user_override,
        occasion=occasion,
        tone=tone,
        length_preference=length_preference,
        personal_details=personal_details,
        additional_guidance=additional_guidance,
    )

    prompt = NOTE_WRITER_PROMPT.format(
        occasion_category=inputs["occasion_category"],
        specific_moment=inputs["specific_moment"],
        recipient_name=inputs["recipient_name"],
        relationship=inputs["relationship"],
        relationship_closeness=inputs["relationship_closeness"],
        sender_intent=inputs["sender_intent"],
        sender_feeling=inputs["sender_feeling"],
        sender_name=inputs["sender_name"],
        language=inputs["language"],
        known_context=inputs["known_context"],
        user_override=inputs["user_override"],
    )

    _log_section("WRITER — NORMALIZED INPUTS", inputs)
    _log_section("WRITER — FORMATTED PROMPT", prompt)
    print(f"[WRITER] Calling Gemini model={model} temperature=0.8 ...", flush=True)

    response = generate_text(prompt, model=model, temperature=0.8)

    _log_section("WRITER — RAW MODEL OUTPUT", response)

    draft_note = parse_final_note(response)
    craft_notes = parse_craft_or_revision_notes(response)

    _log_section("WRITER — PARSED FINAL NOTE", draft_note)
    _log_section("WRITER — CRAFT NOTES", craft_notes)

    return {
        "draft_note": draft_note,
        "craft_notes": craft_notes,
        "raw_response": response,
        "prompt": prompt,
    }


def review_greeting_card_note(
    draft_note,
    occasion_category=None,
    specific_moment=None,
    recipient_name=None,
    relationship=None,
    relationship_closeness=None,
    sender_intent=None,
    sender_feeling=None,
    known_context=None,
    sender_name="",
    language="English",
    user_override=None,
    model=DEFAULT_MODEL,
    # Legacy fallbacks
    occasion=None,
    tone=None,
    length_preference=None,
    personal_details=None,
    additional_guidance=None,
):
    """
    Review a drafted greeting-card note against Notion core quality criteria.
    """
    inputs = _normalize_card_inputs(
        occasion_category=occasion_category,
        specific_moment=specific_moment,
        recipient_name=recipient_name,
        relationship=relationship,
        relationship_closeness=relationship_closeness,
        sender_intent=sender_intent,
        sender_feeling=sender_feeling,
        known_context=known_context,
        sender_name=sender_name,
        language=language,
        user_override=user_override,
        occasion=occasion,
        tone=tone,
        length_preference=length_preference,
        personal_details=personal_details,
        additional_guidance=additional_guidance,
    )

    prompt = NOTE_REVIEWER_PROMPT.format(
        occasion_category=inputs["occasion_category"],
        specific_moment=inputs["specific_moment"],
        recipient_name=inputs["recipient_name"],
        relationship=inputs["relationship"],
        relationship_closeness=inputs["relationship_closeness"],
        sender_intent=inputs["sender_intent"],
        sender_feeling=inputs["sender_feeling"],
        sender_name=inputs["sender_name"],
        language=inputs["language"],
        known_context=inputs["known_context"],
        user_override=inputs["user_override"],
        draft_note=draft_note or "",
    )

    _log_section("REVIEWER — FORMATTED PROMPT", prompt)
    print(f"[REVIEWER] Calling Gemini model={model} temperature=0.2 ...", flush=True)

    response = generate_text(prompt, model=model, temperature=0.2)

    _log_section("REVIEWER — RAW MODEL OUTPUT", response)

    review = parse_review(response)
    _log_section(
        "REVIEWER — PARSED VERDICT",
        f"verdict={review['verdict']}\nfailures={review['failures']}",
    )

    return {
        "verdict": review["verdict"],
        "failures": review["failures"],
        "evaluation_breakdown": review["evaluation_breakdown"],
        "raw_response": response,
        "prompt": prompt,
    }


def revise_greeting_card_note(
    draft_note,
    review_feedback,
    occasion_category=None,
    specific_moment=None,
    recipient_name=None,
    relationship=None,
    relationship_closeness=None,
    sender_intent=None,
    sender_feeling=None,
    known_context=None,
    sender_name="",
    language="English",
    user_override=None,
    model=DEFAULT_MODEL,
    # Legacy fallbacks
    occasion=None,
    tone=None,
    length_preference=None,
    personal_details=None,
    additional_guidance=None,
):
    """
    Revise a greeting-card note using reviewer failure feedback.
    """
    inputs = _normalize_card_inputs(
        occasion_category=occasion_category,
        specific_moment=specific_moment,
        recipient_name=recipient_name,
        relationship=relationship,
        relationship_closeness=relationship_closeness,
        sender_intent=sender_intent,
        sender_feeling=sender_feeling,
        known_context=known_context,
        sender_name=sender_name,
        language=language,
        user_override=user_override,
        occasion=occasion,
        tone=tone,
        length_preference=length_preference,
        personal_details=personal_details,
        additional_guidance=additional_guidance,
    )

    prompt = NOTE_REVISER_PROMPT.format(
        occasion_category=inputs["occasion_category"],
        specific_moment=inputs["specific_moment"],
        recipient_name=inputs["recipient_name"],
        relationship=inputs["relationship"],
        relationship_closeness=inputs["relationship_closeness"],
        sender_intent=inputs["sender_intent"],
        sender_feeling=inputs["sender_feeling"],
        sender_name=inputs["sender_name"],
        language=inputs["language"],
        known_context=inputs["known_context"],
        user_override=inputs["user_override"],
        draft_note=draft_note or "",
        review_feedback=review_feedback or "No feedback provided.",
    )

    _log_section("REVISER — FORMATTED PROMPT", prompt)
    print(f"[REVISER] Calling Gemini model={model} temperature=0.6 ...", flush=True)

    response = generate_text(prompt, model=model, temperature=0.6)

    _log_section("REVISER — RAW MODEL OUTPUT", response)

    revised_note = parse_final_note(response)
    revision_summary = parse_craft_or_revision_notes(response)

    _log_section("REVISER — PARSED REVISED NOTE", revised_note)
    _log_section("REVISER — REVISION SUMMARY", revision_summary)

    return {
        "revised_note": revised_note,
        "revision_summary": revision_summary,
        "raw_response": response,
        "prompt": prompt,
    }


def generate_greeting_card_note(
    occasion_category=None,
    specific_moment=None,
    recipient_name=None,
    relationship=None,
    relationship_closeness=None,
    sender_intent=None,
    sender_feeling=None,
    known_context=None,
    sender_name="",
    language="English",
    user_override=None,
    model=DEFAULT_MODEL,
    enable_review_loop=True,
    max_review_loops=MAX_REVIEW_LOOPS,
    # Legacy fallbacks
    occasion=None,
    tone=None,
    length_preference=None,
    personal_details=None,
    additional_guidance=None,
):
    """
    Generate a personal greeting-card note using a write -> review -> revise loop.
    Supports both legacy parameter names and the new Notion schema.
    """
    _log_section(
        "PIPELINE START — generate_greeting_card_note",
        (
            f"occasion_category={occasion_category}\n"
            f"specific_moment={specific_moment}\n"
            f"recipient_name={recipient_name}\n"
            f"relationship={relationship}\n"
            f"relationship_closeness={relationship_closeness}\n"
            f"model={model}\n"
            f"enable_review_loop={enable_review_loop}\n"
            f"max_review_loops={max_review_loops}"
        ),
    )

    # Generate the initial draft
    writer_result = generate_writer_note(
        occasion_category=occasion_category,
        specific_moment=specific_moment,
        recipient_name=recipient_name,
        relationship=relationship,
        relationship_closeness=relationship_closeness,
        sender_intent=sender_intent,
        sender_feeling=sender_feeling,
        known_context=known_context,
        sender_name=sender_name,
        language=language,
        user_override=user_override,
        model=model,
        occasion=occasion,
        tone=tone,
        length_preference=length_preference,
        personal_details=personal_details,
        additional_guidance=additional_guidance,
    )
    current_note = writer_result["draft_note"]
    craft_notes = writer_result["craft_notes"]
    stage_logs = [
        {
            "event_type": "writer",
            "prompt": writer_result.get("prompt") or "",
            "response": writer_result.get("raw_response") or "",
            "parsed_note": current_note,
            "meta": {"craft_notes": craft_notes},
        }
    ]

    if not enable_review_loop:
        return {
            "final_note": current_note,
            "verdict": "SKIPPED_REVIEW",
            "attempts": 1,
            "craft_notes": craft_notes,
            "review_history": [],
            "writer_raw": writer_result["raw_response"],
            "last_reviser_raw": "",
            "stage_logs": stage_logs,
        }

    # Run review -> revise loop
    review_history = []
    last_reviser_raw = ""
    final_verdict = "FAIL"

    for attempt in range(1, max_review_loops + 1):
        print(f"[PIPELINE] Review/revise attempt {attempt}/{max_review_loops}", flush=True)
        review_result = review_greeting_card_note(
            current_note,
            occasion_category=occasion_category,
            specific_moment=specific_moment,
            recipient_name=recipient_name,
            relationship=relationship,
            relationship_closeness=relationship_closeness,
            sender_intent=sender_intent,
            sender_feeling=sender_feeling,
            known_context=known_context,
            sender_name=sender_name,
            language=language,
            user_override=user_override,
            model=model,
            occasion=occasion,
            tone=tone,
            length_preference=length_preference,
            personal_details=personal_details,
            additional_guidance=additional_guidance,
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
        stage_logs.append(
            {
                "event_type": "reviewer",
                "prompt": review_result.get("prompt") or "",
                "response": review_result.get("raw_response") or "",
                "parsed_note": current_note,
                "meta": {
                    "attempt": attempt,
                    "verdict": review_result["verdict"],
                    "failures": review_result["failures"],
                },
            }
        )

        if review_result["verdict"] == "PASS":
            break

        # Revise on failure
        feedback = format_failures_for_reviser(review_result["failures"])
        reviser_result = revise_greeting_card_note(
            current_note,
            feedback,
            occasion_category=occasion_category,
            specific_moment=specific_moment,
            recipient_name=recipient_name,
            relationship=relationship,
            relationship_closeness=relationship_closeness,
            sender_intent=sender_intent,
            sender_feeling=sender_feeling,
            known_context=known_context,
            sender_name=sender_name,
            language=language,
            user_override=user_override,
            model=model,
            occasion=occasion,
            tone=tone,
            length_preference=length_preference,
            personal_details=personal_details,
            additional_guidance=additional_guidance,
        )
        current_note = reviser_result["revised_note"]
        last_reviser_raw = reviser_result["raw_response"]
        if reviser_result["revision_summary"]:
            craft_notes = reviser_result["revision_summary"]
        stage_logs.append(
            {
                "event_type": "reviser",
                "prompt": reviser_result.get("prompt") or "",
                "response": reviser_result.get("raw_response") or "",
                "parsed_note": current_note,
                "meta": {
                    "attempt": attempt,
                    "revision_summary": reviser_result.get("revision_summary") or "",
                },
            }
        )

    _log_section(
        "PIPELINE END — FINAL RESULT",
        f"verdict={final_verdict}\nattempts={len(review_history)}\nfinal_note=\n{current_note}",
    )

    return {
        "final_note": current_note,
        "verdict": final_verdict,
        "attempts": len(review_history),
        "craft_notes": craft_notes,
        "review_history": review_history,
        "writer_raw": writer_result["raw_response"],
        "last_reviser_raw": last_reviser_raw,
        "stage_logs": stage_logs,
    }


def refine_greeting_card_note(
    current_note,
    refinement_instruction,
    occasion_category=None,
    specific_moment=None,
    recipient_name=None,
    relationship=None,
    relationship_closeness=None,
    sender_intent=None,
    sender_feeling=None,
    known_context=None,
    sender_name="",
    language="English",
    user_override=None,
    model=DEFAULT_MODEL,
    # Legacy fallbacks
    occasion=None,
    tone=None,
    length_preference=None,
    personal_details=None,
    additional_guidance=None,
):
    """
    Refine an existing note (e.g. adjust voice or correct a detail) in a single pass.
    """
    _log_section(
        "REFINE START",
        f"instruction={refinement_instruction}\ncurrent_note=\n{current_note}",
    )

    inputs = _normalize_card_inputs(
        occasion_category=occasion_category,
        specific_moment=specific_moment,
        recipient_name=recipient_name,
        relationship=relationship,
        relationship_closeness=relationship_closeness,
        sender_intent=sender_intent,
        sender_feeling=sender_feeling,
        known_context=known_context,
        sender_name=sender_name,
        language=language,
        user_override=user_override,
        occasion=occasion,
        tone=tone,
        length_preference=length_preference,
        personal_details=personal_details,
        additional_guidance=additional_guidance,
    )

    combined_guidance = (
        f"{inputs['user_override']}\n\n"
        f"REFINEMENT INSTRUCTION FOR THIS REWRITE: {refinement_instruction}\n\n"
        f"Please rewrite the following existing draft according to the refinement instruction. "
        f"Preserve as much of the original core and context as possible, but ensure the instruction is fully realized.\n\n"
        f"<existing_draft>\n{current_note}\n</existing_draft>"
    ).strip()

    writer_result = generate_writer_note(
        occasion_category=occasion_category,
        specific_moment=specific_moment,
        recipient_name=recipient_name,
        relationship=relationship,
        relationship_closeness=relationship_closeness,
        sender_intent=sender_intent,
        sender_feeling=sender_feeling,
        known_context=inputs["known_context"],
        sender_name=inputs["sender_name"],
        language=inputs["language"],
        user_override=combined_guidance,
        model=model,
    )

    _log_section("REFINE END — REFINED NOTE", writer_result["draft_note"])
    return {
        "final_note": writer_result["draft_note"],
        "prompt": writer_result.get("prompt") or "",
        "raw_response": writer_result.get("raw_response") or "",
        "instruction": refinement_instruction,
    }
