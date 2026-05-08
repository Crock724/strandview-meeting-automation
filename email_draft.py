"""
email_draft.py — Gmail draft creation module.

Composes a follow-up email from the meeting analysis and saves it as a
Gmail draft via the Gmail API (OAuth2).
Requires credentials.json (OAuth client secret) and will write token.json
after the first authorization flow.
"""

import base64
from email.mime.text import MIMEText
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/gmail.compose"]
_CREDENTIALS_FILE = Path(__file__).parent / "credentials.json"
_TOKEN_FILE = Path(__file__).parent / "token.json"
_DRAFTS_URL = "https://mail.google.com/mail/u/0/#drafts"


def _get_credentials() -> Credentials:
    creds = None
    if _TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(_TOKEN_FILE), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not _CREDENTIALS_FILE.exists():
                raise FileNotFoundError(
                    f"credentials.json not found at {_CREDENTIALS_FILE}. "
                    "Download it from Google Cloud Console (OAuth 2.0 Client ID)."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(_CREDENTIALS_FILE), SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open(_TOKEN_FILE, "w") as fh:
            fh.write(creds.to_json())
    return creds


def create_draft(analysis_dict: dict) -> dict:
    """Compose a follow-up email and save it as a Gmail draft.

    Args:
        analysis_dict: Structured analysis output from analyze_transcript(), must
            contain a 'follow_up_email' key with 'to', 'subject', and 'body'.

    Returns:
        Dict with keys 'draft_id' (Gmail draft ID string) and 'url' (drafts inbox URL).

    Raises:
        FileNotFoundError: If credentials.json is missing.
        RuntimeError: If authentication or the Gmail API call fails.
    """
    try:
        print("📧 Authenticating with Gmail...")
        creds = _get_credentials()

        follow_up = analysis_dict.get("follow_up_email", {})
        to = follow_up.get("to") or ""
        subject = follow_up.get("subject", "")
        body = follow_up.get("body", "")

        message = MIMEText(body, "plain")
        message["to"] = to
        message["subject"] = subject
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

        print("📧 Creating Gmail draft...")
        service = build("gmail", "v1", credentials=creds)
        draft = (
            service.users()
            .drafts()
            .create(userId="me", body={"message": {"raw": raw}})
            .execute()
        )

        draft_id = draft.get("id", "")
        print(f"✅ Draft created. View at: {_DRAFTS_URL}")
        return {"draft_id": draft_id, "url": _DRAFTS_URL}

    except FileNotFoundError:
        raise
    except HttpError as exc:
        msg = f"Gmail API error {exc.status_code}: {exc.reason}"
        print(f"❌ {msg}")
        raise RuntimeError(msg) from exc
    except Exception as exc:
        msg = f"Failed to create Gmail draft: {exc}"
        print(f"❌ {msg}")
        raise RuntimeError(msg) from exc


def create_gmail_draft(analysis_dict: dict) -> str:
    """Backward-compatible wrapper — returns just the draft ID string."""
    return create_draft(analysis_dict)["draft_id"]
