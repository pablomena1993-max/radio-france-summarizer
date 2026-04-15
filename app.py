"""Radio France Podcast Summarizer — Application Desktop avec filtres avancés."""

import os
import threading
from datetime import datetime
from pathlib import Path

import customtkinter as ctk

from config import MAX_SELECTIONS, TRANSCRIPTS_DIR, SUMMARIES_DIR
from radio_france import get_all_recent_podcasts, group_by_theme
from downloader import download_episode, cleanup
from transcriber import (
    transcribe_episode, save_transcript,
    set_groq_api_key, get_groq_api_key, check_groq_api,
    set_colab_url, get_colab_url, check_colab_server,
    get_active_mode,
)
from summarizer import summarize_transcript, check_claude_available
from pdf_generator import markdown_to_pdf

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# Couleurs
C_BG_DARK = "#0f172a"
C_BG_CARD = "#1e293b"
C_BG_CARD_HOVER = "#334155"
C_BG_CARD_SELECTED = "#1e3a5f"
C_ACCENT = "#3b82f6"
C_ACCENT_HOVER = "#2563eb"
C_PURPLE = "#7c3aed"
C_GREEN = "#16a34a"
C_TEXT = "#e5e7eb"
C_TEXT_DIM = "#9ca3af"
C_TEXT_MUTED = "#6b7280"
C_SEPARATOR = "#334155"


def format_duration(seconds: int) -> str:
    if not seconds:
        return ""
    h, remainder = divmod(seconds, 3600)
    m, s = divmod(remainder, 60)
    if h:
        return f"{h}h{m:02d}"
    return f"{m}:{s:02d}"


class PodcastApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Radio France — Podcasts du jour")
        self.geometry("1200x900")
        self.minsize(1000, 700)
        self.configure(fg_color=C_BG_DARK)

        self.podcasts: list[dict] = []
        self.filtered_podcasts: list[dict] = []
        self.checkbox_vars: dict[str, ctk.BooleanVar] = {}
        self.row_frames: dict[str, ctk.CTkFrame] = {}
        self.selection_count = 0
        self.claude_ok = False
        self.all_themes: list[str] = []
        self.current_theme_filter = "Tous les thèmes"
        self.current_min_duration = 0

        self._build_ui()
        self._check_auth_async()
        self._auto_connect_groq()

    # ═══════════════════════════════════════════════════════════════
    #  UI Construction
    # ═══════════════════════════════════════════════════════════════

    def _build_ui(self):
        # ── Header ──────────────────────────────────────────────────
        header = ctk.CTkFrame(self, fg_color=C_BG_CARD, corner_radius=0, height=60)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header,
            text="  Radio France — Podcasts des dernieres 24h",
            font=ctk.CTkFont(size=20, weight="bold"), text_color=C_TEXT,
        ).pack(side="left", padx=16)

        self.auth_label = ctk.CTkLabel(
            header, text="  Claude : verification...",
            font=ctk.CTkFont(size=11), text_color=C_TEXT_MUTED,
        )
        self.auth_label.pack(side="right", padx=16)

        self.counter_label = ctk.CTkLabel(
            header, text="0 / 10 selectionnes",
            font=ctk.CTkFont(size=13, weight="bold"), text_color=C_TEXT_MUTED,
        )
        self.counter_label.pack(side="right", padx=(0, 16))

        # ── Action buttons ──────────────────────────────────────────
        btn_bar = ctk.CTkFrame(self, fg_color="transparent", height=55)
        btn_bar.pack(fill="x", padx=16, pady=(10, 0))

        self.fetch_btn = ctk.CTkButton(
            btn_bar, text="1. Recuperer les podcasts", command=self._on_fetch,
            height=40, font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=C_ACCENT, hover_color=C_ACCENT_HOVER,
        )
        self.fetch_btn.pack(side="left")

        self.process_btn = ctk.CTkButton(
            btn_bar, text="2. Transcrire la selection", command=self._on_process,
            height=40, font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=C_PURPLE, hover_color="#6d28d9", state="disabled",
        )
        self.process_btn.pack(side="left", padx=10)

        self.summarize_btn = ctk.CTkButton(
            btn_bar, text="3. Resumer + PDF", command=self._on_summarize,
            height=40, font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=C_GREEN, hover_color="#15803d", state="disabled",
        )
        self.summarize_btn.pack(side="left")

        # Boutons d'accès dossiers
        for label, folder in [("summaries/", SUMMARIES_DIR), ("transcripts/", TRANSCRIPTS_DIR)]:
            ctk.CTkButton(
                btn_bar, text=f"Ouvrir {label}",
                command=lambda f=folder: os.startfile(str(f)),
                height=34, font=ctk.CTkFont(size=11),
                fg_color="#374151", hover_color="#4b5563", width=120,
            ).pack(side="right", padx=(4, 0))

        # ── Transcription engine bar ────────────────────────────────
        engine_bar = ctk.CTkFrame(self, fg_color="#1a1a2e", corner_radius=10, height=44)
        engine_bar.pack(fill="x", padx=16, pady=(8, 0))
        engine_bar.pack_propagate(False)

        self.engine_indicator = ctk.CTkLabel(
            engine_bar, text="  CPU local (lent)",
            font=ctk.CTkFont(size=11, weight="bold"), text_color="#f59e0b", width=140,
        )
        self.engine_indicator.pack(side="left", padx=(12, 8))

        ctk.CTkLabel(
            engine_bar, text="Cle Groq :",
            font=ctk.CTkFont(size=11), text_color=C_TEXT_DIM,
        ).pack(side="left", padx=(0, 4))

        self.groq_entry = ctk.CTkEntry(
            engine_bar, placeholder_text="gsk_...",
            width=260, height=30, font=ctk.CTkFont(size=11), show="*",
        )
        self.groq_entry.pack(side="left", padx=(0, 6))

        # Pre-fill from .env if available
        env_key = os.environ.get("GROQ_API_KEY", "")
        if env_key:
            self.groq_entry.insert(0, env_key)

        self.groq_connect_btn = ctk.CTkButton(
            engine_bar, text="Activer Groq", command=self._on_groq_connect,
            height=30, font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#f97316", hover_color="#ea580c", width=100,
        )
        self.groq_connect_btn.pack(side="left", padx=(0, 6))

        self.groq_disconnect_btn = ctk.CTkButton(
            engine_bar, text="Deconnecter", command=self._on_groq_disconnect,
            height=30, font=ctk.CTkFont(size=11),
            fg_color="#374151", hover_color="#4b5563", width=100,
        )
        self.groq_disconnect_btn.pack(side="left")
        self.groq_disconnect_btn.pack_forget()

        self.engine_status = ctk.CTkLabel(
            engine_bar, text="Gratuit sur groq.com/keys",
            font=ctk.CTkFont(size=10), text_color=C_TEXT_MUTED,
        )
        self.engine_status.pack(side="right", padx=12)

        # ── Filters bar ────────────────────────────────────────────
        self.filter_frame = ctk.CTkFrame(self, fg_color=C_BG_CARD, corner_radius=10, height=50)
        self.filter_frame.pack(fill="x", padx=16, pady=(10, 0))
        self.filter_frame.pack_propagate(False)

        # Recherche texte
        ctk.CTkLabel(
            self.filter_frame, text="Rechercher :",
            font=ctk.CTkFont(size=12), text_color=C_TEXT_DIM,
        ).pack(side="left", padx=(12, 4))

        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._apply_filters())
        self.search_entry = ctk.CTkEntry(
            self.filter_frame, textvariable=self.search_var,
            placeholder_text="Titre, emission, station...",
            width=220, height=32, font=ctk.CTkFont(size=12),
        )
        self.search_entry.pack(side="left", padx=(0, 16))

        # Filtre par thème
        ctk.CTkLabel(
            self.filter_frame, text="Theme :",
            font=ctk.CTkFont(size=12), text_color=C_TEXT_DIM,
        ).pack(side="left", padx=(0, 4))

        self.theme_var = ctk.StringVar(value="Tous les themes")
        self.theme_menu = ctk.CTkOptionMenu(
            self.filter_frame,
            variable=self.theme_var,
            values=["Tous les themes"],
            command=self._on_theme_changed,
            width=200, height=32, font=ctk.CTkFont(size=12),
            fg_color="#374151", button_color="#4b5563",
        )
        self.theme_menu.pack(side="left", padx=(0, 16))

        # Durée minimale
        ctk.CTkLabel(
            self.filter_frame, text="Duree min :",
            font=ctk.CTkFont(size=12), text_color=C_TEXT_DIM,
        ).pack(side="left", padx=(0, 4))

        self.duration_label = ctk.CTkLabel(
            self.filter_frame, text="0 min",
            font=ctk.CTkFont(size=12, weight="bold"), text_color=C_ACCENT,
            width=55,
        )

        self.duration_slider = ctk.CTkSlider(
            self.filter_frame, from_=0, to=120, number_of_steps=24,
            command=self._on_duration_changed,
            width=160, height=18,
            progress_color=C_ACCENT, button_color=C_ACCENT,
        )
        self.duration_slider.set(0)
        self.duration_slider.pack(side="left", padx=(0, 4))
        self.duration_label.pack(side="left", padx=(0, 12))

        # Compteur résultats
        self.results_label = ctk.CTkLabel(
            self.filter_frame, text="",
            font=ctk.CTkFont(size=12), text_color=C_TEXT_MUTED,
        )
        self.results_label.pack(side="right", padx=12)

        # ── Selection helpers ───────────────────────────────────────
        sel_bar = ctk.CTkFrame(self, fg_color="transparent", height=30)
        sel_bar.pack(fill="x", padx=16, pady=(6, 0))

        ctk.CTkButton(
            sel_bar, text="Tout selectionner (visible)",
            command=self._select_all_visible,
            height=28, font=ctk.CTkFont(size=11),
            fg_color="#374151", hover_color="#4b5563", width=170,
        ).pack(side="left")

        ctk.CTkButton(
            sel_bar, text="Tout deselectionner",
            command=self._deselect_all,
            height=28, font=ctk.CTkFont(size=11),
            fg_color="#374151", hover_color="#4b5563", width=140,
        ).pack(side="left", padx=(6, 0))

        # Status
        self.status_label = ctk.CTkLabel(
            sel_bar, text="Cliquez sur  \"1. Recuperer les podcasts\"  pour commencer",
            font=ctk.CTkFont(size=12), text_color=C_TEXT_MUTED,
        )
        self.status_label.pack(side="right", padx=8)

        # ── Progress bar ────────────────────────────────────────────
        self.progress = ctk.CTkProgressBar(self, height=5, progress_color=C_ACCENT)
        self.progress.pack(fill="x", padx=16, pady=(6, 0))
        self.progress.set(0)

        # ── Scrollable podcast list ─────────────────────────────────
        self.scroll_frame = ctk.CTkScrollableFrame(
            self, fg_color="transparent",
            scrollbar_button_color="#334155",
            scrollbar_button_hover_color="#475569",
        )
        self.scroll_frame.pack(fill="both", expand=True, padx=16, pady=(6, 0))

        # ── Transcript panel (hidden by default) ────────────────────
        self.transcript_panel = ctk.CTkFrame(self, fg_color="#111827", corner_radius=8)
        self.transcript_panel.pack(fill="x", padx=16, pady=(6, 12))
        self.transcript_panel.pack_forget()

        tp_header = ctk.CTkFrame(self.transcript_panel, fg_color="transparent")
        tp_header.pack(fill="x", padx=12, pady=(8, 0))

        self.transcript_title = ctk.CTkLabel(
            tp_header, text="Transcription en cours",
            font=ctk.CTkFont(size=13, weight="bold"), text_color="#93c5fd",
        )
        self.transcript_title.pack(side="left")

        self.transcript_percent = ctk.CTkLabel(
            tp_header, text="0%",
            font=ctk.CTkFont(size=13, weight="bold"), text_color=C_GREEN,
        )
        self.transcript_percent.pack(side="right")

        self.transcript_progress = ctk.CTkProgressBar(
            self.transcript_panel, height=4, progress_color=C_PURPLE,
        )
        self.transcript_progress.pack(fill="x", padx=12, pady=(6, 0))
        self.transcript_progress.set(0)

        self.live_text = ctk.CTkTextbox(
            self.transcript_panel, height=110, fg_color="#0d1117",
            font=ctk.CTkFont(size=11), text_color="#d1d5db",
            wrap="word", state="disabled",
        )
        self.live_text.pack(fill="x", padx=12, pady=(6, 10))

    # ═══════════════════════════════════════════════════════════════
    #  Auth check
    # ═══════════════════════════════════════════════════════════════

    def _check_auth_async(self):
        threading.Thread(target=self._check_auth_worker, daemon=True).start()

    def _check_auth_worker(self):
        ok, msg = check_claude_available()
        self.claude_ok = ok
        color = C_GREEN if ok else "#ef4444"
        symbol = "OK" if ok else "X"
        self.after(0, lambda: self.auth_label.configure(
            text=f"  {msg}  {symbol}", text_color=color,
        ))

    def _auto_connect_groq(self):
        """Connexion automatique si la cle Groq est dans .env."""
        key = os.environ.get("GROQ_API_KEY", "").strip()
        if key:
            self.groq_entry.delete(0, "end")
            self.groq_entry.insert(0, key)
            self._on_groq_connect()

    # ═══════════════════════════════════════════════════════════════
    #  Fetch podcasts
    # ═══════════════════════════════════════════════════════════════

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
            self.after(0, self._on_fetch_done)
        except Exception as e:
            self.after(0, lambda: self._set_status(f"Erreur : {e}"))
            self.after(0, lambda: self.fetch_btn.configure(state="normal", text="1. Reessayer"))
            self.after(0, self.progress.stop)

    def _on_fetch_done(self):
        self.progress.stop()
        self.progress.configure(mode="determinate")
        self.progress.set(0)

        # Build theme list
        groups = group_by_theme(self.podcasts)
        self.all_themes = list(groups.keys())
        theme_options = ["Tous les themes"] + [
            f"{t} ({len(groups[t])})" for t in self.all_themes
        ]
        self.theme_menu.configure(values=theme_options)
        self.theme_var.set("Tous les themes")

        # Reset filters
        self.current_theme_filter = "Tous les themes"
        self.current_min_duration = 0
        self.duration_slider.set(0)
        self.search_var.set("")

        # Reset selection
        self.checkbox_vars.clear()
        self.row_frames.clear()
        self.selection_count = 0
        for p in self.podcasts:
            self.checkbox_vars[p["id"]] = ctk.BooleanVar(value=False)

        self._apply_filters()
        self.fetch_btn.configure(state="normal", text="1. Actualiser")
        self._check_existing_transcripts()

    # ═══════════════════════════════════════════════════════════════
    #  Filters
    # ═══════════════════════════════════════════════════════════════

    def _on_theme_changed(self, value: str):
        self.current_theme_filter = value
        self._apply_filters()

    def _on_duration_changed(self, value: float):
        mins = int(value)
        self.current_min_duration = mins * 60
        if mins == 0:
            self.duration_label.configure(text="0 min")
        elif mins < 60:
            self.duration_label.configure(text=f"{mins} min")
        else:
            h = mins // 60
            m = mins % 60
            self.duration_label.configure(text=f"{h}h{m:02d}" if m else f"{h}h")
        self._apply_filters()

    def _apply_filters(self):
        if not self.podcasts:
            return

        search = self.search_var.get().strip().lower()

        # Theme filter
        theme_filter = self.current_theme_filter
        if theme_filter.startswith("Tous"):
            theme_name = None
        else:
            # Strip the count: "Info (86)" -> "Info"
            theme_name = theme_filter.rsplit(" (", 1)[0]

        filtered = []
        for p in self.podcasts:
            # Duration filter
            if p["duration"] and p["duration"] < self.current_min_duration:
                continue

            # Theme filter
            if theme_name and theme_name not in p["themes"]:
                continue

            # Text search
            if search:
                haystack = (
                    p["title"].lower() + " " +
                    p["show_name"].lower() + " " +
                    p["station_name"].lower() + " " +
                    " ".join(p["themes"]).lower()
                )
                if search not in haystack:
                    continue

            filtered.append(p)

        self.filtered_podcasts = filtered
        self._render_podcast_list()

    def _render_podcast_list(self):
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
        self.row_frames.clear()

        if not self.filtered_podcasts:
            ctk.CTkLabel(
                self.scroll_frame,
                text="Aucun podcast ne correspond aux filtres",
                font=ctk.CTkFont(size=14), text_color=C_TEXT_MUTED,
            ).pack(pady=40)
            self.results_label.configure(text="0 resultats")
            return

        # Group filtered podcasts by theme for display
        groups = group_by_theme(self.filtered_podcasts)

        total_displayed = 0
        for theme_name, theme_podcasts in groups.items():
            # Theme header
            theme_header = ctk.CTkFrame(self.scroll_frame, fg_color=C_BG_CARD, corner_radius=8)
            theme_header.pack(fill="x", pady=(10, 3))

            ctk.CTkLabel(
                theme_header,
                text=f"  {theme_name}  ({len(theme_podcasts)})",
                font=ctk.CTkFont(size=14, weight="bold"), text_color="#93c5fd",
            ).pack(side="left", padx=8, pady=5)

            # Select all for this theme
            def _select_theme(podcasts=theme_podcasts):
                for p in podcasts:
                    pid = p["id"]
                    if not self.checkbox_vars[pid].get() and self.selection_count < MAX_SELECTIONS:
                        self.checkbox_vars[pid].set(True)
                        self.selection_count += 1
                        self._style_row(pid)
                self._update_counter()

            ctk.CTkButton(
                theme_header, text="Selectionner ce theme",
                command=_select_theme,
                height=24, font=ctk.CTkFont(size=10),
                fg_color="#374151", hover_color="#4b5563", width=130,
            ).pack(side="right", padx=8, pady=5)

            # Column headers
            col_header = ctk.CTkFrame(self.scroll_frame, fg_color="transparent", height=22)
            col_header.pack(fill="x", padx=4, pady=(2, 0))

            for text, width, anchor in [
                ("", 32, "w"), ("Heure", 55, "w"), ("Duree", 55, "w"),
                ("Station", 110, "w"), ("Emission", 180, "w"), ("Titre", 400, "w"),
            ]:
                ctk.CTkLabel(
                    col_header, text=text, width=width,
                    font=ctk.CTkFont(size=10), text_color=C_TEXT_MUTED, anchor=anchor,
                ).pack(side="left", padx=2)

            # Podcast rows
            for p in theme_podcasts:
                self._add_podcast_row(p)
                total_displayed += 1

        selected = sum(1 for v in self.checkbox_vars.values() if v.get())
        self.results_label.configure(text=f"{total_displayed} resultats")
        self._set_status(
            f"{len(self.podcasts)} podcasts | {total_displayed} affiches | {selected} selectionnes"
        )
        self._update_counter()

    def _add_podcast_row(self, podcast: dict):
        pid = podcast["id"]

        is_selected = self.checkbox_vars.get(pid, ctk.BooleanVar(value=False)).get()
        bg = C_BG_CARD_SELECTED if is_selected else "transparent"

        row = ctk.CTkFrame(self.scroll_frame, fg_color=bg, corner_radius=4, height=34)
        row.pack(fill="x", padx=2, pady=1)
        self.row_frames[pid] = row

        # Make entire row clickable
        def _on_row_click(event, podcast_id=pid):
            self._toggle_selection(podcast_id)

        row.bind("<Button-1>", _on_row_click)

        # Checkbox
        var = self.checkbox_vars.get(pid, ctk.BooleanVar(value=False))
        cb = ctk.CTkCheckBox(
            row, text="", variable=var, width=24,
            command=lambda: self._on_checkbox_toggle(pid),
            checkbox_width=18, checkbox_height=18,
        )
        cb.pack(side="left", padx=(8, 2))

        # Time
        date_str = (
            datetime.fromtimestamp(podcast["date"]).strftime("%d/%m %H:%M")
            if podcast["date"] else ""
        )
        lbl_time = ctk.CTkLabel(
            row, text=date_str, width=55,
            font=ctk.CTkFont(size=11), text_color=C_TEXT_DIM,
        )
        lbl_time.pack(side="left", padx=(0, 4))
        lbl_time.bind("<Button-1>", _on_row_click)

        # Duration
        dur = format_duration(podcast["duration"]) if podcast["duration"] else ""
        dur_color = C_TEXT if podcast.get("duration", 0) >= 600 else C_TEXT_MUTED
        lbl_dur = ctk.CTkLabel(
            row, text=dur, width=55,
            font=ctk.CTkFont(size=11, weight="bold"), text_color=dur_color,
        )
        lbl_dur.pack(side="left", padx=(0, 4))
        lbl_dur.bind("<Button-1>", _on_row_click)

        # Station
        lbl_station = ctk.CTkLabel(
            row, text=podcast["station_name"], width=110,
            font=ctk.CTkFont(size=11), text_color=C_TEXT_MUTED, anchor="w",
        )
        lbl_station.pack(side="left", padx=(0, 4))
        lbl_station.bind("<Button-1>", _on_row_click)

        # Show name
        lbl_show = ctk.CTkLabel(
            row, text=podcast["show_name"][:28], width=180,
            font=ctk.CTkFont(size=11, weight="bold"), text_color="#d1d5db", anchor="w",
        )
        lbl_show.pack(side="left", padx=(0, 4))
        lbl_show.bind("<Button-1>", _on_row_click)

        # Title
        lbl_title = ctk.CTkLabel(
            row, text=podcast["title"][:70],
            font=ctk.CTkFont(size=11), text_color=C_TEXT, anchor="w",
        )
        lbl_title.pack(side="left", fill="x", expand=True)
        lbl_title.bind("<Button-1>", _on_row_click)

    # ═══════════════════════════════════════════════════════════════
    #  Selection
    # ═══════════════════════════════════════════════════════════════

    def _toggle_selection(self, pid: str):
        var = self.checkbox_vars.get(pid)
        if not var:
            return
        current = var.get()
        if not current and self.selection_count >= MAX_SELECTIONS:
            self._set_status(f"Maximum {MAX_SELECTIONS} podcasts. Deselectionnez-en un d'abord.")
            return
        var.set(not current)
        self._on_checkbox_toggle(pid)

    def _on_checkbox_toggle(self, pid: str):
        checked = self.checkbox_vars[pid].get()
        if checked:
            if self.selection_count >= MAX_SELECTIONS:
                self.checkbox_vars[pid].set(False)
                self._set_status(f"Maximum {MAX_SELECTIONS} podcasts. Deselectionnez-en un d'abord.")
                return
            self.selection_count += 1
        else:
            self.selection_count = max(0, self.selection_count - 1)
        self._style_row(pid)
        self._update_counter()

    def _style_row(self, pid: str):
        row = self.row_frames.get(pid)
        if not row:
            return
        checked = self.checkbox_vars[pid].get()
        row.configure(fg_color=C_BG_CARD_SELECTED if checked else "transparent")

    def _select_all_visible(self):
        for p in self.filtered_podcasts:
            pid = p["id"]
            if not self.checkbox_vars[pid].get() and self.selection_count < MAX_SELECTIONS:
                self.checkbox_vars[pid].set(True)
                self.selection_count += 1
                self._style_row(pid)
        self._update_counter()

    def _deselect_all(self):
        for pid, var in self.checkbox_vars.items():
            if var.get():
                var.set(False)
                self._style_row(pid)
        self.selection_count = 0
        self._update_counter()

    def _update_counter(self):
        count = self.selection_count
        color = C_GREEN if 0 < count <= MAX_SELECTIONS else C_TEXT_MUTED
        self.counter_label.configure(
            text=f"{count} / {MAX_SELECTIONS} selectionnes", text_color=color,
        )
        self.process_btn.configure(
            state="normal" if count > 0 else "disabled",
        )

    # ═══════════════════════════════════════════════════════════════
    #  Transcript panel
    # ═══════════════════════════════════════════════════════════════

    def _show_transcript_panel(self, title: str):
        self.transcript_title.configure(text=f"Transcription : {title[:60]}")
        self.transcript_percent.configure(text="0%")
        self.transcript_progress.set(0)
        self.live_text.configure(state="normal")
        self.live_text.delete("1.0", "end")
        self.live_text.configure(state="disabled")
        self.transcript_panel.pack(fill="x", padx=16, pady=(6, 12))

    def _hide_transcript_panel(self):
        self.transcript_panel.pack_forget()

    def _update_transcript_live(self, percent: float, text: str):
        self.transcript_progress.set(percent)
        self.transcript_percent.configure(text=f"{int(percent * 100)}%")
        if text:
            self.live_text.configure(state="normal")
            self.live_text.insert("end", text + " ")
            self.live_text.see("end")
            self.live_text.configure(state="disabled")

    # ═══════════════════════════════════════════════════════════════
    #  Process (download + transcribe)
    # ═══════════════════════════════════════════════════════════════

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
            self.after(0, lambda e=ep, c=completed: self._set_status(
                f"Telechargement {c+1}/{total} : {e['show_name']} - {e['title'][:50]}"
            ))

            try:
                audio_path = download_episode(ep["mp3_url"], ep["id"], ep["title"])
            except Exception as e:
                self.after(0, lambda err=e: self._set_status(f"Erreur telechargement : {err}"))
                completed += 1
                self.after(0, lambda c=completed: self.progress.set(c / total))
                continue

            ep_title = f"{ep['show_name']} - {ep['title'][:40]}"
            self.after(0, lambda t=ep_title: self._show_transcript_panel(t))
            self.after(0, lambda e=ep, c=completed: self._set_status(
                f"Transcription {c+1}/{total} : {e['show_name']} - {e['title'][:50]}"
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
                self.after(0, lambda err=e: self._set_status(f"Erreur transcription : {err}"))
            finally:
                cleanup(audio_path)

            completed += 1
            self.after(0, lambda c=completed: self.progress.set(c / total))

        n = len(transcript_paths)
        self.after(0, lambda: self._set_status(
            f"Transcription terminee - {n} fichier(s) - Cliquez sur  \"3. Resumer + PDF\""
        ))
        self.after(0, self._enable_all_buttons)
        self.after(0, self._check_existing_transcripts)
        self.after(0, self._hide_transcript_panel)

    # ═══════════════════════════════════════════════════════════════
    #  Summarize + PDF
    # ═══════════════════════════════════════════════════════════════

    def _check_existing_transcripts(self):
        transcripts = list(TRANSCRIPTS_DIR.glob("*.txt"))
        unsummarized = [
            t for t in transcripts
            if not (SUMMARIES_DIR / t.with_suffix(".md").name).exists()
        ]
        if unsummarized:
            self.summarize_btn.configure(
                state="normal" if self.claude_ok else "disabled",
                text=f"3. Resumer + PDF ({len(unsummarized)} en attente)",
            )
        else:
            self.summarize_btn.configure(state="disabled", text="3. Resumer + PDF")

    def _on_summarize(self):
        if not self.claude_ok:
            self._set_status("Claude Code non detecte. Lancez 'claude auth login'")
            return

        self._disable_all_buttons()
        self._hide_transcript_panel()
        self.summarize_btn.configure(text="Resume en cours...")
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
            self.after(0, lambda: self._set_status("Tous les transcripts sont deja resumes."))
            self.after(0, self._enable_all_buttons)
            return

        total = len(to_process)
        success = 0

        for i, t_path in enumerate(to_process):
            name = t_path.stem[:50]
            self.after(0, lambda n=name, idx=i: self._set_status(
                f"Resume {idx+1}/{total} via Claude : {n}..."
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
            f"Termine - {success}/{total} resume(s) + PDF generes dans summaries/"
        ))
        self.after(0, self._enable_all_buttons)
        self.after(0, self._check_existing_transcripts)

    # ═══════════════════════════════════════════════════════════════
    #  Groq API connection
    # ═══════════════════════════════════════════════════════════════

    def _on_groq_connect(self):
        key = self.groq_entry.get().strip()
        if not key:
            self.engine_status.configure(text="Entrez une cle API", text_color="#ef4444")
            return

        self.groq_connect_btn.configure(state="disabled", text="Test...")
        self.engine_status.configure(text="Verification...", text_color=C_TEXT_MUTED)

        def worker():
            info = check_groq_api(key)
            if info:
                set_groq_api_key(key)
                # Sauvegarder la cle dans .env pour les prochaines sessions
                self.after(0, lambda: self._save_groq_key(key))
                models = ", ".join(info.get("models", []))
                self.after(0, lambda: self._groq_connected(models))
            else:
                self.after(0, self._groq_failed)

        threading.Thread(target=worker, daemon=True).start()

    def _save_groq_key(self, key: str):
        """Sauvegarde la cle Groq dans .env pour persistence."""
        from pathlib import Path
        env_path = Path(__file__).parent / ".env"
        lines = []
        key_found = False
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                if line.startswith("GROQ_API_KEY="):
                    lines.append(f"GROQ_API_KEY={key}")
                    key_found = True
                else:
                    lines.append(line)
        if not key_found:
            lines.append(f"GROQ_API_KEY={key}")
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _groq_connected(self, models: str):
        self.engine_indicator.configure(
            text="  Groq (ultra-rapide)", text_color=C_GREEN,
        )
        self.engine_status.configure(
            text=f"Actif — whisper-large-v3-turbo | ~15s pour 30 min d'audio",
            text_color=C_GREEN,
        )
        self.groq_connect_btn.pack_forget()
        self.groq_disconnect_btn.pack(side="left", padx=(0, 6))
        self.groq_entry.configure(state="disabled")

    def _groq_failed(self):
        set_groq_api_key(None)
        self.groq_connect_btn.configure(state="normal", text="Activer Groq")
        self.engine_status.configure(
            text="Cle invalide — verifiez sur groq.com/keys", text_color="#ef4444",
        )

    def _on_groq_disconnect(self):
        set_groq_api_key(None)
        self.engine_indicator.configure(text="  CPU local (lent)", text_color="#f59e0b")
        self.engine_status.configure(text="Gratuit sur groq.com/keys", text_color=C_TEXT_MUTED)
        self.groq_entry.configure(state="normal")
        self.groq_disconnect_btn.pack_forget()
        self.groq_connect_btn.pack(side="left", padx=(0, 6))

    # ═══════════════════════════════════════════════════════════════
    #  Helpers
    # ═══════════════════════════════════════════════════════════════

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
            text="2. Transcrire la selection",
        )
        self._check_existing_transcripts()


if __name__ == "__main__":
    app = PodcastApp()
    app.mainloop()
