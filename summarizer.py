"""Génération de résumés via Claude Code CLI (utilise l'abonnement Pro/Max)."""

import os
import shutil
import subprocess
from pathlib import Path

from config import TRANSCRIPTS_DIR, SUMMARIES_DIR

SUMMARY_PROMPT = '''Lis le transcript de podcast ci-dessous et génère un résumé EXHAUSTIF en Markdown.

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


def find_claude_cli() -> str | None:
    """Trouve l'exécutable Claude Code sur le système."""
    # 1. Chercher dans le PATH standard
    found = shutil.which("claude")
    if found:
        return found

    # 2. Chercher dans les emplacements npm Windows courants
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


def summarize_transcript(transcript_path: Path) -> Path | None:
    """
    Résume un transcript en appelant Claude Code CLI.
    Utilise l'abonnement Pro/Max de l'utilisateur (authentification via claude auth login).
    Retourne le chemin du fichier .md généré, ou None si erreur.
    """
    cli = find_claude_cli()
    if not cli:
        return None

    transcript_text = transcript_path.read_text(encoding="utf-8")
    output_path = SUMMARIES_DIR / transcript_path.with_suffix(".md").name

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
        if not summary:
            return None

        output_path.write_text(summary, encoding="utf-8")
        return output_path

    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
