"""CLI interactif — liste tous les podcasts Radio France des dernières 24h par catégorie."""

import sys
import os
from datetime import datetime

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt
from rich.panel import Panel
from rich.text import Text

from config import MAX_SELECTIONS
from radio_france import get_all_recent_podcasts, group_by_theme
from downloader import download_episode, cleanup
from transcriber import transcribe_episode, save_transcript

console = Console()


def format_duration(seconds: int) -> str:
    if not seconds:
        return "?"
    m, s = divmod(seconds, 60)
    return f"{m}:{s:02d}"


def format_date(timestamp: int) -> str:
    if not timestamp:
        return "?"
    return datetime.fromtimestamp(timestamp).strftime("%d/%m %H:%M")


def parse_selection(text: str, max_val: int) -> list[int]:
    """Parse '1,3,5' ou '1-5' ou '1-3,7,9-10'."""
    indices = set()
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start, end = part.split("-", 1)
            start, end = int(start.strip()), int(end.strip())
            indices.update(range(start, end + 1))
        else:
            indices.add(int(part))
    return sorted(i for i in indices if 1 <= i <= max_val)


def step_list_podcasts() -> list[dict]:
    """Étape 1 : Récupérer et afficher tous les podcasts des dernières 24h."""
    console.print(
        Panel(
            "[bold]Radio France — Podcasts des dernières 24h[/bold]\n"
            "Tous les podcasts disponibles, classés par catégorie",
            style="blue",
        )
    )

    with console.status(
        "Récupération des podcasts sur toutes les stations Radio France..."
    ):
        podcasts = get_all_recent_podcasts(hours=24)

    if not podcasts:
        console.print("[yellow]Aucun podcast trouvé dans les dernières 24h.[/yellow]")
        return []

    console.print(f"\n[bold green]{len(podcasts)} podcasts[/bold green] trouvés\n")

    # Grouper par thème
    groups = group_by_theme(podcasts)

    # Numérotation globale pour la sélection
    global_index = 1
    index_map = {}  # global_index -> podcast

    for theme_name, theme_podcasts in groups.items():
        table = Table(
            title=f"📁 {theme_name} ({len(theme_podcasts)})",
            title_style="bold magenta",
            show_lines=False,
            pad_edge=False,
        )
        table.add_column("#", style="bold cyan", width=5, justify="right")
        table.add_column("Heure", width=12)
        table.add_column("Émission", style="dim", max_width=25)
        table.add_column("Titre", max_width=55)
        table.add_column("Durée", width=7, justify="right")
        table.add_column("Station", style="dim", width=15)

        for p in theme_podcasts:
            index_map[global_index] = p
            table.add_row(
                str(global_index),
                format_date(p["date"]),
                p["show_name"][:25],
                p["title"][:55],
                format_duration(p["duration"]),
                p["station_name"],
            )
            global_index += 1

        console.print(table)
        console.print()

    return index_map


def step_select(index_map: dict) -> list[dict]:
    """Étape 2 : Sélection des podcasts à analyser."""
    max_num = max(index_map.keys())
    console.print(
        f"[bold]Sélectionnez les podcasts à analyser[/bold] "
        f"(max {MAX_SELECTIONS})\n"
        f"[dim]Formats : 1,3,5 | 1-5 | 1-3,12,45-47[/dim]"
    )

    selection_text = Prompt.ask("\n[bold cyan]Votre sélection[/bold cyan]")
    indices = parse_selection(selection_text, max_num)

    if not indices:
        console.print("[yellow]Aucune sélection valide.[/yellow]")
        return []

    if len(indices) > MAX_SELECTIONS:
        console.print(
            f"[yellow]Maximum {MAX_SELECTIONS} — "
            f"seuls les {MAX_SELECTIONS} premiers seront traités.[/yellow]"
        )
        indices = indices[:MAX_SELECTIONS]

    selected = [index_map[i] for i in indices if i in index_map]

    console.print(f"\n[green]✓ {len(selected)} podcast(s) sélectionné(s) :[/green]")
    for p in selected:
        console.print(f"  • {p['show_name']} — {p['title']}")

    return selected


def step_process(episodes: list[dict]) -> list:
    """Étape 3 : Télécharger et transcrire."""
    console.print(
        Panel(
            f"[bold]Traitement de {len(episodes)} podcast(s)[/bold]\n"
            "Téléchargement → Transcription locale",
            style="green",
        )
    )

    transcript_paths = []

    for i, ep in enumerate(episodes, 1):
        console.rule(
            f"[bold]{i}/{len(episodes)} — {ep['show_name']} : {ep['title']}[/bold]"
        )

        # Téléchargement
        try:
            audio_path = download_episode(ep["mp3_url"], ep["id"], ep["title"])
            size_mb = audio_path.stat().st_size / (1024 * 1024)
            console.print(f"[green]✓ Téléchargé[/green] ({size_mb:.1f} Mo)")
        except Exception as e:
            console.print(f"[red]✗ Erreur de téléchargement : {e}[/red]")
            continue

        # Transcription
        try:
            with console.status(
                "Transcription en cours (peut prendre plusieurs minutes)..."
            ):
                transcript = transcribe_episode(audio_path)

            path = save_transcript(
                transcript=transcript,
                episode_title=ep["title"],
                show_name=ep.get("show_name", ""),
                episode_date=ep["date"],
                episode_id=ep["id"],
                station_name=ep.get("station_name", ""),
                themes=ep.get("themes", []),
            )
            transcript_paths.append(path)
            word_count = len(transcript.split())
            console.print(
                f"[green]✓ Transcrit[/green] ({word_count} mots) → {path.name}"
            )

        except Exception as e:
            console.print(f"[red]✗ Erreur de transcription : {e}[/red]")
        finally:
            cleanup(audio_path)

    return transcript_paths


def main():
    try:
        # Étape 1 : Listing
        index_map = step_list_podcasts()
        if not index_map:
            return

        # Étape 2 : Sélection
        selected = step_select(index_map)
        if not selected:
            return

        # Étape 3 : Traitement
        paths = step_process(selected)

        # Résumé final
        if paths:
            console.print()
            console.print(
                Panel(
                    f"[bold green]✓ {len(paths)} transcript(s) prêt(s)[/bold green]\n\n"
                    + "\n".join(f"  • {p.name}" for p in paths)
                    + "\n\n[bold]Prochaine étape — générer les résumés PDF :[/bold]\n"
                    "  [cyan]claude --agent podcast-summarizer[/cyan]",
                    title="Terminé",
                    style="green",
                )
            )
        else:
            console.print("[yellow]Aucun transcript n'a pu être généré.[/yellow]")

    except KeyboardInterrupt:
        console.print("\n[dim]Interruption.[/dim]")
        sys.exit(0)


if __name__ == "__main__":
    main()
