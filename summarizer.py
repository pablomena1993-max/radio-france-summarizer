"""Génération de résumés — Groq API (rapide) ou Claude Code CLI (premium)."""

import os
import shutil
import subprocess
from pathlib import Path

import httpx

from config import TRANSCRIPTS_DIR, SUMMARIES_DIR

GROQ_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

SUMMARY_PROMPT = '''Tu es un expert en analyse et synthèse de contenus audio francophones.
Lis le transcript de podcast ci-dessous et génère un compte-rendu TRÈS DÉTAILLÉ et EXHAUSTIF en Markdown.
L'objectif est que le lecteur apprenne AUTANT que s'il avait écouté 100% du podcast.

Le compte-rendu DOIT suivre cette structure exacte :

# [Titre de l'épisode]

**Émission** : [nom]
**Station** : [station]
**Date** : [date]
**Catégories** : [thèmes]

---

## Résumé exécutif

[5-8 phrases résumant l'essentiel — contexte, enjeux principaux, conclusions]

## Sujets abordés en détail

### [Sujet 1 — titre descriptif]

**Contexte** : [Pourquoi ce sujet est abordé, quel est l'enjeu]

**Développement** : [Explication détaillée du sujet, avec TOUS les arguments avancés par les intervenants. Développer chaque point, ne rien omettre. Inclure les exemples concrets, les anecdotes, les cas pratiques mentionnés.]

**Données et chiffres** :
- [Chaque donnée chiffrée mentionnée dans le podcast, avec son contexte]

**Citations marquantes** :
> [Citation exacte 1]
> [Citation exacte 2 si disponible]

### [Sujet 2 — titre descriptif]
[Même structure détaillée...]

### [Sujet 3...]
[Autant de sujets que nécessaire — ne pas fusionner des sujets distincts]

## Exemples concrets et cas pratiques

- **[Exemple 1]** : [description détaillée de l'exemple, pourquoi il est mentionné, ce qu'il illustre]
- **[Exemple 2]** : [...]
[Lister TOUS les exemples, anecdotes, études de cas, expériences personnelles mentionnés]

## Personnes et organisations citées

- **[Nom complet]** : [rôle exact, titre, organisation, pourquoi cette personne est citée]
[Lister TOUTES les personnes mentionnées, même brièvement]

## Concepts et idées clés

- **[Concept 1]** : [explication détaillée — ce que c'est, pourquoi c'est important, comment ça fonctionne]
- **[Concept 2]** : [...]
[Chaque concept technique ou intellectuel doit être expliqué en 3-5 phrases minimum]

## Points de débat et désaccords

- [Positions divergentes entre les intervenants]
- [Questions restées sans réponse]
- [Nuances apportées par les experts]

## Ce qu'il faut retenir (apprentissages clés)

1. [Apprentissage concret 1 — formulé comme un fait ou un conseil actionnable]
2. [Apprentissage concret 2]
3. [...]
[5-10 points clés que le lecteur doit absolument retenir]

## Conclusions et perspectives

- [Synthèse des positions]
- [Recommandations des intervenants]
- [Questions ouvertes pour l'avenir]

RÈGLES IMPÉRATIVES :
- Écris TOUJOURS en français
- Sois EXHAUSTIF et DÉTAILLÉ : le lecteur ne doit PAS avoir besoin d'écouter le podcast
- Préserve TOUS les noms propres, chiffres, dates, pourcentages et citations exactes
- Ne simplifie JAMAIS les arguments complexes — développe-les avec tous les détails
- Inclus TOUS les exemples concrets mentionnés dans le podcast
- Chaque section doit être substantielle (pas de listes à 1 élément)
- Le compte-rendu doit faire au minimum 2000 mots
- Privilégie la richesse d'information sur la concision

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
            print(f"[summarizer] Groq rate limit — fallback Claude")
            return None
        if resp.status_code != 200:
            print(f"[summarizer] Groq error {resp.status_code}: {resp.text[:200]}")
            return None

        result = resp.json()
        content = result["choices"][0]["message"]["content"].strip()
        return content if content else None

    except Exception as e:
        print(f"[summarizer] Groq exception: {e}")
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
