"""Transcription des podcasts — Groq API (rapide), Colab GPU, ou local CPU."""

import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Callable

import httpx
from rich.console import Console

from config import WHISPER_MODEL, TRANSCRIPTS_DIR

console = Console()

_model = None

# ── Mode de transcription ───────────────────────────────────────
# Priorité : groq > colab > local
_groq_api_key: str | None = None
_colab_url: str | None = None

GROQ_MAX_FILE_SIZE = 24 * 1024 * 1024  # 24 MB (marge sous la limite de 25 MB)
GROQ_MODEL = "whisper-large-v3-turbo"


# ═══════════════════════════════════════════════════════════════
#  Configuration
# ═══════════════════════════════════════════════════════════════

def set_groq_api_key(key: str | None):
    global _groq_api_key
    _groq_api_key = key.strip() if key else None


def get_groq_api_key() -> str | None:
    return _groq_api_key


def set_colab_url(url: str | None):
    global _colab_url
    _colab_url = url.rstrip("/") if url else None


def get_colab_url() -> str | None:
    return _colab_url


def get_active_mode() -> str:
    """Retourne le mode de transcription actif."""
    if _groq_api_key:
        return "groq"
    if _colab_url:
        return "colab"
    return "local"


def check_groq_api(key: str) -> dict | None:
    """Vérifie si la clé Groq est valide. Retourne les infos ou None."""
    try:
        resp = httpx.get(
            "https://api.groq.com/openai/v1/models",
            headers={"Authorization": f"Bearer {key.strip()}"},
            timeout=10,
        )
        if resp.status_code == 200:
            models = resp.json().get("data", [])
            whisper_models = [m["id"] for m in models if "whisper" in m["id"]]
            return {"models": whisper_models, "status": "ok"}
    except Exception:
        pass
    return None


def check_colab_server(url: str) -> dict | None:
    """Vérifie si le serveur Colab est accessible."""
    try:
        resp = httpx.get(f"{url.rstrip('/')}/health", timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return None


# ═══════════════════════════════════════════════════════════════
#  Compression audio (pour respecter la limite 25 MB de Groq)
# ═══════════════════════════════════════════════════════════════

def _find_ffmpeg() -> str | None:
    found = shutil.which("ffmpeg")
    if found:
        return found
    # Chercher dans les emplacements Windows courants
    winget_path = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
    if winget_path.exists():
        for p in winget_path.rglob("ffmpeg.exe"):
            return str(p)
    return None


def _compress_audio(audio_path: Path) -> Path:
    """Compresse un fichier audio en MP3 mono 48kbps pour passer sous 25 MB."""
    ffmpeg = _find_ffmpeg()
    if not ffmpeg:
        raise RuntimeError(
            "ffmpeg requis pour compresser les fichiers > 24 MB. "
            "Installez-le via: winget install Gyan.FFmpeg"
        )

    compressed = Path(tempfile.mktemp(suffix=".mp3"))
    cmd = [
        ffmpeg, "-i", str(audio_path),
        "-ac", "1",           # mono
        "-ar", "16000",       # 16kHz (suffisant pour la parole)
        "-b:a", "48k",        # 48 kbps
        "-y",                 # overwrite
        str(compressed),
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"Erreur ffmpeg : {result.stderr.decode()[:200]}")

    return compressed


# ═══════════════════════════════════════════════════════════════
#  Transcription Groq (cloud, ultra-rapide)
# ═══════════════════════════════════════════════════════════════

def _transcribe_groq(
    audio_path: Path,
    on_progress: Callable[[float, str], None] | None = None,
) -> str:
    """Transcrit via l'API Groq (whisper-large-v3-turbo, ~15s pour 30 min)."""
    if on_progress:
        on_progress(0.05, "Preparation...")

    # Compresser si le fichier est trop gros
    file_to_send = audio_path
    compressed = None
    file_size = audio_path.stat().st_size

    if file_size > GROQ_MAX_FILE_SIZE:
        if on_progress:
            size_mb = file_size / (1024 * 1024)
            on_progress(0.1, f"Compression ({size_mb:.0f} MB > 24 MB)...")
        compressed = _compress_audio(audio_path)
        file_to_send = compressed

    if on_progress:
        on_progress(0.2, "Envoi vers Groq...")

    try:
        with open(file_to_send, "rb") as f:
            resp = httpx.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {_groq_api_key}"},
                files={"file": (file_to_send.name, f, "audio/mpeg")},
                data={
                    "model": GROQ_MODEL,
                    "language": "fr",
                    "response_format": "verbose_json",
                },
                timeout=300,
            )

        if resp.status_code == 429:
            raise RuntimeError("Limite Groq atteinte — reessayez dans quelques minutes")
        if resp.status_code != 200:
            raise RuntimeError(f"Erreur Groq {resp.status_code}: {resp.text[:200]}")

        result = resp.json()
        transcript = result.get("text", "").strip()

        if not transcript:
            raise RuntimeError("Groq a retourne un transcript vide")

        duration = result.get("duration", 0)
        if on_progress:
            on_progress(1.0, f"Groq: {duration:.0f}s d'audio transcrit")

        return transcript

    finally:
        if compressed and compressed.exists():
            compressed.unlink()


# ═══════════════════════════════════════════════════════════════
#  Transcription Colab (GPU distant)
# ═══════════════════════════════════════════════════════════════

def _transcribe_colab(
    audio_path: Path,
    on_progress: Callable[[float, str], None] | None = None,
) -> str:
    """Transcrit via le serveur Colab GPU."""
    if on_progress:
        on_progress(0.1, "Envoi vers le serveur GPU...")

    with open(audio_path, "rb") as f:
        resp = httpx.post(
            f"{_colab_url}/transcribe",
            files={"file": (audio_path.name, f, "audio/mpeg")},
            data={"language": "fr"},
            timeout=600,
        )

    if resp.status_code != 200:
        raise RuntimeError(f"Erreur serveur Colab : {resp.status_code}")

    result = resp.json()
    if "error" in result:
        raise RuntimeError(f"Erreur transcription : {result['error']}")

    transcript = result["transcript"]
    speedup = result.get("speedup", "?")

    if on_progress:
        on_progress(1.0, f"GPU: {speedup}x temps reel")

    return transcript


# ═══════════════════════════════════════════════════════════════
#  Transcription locale (CPU)
# ═══════════════════════════════════════════════════════════════

def _get_model():
    """Charge le modèle Whisper local une seule fois (lazy loading)."""
    global _model
    if _model is None:
        from faster_whisper import WhisperModel

        cpu_threads = os.cpu_count() or 8
        console.print(
            f"[dim]Chargement du modèle Whisper '{WHISPER_MODEL}' "
            f"(CPU, {cpu_threads} threads)...[/dim]"
        )
        _model = WhisperModel(
            WHISPER_MODEL,
            device="cpu",
            compute_type="int8",
            cpu_threads=cpu_threads,
        )
    return _model


def _transcribe_local(
    audio_path: Path,
    on_progress: Callable[[float, str], None] | None = None,
) -> str:
    """Transcrit en local sur CPU."""
    model = _get_model()

    segments, info = model.transcribe(
        str(audio_path),
        language="fr",
        beam_size=1,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=500),
        condition_on_previous_text=False,
    )

    total_duration = info.duration
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


# ═══════════════════════════════════════════════════════════════
#  Point d'entrée principal
# ═══════════════════════════════════════════════════════════════

def transcribe_episode(
    audio_path: Path,
    on_progress: Callable[[float, str], None] | None = None,
) -> str:
    """
    Transcrit un fichier audio en texte français.
    Priorité : Groq API > Colab GPU > local CPU.
    """
    if _groq_api_key:
        return _transcribe_groq(audio_path, on_progress)
    if _colab_url:
        return _transcribe_colab(audio_path, on_progress)
    return _transcribe_local(audio_path, on_progress)


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
