"""
Greeting Card Notes — prototype Streamlit app.

Run from the repo root:
    streamlit run greeting_card_notes/app.py
"""

import sys
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

# Ensure repo root is on sys.path so `greeting_card_notes.*` imports work
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

load_dotenv(REPO_ROOT / ".env")

from greeting_card_notes.services.gemini_client import has_api_key
from greeting_card_notes.services.note_pipeline import (
    generate_greeting_card_note,
    refine_greeting_card_note,
)

OCCASIONS = [
    "Birthday",
    "Congratulations",
    "Get Well",
    "Thank You",
    "Condolences / Sympathy",
    "Anniversary",
    "Other / Custom",
]

TONES = [
    "Warm and sincere",
    "Casual and friendly",
    "Heartfelt and emotional",
    "Light and playful",
    "Formal and respectful",
    "Short and simple",
]

LENGTHS = ["Short", "Medium", "Long"]

RELATIONSHIPS = [
    "Friend",
    "Best friend",
    "Partner / Spouse",
    "Parent",
    "Child",
    "Sibling",
    "Colleague",
    "Mentor",
    "Neighbor",
    "Acquaintance",
    "Other",
]


def init_state():
    """
    Initialize Streamlit session state defaults for the app.

    :return: None
    """
    # Set default session values only when missing
    defaults = {
        "final_note": "",
        "craft_notes": "",
        "verdict": "",
        "attempts": 0,
        "review_history": [],
        "last_request": None,
        "error": "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def build_card_request_fields(
    occasion,
    custom_occasion,
    recipient_name,
    relationship,
    custom_relationship,
    years_known,
    tone,
    length_preference,
    sender_name,
    language,
    personal_details,
    additional_guidance,
):
    """
    Build normalized card request fields from the UI form values.

    :param occasion: Selected occasion from the dropdown.
    :param custom_occasion: Custom occasion text when Other is selected.
    :param recipient_name: Recipient name from the form.
    :param relationship: Selected relationship from the dropdown.
    :param custom_relationship: Custom relationship text when Other is selected.
    :param years_known: How long the sender has known the recipient.
    :param tone: Selected tone.
    :param length_preference: Selected note length.
    :param sender_name: Optional sender name for sign-off.
    :param language: Output language.
    :param personal_details: Personal details from the form.
    :param additional_guidance: Optional extra guidance from the form.
    :return: Dict of normalized request fields for the note pipeline.
    """
    # Resolve custom occasion if provided
    resolved_occasion = occasion
    if occasion == "Other / Custom" and custom_occasion.strip():
        resolved_occasion = custom_occasion.strip()

    # Resolve custom relationship if provided
    resolved_relationship = relationship
    if relationship == "Other" and custom_relationship.strip():
        resolved_relationship = custom_relationship.strip()

    return {
        "occasion": resolved_occasion,
        "recipient_name": recipient_name.strip(),
        "relationship": resolved_relationship,
        "years_known": years_known.strip(),
        "tone": tone,
        "length_preference": length_preference,
        "personal_details": personal_details.strip(),
        "sender_name": sender_name.strip(),
        "language": language.strip() or "English",
        "additional_guidance": additional_guidance.strip(),
    }


def main():
    """
    Run the Greeting Card Notes Streamlit prototype.

    :return: None
    """
    st.set_page_config(
        page_title="Greeting Card Notes",
        page_icon="✉️",
        layout="wide",
    )
    init_state()

    st.title("Greeting Card Notes")
    st.caption(
        "Prototype: turn a few personal details into a copy-ready card note. "
        "Powered by Gemini with a write → review → revise loop."
    )

    if not has_api_key():
        st.error(
            "Missing `GOOGLE_API_KEY`. Add it to your project `.env` locally, "
            "or to Streamlit secrets when deploying:\n\n"
            'GOOGLE_API_KEY = "your-google-api-key"'
        )
        st.stop()

    has_note = bool(st.session_state.final_note)
    has_error = bool(st.session_state.error)

    if has_note or has_error:
        left, right = st.columns([1.05, 1], gap="large")
    else:
        left, right = st.container(), None

    with left:
        st.subheader("Card details")
        with st.form("card_form", clear_on_submit=False):
            c1, c2 = st.columns(2)
            with c1:
                occasion = st.selectbox("Occasion", OCCASIONS, index=0)
                custom_occasion = st.text_input(
                    "Custom occasion (if Other)",
                    placeholder="e.g. New baby, Housewarming",
                )
                recipient_name = st.text_input("Recipient name", placeholder="e.g. Priya")
                relationship = st.selectbox("Relationship", RELATIONSHIPS, index=0)
                custom_relationship = st.text_input(
                    "Custom relationship (if Other)",
                    placeholder="e.g. College roommate",
                )
            with c2:
                years_known = st.text_input(
                    "How long have you known them?",
                    placeholder="e.g. 8 years / since college",
                )
                tone = st.selectbox("Tone", TONES, index=0)
                length_preference = st.selectbox("Length", LENGTHS, index=1)
                sender_name = st.text_input(
                    "Your name (optional sign-off)",
                    placeholder="e.g. Niket",
                )
                language = st.text_input("Language", value="English")

            personal_details = st.text_area(
                "Personal details (what makes this note specific)",
                height=140,
                placeholder=(
                    "Examples:\n"
                    "- She always brings homemade food when someone is sick\n"
                    "- We hiked in Himachal last year\n"
                    "- He helped me prepare for interviews"
                ),
            )
            additional_guidance = st.text_area(
                "Extra guidance (optional)",
                height=80,
                placeholder="e.g. Keep it short enough for a small card. Don't mention the surprise party.",
            )

            submitted = st.form_submit_button("Generate note", type="primary", use_container_width=True)

        if submitted:
            if not recipient_name.strip():
                st.warning("Recipient name is required.")
            elif not personal_details.strip():
                st.info(
                    "No personal details provided — the note can still be written, "
                    "but it will be less specific. Consider adding at least one real detail."
                )

            # Build request fields from the form
            request_fields = build_card_request_fields(
                occasion,
                custom_occasion,
                recipient_name,
                relationship,
                custom_relationship,
                years_known,
                tone,
                length_preference,
                sender_name,
                language,
                personal_details,
                additional_guidance,
            )

            with st.spinner("Writing and polishing your note..."):
                try:
                    # Generate note through write -> review -> revise pipeline
                    result = generate_greeting_card_note(
                        request_fields["occasion"],
                        request_fields["recipient_name"],
                        request_fields["relationship"],
                        request_fields["years_known"],
                        request_fields["tone"],
                        request_fields["length_preference"],
                        request_fields["personal_details"],
                        sender_name=request_fields["sender_name"],
                        language=request_fields["language"],
                        additional_guidance=request_fields["additional_guidance"],
                    )
                    st.session_state.final_note = result["final_note"]
                    st.session_state.craft_notes = result["craft_notes"]
                    st.session_state.verdict = result["verdict"]
                    st.session_state.attempts = result["attempts"]
                    st.session_state.review_history = result["review_history"]
                    st.session_state.last_request = request_fields
                    st.session_state.error = ""
                except Exception as exc:
                    st.session_state.error = str(exc)

    if right is not None:
        with right:
            st.subheader("Your note")

            if st.session_state.error:
                st.error(st.session_state.error)

            if st.session_state.final_note:
                # Avoid binding a widget key to note text so refinements always refresh the display
                st.text_area(
                    "Copy-ready note",
                    value=st.session_state.final_note,
                    height=260,
                )

                meta_cols = st.columns(3)
                with meta_cols[0]:
                    st.metric("Review verdict", st.session_state.verdict or "—")
                with meta_cols[1]:
                    st.metric("Review attempts", st.session_state.attempts or 0)
                with meta_cols[2]:
                    word_count = len(st.session_state.final_note.split())
                    st.metric("Word count", word_count)

                if st.session_state.craft_notes:
                    with st.expander("Why this note works", expanded=False):
                        st.markdown(st.session_state.craft_notes)

                st.markdown("#### Quick refinements")
                r1, r2, r3, r4 = st.columns(4)
                refinements = [
                    (r1, "Shorter", "Make the note noticeably shorter while keeping the personal core."),
                    (r2, "Warmer", "Make the note warmer and more emotionally open, without becoming dramatic."),
                    (r3, "More casual", "Make the note more casual and conversational, like a close friend wrote it."),
                    (r4, "Less AI-sounding", "Rewrite to sound even more like a real human handwritten card note; remove any polished AI phrasing."),
                ]

                for col, label, instruction in refinements:
                    with col:
                        if st.button(label, use_container_width=True, disabled=not st.session_state.last_request):
                            with st.spinner(f"Applying: {label}..."):
                                try:
                                    # Refine the current note with a single-pass rewrite
                                    req = st.session_state.last_request
                                    st.session_state.final_note = refine_greeting_card_note(
                                        st.session_state.final_note,
                                        instruction,
                                        req["occasion"],
                                        req["recipient_name"],
                                        req["relationship"],
                                        req["years_known"],
                                        req["tone"],
                                        req["length_preference"],
                                        req["personal_details"],
                                        sender_name=req["sender_name"],
                                        language=req["language"],
                                        additional_guidance=req["additional_guidance"],
                                    )
                                    st.session_state.error = ""
                                    st.rerun()
                                except Exception as exc:
                                    st.session_state.error = str(exc)
                                    st.rerun()



if __name__ == "__main__":
    main()
