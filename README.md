# Meeting Intelligence Pipeline — From Raw Audio to CRM in 60 Seconds

Drop in a meeting recording. Walk away with a structured deal summary, a pre-drafted follow-up email sitting in your Gmail, and a live Airtable record — all without touching a keyboard.

This project is an end-to-end automation pipeline built for investment and business development workflows where post-meeting admin is the enemy of momentum. It chains four APIs in sequence — AssemblyAI for speech-to-text, Claude for structured intelligence extraction, Airtable for CRM persistence, and Gmail for draft generation — into a single CLI command that runs in under a minute per call.

The motivation is simple: the most valuable 10 minutes after a founder call are usually spent writing notes instead of thinking about the deal. This pipeline handles the former so you can focus on the latter.

---

## Architecture

The pipeline runs in four sequential phases, each one feeding structured data to the next.

**Phase 1 — Transcription (AssemblyAI).** The pipeline accepts either a raw audio file (`.m4a`, `.mp3`, `.wav`) or a pre-existing `.txt` transcript. If audio is provided, it's uploaded to AssemblyAI's async transcription API and polled until complete. The result is a clean transcript string passed forward to analysis.

**Phase 2 — Analysis (Claude Sonnet 4.5).** The transcript is sent to Claude with a structured prompt that asks for: a meeting title, contact and company name, a 2–3 sentence executive summary, a list of key discussion points, all action items with owners and due dates, a deal stage signal (`Hot / Warm / Cold`), overall sentiment, and a fully drafted follow-up email in the voice of the Strandview partner. Claude returns a single JSON object — no post-processing gymnastics required.

**Phase 3 — Storage (Airtable).** The parsed JSON is mapped to an Airtable record via the REST API. Each meeting becomes a row with fields for the deal name, company, contact, stage signal, sentiment, summary, and a serialized copy of the action items. The record URL is surfaced in the terminal output for one-click access.

**Phase 4 — Email Draft (Gmail API).** The `follow_up_email` object from the Claude response is encoded and pushed to Gmail as a draft via OAuth 2.0. The draft lands in the sender's Drafts folder, addressed and subject-lined, ready for a human to review and send. No email is ever sent automatically.

```
audio/transcript
      │
      ▼
 transcription.py  ── AssemblyAI async transcription
      │
      ▼
   analysis.py     ── Claude: extract deal intelligence → JSON
      │
      ├──▶ storage.py      ── Airtable REST API → CRM record
      │
      └──▶ email_draft.py  ── Gmail API → draft in Drafts folder
```

The full structured output is also saved locally as a timestamped JSON file in `outputs/`.

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/your-username/strandview-assignment.git
cd strandview-assignment
```

### 2. Create and activate a virtual environment

```bash
# macOS / Linux
python -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in each value:

```ini
ASSEMBLYAI_API_KEY=your_assemblyai_api_key_here

ANTHROPIC_API_KEY=your_anthropic_api_key_here

AIRTABLE_API_KEY=your_airtable_api_key_here
AIRTABLE_BASE_ID=your_airtable_base_id_here      # looks like appXXXXXXXXXXXXXX
AIRTABLE_TABLE_ID=your_airtable_table_name_or_id  # table name or tblXXXXXXXX
```

| Variable | Where to get it |
|---|---|
| `ASSEMBLYAI_API_KEY` | [app.assemblyai.com](https://app.assemblyai.com) → API Keys |
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) → API Keys |
| `AIRTABLE_API_KEY` | Airtable account → Developer Hub → Personal access tokens |
| `AIRTABLE_BASE_ID` | Your Airtable base URL: `airtable.com/appXXXXXX/...` |
| `AIRTABLE_TABLE_ID` | Table name or the `tblXXXXXX` ID from the URL |

**Airtable base setup:** Create a new base with a table that has these fields: `Meeting Title` (Single line text), `Company` (Single line text), `Contact` (Single line text), `Meeting Type` (Single line text), `Deal Stage Signal` (Single line text), `Sentiment` (Single line text), `Summary` (Long text), `Action Items` (Long text), `Key Points` (Long text).

### 5. Configure Gmail OAuth

1. Go to [Google Cloud Console](https://console.cloud.google.com) and create a new project.
2. Navigate to **APIs & Services → Library** and enable the **Gmail API**.
3. Go to **APIs & Services → Credentials** and create an **OAuth 2.0 Client ID** (Application type: Desktop app).
4. Download the credentials file and save it as `credentials.json` in the project root.
5. On first run, a browser window will open for you to authorize access. The token is cached as `token.json` automatically — you won't be prompted again.

> `credentials.json` and `token.json` are git-ignored. Never commit them.

---

## Usage

```bash
python pipeline.py sample_transcripts/founder_call_001.m4a
```

That's it. Here's what happens:

| Phase | What it does | Time |
|---|---|---|
| **Transcription** | Uploads audio to AssemblyAI, polls until complete | ~20–40s |
| **Analysis** | Sends transcript to Claude, receives structured JSON | ~5–10s |
| **Storage** | Creates an Airtable record, returns a direct URL | ~1s |
| **Email Draft** | Pushes the follow-up draft to Gmail Drafts | ~1s |

When it finishes, the terminal prints a summary box:

```
╔════════════════════════════════════════════╗
║              PIPELINE COMPLETE             ║
╠════════════════════════════════════════════╣
║  Meeting:  Lumen Logistics Seed Pitch      ║
║  Contact:  Marcus (Lumen)                  ║
║  Stage:    Hot                             ║
║  Sentiment:Positive                        ║
╚════════════════════════════════════════════╝

📊 Airtable: https://airtable.com/appXXX/tblXXX/...
📧 Gmail:    https://mail.google.com/mail/u/0/#drafts/...
💾 JSON:     outputs/20260507_234438_marcus.json
```

You can also pass a `.txt` transcript directly to skip the transcription phase, or use flags to isolate specific phases during development:

```bash
# Skip email drafting
python pipeline.py sample_transcripts/founder_call_001.m4a --skip-email

# Skip Airtable storage
python pipeline.py sample_transcripts/founder_call_001.m4a --skip-storage

# Analyze a pre-existing transcript
python pipeline.py sample_transcripts/example_transcript.txt
```

---

## Tech Stack

- **[AssemblyAI](https://www.assemblyai.com/)** — Handles async speech-to-text with high accuracy across accents and noisy environments; the async polling model means we're not blocked waiting on a slow HTTP response.
- **[Anthropic Claude Sonnet 4.5](https://www.anthropic.com/)** — Extracts structured deal intelligence from unstructured conversation; instruction-following and JSON output quality are consistently strong enough that we don't need schema validation layers on top.
- **[Airtable](https://airtable.com/)** — Acts as a lightweight CRM with a REST API that's fast to iterate on; non-engineers on the team can see, filter, and update meeting records without touching any code.
- **[Gmail API](https://developers.google.com/gmail)** — Creates drafts directly in the sender's inbox via OAuth 2.0; the human stays in the loop and no email is ever sent without review.
- **Python** — Glue language of choice; clean module boundaries (`transcription`, `analysis`, `storage`, `email_draft`) keep each integration independently testable and swappable.

---

## Cost

The pipeline is cheap to run. Here's a rough breakdown per meeting:

| Service | Cost |
|---|---|
| AssemblyAI transcription (~45 min audio) | ~$0.27 |
| Claude Sonnet 4.5 (input + output tokens) | ~$0.05–0.10 |
| Airtable, Gmail API | Free tier |
| **Total per meeting** | **< $0.40** |

At 10 calls per week (40/month), you're looking at roughly **$16–18/month** in API costs. Even with headroom for longer calls and retries, staying under $35/month at that volume is straightforward.

---

## Sample Output

All pipeline outputs are saved to the `outputs/` directory as timestamped JSON files. Here's the structure, drawn from a real run on `founder_call_001.m4a`:

**`outputs/20260507_234438_marcus.json`**

```json
{
  "meeting_title": "Lumen Logistics Seed Pitch",
  "contact_name": "Marcus",
  "company": "Lumen",
  "meeting_type": "Founder Call",
  "deal_stage_signal": "Hot",
  "overall_sentiment": "Positive",
  "summary": "Marcus (Founder/CEO) and Sarah (Strandview) discussed Lumen's $4M seed raise for their AI-native logistics orchestration platform targeting mid-market shippers. Lumen has 19 paying customers, $240K ARR growing 35% MoM, and 82% gross margins with a 3-week onboarding vs. 9 months for incumbents like Project44.",
  "key_points": [
    "Raising $4M seed; $2M soft-circled from Bain Capital Ventures and Flexport angels",
    "19 paying customers, $240K ARR, 35% MoM growth, 82% gross margins",
    "AI-powered onboarding: 3 weeks vs. 9 months for incumbents"
  ],
  "action_items": [
    {
      "task": "Send financial model, customer list, and reference contacts",
      "owner": "Marcus",
      "due_date": null
    },
    {
      "task": "Present Lumen at Strandview investment committee",
      "owner": "Sarah",
      "due_date": null
    }
  ],
  "follow_up_email": {
    "subject": "Lumen Seed Round — Next Steps & Materials Request",
    "body": "Hi Marcus, ..."
  }
}
```

The full file — including the complete drafted email — is in `outputs/20260507_234438_marcus.json`.

---

## Roadmap

### Pre-call Intelligence Briefs

The obvious next feature is flipping the pipeline around: instead of processing what happened after a call, generate a brief _before_ it.

Given a founder name and company, the pipeline could pull recent news (Crunchbase, TechCrunch, LinkedIn), summarize their last funding round and investor list, flag any competitive signals or red flags, and surface questions worth asking — all delivered as a one-page brief 30 minutes before the meeting starts.

This would close the loop on the full meeting lifecycle: arrive prepared, run the call, and walk away with next steps handled — without any manual research or note-taking at any stage.
