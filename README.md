# Radio France Podcast Summarizer

Outil pour découvrir, transcrire et résumer les podcasts Radio France — **100% gratuit**.

## Fonctionnalités

1. **Recherche** d'émissions sur Radio France (France Inter, France Culture, franceinfo, etc.)
2. **Sélection** de jusqu'à 10 épisodes
3. **Transcription locale** de l'audio via faster-whisper (gratuit, sans API)
4. **Résumés exhaustifs** via un agent Claude Code (utilise votre abonnement existant)

## Prérequis

- **Python 3.11+**
- **ffmpeg** : nécessaire pour le traitement audio
  ```bash
  # Windows
  winget install ffmpeg
  
  # macOS
  brew install ffmpeg
  
  # Linux
  sudo apt install ffmpeg
  ```
- **Claude Code** : pour la génération des résumés (abonnement Pro/Team)

## Installation

```bash
cd radio-france-summarizer
pip install -r requirements.txt
```

Le premier lancement téléchargera automatiquement le modèle Whisper (~1.5 Go pour `medium`).

## Utilisation

### Étape 1 : Découvrir et transcrire

```bash
python main.py
```

Le CLI vous guide :
1. Recherchez une émission (ex: "Les Matins", "Le 7/9", "Grand Reportage")
2. Sélectionnez une émission dans les résultats
3. Choisissez jusqu'à 10 épisodes (ex: `1,3,5` ou `1-5`)
4. Les transcripts sont sauvegardés dans `transcripts/`

### Étape 2 : Générer les résumés

```bash
claude --agent podcast-summarizer
```

L'agent Claude Code lit les transcripts et génère des résumés complets dans `summaries/`.

## Configuration

Copiez `.env.example` en `.env` pour personnaliser :

```bash
cp .env.example .env
```

| Variable | Défaut | Description |
|----------|--------|-------------|
| `WHISPER_MODEL` | `medium` | Modèle Whisper (`tiny`, `base`, `small`, `medium`, `large-v3`) |

Plus le modèle est grand, plus la transcription est précise mais lente.

## Structure des fichiers

```
transcripts/          # Transcripts générés
  2026-04-14_Le_titre.txt

summaries/            # Résumés générés
  2026-04-14_Le_titre.md
```

## Coûts

| Composant | Coût |
|-----------|------|
| API Radio France | Gratuit (token public) |
| Transcription (faster-whisper) | Gratuit (local) |
| Résumés (Claude Code) | Inclus dans l'abonnement |
| **Total** | **0 €** |
