# Guide d'utilisation quotidien

## Votre routine quotidienne en 3 commandes

Chaque jour, ouvrez Claude Code et dites simplement :

> "Lance les podcasts Radio France du jour"

Claude Code exécutera les étapes pour vous. Voici le détail de ce qui se passe.

---

## Étape 1 — Lister les podcasts des dernières 24h

### Commande

```bash
cd c:/Users/pablo/OneDrive/Documents/Claude/radio-france-summarizer
python main.py
```

### Ce qui se passe

Le programme interroge **toutes les stations Radio France** (France Inter, franceinfo, France Culture, France Musique, Fip, Mouv') et récupère tous les podcasts publiés dans les dernières 24 heures.

Ils s'affichent **classés par catégorie** sous forme de tableaux :

```
📁 Info (87)
  #   Heure       Émission                  Titre                                    Durée   Station
  1   14/04 09:04 Le 7/9                    Interview du ministre de l'Économie      14:30   France Inter
  2   14/04 08:30 8h30 franceinfo           Prix des carburants, travail le 1er-Mai  23:15   franceinfo
  ...

📁 Sciences et Savoirs (48)
  88  14/04 09:04 La Terre au carré         Tchernobyl, 40 ans après                 38:00   France Inter
  89  14/04 08:00 La Méthode scientifique   L'IA peut-elle penser ?                  51:20   France Culture
  ...

📁 Monde (35)
  ...
```

Chaque podcast a un **numéro unique** (#1, #2, #88, etc.) qui sert à la sélection.

---

## Étape 2 — Sélectionner les podcasts à analyser

### Ce qui se passe

Le programme vous demande :

```
Sélectionnez les podcasts à analyser (max 10)
Formats : 1,3,5 | 1-5 | 1-3,12,45-47

Votre sélection : _
```

### Comment sélectionner

| Vous tapez | Résultat |
|-----------|----------|
| `3` | Seulement le podcast #3 |
| `1,5,12` | Les podcasts #1, #5 et #12 |
| `1-5` | Les podcasts #1 à #5 (5 podcasts) |
| `1-3,88,120-122` | Les #1, #2, #3, #88, #120, #121, #122 |

**Maximum 10 podcasts** par session (la transcription prend du temps).

### Après validation

Le programme :
1. **Télécharge** chaque MP3 (barre de progression visible)
2. **Transcrit** l'audio en texte français (peut prendre 2-5 min par podcast selon la durée)
3. **Sauvegarde** le transcript dans `transcripts/`

```
━━ 1/3 — La Terre au carré : Tchernobyl, 40 ans après ━━
✓ Téléchargé (45.2 Mo)
✓ Transcrit (6 823 mots) → 2026-04-14_Tchernobyl_40_ans_apres.txt

━━ 2/3 — Le 7/9 : Interview du ministre ━━
✓ Téléchargé (18.7 Mo)
✓ Transcrit (3 201 mots) → 2026-04-14_Interview_du_ministre.txt
```

**Note** : le premier lancement télécharge le modèle Whisper (~1.5 Go). C'est une seule fois.

---

## Étape 3 — Générer les résumés et PDF

### Commande

```bash
claude --agent podcast-summarizer
```

Ou, si vous êtes déjà dans Claude Code, dites simplement :

> "Résume les transcripts et génère les PDF"

### Ce qui se passe

L'agent Claude Code :
1. **Lit** chaque fichier `.txt` dans `transcripts/`
2. **Analyse en profondeur** le contenu
3. **Génère un résumé structuré** en Markdown dans `summaries/`
4. **Convertit en PDF** stylisé

### Ce que contient chaque résumé

- **Résumé exécutif** : l'essentiel en 3-5 phrases
- **Sujets abordés** : chaque thème avec contexte, arguments, données chiffrées, citations
- **Personnes et organisations** : tous les noms cités avec leur rôle
- **Concepts et idées clés** : chaque concept développé et expliqué
- **Conclusions et perspectives** : consensus, désaccords, questions ouvertes

Le but : **vous n'avez pas besoin d'écouter le podcast** — le résumé capture tout le contenu intellectuel.

---

## Où trouver vos fichiers

```
radio-france-summarizer/
├── transcripts/                    ← Transcriptions brutes
│   ├── 2026-04-14_Tchernobyl.txt
│   └── 2026-04-14_Interview.txt
└── summaries/                      ← Résumés + PDF
    ├── 2026-04-14_Tchernobyl.md    ← Résumé Markdown
    ├── 2026-04-14_Tchernobyl.pdf   ← Résumé PDF
    ├── 2026-04-14_Interview.md
    └── 2026-04-14_Interview.pdf
```

---

## Résumé : votre routine quotidienne

| Étape | Quoi | Comment | Durée |
|-------|------|---------|-------|
| 1 | Lister les podcasts | `python main.py` | ~30 sec |
| 2 | Sélectionner + transcrire | Taper les numéros | 2-5 min/podcast |
| 3 | Résumer + PDF | `claude --agent podcast-summarizer` | 1-2 min/podcast |

---

## FAQ

### La transcription est lente, que faire ?

Par défaut, le modèle `medium` est utilisé. Pour aller plus vite (qualité légèrement inférieure) :
- Éditez `.env` et changez `WHISPER_MODEL=small` ou `WHISPER_MODEL=base`

Pour la meilleure qualité (plus lent) :
- `WHISPER_MODEL=large-v3`

### Je veux voir les podcasts de plus de 24h ?

Demandez à Claude Code :
> "Lance main.py avec 48h de recul"

Ou modifiez `config.py` : changez la valeur dans `get_all_recent_podcasts(hours=48)`.

### Les transcripts s'accumulent, comment nettoyer ?

Supprimez les anciens fichiers :
```bash
rm transcripts/*.txt
rm summaries/*.md summaries/*.pdf
```
