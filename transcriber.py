"""Transcription locale des podcasts via faster-whisper."""

import re
from datetime import datetime
from pathlib import Path
from typing import Callable

from rich.console import Console

from config import WHISPER_MODEL, TRANSCRIPTS_DIR

console = Console()

_model = None


def _get_model():
    """Charge le modèle Whisper une seule fois (lazy loading)."""
    global _model
    if _model is None:
        from faster_whisper import WhisperModel

        console.print(
            f"[dim]Chargement du modèle Whisper '{WHISPER_MODEL}'... "
            f"(premier lancement uniquement)[/dim]"
        )
        _model = WhisperModel(
            WHISPER_MODEL,
            device="cpu",
            compute_type="int8",
            cpu_threads=16,
            num_workers=4,
        )
    return _model


def transcribe_episode(
    audio_path: Path,
    on_progress: Callable[[float, str], None] | None = None,
) -> str:
    """
    Transcrit un fichier audio en texte français.

    on_progress(percent, last_text) est appelé après chaque segment :
      - percent : 0.0 à 1.0 (basé sur le timestamp / durée totale)
      - last_text : texte du dernier segment transcrit
    """
    model = _get_model()

    segments, info = model.transcribe(
        str(audio_path),
        language="fr",
        beam_size=1,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=500),
        condition_on_previous_text=False,
    )

    total_duration = info.duration  # Durée totale en secondes

    parts = []
    for segment in segments:
        text = segment.text.strip()
        parts.append(text)

        if on_progress and total_duration > 0:
            percent = min(segment.end / total_duration, 1.0)
            on_progress(percent, text)

    transcript = " ".join(parts)
    transcript = re.sub(r" +", " ", transcript)

    if on_progress:
        on_progress(1.0, "")

    return transcript


def save_transcript(
    transcript: str,
    episode_title: str,
    show_name: str,
    episode_date: int,
    episode_id: str,
    station_name: str = "",
    themes: list[str] | None = None,
) -> Path:
    """Sauvegarde un transcript avec métadonnées complètes."""
    date_str = datetime.fromtimestamp(episode_date).strftime("%Y-%m-%d")
    filename = re.sub(r'[<>:"/\\|?*]', "", episode_title)
    filename = re.sub(r"\s+", "_", filename.strip())[:80]
    output_path = TRANSCRIPTS_DIR / f"{date_str}_{filename}.txt"

    theme_str = ", ".join(themes) if themes else "Non classé"

    header = (
        f"Émission : {show_name}\n"
        f"Épisode : {episode_title}\n"
        f"Station : {station_name}\n"
        f"Date : {date_str}\n"
        f"Catégories : {theme_str}\n"
        f"ID : {episode_id}\n"
        f"{'=' * 60}\n\n"
    )

    output_path.write_text(header + transcript, encoding="utf-8")
    return output_path
