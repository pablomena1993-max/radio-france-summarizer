"""Génération de résumés — Groq API (rapide) ou Claude Code CLI (premium)."""

import os
import shutil
import subprocess
from pathlib import Path

import httpx

from config import TRANSCRIPTS_DIR, SUMMARIES_DIR

GROQ_MODEL = "meta-llama/llama-4-maverick-17b-128e-instruct"

SUMMARY_PROMPT = '''Tu es un expert en analyse et synthèse de contenus audio francophones.
Lis le transcript de podcast ci-dessous et génère un résumé EXHAUSTIF en Markdown.

Le résumé DOIT suivre cette structure exacte :

# [Titre de l'épisode]

**Émission** : [nom]
**Station** : [station]
**Date** : [date]
**Catégories** : [thèmes]

---

## Résumé exécutif

[3-5 phrases résumant l'essentiel]

## Sujets abordés

### [Sujet 1]

[Contexte, enjeux, arguments des intervenants, données chiffrées]

> [Citation marquante si disponible]

### [Sujet 2]
[...]

## Personnes et organisations

- **[Nom]** : [rôle/contexte]

## Concepts et idées clés

- **[Concept]** : [explication détaillée]

## Conclusions et perspectives

- [Points de consensus ou désaccord]
- [Questions ouvertes]

RÈGLES :
- Écris en français
- Sois EXHAUSTIF : le lecteur ne doit PAS avoir besoin d'écouter le podcast
- Préserve TOUS les noms propres, chiffres, dates et citations
- Ne simplifie pas les arguments complexes, développe-les

Voici le transcript :

'''


# ═══════════════════════════════════════════════════════════════
#  Groq API (rapide, gratuit)
# ═══════════════════════════════════════════════════════════════

def _get_groq_key() -> str | None:
    """Récupère la clé Groq depuis l'environnement."""
    return os.environ.get("GROQ_API_KEY", "").strip() or None


def _summarize_groq(transcript_text: str) -> str | None:
    """Résume via Groq API (Llama 4 Maverick)."""
    key = _get_groq_key()
    if not key:
        return None

    try:
        resp = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json={
                "model": GROQ_MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": "Tu es un expert en analyse et synthèse de contenus audio francophones. Tu produis des résumés exhaustifs, structurés et fidèles.",
                    },
                    {
                        "role": "user",
                        "content": SUMMARY_PROMPT + transcript_text,
                    },
                ],
                "temperature": 0.3,
                "max_tokens": 8192,
            },
            timeout=120,
        )

        if resp.status_code == 429:
            return None  # Rate limit → fallback Claude
        if resp.status_code != 200:
            return None

        result = resp.json()
        content = result["choices"][0]["message"]["content"].strip()
        return content if content else None

    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════
#  Claude CLI (premium, fallback)
# ═══════════════════════════════════════════════════════════════

def find_claude_cli() -> str | None:
    """Trouve l'exécutable Claude Code sur le système."""
    found = shutil.which("claude")
    if found:
        return found

    npm_paths = [
        Path(os.environ.get("APPDATA", "")) / "npm" / "claude.cmd",
        Path.home() / "AppData" / "Roaming" / "npm" / "claude.cmd",
    ]
    for p in npm_paths:
        if p.exists():
            return str(p)

    return None


def check_claude_available() -> tuple[bool, str]:
    """Vérifie si Claude Code est installé et accessible."""
    cli = find_claude_cli()
    if not cli:
        return False, "Claude Code non trouvé"

    try:
        result = subprocess.run(
            [cli, "--version"],
            capture_output=True, text=True, timeout=10,
            shell=(cli.endswith(".cmd")),
        )
        if result.returncode == 0:
            version = result.stdout.strip()
            return True, f"Claude Code {version}"
        return False, "Claude Code erreur"
    except Exception as e:
        return False, f"Erreur : {e}"


def _summarize_claude(transcript_text: str) -> str | None:
    """Résume via Claude Code CLI."""
    cli = find_claude_cli()
    if not cli:
        return None

    full_prompt = SUMMARY_PROMPT + transcript_text

    try:
        result = subprocess.run(
            [cli, "--print", "--output-format", "text", "-p", full_prompt],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(SUMMARIES_DIR),
            shell=(cli.endswith(".cmd")),
        )

        if result.returncode != 0:
            return None

        summary = result.stdout.strip()
        return summary if summary else None

    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


# ═══════════════════════════════════════════════════════════════
#  Point d'entrée
# ═══════════════════════════════════════════════════════════════

def summarize_transcript(transcript_path: Path) -> Path | None:
    """
    Résume un transcript. Priorité : Groq (rapide) → Claude CLI (premium).
    Retourne le chemin du fichier .md généré, ou None si erreur.
    """
    transcript_text = transcript_path.read_text(encoding="utf-8")
    output_path = SUMMARIES_DIR / transcript_path.with_suffix(".md").name

    # Essayer Groq d'abord (rapide, gratuit)
    summary = _summarize_groq(transcript_text)

    # Fallback Claude CLI si Groq echoue
    if not summary:
        summary = _summarize_claude(transcript_text)

    if not summary:
        return None

    output_path.write_text(summary, encoding="utf-8")
    return output_path
