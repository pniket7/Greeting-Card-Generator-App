"""
Custom visual styles for the greeting-card notes Streamlit UI.
"""

APP_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,650;9..144,700&family=Manrope:wght@400;500;600;700&display=swap');

:root {
  --ink: #15241f;
  --ink-soft: #3d4f48;
  --paper: #fffdf8;
  --paper-edge: #e7e0d2;
  --wash: #eef3ef;
  --moss: #1f5c56;
  --moss-deep: #163f3b;
  --sand: #f3efe6;
  --accent: #b4532a;
  --shadow: 0 18px 50px rgba(21, 36, 31, 0.08);
}

html, body, [class*="css"] {
  font-family: "Manrope", sans-serif;
}

.stApp {
  background:
    radial-gradient(1200px 600px at 8% -10%, #dfeae3 0%, transparent 55%),
    radial-gradient(900px 500px at 100% 0%, #f0e4d4 0%, transparent 50%),
    linear-gradient(180deg, #f7f3ea 0%, #eef3ef 45%, #f3efe6 100%);
  color: var(--ink);
}

.stApp::before {
  content: "";
  position: fixed;
  inset: 0;
  pointer-events: none;
  opacity: 0.35;
  background-image:
    linear-gradient(rgba(21, 36, 31, 0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(21, 36, 31, 0.03) 1px, transparent 1px);
  background-size: 28px 28px;
  mask-image: radial-gradient(circle at 50% 20%, black 20%, transparent 75%);
}

#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
header[data-testid="stHeader"] {
  background: transparent;
}

.block-container {
  padding-top: 1.6rem !important;
  padding-bottom: 3rem !important;
  max-width: 1120px;
}

.ogn-hero {
  animation: ogn-rise 700ms ease-out both;
  margin: 0.2rem 0 1.6rem 0;
}

.ogn-kicker {
  display: inline-block;
  font-family: "Manrope", sans-serif;
  font-size: 0.78rem;
  font-weight: 600;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--moss);
  margin-bottom: 0.55rem;
}

.ogn-brand {
  font-family: "Fraunces", serif;
  font-weight: 700;
  font-size: clamp(2.4rem, 5vw, 3.6rem);
  line-height: 0.98;
  letter-spacing: -0.03em;
  color: var(--ink);
  margin: 0;
}

.ogn-brand span {
  color: var(--moss);
}

.ogn-sub {
  margin-top: 0.75rem;
  max-width: 34rem;
  font-size: 1.05rem;
  line-height: 1.55;
  color: var(--ink-soft);
}

.ogn-panel-label {
  font-family: "Fraunces", serif;
  font-size: 1.45rem;
  font-weight: 650;
  color: var(--ink);
  margin: 0.2rem 0 0.85rem 0;
  animation: ogn-rise 800ms ease-out both;
}

.ogn-note-shell {
  background: var(--paper);
  border: 1px solid var(--paper-edge);
  box-shadow: var(--shadow);
  border-radius: 18px;
  padding: 1.35rem 1.35rem 1.1rem 1.35rem;
  position: relative;
  overflow: hidden;
  animation: ogn-rise 850ms ease-out both;
}

.ogn-note-shell::before {
  content: "";
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 6px;
  background: linear-gradient(180deg, var(--moss), #8fae8a);
}

.ogn-note-label {
  font-family: "Fraunces", serif;
  font-size: 1.35rem;
  font-weight: 650;
  margin-bottom: 0.35rem;
}

.ogn-note-meta {
  font-size: 0.85rem;
  color: var(--ink-soft);
  margin-bottom: 0.85rem;
}

div[data-testid="stForm"] {
  background: rgba(255, 253, 248, 0.72);
  border: 1px solid rgba(231, 224, 210, 0.95);
  border-radius: 22px;
  padding: 1.15rem 1.15rem 0.85rem 1.15rem;
  box-shadow: var(--shadow);
  backdrop-filter: blur(6px);
  animation: ogn-rise 780ms ease-out both;
}

div[data-testid="stTextInput"] label,
div[data-testid="stSelectbox"] label,
div[data-testid="stTextArea"] label {
  font-family: "Manrope", sans-serif !important;
  font-size: 0.86rem !important;
  font-weight: 600 !important;
  color: var(--ink-soft) !important;
  letter-spacing: 0.01em;
}

div[data-testid="stTextInput"] input,
div[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
div[data-testid="stTextArea"] textarea {
  background: #fffdf8 !important;
  border: 1px solid #ddd4c4 !important;
  border-radius: 12px !important;
  color: var(--ink) !important;
  box-shadow: none !important;
}

div[data-testid="stTextArea"] textarea {
  min-height: 120px;
  line-height: 1.5;
}

div[data-testid="stForm"] .stButton > button[kind="primary"],
div[data-testid="stForm"] button[data-testid="baseButton-primary"] {
  background: linear-gradient(135deg, var(--moss) 0%, var(--moss-deep) 100%) !important;
  color: #f7fffc !important;
  border: none !important;
  border-radius: 999px !important;
  font-family: "Manrope", sans-serif !important;
  font-weight: 700 !important;
  letter-spacing: 0.02em !important;
  padding: 0.7rem 1.2rem !important;
  transition: transform 180ms ease, filter 180ms ease !important;
}

div[data-testid="stForm"] .stButton > button[kind="primary"]:hover {
  filter: brightness(1.05);
  transform: translateY(-1px);
}

div[data-testid="stHorizontalBlock"] .stButton > button {
  background: #fffdf8 !important;
  color: var(--moss-deep) !important;
  border: 1px solid #cfd9d3 !important;
  border-radius: 999px !important;
  font-weight: 600 !important;
  transition: background 160ms ease, transform 160ms ease !important;
}

div[data-testid="stHorizontalBlock"] .stButton > button:hover {
  background: #e7f0ec !important;
  transform: translateY(-1px);
}

div[data-testid="stMetric"] {
  background: rgba(255, 253, 248, 0.7);
  border: 1px solid var(--paper-edge);
  border-radius: 14px;
  padding: 0.55rem 0.7rem;
}

div[data-testid="stMetric"] label {
  color: var(--ink-soft) !important;
}

@keyframes ogn-rise {
  from {
    opacity: 0;
    transform: translateY(14px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (max-width: 768px) {
  .ogn-brand {
    font-size: 2.2rem;
  }
  .block-container {
    padding-left: 1rem !important;
    padding-right: 1rem !important;
  }
}
"""


def apply_styles():
    """
    Inject custom CSS into the Streamlit app.

    :return: None
    """
    import streamlit as st

    st.markdown(f"<style>{APP_CSS}</style>", unsafe_allow_html=True)


def render_hero():
    """
    Render the branded hero header.

    :return: None
    """
    import streamlit as st

    st.markdown(
        """
        <div class="ogn-hero">
          <div class="ogn-kicker">Personal card notes</div>
          <h1 class="ogn-brand">one.<span>good</span>.note</h1>
          <p class="ogn-sub">
            Write something that sounds like you — specific, human, and ready to copy onto a real card.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
