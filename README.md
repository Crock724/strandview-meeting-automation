# AI Meeting Workflow Automation

Automatically transcribes meeting audio, extracts action items and summaries via Claude, stores results in Airtable, and drafts follow-up emails via Gmail.

## Pipeline overview

```
Audio / Transcript
       │
       ▼
 transcription.py   (AssemblyAI)
       │
       ▼
   analysis.py      (Claude)
       │
       ├──▶ storage.py     (Airtable record)
       │
       └──▶ email_draft.py (Gmail draft)
```

## Setup

### 1. Clone and activate the virtual environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python -m venv venv
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

> `requirements.txt` will be added once dependencies are finalized.

### 3. Configure environment variables

```bash
cp .env.example .env
# Edit .env and fill in all API keys
```

| Variable | Where to get it |
|---|---|
| `ASSEMBLYAI_API_KEY` | [app.assemblyai.com](https://app.assemblyai.com) |
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) |
| `AIRTABLE_API_KEY` | Airtable account → API section |
| `AIRTABLE_BASE_ID` | From your Airtable base URL (`appXXXXXX`) |
| `AIRTABLE_TABLE_ID` | Table name or ID from Airtable |

### 4. Gmail OAuth credentials

1. Create a project in [Google Cloud Console](https://console.cloud.google.com).
2. Enable the **Gmail API**.
3. Create OAuth 2.0 credentials (Desktop app type).
4. Download and save as `credentials.json` in the project root.
5. On first run the browser will open for authorization; `token.json` is cached automatically.

### 5. Run the pipeline

```bash
# With an audio file
python pipeline.py path/to/meeting.mp3

# With an existing transcript
python pipeline.py sample_transcripts/example_transcript.txt
```

Outputs (Airtable record ID, Gmail draft ID) are printed to stdout.

## Project structure

```
.
├── pipeline.py            # CLI entry point
├── transcription.py       # AssemblyAI integration
├── analysis.py            # Claude integration
├── storage.py             # Airtable integration
├── email_draft.py         # Gmail draft integration
├── sample_transcripts/    # Example input files
├── outputs/               # Local output artifacts (git-ignored)
├── .env.example           # Environment variable template
└── .gitignore
```
