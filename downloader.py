"""Téléchargement des fichiers MP3 des podcasts."""

import re
from pathlib import Path

import httpx
from rich.progress import Progress, BarColumn, DownloadColumn, TransferSpeedColumn

from config import TEMP_AUDIO_DIR


def sanitize_filename(name: str) -> str:
    """Nettoie un nom pour l'utiliser comme nom de fichier."""
    name = re.sub(r'[<>:"/\\|?*]', "", name)
    name = re.sub(r"\s+", "_", name.strip())
    return name[:100]


def download_episode(mp3_url: str, episode_id: str, title: str = "") -> Path:
    """Télécharge un épisode MP3 avec barre de progression."""
    filename = sanitize_filename(title) if title else episode_id
    output_path = TEMP_AUDIO_DIR / f"{filename}.mp3"

    if output_path.exists():
        return output_path

    with httpx.stream("GET", mp3_url, timeout=60, follow_redirects=True) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0))

        with Progress(
            "[progress.description]{task.description}",
            BarColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
        ) as progress:
            task = progress.add_task(f"Téléchargement", total=total)

            with open(output_path, "wb") as f:
                for chunk in resp.iter_bytes(chunk_size=8192):
                    f.write(chunk)
                    progress.update(task, advance=len(chunk))

    return output_path


def cleanup(audio_path: Path):
    """Supprime un fichier audio temporaire."""
    if audio_path.exists():
        audio_path.unlink()
