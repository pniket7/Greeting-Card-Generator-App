# Rooting For You — Personal Note Generator

A premium personal note-writing service that turns rough personal details into sincere, specific, copy-ready card notes, texts, or emails. This repository contains the premium, modern-stack FastAPI + Tailwind CSS web application, fully aligned with the Notion Website Wireframe v3 specification.

---

## 🚀 The Modern Web Stack (FastAPI + Tailwind CSS)

We have consolidated the entire application into a single, clean directory under `greeting_card_notes_web/` delivering a highly editorial, premium single-page web app. It strictly implements the **Website Wireframe v3** design specifications:
- **Visual Direction**: Spacious, editorial off-white paper and charcoal-black aesthetic.
- **Typography**: Editorial serif headings (`Lora`) and calm modern sans-serif navigation/inputs (`Inter`).
- **Interactive Flow**: A clean 3-step wizard (Email Setup &rarr; Who & Why &rarr; Specifics) followed by a final tactile, visual card preview.
- **Assisted Refinements**: Enforces the strict rule-set limit of up to 2 AI refinements (Warmer, Restrained, More Direct, or Custom additions) with complete safety (option to restore original draft).
- **Manual Editing**: Unlimited in-place manual note text editing and local downloads (.txt).

---

## ☁️ Shareable Cloud Deployment (Free & Public)

To share this premium app with teammates, customers, or anyone else on the web, you need to host the backend where it can run 24/7.

Here are the two best **free** and highly secure cloud hosting platforms that support our modern FastAPI stack:

### Option A: Hugging Face Spaces (Docker) — ✦ Recommended (100% Free Forever, No Limits)

Hugging Face Spaces is an incredible platform that lets you host containerized web apps completely for free. It does not require a credit card, has no usage limits, and gives you a beautiful public URL.

1. **Create an Account**: Go to [huggingface.co](https://huggingface.co) and sign up for a free account.
2. **Create a New Space**:
   - Click your profile image in the top right &rarr; **New Space**.
   - **Space Name**: Choose a name (e.g. `rooting-for-you`).
   - **SDK**: Select **Docker** (very important).
   - **Docker Template**: Select **Blank** (or none).
   - **Space Hardware**: Choose the default **CPU Basic (Free)**.
   - **Visibility**: Set to **Public**.
   - Click **Create Space**.
3. **Add your Gemini API Key**:
   - Inside your new Space, click the **Settings** tab.
   - Scroll down to the **Variables and Secrets** section.
   - Click **New Secret**.
   - **Name**: `GOOGLE_API_KEY`
   - **Value**: (Paste your Google Gemini API Key here)
   - Click **Save**.
4. **Upload your Code**:
   - Go to the **Files** tab of your Space and click **Add File** &rarr; **Upload Files**.
   - Drag and drop **all files** inside `one.good.note-main/one.good.note-main/greeting_card_notes_web/` (including `Dockerfile`, `requirements.txt`, `run.py`, the `backend/` folder, and the `frontend/` folder) directly into the root of the upload container.
   - Commit changes.
5. **Launch**: Hugging Face will automatically read the `Dockerfile`, build your container, and start your live public URL (e.g., `https://username-rooting-for-you.hf.space`) within 2 minutes!

---

### Option B: Render.com (Free Web Service)

Render connects directly to your GitHub repository and automatically deploys your code.

1. **Push your code to GitHub** (make sure your repo is private if you have secrets, though `GOOGLE_API_KEY` will be saved as an environment variable and is totally safe).
2. **Sign up at Render**: Create a free account on [render.com](https://render.com).
3. **Create a Web Service**:
   - Click **New +** &rarr; **Web Service**.
   - Connect your GitHub repository.
   - **Root Directory**: `one.good.note-main/one.good.note-main/greeting_card_notes_web`
   - **Runtime**: `Docker` (Render will automatically build and run the Dockerfile)
4. **Add Environment Secrets**:
   - `GOOGLE_API_KEY` = your Gemini API key
   - `SUPABASE_URL` = `https://xxxx.supabase.co`
   - `SUPABASE_SERVICE_ROLE_KEY` = your service role key
5. **Deploy**: Render will build the site and give you a free public link.
   *Note: Free Render web services spin down after 15 minutes of inactivity. The next visitor will experience a "cold start" delay of about 50 seconds to boot the server back up.*

---

## 📊 Supabase Logging (inputs + prompts + responses)

Every generate/refine run can be stored in Supabase for debugging and product analysis.

### What gets stored

**`note_sessions`** — one row per generated note:
- user inputs (email optional, occasion, relationship, known_context, etc.)
- final note, verdict, refinement count

**`note_events`** — one row per pipeline stage:
- `writer` / `reviewer` / `reviser` / `refine`
- full formatted **prompt**
- full model **response**
- parsed note + metadata (verdict, failures, instruction)

### Setup (free Supabase account)

1. Create a free project at [supabase.com](https://supabase.com)
2. Open **SQL Editor** → paste and run `greeting_card_notes_web/supabase_schema.sql`
3. Open **Project Settings → API** and copy:
   - Project URL → `SUPABASE_URL`
   - `service_role` key → `SUPABASE_SERVICE_ROLE_KEY` (server only; never put in frontend)
4. Add both env vars to Render (and optionally local `.env`)
5. Redeploy. Generate a note, then open Supabase **Table Editor**:
   - `note_sessions` for the run summary
   - `note_events` for prompt/response traces

If Supabase env vars are missing, the app still works — logging is skipped with a warning in Render logs.

---

## 💻 Running Locally

### Running the Modern Stack

1. **Install dependencies**:
   ```bash
   pip install -r one.good.note-main/one.good.note-main/greeting_card_notes_web/requirements.txt
   ```

2. **Set keys** in the project root `.env`:
   ```env
   GOOGLE_API_KEY="your-gemini-api-key"
   SUPABASE_URL="https://xxxx.supabase.co"
   SUPABASE_SERVICE_ROLE_KEY="your-service-role-key"
   ```

3. **Start the server**:
   ```bash
   python one.good.note-main/one.good.note-main/greeting_card_notes_web/run.py
   ```

4. Open your browser and go to: **[http://127.0.0.1:8000](http://127.0.0.1:8000)**

---

## 🛠️ Folder Layout

```text
one.good.note-main/
  greeting_card_notes_web/
    backend/
      main.py
      prompts/
      services/
        note_pipeline.py
        logging_service.py      # Supabase session + event logging
        occasion_metadata.py
        parsers.py
        gemini_client.py
        card_image.py
    frontend/
      index.html
    supabase_schema.sql         # Run once in Supabase SQL Editor
    requirements.txt
    Dockerfile
    run.py
```

---

## ✦ Core Writing Architecture

Our LLM prompt pipeline is built using the **Mark → Meaning → Land** architecture:
1. **Mark the moment**: Sincere acknowledgement of the occasion with appropriate emotional energy.
2. **Give it meaning**: Anchor the note in exactly ONE observed quality, effort, or relationship habit (reusing user rough inputs). No fabricated facts.
3. **Land emotionally**: Close with a natural relational wish, supportive offer, or warm anticipation suited to the relationship closeness.

Our specialized **Reviewer Agent** verifies quality against **8 Core Rules**:
- `[MEANING]` `[FOCUS]` `[FIT]` `[FEELING]` `[TRUTH]` `[VOICE]` `[FREEDOM]` `[RESTRAINT]`
