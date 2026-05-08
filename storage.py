"""
storage.py — Airtable storage module.

Creates a new record in the configured Airtable base/table from the
structured analysis output.
Requires AIRTABLE_API_KEY, AIRTABLE_BASE_ID, and AIRTABLE_TABLE_ID in .env.
"""

import datetime
import os

import requests
from dotenv import load_dotenv

_ALLOWED = {
    "Meeting Type": {"Founder Call", "Investor Call", "Customer", "Other"},
    "Deal Stage Signal": {"Cold", "Warming", "Hot", "Closed-Won", "Closed-Lost", "N/A"},
    "Sentiment": {"Positive", "Neutral", "Negative", "Mixed"},
}


def _format_key_points(key_points: list) -> str:
    return "\n".join(f"• {point}" for point in key_points)


def _format_action_items(action_items: list) -> str:
    lines = []
    for item in action_items:
        task = item.get("task", "")
        owner = item.get("owner", "")
        due = item.get("due_date")
        line = f"• {task} — Owner: {owner}"
        if due:
            line += f", Due: {due}"
        lines.append(line)
    return "\n".join(lines)


def _warn_if_invalid(fields: dict) -> None:
    for field, allowed in _ALLOWED.items():
        value = fields.get(field, "")
        if value and value not in allowed:
            print(
                f"⚠️  '{field}' value '{value}' is not in the allowed set "
                f"{allowed} — Airtable may reject this with a 422."
            )


def save_to_airtable(analysis_dict: dict) -> str:
    """POST analysis results to Airtable and return the URL of the created record.

    Args:
        analysis_dict: Structured dict produced by analyze_transcript().

    Returns:
        The full clickable URL of the created Airtable record.

    Raises:
        EnvironmentError: If any required Airtable env var is missing.
        RuntimeError: If the Airtable API returns a non-200 response.
    """
    load_dotenv()

    api_key = os.environ.get("AIRTABLE_API_KEY")
    base_id = os.environ.get("AIRTABLE_BASE_ID")
    table_id = os.environ.get("AIRTABLE_TABLE_ID")

    for name, val in [
        ("AIRTABLE_API_KEY", api_key),
        ("AIRTABLE_BASE_ID", base_id),
        ("AIRTABLE_TABLE_ID", table_id),
    ]:
        if not val:
            raise EnvironmentError(f"{name} is not set. Add it to your .env file.")

    follow_up = analysis_dict.get("follow_up_email", {}) or {}
    subject = follow_up.get("subject", "")
    body = follow_up.get("body", "")
    email_draft = f"Subject: {subject}\n\n{body}" if subject else body

    fields = {
        "Meeting Title": analysis_dict.get("meeting_title", ""),
        "Date": analysis_dict.get("date") or datetime.date.today().isoformat(),
        "Contact Name": analysis_dict.get("contact_name", ""),
        "Company": analysis_dict.get("company", ""),
        "Meeting Type": analysis_dict.get("meeting_type", ""),
        "Summary": analysis_dict.get("summary", ""),
        "Key Points": _format_key_points(analysis_dict.get("key_points", [])),
        "Action Items": _format_action_items(analysis_dict.get("action_items", [])),
        "Deal Stage Signal": analysis_dict.get("deal_stage_signal", ""),
        "Sentiment": analysis_dict.get("overall_sentiment", ""),
        "Follow-up Email Draft": email_draft,
    }

    _warn_if_invalid(fields)

    endpoint = f"https://api.airtable.com/v0/{base_id}/{table_id}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    print("📊 Pushing record to Airtable...")
    response = requests.post(endpoint, headers=headers, json={"fields": fields})

    if response.status_code != 200:
        print(f"❌ Airtable returned {response.status_code}: {response.text}")
        raise RuntimeError(
            f"Airtable API error {response.status_code}: {response.text}"
        )

    record_id = response.json()["id"]
    record_url = f"https://airtable.com/{base_id}/{table_id}/{record_id}"
    print(f"✅ Airtable record created: {record_url}")

    return record_url


def create_airtable_record(analysis_dict: dict) -> str:
    """Backward-compatible alias used by pipeline.py."""
    return save_to_airtable(analysis_dict)
