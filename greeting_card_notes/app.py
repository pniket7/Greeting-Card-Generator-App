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

from greeting_card_notes.services.gemini_client import DEFAULT_MODEL, has_api_key
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

# Creative visual styles for rendering the card
CARD_THEMES = {
    "Classic Cream": {
        "bg": "#fdfbf7",
        "color": "#2c2520",
        "border": "#e6dfd3",
        "inner_border": "rgba(44, 37, 32, 0.15)",
        "accent": "#8c7853"
    },
    "Blush Romance": {
        "bg": "#fffbfb",
        "color": "#4a2828",
        "border": "#f2d6d6",
        "inner_border": "rgba(74, 40, 40, 0.12)",
        "accent": "#b85c5c"
    },
    "Midnight Gold": {
        "bg": "#111115",
        "color": "#f1eae0",
        "border": "#d4af37",
        "inner_border": "rgba(212, 175, 55, 0.3)",
        "accent": "#d4af37"
    },
    "Forest Spruce": {
        "bg": "#f4f6f4",
        "color": "#1c2e24",
        "border": "#ccd5cc",
        "inner_border": "rgba(28, 46, 36, 0.12)",
        "accent": "#3b604b"
    }
}

FONT_STYLES = {
    "Warm Cursive": {
        "family": "'Caveat', cursive",
        "size": "24px",
        "weight": "400",
        "line_height": "1.4"
    },
    "Elegant Serif": {
        "family": "'Lora', serif",
        "size": "17px",
        "weight": "400",
        "line_height": "1.7"
    },
    "Modern Sans": {
        "family": "'Inter', sans-serif",
        "size": "16px",
        "weight": "400",
        "line_height": "1.6"
    }
}


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


def inject_custom_styles():
    """
    Inject custom CSS styles for a premium design interface.

    :return: None
    """
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Caveat:wght@400;700&family=Playfair+Display:ital,wght@0,400;0,600;1,400&family=Lora:ital,wght@0,400;0,500;1,400&family=Inter:wght@300;400;500;600&display=swap');

        /* Form styling */
        div[data-testid="stForm"] {
            background-color: rgba(255, 255, 255, 0.02) !important;
            border: 1px solid rgba(255, 255, 255, 0.08) !important;
            border-radius: 16px !important;
            padding: 30px !important;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15) !important;
        }

        /* Titles and Typography */
        .app-title {
            font-family: 'Playfair Display', serif !important;
            font-weight: 600 !important;
            letter-spacing: -0.5px !important;
            background: linear-gradient(135deg, #ffffff 0%, #cacacd 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0px;
        }

        .section-header {
            font-family: 'Playfair Display', serif !important;
            font-weight: 500 !important;
            margin-bottom: 15px;
            color: #cacacd;
        }

        /* Button Styling */
        button[kind="primary"] {
            background: linear-gradient(135deg, #dfb747 0%, #c39f2f 100%) !important;
            color: #0d0d11 !important;
            border: none !important;
            font-weight: 600 !important;
            border-radius: 8px !important;
            padding: 10px 24px !important;
            transition: all 0.3s ease !important;
            box-shadow: 0 4px 15px rgba(223, 183, 71, 0.25) !important;
        }

        button[kind="primary"]:hover {
            transform: translateY(-1px) !important;
            box-shadow: 0 6px 20px rgba(223, 183, 71, 0.35) !important;
        }

        /* Quick refinement button pills */
        button[kind="secondary"] {
            background-color: rgba(255, 255, 255, 0.03) !important;
            color: #e2e2e9 !important;
            border: 1px solid rgba(255, 255, 255, 0.08) !important;
            border-radius: 20px !important;
            font-size: 14px !important;
            font-weight: 500 !important;
            padding: 6px 16px !important;
            transition: all 0.2s ease !important;
        }

        button[kind="secondary"]:hover {
            background-color: rgba(255, 255, 255, 0.08) !important;
            border-color: rgba(255, 255, 255, 0.2) !important;
            transform: translateY(-1px) !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


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
    inject_custom_styles()

    st.markdown('<h1 class="app-title">Greeting Card Notes</h1>', unsafe_allow_html=True)
    st.caption(
        "Prototype: turn a few personal details into a copy-ready card note. "
    )
    st.markdown("<br>", unsafe_allow_html=True)

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
        st.markdown('<h3 class="section-header">Card details</h3>', unsafe_allow_html=True)
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

            with st.spinner("Generating your greeting card note..."):
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
            st.markdown('<h3 class="section-header">Your note</h3>', unsafe_allow_html=True)

            if st.session_state.error:
                st.error(st.session_state.error)

            if st.session_state.final_note:
                # Sub-menu for customize options
                style_c1, style_c2 = st.columns(2)
                with style_c1:
                    theme_name = st.selectbox("Card theme style", list(CARD_THEMES.keys()), index=0)
                with style_c2:
                    font_name = st.selectbox("Cursive / Font style", list(FONT_STYLES.keys()), index=0)

                theme = CARD_THEMES[theme_name]
                font = FONT_STYLES[font_name]

                # Render a gorgeous, tactile visual greeting card
                card_html = f"""
                <div style="
                    background-color: {theme['bg']};
                    color: {theme['color']};
                    border: 1px solid {theme['border']};
                    border-radius: 16px;
                    padding: 30px;
                    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.15);
                    margin-top: 15px;
                    margin-bottom: 24px;
                    position: relative;
                    overflow: hidden;
                    background-image: radial-gradient({theme['inner_border']} 1.2px, transparent 0);
                    background-size: 16px 12px;
                ">
                    <div style="
                        border: 1px dashed {theme['inner_border']};
                        border-radius: 10px;
                        padding: 25px;
                        min-height: 180px;
                        display: flex;
                        flex-direction: column;
                        justify-content: space-between;
                    ">
                        <div style="
                            font-family: {font['family']};
                            font-size: {font['size']};
                            font-weight: {font['weight']};
                            line-height: {font['line_height']};
                            white-space: pre-line;
                            text-shadow: 0 0 1px rgba(0,0,0,0.01);
                        ">
                            {st.session_state.final_note}
                        </div>
                        <div style="
                            align-self: flex-end;
                            margin-top: 25px;
                            font-family: 'Playfair Display', 'Lora', serif;
                            font-size: 10px;
                            text-transform: uppercase;
                            letter-spacing: 2px;
                            color: {theme['accent']};
                            opacity: 0.6;
                        ">
                            crafted with care
                        </div>
                    </div>
                </div>
                """
                st.markdown(card_html, unsafe_allow_html=True)

                # Collapsible raw copy area to avoid cluttering the beautiful display
                with st.expander("Copy text options", expanded=False):
                    st.text_area(
                        "Copy-ready plain text",
                        value=st.session_state.final_note,
                        height=150,
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
