"""
Parsers for writer / reviewer / reviser XML-style outputs.
"""

import re


def extract_tag(text, tag):
    """
    Extract the inner content of an XML-style tag from text.

    :param text: The full model response text.
    :param tag: The tag name to extract.
    :return: The stripped tag content, or None if not found.
    """
    # Match the requested tag with DOTALL so multiline content is captured
    pattern = rf"<{tag}>\s*(.*?)\s*</{tag}>"
    match = re.search(pattern, text, flags=re.DOTALL | re.IGNORECASE)
    if not match:
        return None
    return match.group(1).strip()


def parse_final_note(response_text):
    """
    Parse the final note text from a writer or reviser response.

    :param response_text: The full model response text.
    :return: The copy-ready note text.
    """
    # Prefer the structured final_note tag when present
    note = extract_tag(response_text, "final_note")
    if note:
        return note.strip().strip('"').strip("'")

    # Fallback: if the model ignored XML, return the raw text cleaned a bit
    cleaned = response_text.strip()
    cleaned = re.sub(r"^```(?:\w+)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def parse_craft_or_revision_notes(response_text):
    """
    Parse craft notes or revision summary from a model response.

    :param response_text: The full model response text.
    :return: The craft notes / revision summary text, or an empty string.
    """
    return (
        extract_tag(response_text, "craft_notes")
        or extract_tag(response_text, "revision_summary")
        or ""
    )


def parse_review(response_text):
    """
    Parse PASS/FAIL review output and failure details from a reviewer response.

    :param response_text: The full reviewer model response text.
    :return: Dict with verdict, failures, raw, and evaluation_breakdown.
    """
    # Normalize verdict text
    verdict_raw = (extract_tag(response_text, "verdict") or "").strip().upper()
    if verdict_raw == "PASS":
        verdict = "PASS"
    elif "FAIL" in verdict_raw:
        verdict = "FAIL"
    else:
        verdict = "FAIL"

    # Extract each failure block
    failures = []
    for failure_block in re.findall(
        r"<failure>\s*(.*?)\s*</failure>",
        response_text,
        flags=re.DOTALL | re.IGNORECASE,
    ):
        reason_match = re.search(
            r"<reason>\s*(.*?)\s*</reason>",
            failure_block,
            flags=re.DOTALL | re.IGNORECASE,
        )
        fix_match = re.search(
            r"<needed_fix>\s*(.*?)\s*</needed_fix>",
            failure_block,
            flags=re.DOTALL | re.IGNORECASE,
        )
        failures.append(
            {
                "reason": reason_match.group(1).strip() if reason_match else failure_block.strip(),
                "needed_fix": fix_match.group(1).strip() if fix_match else "",
            }
        )

    # Clear failures on PASS
    if verdict == "PASS":
        failures = []

    return {
        "verdict": verdict,
        "failures": failures,
        "raw": response_text,
        "evaluation_breakdown": extract_tag(response_text, "evaluation_breakdown") or "",
    }


def format_failures_for_reviser(failures):
    """
    Format reviewer failure items into text for the reviser prompt.

    :param failures: List of failure dicts with reason and needed_fix.
    :return: A formatted feedback string for the reviser.
    """
    # Handle empty failure lists safely
    if not failures:
        return "No explicit failures listed."

    # Build numbered feedback lines
    parts = []
    for i, item in enumerate(failures, start=1):
        parts.append(
            f"{i}. Reason: {item.get('reason', '').strip()}\n"
            f"   Needed fix: {item.get('needed_fix', '').strip()}"
        )
    return "\n".join(parts)
