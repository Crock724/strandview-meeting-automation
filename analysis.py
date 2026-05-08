"""
analysis.py — Claude API analysis module.

Sends the meeting transcript (plus optional AssemblyAI NLP enrichment) to Claude
and returns structured JSON: summary, key points, action items, deal-stage signal,
sentiment, and a drafted follow-up email.
Requires ANTHROPIC_API_KEY in .env.
"""

import json
import os
from typing import Any

import anthropic
from dotenv import load_dotenv

MODEL = "claude-sonnet-4-5"

SYSTEM_PROMPT = (
    "You are an executive assistant at Strandview, a venture capital firm. "
    "Your role is to process meeting transcripts and extract structured intelligence "
    "for the investment team. You summarize calls, extract clear action items with "
    "owners and due dates, infer deal stage signals from language and context, and "
    "draft professional follow-up emails on behalf of the Strandview team. "
    "Always respond with raw, valid JSON only — no markdown fences, no commentary, "
    "no preamble."
)

_JSON_SCHEMA = """{
  "meeting_title": "string — concise title like 'Lumen Logistics Seed Pitch'",
  "date": "YYYY-MM-DD or null if not mentioned",
  "contact_name": "string — primary external person",
  "company": "string — primary external company",
  "meeting_type": "Founder Call | Investor Call | Customer | Other",
  "summary": "3-4 sentence executive summary of the call",
  "key_points": ["bullet 1", "bullet 2", ...],
  "action_items": [{"task": "...", "owner": "person name", "due_date": "YYYY-MM-DD or null"}],
  "deal_stage_signal": "Cold | Warming | Hot | Closed-Won | Closed-Lost | N/A",
  "overall_sentiment": "Positive | Neutral | Negative | Mixed",
  "follow_up_email": {
    "to": "email address if mentioned, else empty string",
    "subject": "professional subject line",
    "body": "full email body referencing specific call details, signed from the Strandview side"
  }
}"""


def _build_user_prompt(transcription_dict: dict) -> str:
    transcript = transcription_dict.get("transcript", "")
    nlp_enriched = transcription_dict.get("nlp_enriched", False)

    parts = [
        "Analyze the meeting transcript below and return ONLY valid JSON matching this schema:\n",
        f"SCHEMA:\n{_JSON_SCHEMA}\n",
        f"TRANSCRIPT:\n{transcript}",
    ]

    if nlp_enriched:
        sentiment = transcription_dict.get("sentiment_summary")
        if sentiment:
            parts.append(
                "\nSENTIMENT SUMMARY (from AssemblyAI):\n"
                f"  Positive: {sentiment.get('positive', 0)}, "
                f"Neutral: {sentiment.get('neutral', 0)}, "
                f"Negative: {sentiment.get('negative', 0)}"
            )

        entities = transcription_dict.get("entities", [])
        if entities:
            top = entities[:30]
            lines = [f"  - {e['text']} ({e['entity_type']})" for e in top]
            parts.append(f"\nDETECTED ENTITIES (top {len(top)}):\n" + "\n".join(lines))

        chapters = transcription_dict.get("chapters", [])
        if chapters:
            lines = [
                f"  - [{c['gist']}] {c['headline']}: {c['summary']}"
                for c in chapters
            ]
            parts.append("\nCHAPTERS:\n" + "\n".join(lines))

        topics = transcription_dict.get("topics", [])
        if topics:
            lines = [
                f"  - {t['label']} (relevance: {t['relevance']})"
                for t in topics[:15]
            ]
            parts.append("\nTOPICS:\n" + "\n".join(lines))

    return "\n".join(parts)


def _strip_fences(text: str) -> str:
    """Remove markdown code fences Claude sometimes wraps JSON in."""
    text = text.strip()
    if text.startswith("```"):
        text = text[text.index("\n") + 1:] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[: text.rfind("```")]
    return text.strip()


def _call_claude(client: anthropic.Anthropic, user_prompt: str, prefix: str = "") -> str:
    content = (prefix + "\n\n" + user_prompt) if prefix else user_prompt
    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content}],
    )
    return response.content[0].text


def analyze(transcription_dict: dict) -> dict[str, Any]:
    """Analyze a meeting transcript dict with Claude and return structured output.

    Args:
        transcription_dict: Dict produced by transcription.process_input(), with keys:
            transcript, nlp_enriched, speaker_segments, entities,
            sentiment_summary, chapters, topics.

    Returns:
        Parsed dict matching the analysis JSON schema.

    Raises:
        EnvironmentError: If ANTHROPIC_API_KEY is not set.
        ValueError: If Claude's response cannot be parsed as JSON after one retry.
    """
    load_dotenv()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY is not set. Add it to your .env file.")

    client = anthropic.Anthropic(api_key=api_key)
    user_prompt = _build_user_prompt(transcription_dict)

    print("🤖 Sending transcript to Claude for analysis...")
    raw = _call_claude(client, user_prompt)

    try:
        result = json.loads(_strip_fences(raw))
    except json.JSONDecodeError:
        print("⚠️  JSON parse failed — retrying with stricter instruction...")
        raw = _call_claude(
            client,
            user_prompt,
            prefix="RETURN ONLY RAW JSON, NO MARKDOWN, NO CODE FENCES, NO COMMENTARY.",
        )
        try:
            result = json.loads(_strip_fences(raw))
        except json.JSONDecodeError as exc:
            raise ValueError(
                "Claude returned non-JSON response after retry.\n"
                f"Raw response:\n{raw}"
            ) from exc

    key_points = result.get("key_points", [])
    action_items = result.get("action_items", [])
    print(
        f"✅ Analysis complete. Extracted {len(key_points)} key points "
        f"and {len(action_items)} action items."
    )

    return result


# Backward-compat alias — pipeline.py imports this name
analyze_transcript = analyze
