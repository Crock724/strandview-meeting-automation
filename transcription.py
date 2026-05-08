"""
transcription.py — AssemblyAI transcription module.

Handles audio-to-text transcription and loading of existing transcript files.
Loads ASSEMBLYAI_API_KEY from .env via python-dotenv.
"""

import sys
from pathlib import Path

import assemblyai as aai
from dotenv import load_dotenv
import os

load_dotenv()

AUDIO_EXTENSIONS = {".m4a", ".mp3", ".wav", ".mp4", ".flac"}

TranscriptDict = dict  # shape documented in process_input docstring


def process_input(file_path: str | Path) -> TranscriptDict:
    """Public entry point — detects file type and dispatches to the right handler.

    Returns a dict with the following keys:
        transcript        (str)   full transcript text
        nlp_enriched      (bool)  True when AssemblyAI NLP features were used
        speaker_segments  (list)  [{"speaker": str, "text": str, "start": int, "end": int}]
        entities          (list)  [{"text": str, "entity_type": str, "start": int, "end": int}]
        sentiment_summary (dict|None) {"positive": int, "neutral": int, "negative": int}
        chapters          (list)  [{"gist": str, "headline": str, "summary": str,
                                    "start": int, "end": int}]
        topics            (list)  [{"label": str, "relevance": float}]

    Args:
        file_path: Path to a .txt transcript or an audio file.

    Raises:
        SystemExit: If ASSEMBLYAI_API_KEY is missing.
        RuntimeError: If AssemblyAI returns an error status.
        ValueError: If the file extension is not recognised.
    """
    path = Path(file_path)
    ext = path.suffix.lower()

    _configure_api_key()

    if ext == ".txt":
        return load_transcript(path)
    elif ext in AUDIO_EXTENSIONS:
        return transcribe_audio(path)
    else:
        raise ValueError(
            f"Unsupported file type '{ext}'. "
            f"Expected .txt or one of {sorted(AUDIO_EXTENSIONS)}."
        )


def load_transcript(txt_path: Path) -> TranscriptDict:
    """Read a plain-text transcript file and return it in the standard dict shape.

    No NLP enrichment is performed — all enrichment fields are empty/None.

    Args:
        txt_path: Path to the .txt transcript file.

    Returns:
        TranscriptDict with nlp_enriched=False and all NLP fields empty.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    print(f"📁 Loading transcript from file: {txt_path}")
    text = txt_path.read_text(encoding="utf-8")
    print(f"✅ Transcript loaded ({len(text)} characters).")
    return {
        "transcript": text,
        "nlp_enriched": False,
        "speaker_segments": [],
        "entities": [],
        "sentiment_summary": None,
        "chapters": [],
        "topics": [],
    }


def transcribe_audio(audio_path: Path) -> TranscriptDict:
    """Transcribe an audio file via AssemblyAI with all NLP features enabled.

    Features enabled: speaker_labels, sentiment_analysis, entity_detection,
    auto_chapters, iab_categories.  The SDK handles upload and polling internally.

    Args:
        audio_path: Path to the local audio file.

    Returns:
        TranscriptDict with nlp_enriched=True and all NLP fields populated.

    Raises:
        RuntimeError: If AssemblyAI returns an error status.
    """
    print(f"🎙️  Submitting audio to AssemblyAI: {audio_path}")

    config = aai.TranscriptionConfig(
        speaker_labels=True,
        sentiment_analysis=True,
        entity_detection=True,
        auto_chapters=True,
        iab_categories=True,
    )
    config.speech_models = ["universal"]

    transcriber = aai.Transcriber()
    print("⏳ Transcription in progress (this takes 1-2 min for typical audio)...")
    transcript = transcriber.transcribe(str(audio_path), config=config)

    if transcript.status == aai.TranscriptStatus.error:
        raise RuntimeError(f"AssemblyAI transcription failed: {transcript.error}")

    speaker_segments = _extract_speaker_segments(transcript)
    entities = _extract_entities(transcript)
    sentiment_summary = _extract_sentiment_summary(transcript)
    chapters = _extract_chapters(transcript)
    topics = _extract_topics(transcript)

    print(
        f"✅ Transcription complete. "
        f"Found {len(speaker_segments)} speaker segments, {len(entities)} entities."
    )

    return {
        "transcript": transcript.text or "",
        "nlp_enriched": True,
        "speaker_segments": speaker_segments,
        "entities": entities,
        "sentiment_summary": sentiment_summary,
        "chapters": chapters,
        "topics": topics,
    }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _configure_api_key() -> None:
    api_key = os.environ.get("ASSEMBLYAI_API_KEY")
    if not api_key:
        print("❌ ASSEMBLYAI_API_KEY is not set. Add it to your .env file.")
        sys.exit(1)
    aai.settings.api_key = api_key


def _extract_speaker_segments(transcript: aai.Transcript) -> list[dict]:
    if not transcript.utterances:
        return []
    return [
        {
            "speaker": u.speaker,
            "text": u.text,
            "start": u.start,
            "end": u.end,
        }
        for u in transcript.utterances
    ]


def _extract_entities(transcript: aai.Transcript) -> list[dict]:
    if not transcript.entities:
        return []
    return [
        {
            "text": e.text,
            "entity_type": e.entity_type.value if hasattr(e.entity_type, "value") else str(e.entity_type),
            "start": e.start,
            "end": e.end,
        }
        for e in transcript.entities
    ]


def _extract_sentiment_summary(transcript: aai.Transcript) -> dict | None:
    results = transcript.sentiment_analysis
    if not results:
        return None
    counts: dict[str, int] = {"positive": 0, "neutral": 0, "negative": 0}
    for r in results:
        label = r.sentiment.value.lower() if hasattr(r.sentiment, "value") else str(r.sentiment).lower()
        if label in counts:
            counts[label] += 1
    return counts


def _extract_chapters(transcript: aai.Transcript) -> list[dict]:
    if not transcript.chapters:
        return []
    return [
        {
            "gist": c.gist,
            "headline": c.headline,
            "summary": c.summary,
            "start": c.start,
            "end": c.end,
        }
        for c in transcript.chapters
    ]


def _extract_topics(transcript: aai.Transcript) -> list[dict]:
    results = transcript.iab_categories
    if not results:
        return []
    # results.summary is a dict of {label: relevance_score}
    summary = getattr(results, "summary", {}) or {}
    return [
        {"label": label, "relevance": round(score, 4)}
        for label, score in sorted(summary.items(), key=lambda x: x[1], reverse=True)
    ]
