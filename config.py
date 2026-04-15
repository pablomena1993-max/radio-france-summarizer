"""Configuration du projet Radio France Podcast Summarizer."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Fix Windows : désactiver les symlinks Hugging Face (cause des téléchargements corrompus)
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["HF_HUB_DISABLE_SYMLINKS"] = "1"

# Chemins du projet
PROJECT_DIR = Path(__file__).parent
TRANSCRIPTS_DIR = PROJECT_DIR / "transcripts"
SUMMARIES_DIR = PROJECT_DIR / "summaries"
TEMP_AUDIO_DIR = PROJECT_DIR / "tmp_audio"

# Créer les répertoires s'ils n'existent pas
TRANSCRIPTS_DIR.mkdir(exist_ok=True)
SUMMARIES_DIR.mkdir(exist_ok=True)
TEMP_AUDIO_DIR.mkdir(exist_ok=True)

# API Radio France v1 (token public, pas d'inscription nécessaire)
RADIO_FRANCE_API_BASE = "https://api.radiofrance.fr/v1"
RADIO_FRANCE_TOKEN = "9ab343ce-cae2-4bdb-90ca-526a3dede870"

# Transcription locale
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "medium")

# Limites
MAX_SELECTIONS = 10
EPISODES_PER_PAGE = 20

# Stations Radio France
STATIONS = [
    {"id": "1", "name": "France Inter", "slug": "france-inter"},
    {"id": "2", "name": "franceinfo", "slug": "franceinfo"},
    {"id": "4", "name": "France Culture", "slug": "france-culture"},
    {"id": "5", "name": "France Musique", "slug": "france-musique"},
    {"id": "6", "name": "Fip", "slug": "fip"},
    {"id": "7", "name": "Mouv'", "slug": "mouv"},
]
