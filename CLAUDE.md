# Radio France Podcast Summarizer

Outil pour lister tous les podcasts Radio France des dernières 24h par catégorie,
les transcrire localement, puis générer des résumés exhaustifs en PDF via l'agent Claude Code.

## Structure
- `main.py` : CLI — liste 24h par catégorie → sélection → download → transcription
- `radio_france.py` : Client API Radio France v1 (toutes stations, tous thèmes)
- `downloader.py` : Téléchargement MP3
- `transcriber.py` : Transcription locale via faster-whisper
- `pdf_generator.py` : Conversion des résumés Markdown → PDF
- `config.py` : Configuration et constantes
- `transcripts/` : Transcripts générés (.txt)
- `summaries/` : Résumés (.md) et PDF (.pdf)

## Commandes
- Lancer le CLI : `python main.py`
- Générer les résumés + PDF : `claude --agent podcast-summarizer`
- Convertir les .md en PDF : `python -c "from pdf_generator import convert_all_summaries; convert_all_summaries()"`
