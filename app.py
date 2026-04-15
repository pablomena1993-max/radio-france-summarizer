"""Radio France Podcast Summarizer — Application Desktop."""

import os
import subprocess
import threading
from datetime import datetime
from pathlib import Path

import customtkinter as ctk

from config import MAX_SELECTIONS, TRANSCRIPTS_DIR, SUMMARIES_DIR
from radio_france import get_all_recent_podcasts, group_by_theme
from downloader import download_episode, cleanup
from transcriber import transcribe_episode, save_transcript
from summarizer import summarize_transcript, check_claude_available
from pdf_generator import markdown_to_pdf

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class PodcastApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Radio France — Podcasts du jour")
        self.geometry("1100x850")
        self.minsize(900, 700)

        self.podcasts: list[dict] = []
        self.checkboxes: dict[str, ctk.CTkCheckBox] = {}
        self.checkbox_vars: dict[str, ctk.BooleanVar] = {}
        self.selection_count = 0
        self.claude_ok = False

        self._build_ui()
        self._check_auth_async()

    # ─── UI Construction ────────────────────────────────────────

    def _build_ui(self):
        # Top bar
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=20, pady=(15, 0))

        ctk.CTkLabel(
            top,
            text="Radio France — Podcasts des dernières 24h",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).pack(side="left")

        self.auth_label = ctk.CTkLabel(
            top, text="  Claude : vérification...",
            font=ctk.CTkFont(size=12), text_color="#6b7280",
        )
        self.auth_label.pack(side="right")

        self.counter_label = ctk.CTkLabel(
            top, text="0 / 10 sélectionnés",
            font=ctk.CTkFont(size=14), text_color="#888888",
        )
        self.counter_label.pack(side="right", padx=(0, 20))

        # ── Buttons ─────────────────────────────────────────────
        row1 = ctk.CTkFrame(self, fg_color="transparent")
        row1.pack(fill="x", padx=20, pady=(10, 0))

        self.fetch_btn = ctk.CTkButton(
            row1, text="1. Récupérer les podcasts", command=self._on_fetch,
            height=42, font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#2563eb", hover_color="#1d4ed8",
        )
        self.fetch_btn.pack(side="left")

        self.process_btn = ctk.CTkButton(
            row1, text="2. Transcrire la sélection", command=self._on_process,
            height=42, font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#7c3aed", hover_color="#6d28d9", state="disabled",
        )
        self.process_btn.pack(side="left", padx=10)

        self.summarize_btn = ctk.CTkButton(
            row1, text="3. Résumer + PDF", command=self._on_summarize,
            height=42, font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#16a34a", hover_color="#15803d", state="disabled",
        )
        self.summarize_btn.pack(side="left")

        ctk.CTkButton(
            row1, text="Ouvrir summaries/",
            command=lambda: os.startfile(str(SUMMARIES_DIR)),
            height=36, font=ctk.CTkFont(size=12),
            fg_color="#374151", hover_color="#4b5563", width=130,
        ).pack(side="right")

        ctk.CTkButton(
            row1, text="Ouvrir transcripts/",
            command=lambda: os.startfile(str(TRANSCRIPTS_DIR)),
            height=36, font=ctk.CTkFont(size=12),
            fg_color="#374151", hover_color="#4b5563", width=130,
        ).pack(side="right", padx=(0, 8))

        # ── Status + Progress ───────────────────────────────────
        self.status_label = ctk.CTkLabel(
            self, text="Cliquez sur « 1. Récupérer les podcasts » pour commencer",
            font=ctk.CTkFont(size=13), text_color="#9ca3af",
        )
        self.status_label.pack(fill="x", padx=20, pady=(8, 0))

        # Progress bar principale (épisodes)
        self.progress = ctk.CTkProgressBar(self, height=6)
        self.progress.pack(fill="x", padx=20, pady=(4, 0))
        self.progress.set(0)

        # ── Scrollable podcast list ─────────────────────────────
        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_frame.pack(fill="both", expand=True, padx=20, pady=(8, 0))

        # ── Panneau de transcription en temps réel ──────────────
        self.transcript_panel = ctk.CTkFrame(self, fg_color="#111827", corner_radius=8)
        self.transcript_panel.pack(fill="x", padx=20, pady=(8, 15))
        self.transcript_panel.pack_forget()  # Caché par défaut

        # Header du panneau
        tp_header = ctk.CTkFrame(self.transcript_panel, fg_color="transparent")
        tp_header.pack(fill="x", padx=12, pady=(8, 0))

        self.transcript_title = ctk.CTkLabel(
            tp_header, text="Transcription en cours",
            font=ctk.CTkFont(size=13, weight="bold"), text_color="#93c5fd",
        )
        self.transcript_title.pack(side="left")

        self.transcript_percent = ctk.CTkLabel(
            tp_header, text="0%",
            font=ctk.CTkFont(size=13, weight="bold"), text_color="#16a34a",
        )
        self.transcript_percent.pack(side="right")

        # Barre de progression du transcript en cours
        self.transcript_progress = ctk.CTkProgressBar(
            self.transcript_panel, height=4, progress_color="#7c3aed",
        )
        self.transcript_progress.pack(fill="x", padx=12, pady=(6, 0))
        self.transcript_progress.set(0)

        # Zone de texte en temps réel (scrollable)
        self.live_text = ctk.CTkTextbox(
            self.transcript_panel, height=120, fg_color="#0d1117",
            font=ctk.CTkFont(size=11), text_color="#d1d5db",
            wrap="word", state="disabled",
        )
        self.live_text.pack(fill="x", padx=12, pady=(6, 10))

    # ─── Auth check ─────────────────────────────────────────────

    def _check_auth_async(self):
        threading.Thread(target=self._check_auth_worker, daemon=True).start()

    def _check_auth_worker(self):
        ok, msg = check_claude_available()
        self.claude_ok = ok
        color = "#16a34a" if ok else "#ef4444"
        symbol = "\u2713" if ok else "\u2717"
        self.after(0, lambda: self.auth_label.configure(
            text=f"  {msg}  {symbol}", text_color=color,
        ))

    # ─── Fetch podcasts ─────────────────────────────────────────

    def _on_fetch(self):
        self.fetch_btn.configure(state="disabled", text="Chargement...")
        self.process_btn.configure(state="disabled")
        self.summarize_btn.configure(state="disabled")
        self._set_status("Interrogation de toutes les stations Radio France...")
        self.progress.configure(mode="indeterminate")
        self.progress.start()

        threading.Thread(target=self._fetch_worker, daemon=True).start()

    def _fetch_worker(self):
        try:
            self.podcasts = get_all_recent_podcasts(hours=24)
            self.after(0, self._display_podcasts)
        except Exception as e:
            self.after(0, lambda: self._set_status(f"Erreur : {e}"))
            self.after(0, lambda: self.fetch_btn.configure(
                state="normal", text="1. Réessayer",
            ))
            self.after(0, self.progress.stop)

    def _display_podcasts(self):
        self.progress.stop()
        self.progress.set(0)

        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
        self.checkboxes.clear()
        self.checkbox_vars.clear()
        self.selection_count = 0
        self._update_counter()

        groups = group_by_theme(self.podcasts)

        for theme_name, theme_podcasts in groups.items():
            header = ctk.CTkFrame(self.scroll_frame, fg_color="#1e293b", corner_radius=8)
            header.pack(fill="x", pady=(12, 4))
            ctk.CTkLabel(
                header,
                text=f"  {theme_name}  ({len(theme_podcasts)})",
                font=ctk.CTkFont(size=15, weight="bold"), text_color="#93c5fd",
            ).pack(side="left", padx=8, pady=6)

            for p in theme_podcasts:
                self._add_podcast_row(p)

        total = len(self.podcasts)
        cats = len(groups)
        self._set_status(f"{total} podcasts dans {cats} catégories — cochez ceux à analyser")
        self.fetch_btn.configure(state="normal", text="1. Actualiser")
        self._check_existing_transcripts()

    def _add_podcast_row(self, podcast: dict):
        pid = podcast["id"]
        if pid in self.checkbox_vars:
            return

        row = ctk.CTkFrame(self.scroll_frame, fg_color="transparent", height=36)
        row.pack(fill="x", padx=4, pady=1)

        var = ctk.BooleanVar(value=False)
        self.checkbox_vars[pid] = var

        cb = ctk.CTkCheckBox(
            row, text="", variable=var, width=24,
            command=lambda: self._on_checkbox_toggle(pid),
            checkbox_width=20, checkbox_height=20,
        )
        cb.pack(side="left", padx=(8, 4))
        self.checkboxes[pid] = cb

        date_str = (
            datetime.fromtimestamp(podcast["date"]).strftime("%H:%M")
            if podcast["date"] else ""
        )
        ctk.CTkLabel(
            row, text=date_str, width=50,
            font=ctk.CTkFont(size=12), text_color="#9ca3af",
        ).pack(side="left", padx=(0, 8))

        dur = ""
        if podcast["duration"]:
            m, s = divmod(podcast["duration"], 60)
            dur = f"{m}:{s:02d}"
        ctk.CTkLabel(
            row, text=dur, width=50,
            font=ctk.CTkFont(size=12), text_color="#6b7280",
        ).pack(side="left", padx=(0, 8))

        ctk.CTkLabel(
            row, text=podcast["station_name"], width=110,
            font=ctk.CTkFont(size=11), text_color="#6b7280", anchor="w",
        ).pack(side="left", padx=(0, 4))

        ctk.CTkLabel(
            row, text=podcast["show_name"][:28], width=190,
            font=ctk.CTkFont(size=12, weight="bold"), text_color="#d1d5db", anchor="w",
        ).pack(side="left", padx=(0, 4))

        ctk.CTkLabel(
            row, text=podcast["title"][:65],
            font=ctk.CTkFont(size=12), text_color="#e5e7eb", anchor="w",
        ).pack(side="left", fill="x", expand=True)

    # ─── Selection ──────────────────────────────────────────────

    def _on_checkbox_toggle(self, pid: str):
        checked = self.checkbox_vars[pid].get()
        if checked:
            if self.selection_count >= MAX_SELECTIONS:
                self.checkbox_vars[pid].set(False)
                self._set_status(
                    f"Maximum {MAX_SELECTIONS} podcasts. Désélectionnez-en un d'abord."
                )
                return
            self.selection_count += 1
        else:
            self.selection_count -= 1
        self._update_counter()

    def _update_counter(self):
        count = self.selection_count
        color = "#16a34a" if 0 < count <= MAX_SELECTIONS else "#9ca3af"
        self.counter_label.configure(
            text=f"{count} / {MAX_SELECTIONS} sélectionnés", text_color=color,
        )
        self.process_btn.configure(
            state="normal" if count > 0 else "disabled"
        )

    # ─── Live transcript panel ──────────────────────────────────

    def _show_transcript_panel(self, title: str):
        self.transcript_title.configure(text=f"Transcription : {title[:60]}")
        self.transcript_percent.configure(text="0%")
        self.transcript_progress.set(0)
        self.live_text.configure(state="normal")
        self.live_text.delete("1.0", "end")
        self.live_text.configure(state="disabled")
        self.transcript_panel.pack(fill="x", padx=20, pady=(8, 15))

    def _hide_transcript_panel(self):
        self.transcript_panel.pack_forget()

    def _update_transcript_live(self, percent: float, text: str):
        """Appelé depuis le thread de transcription via self.after()."""
        self.transcript_progress.set(percent)
        self.transcript_percent.configure(text=f"{int(percent * 100)}%")

        if text:
            self.live_text.configure(state="normal")
            self.live_text.insert("end", text + " ")
            self.live_text.see("end")
            self.live_text.configure(state="disabled")

    # ─── Process (download + transcribe) ────────────────────────

    def _on_process(self):
        selected = [
            p for p in self.podcasts
            if self.checkbox_vars.get(p["id"], ctk.BooleanVar(value=False)).get()
        ]
        if not selected:
            return

        self._disable_all_buttons()
        self.process_btn.configure(text="Transcription en cours...")
        self.progress.configure(mode="determinate")
        self.progress.set(0)

        threading.Thread(
            target=self._process_worker, args=(selected,), daemon=True
        ).start()

    def _process_worker(self, episodes: list[dict]):
        total = len(episodes)
        completed = 0
        transcript_paths = []

        for ep in episodes:
            # ── Téléchargement ──
            self.after(0, lambda e=ep: self._set_status(
                f"Téléchargement {completed+1}/{total} : "
                f"{e['show_name']} — {e['title'][:50]}"
            ))

            try:
                audio_path = download_episode(ep["mp3_url"], ep["id"], ep["title"])
            except Exception as e:
                self.after(0, lambda err=e: self._set_status(
                    f"Erreur téléchargement : {err}"
                ))
                completed += 1
                self.after(0, lambda c=completed: self.progress.set(c / total))
                continue

            # ── Transcription avec progression en temps réel ──
            ep_title = f"{ep['show_name']} — {ep['title'][:40]}"
            self.after(0, lambda t=ep_title: self._show_transcript_panel(t))
            self.after(0, lambda e=ep, c=completed: self._set_status(
                f"Transcription {c+1}/{total} : "
                f"{e['show_name']} — {e['title'][:50]}"
            ))

            def on_progress(percent: float, text: str):
                self.after(0, lambda p=percent, t=text: self._update_transcript_live(p, t))

            try:
                transcript = transcribe_episode(audio_path, on_progress=on_progress)
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
            except Exception as e:
                self.after(0, lambda err=e: self._set_status(
                    f"Erreur transcription : {err}"
                ))
            finally:
                cleanup(audio_path)

            completed += 1
            self.after(0, lambda c=completed: self.progress.set(c / total))

        n = len(transcript_paths)
        self.after(0, lambda: self._set_status(
            f"Transcription terminée — {n} fichier(s) — "
            "Cliquez sur « 3. Résumer + PDF »"
        ))
        self.after(0, self._enable_all_buttons)
        self.after(0, self._check_existing_transcripts)

    # ─── Summarize + PDF ────────────────────────────────────────

    def _check_existing_transcripts(self):
        transcripts = list(TRANSCRIPTS_DIR.glob("*.txt"))
        unsummarized = [
            t for t in transcripts
            if not (SUMMARIES_DIR / t.with_suffix(".md").name).exists()
        ]
        if unsummarized:
            self.summarize_btn.configure(
                state="normal" if self.claude_ok else "disabled",
                text=f"3. Résumer + PDF ({len(unsummarized)} en attente)",
            )
        else:
            self.summarize_btn.configure(state="disabled", text="3. Résumer + PDF")

    def _on_summarize(self):
        if not self.claude_ok:
            self._set_status(
                "Claude Code non détecté. Installez-le et lancez « claude auth login »"
            )
            return

        self._disable_all_buttons()
        self._hide_transcript_panel()
        self.summarize_btn.configure(text="Résumé en cours...")
        self.progress.configure(mode="determinate")
        self.progress.set(0)

        threading.Thread(target=self._summarize_worker, daemon=True).start()

    def _summarize_worker(self):
        transcripts = sorted(TRANSCRIPTS_DIR.glob("*.txt"))
        to_process = [
            t for t in transcripts
            if not (SUMMARIES_DIR / t.with_suffix(".md").name).exists()
        ]

        if not to_process:
            self.after(0, lambda: self._set_status(
                "Tous les transcripts sont déjà résumés."
            ))
            self.after(0, self._enable_all_buttons)
            return

        total = len(to_process)
        success = 0

        for i, t_path in enumerate(to_process):
            name = t_path.stem[:50]
            self.after(0, lambda n=name, idx=i: self._set_status(
                f"Résumé {idx+1}/{total} via Claude : {n}..."
            ))

            md_path = summarize_transcript(t_path)
            if md_path:
                try:
                    markdown_to_pdf(md_path)
                    success += 1
                except Exception:
                    success += 1

            self.after(0, lambda idx=i: self.progress.set((idx + 1) / total))

        self.after(0, lambda: self._set_status(
            f"Terminé — {success}/{total} résumé(s) + PDF générés dans summaries/"
        ))
        self.after(0, self._enable_all_buttons)
        self.after(0, self._check_existing_transcripts)

    # ─── Helpers ────────────────────────────────────────────────

    def _set_status(self, text: str):
        self.status_label.configure(text=text)

    def _disable_all_buttons(self):
        self.fetch_btn.configure(state="disabled")
        self.process_btn.configure(state="disabled")
        self.summarize_btn.configure(state="disabled")

    def _enable_all_buttons(self):
        self.fetch_btn.configure(state="normal", text="1. Actualiser")
        self.process_btn.configure(
            state="normal" if self.selection_count > 0 else "disabled",
            text="2. Transcrire la sélection",
        )


if __name__ == "__main__":
    app = PodcastApp()
    app.mainloop()
