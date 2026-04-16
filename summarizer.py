"""Génération de résumés — Groq API (rapide) ou Claude Code CLI (premium)."""

import os
import shutil
import subprocess
from pathlib import Path

import httpx

from config import TRANSCRIPTS_DIR, SUMMARIES_DIR

GROQ_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

SUMMARY_PROMPT = '''Tu es un expert en analyse de contenus audio. Tu produis des fiches de synthese structurees.

Lis le transcript ci-dessous et genere une fiche au format YAML entre balises ```yaml ... ```.
Respecte EXACTEMENT cette structure (les champs sont obligatoires) :

```yaml
titre: "[Titre clair et descriptif de l'episode]"
sous_titre: "[Description en 1-2 phrases — la question centrale de l'emission]"
emission: "[Nom de l'emission]"
station: "[Station]"
date: "[YYYY-MM-DD]"
duree: "[XX min]"
categories: ["cat1", "cat2"]

intervenants:
  - nom: "[Prenom Nom]"
    role: "[Titre, fonction, organisation]"
    ouvrage: "[Livre ou reference cite, ou vide]"
  - nom: "[...]"
    role: "[...]"

resume_general: |
  [Resume dense de 8-15 phrases. Couvrir TOUT le contenu : contexte, enjeux, arguments principaux,
  donnees chiffrees, exemples concrets, conclusions. Le lecteur doit comprendre 100% du podcast.
  Mettre en **gras** les termes importants. Inclure les chiffres et dates mentionnes.]

themes_developpes:
  - titre: "[Theme 1 — titre court]"
    contenu: "[3-6 phrases detaillant ce theme avec exemples, chiffres, arguments]"
  - titre: "[Theme 2]"
    contenu: "[...]"
  - titre: "[Theme 3]"
    contenu: "[...]"
  [Minimum 6 themes, maximum 12 — couvrir TOUS les sujets abordes]

chronologie:
  - date: "[annee ou date]"
    evenement: "[description courte]"
    detail: "[contexte, pourquoi c'est important]"
  [Uniquement si le podcast mentionne des dates/evenements historiques. Sinon, omettre cette section.]

citations:
  - texte: "[Citation exacte ou quasi-exacte]"
    auteur: "[Nom]"
    contexte: "[a propos de quoi]"
  - texte: "[...]"
    auteur: "[...]"
  [Minimum 3 citations, maximum 8]

apport_principal: |
  [Synthese en 3-5 phrases : qu'est-ce que cette emission apporte de nouveau ou d'important ?
  Quel est le message central ? Quelles perspectives ouvre-t-elle ?]

mots_cles: ["mot1", "mot2", "mot3", "mot4", "mot5", "mot6", "mot7", "mot8", "mot9", "mot10"]
```

REGLES :
- Ecris en francais
- Sois EXHAUSTIF : le lecteur ne doit PAS avoir besoin d'ecouter le podcast
- Preserve TOUS les noms, chiffres, dates, pourcentages
- Les themes_developpes doivent couvrir TOUS les sujets abordes (minimum 6, idealement 9-12)
- Chaque theme doit faire 4-8 phrases detaillees avec exemples et chiffres
- Le resume_general doit faire au moins 10 phrases denses
- Inclure au minimum 4 citations
- Ne simplifie JAMAIS les arguments complexes
- Utilise TOUTES les informations fournies, ne laisse rien de cote

'''


# ═══════════════════════════════════════════════════════════════
#  Groq API (rapide, gratuit)
# ═══════════════════════════════════════════════════════════════

def _get_groq_key() -> str | None:
    """Récupère la clé Groq depuis l'environnement."""
    return os.environ.get("GROQ_API_KEY", "").strip() or None


EXTRACT_PROMPT = '''Lis ce transcript de podcast et extrais TOUTES les informations importantes.
Sois EXHAUSTIF — ne saute aucun argument, chiffre, nom, exemple ou citation.

Produis une liste structuree :

INTERVENANTS:
- [Nom] | [Role/titre] | [Ouvrage cite]

FAITS ET ARGUMENTS (liste TOUS les points, minimum 15):
1. [fait/argument detaille avec contexte et chiffres]
2. [...]

EXEMPLES CONCRETS:
- [chaque exemple, anecdote, etude de cas mentionne]

CITATIONS (verbatim ou quasi-verbatim):
- "[citation]" — [auteur] — [contexte]

DATES/CHRONOLOGIE:
- [date] : [evenement] — [pourquoi c'est important]

CHIFFRES ET DONNEES:
- [chaque chiffre, pourcentage, statistique mentionne avec son contexte]

Transcript :

'''


def _groq_call(key: str, system: str, user: str, max_tokens: int = 8192) -> str | None:
    """Appel Groq API avec gestion d'erreurs."""
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
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.3,
                "max_tokens": max_tokens,
            },
            timeout=180,
        )

        if resp.status_code == 429:
            print(f"[summarizer] Groq rate limit")
            return None
        if resp.status_code != 200:
            print(f"[summarizer] Groq error {resp.status_code}: {resp.text[:200]}")
            return None

        return resp.json()["choices"][0]["message"]["content"].strip() or None

    except Exception as e:
        print(f"[summarizer] Groq exception: {e}")
        return None


def _summarize_groq(transcript_text: str) -> str | None:
    """Résume via 2 appels Groq : extraction puis structuration YAML."""
    key = _get_groq_key()
    if not key:
        return None

    import time

    # Découper le transcript en morceaux pour extraire plus de détails
    words = transcript_text.split()
    chunk_size = 4000  # ~4000 mots par morceau
    chunks = []
    for i in range(0, len(words), chunk_size):
        chunks.append(" ".join(words[i:i + chunk_size]))

    # Étape 1 : extraire les faits de chaque morceau
    all_facts = []
    for idx, chunk in enumerate(chunks):
        print(f"[summarizer] Etape 1 : extraction {idx+1}/{len(chunks)}...")
        facts = _groq_call(
            key,
            "Tu es un analyste meticuleux. Extrais TOUTES les informations sans rien omettre. Sois tres detaille.",
            EXTRACT_PROMPT + chunk,
            max_tokens=8192,
        )
        if facts:
            all_facts.append(facts)
        if idx < len(chunks) - 1:
            time.sleep(2)

    if not all_facts:
        return None

    combined_facts = "\n\n".join(all_facts)
    print(f"[summarizer] {len(combined_facts.split())} mots de faits extraits au total")

    # Étape 2 : structurer en YAML
    time.sleep(2)
    print("[summarizer] Etape 2 : structuration YAML...")
    yaml_result = _groq_call(
        key,
        "Tu es un expert en synthese. Tu produis des fiches YAML ultra-detaillees. Utilise TOUTES les informations fournies.",
        SUMMARY_PROMPT + "\n\nVoici TOUS les faits extraits du podcast :\n\n" + combined_facts,
        max_tokens=8192,
    )
    return yaml_result


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
    Résume un transcript. Priorité : Claude CLI (qualité max) → Groq (fallback).
    Retourne le chemin du fichier .md généré, ou None si erreur.
    """
    transcript_text = transcript_path.read_text(encoding="utf-8")
    output_path = SUMMARIES_DIR / transcript_path.with_suffix(".md").name

    # Claude d'abord (meilleure qualité, pas de limite tokens)
    summary = _summarize_claude(transcript_text)

    # Fallback Groq si Claude indisponible
    if not summary:
        summary = _summarize_groq(transcript_text)

    if not summary:
        return None

    output_path.write_text(summary, encoding="utf-8")
    return output_path
