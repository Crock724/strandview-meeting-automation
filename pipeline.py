"""
pipeline.py — Main entry point for the AI meeting workflow automation.

Usage:
    python pipeline.py path/to/transcript.txt
    python pipeline.py path/to/audio.mp3
    python pipeline.py path/to/transcript.txt --skip-email
    python pipeline.py path/to/transcript.txt --skip-storage
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import transcription
import analysis
import storage
import email_draft


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AI meeting workflow automation pipeline."
    )
    parser.add_argument(
        "input_file",
        type=Path,
        help="Path to a transcript .txt file or an audio file (mp3, wav, m4a, etc.)",
    )
    parser.add_argument(
        "--skip-email",
        action="store_true",
        help="Skip the Gmail draft phase (useful for testing without burning Gmail API quota).",
    )
    parser.add_argument(
        "--skip-storage",
        action="store_true",
        help="Skip the Airtable storage phase (useful for testing analysis only).",
    )
    return parser.parse_args()


def _section(title: str) -> None:
    print()
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)


def _slugify(name: str) -> str:
    name = name.lower()
    name = re.sub(r"[^\w\s]", "", name)
    name = re.sub(r"\s+", "_", name.strip())
    return name


def _save_json(analysis_dict: dict) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    contact = analysis_dict.get("contact_name", "unknown")
    slug = _slugify(contact) or "unknown"
    out_dir = Path("outputs")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{timestamp}_{slug}.json"
    out_path.write_text(
        json.dumps(analysis_dict, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return out_path


def _summary_box(
    analysis_dict: dict,
    airtable_url: str | None,
    draft_result: dict | None,
    json_path: Path,
) -> None:
    meeting = analysis_dict.get("meeting_title", "—")
    contact = analysis_dict.get("contact_name", "—")
    company = analysis_dict.get("company", "")
    stage = analysis_dict.get("deal_stage_signal", "—")
    sentiment = analysis_dict.get("overall_sentiment", "—")

    contact_line = f"{contact} ({company})" if company else contact
    airtable_str = airtable_url or "(skipped)"
    gmail_str = draft_result["url"] if draft_result else "(skipped)"
    json_str = str(json_path)

    W = 46
    inner = W - 2
    content_w = inner - 4  # space after "║  " and before "║"

    def _trunc(text: str, max_len: int) -> str:
        return text if len(text) <= max_len else text[: max_len - 3] + "..."

    def row(label: str, value: str) -> str:
        field = f"{label:<10}{_trunc(value, content_w - 10)}"
        return f"║  {field:<{content_w}}  ║"

    print()
    print("╔" + "═" * inner + "╗")
    print("║" + "PIPELINE COMPLETE".center(inner) + "║")
    print("╠" + "═" * inner + "╣")
    print(row("Meeting:", meeting))
    print(row("Contact:", contact_line))
    print(row("Stage:", stage))
    print(row("Sentiment:", sentiment))
    print("╚" + "═" * inner + "╝")
    print()
    print(f"📊 Airtable: \033]8;;{airtable_str}\033\\{airtable_str}\033]8;;\033\\" if airtable_url else "📊 Airtable: (skipped)")
    print(f"📧 Gmail:    \033]8;;{gmail_str}\033\\{gmail_str}\033]8;;\033\\" if draft_result else "📧 Gmail:    (skipped)")
    print(f"💾 JSON:     {json_str}")
    print()


def main() -> None:
    args = parse_args()
    input_path: Path = args.input_file

    if not input_path.exists():
        print(f"Error: file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    # ── PHASE 1: TRANSCRIPTION ──────────────────────────────────────────────
    _section("PHASE 1: TRANSCRIPTION")
    try:
        transcription_dict = transcription.process_input(input_path)
    except Exception as exc:
        print(f"\n❌ PHASE 1 FAILED: {exc}", file=sys.stderr)
        sys.exit(1)

    # ── PHASE 2: ANALYSIS ───────────────────────────────────────────────────
    _section("PHASE 2: ANALYSIS")
    try:
        analysis_dict = analysis.analyze(transcription_dict)
    except Exception as exc:
        print(f"\n❌ PHASE 2 FAILED: {exc}", file=sys.stderr)
        sys.exit(2)

    # ── PHASE 3: STORAGE ────────────────────────────────────────────────────
    _section("PHASE 3: STORAGE")
    airtable_url = None
    if args.skip_storage:
        print("⏭️  Storage skipped (--skip-storage).")
    else:
        try:
            airtable_url = storage.save_to_airtable(analysis_dict)
        except Exception as exc:
            print(f"\n❌ PHASE 3 FAILED: {exc}", file=sys.stderr)
            sys.exit(3)

    # ── PHASE 4: EMAIL DRAFT ────────────────────────────────────────────────
    _section("PHASE 4: EMAIL DRAFT")
    draft_result = None
    if args.skip_email:
        print("⏭️  Email draft skipped (--skip-email).")
    else:
        try:
            draft_result = email_draft.create_draft(analysis_dict)
        except Exception as exc:
            print(f"\n❌ PHASE 4 FAILED: {exc}", file=sys.stderr)
            sys.exit(4)

    # ── SAVE JSON ───────────────────────────────────────────────────────────
    _section("SAVING OUTPUT")
    json_path = _save_json(analysis_dict)
    print(f"💾 Analysis saved to: {json_path}")

    # ── SUMMARY ─────────────────────────────────────────────────────────────
    _summary_box(analysis_dict, airtable_url, draft_result, json_path)


if __name__ == "__main__":
    main()
