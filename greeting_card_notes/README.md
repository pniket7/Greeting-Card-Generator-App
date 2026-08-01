# Greeting Card Notes (Prototype)

A starting-point web app that turns a few personal details into a copy-ready greeting-card note using Gemini.

## What it does

1. Collects occasion, relationship, tone, length, and personal details
2. Runs a **writer** prompt 
3. Optionally runs a **review → revise** loop (PASS/FAIL criteria)
4. Shows a copy-ready note, plus quick refinements (shorter / warmer / etc.)

## Setup

### Local (`.env`)

In the project root `.env`:

```env
GOOGLE_API_KEY="your-google-api-key"
```

### Streamlit Community Cloud (secrets)

In the Streamlit Cloud app → **Settings → Secrets**, add:

```toml
GOOGLE_API_KEY = "your-google-api-key"
```

The app reads `GOOGLE_API_KEY` from env first, then falls back to Streamlit secrets.

## Run

From the repo root:

```bash
streamlit run greeting_card_notes/app.py
```

## Deploy (shareable link)

1. Push this repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Deploy with:
   - Main file: `greeting_card_notes/app.py`
   - Requirements file: `greeting_card_notes/requirements.txt`
4. Add the Streamlit secret above
5. Share the `*.streamlit.app` URL

## Folder layout

```text
greeting_card_notes/
  app.py                     # Streamlit UI
  prompts/
    writer_prompt.py         # Note generation prompt
    reviewer_prompt.py       # PASS/FAIL quality review
    reviser_prompt.py        # Feedback-based revision
  services/
    gemini_client.py         # Gemini API wrapper
    parsers.py               # XML output parsers
    note_pipeline.py         # Write → review → revise orchestration
```

## Prototype scope

Included:
- Text-only note generation
- Structured prompts with evaluation scratchpads + XML output
- Optional quality loop

Not included (on purpose):
- Auth / billing
- Image generation
- Print + shipping
- Model training / fine-tuning