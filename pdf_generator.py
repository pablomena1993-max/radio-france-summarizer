"""Génération de fiches PDF professionnelles — design inspiré des rapports Radio France."""

import re
import yaml
from pathlib import Path
from math import ceil

from fpdf import FPDF

from config import SUMMARIES_DIR

FONT_DIR = Path("C:/Windows/Fonts")
FONT_R = FONT_DIR / "segoeui.ttf"
FONT_B = FONT_DIR / "segoeuib.ttf"
FONT_I = FONT_DIR / "segoeuii.ttf"

# Palette sobre — taupe/beige
C_BG = (250, 247, 242)
C_HEADER_BG = (245, 241, 235)
C_CARD_BG = (248, 245, 240)
C_CARD_BORDER = (218, 210, 198)
C_ACCENT = (169, 150, 125)
C_ACCENT_DARK = (120, 105, 85)
C_TEXT = (50, 45, 40)
C_TEXT_LIGHT = (120, 110, 100)
C_TEXT_MUTED = (160, 150, 138)
C_TAG_BG = (235, 230, 222)
C_QUOTE_BG = (248, 246, 242)
C_DATE_BG = (200, 188, 170)
C_WHITE = (255, 255, 255)
C_SECTION_LINE = (200, 190, 175)

# Category accent colors (subtle)
CAT_COLORS = {
    "info": (120, 150, 190),
    "culture": (150, 130, 170),
    "sciences": (110, 160, 130),
    "politique": (180, 120, 120),
    "musique": (170, 130, 150),
    "sport": (180, 150, 110),
    "monde": (120, 155, 180),
    "histoire": (160, 140, 110),
    "societe": (150, 150, 130),
    "environnement": (110, 160, 130),
    "humour": (160, 140, 170),
}


def _parse_yaml_summary(md_path: Path) -> dict | None:
    """Parse un fichier .md contenant du YAML entre balises ```yaml."""
    content = md_path.read_text(encoding="utf-8")

    # Extraire le bloc YAML
    match = re.search(r"```ya?ml\s*\n(.+?)```", content, re.DOTALL)
    if match:
        raw = match.group(1)
    else:
        # Essayer de parser le contenu brut comme YAML
        raw = content

    try:
        data = yaml.safe_load(raw)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return None


def _get_accent(categories: list) -> tuple:
    for cat in categories:
        key = cat.lower().strip()
        for k, v in CAT_COLORS.items():
            if k in key:
                return v
    return C_ACCENT


class FichePDF(FPDF):

    def __init__(self, accent=C_ACCENT):
        super().__init__()
        self._fn = "Helvetica"
        self._accent = accent
        self.set_auto_page_break(auto=True, margin=20)

        if FONT_R.exists() and FONT_B.exists():
            try:
                self.add_font("Segoe", "", str(FONT_R))
                self.add_font("Segoe", "B", str(FONT_B))
                if FONT_I.exists():
                    self.add_font("Segoe", "I", str(FONT_I))
                self._fn = "Segoe"
            except Exception:
                pass

    def header(self):
        pass  # Custom header per page

    def footer(self):
        self.set_y(-12)
        self.set_font(self._fn, "", 7)
        self.set_text_color(*C_TEXT_MUTED)
        self.cell(0, 8, f"Page {self.page_no()}/{{nb}}", align="C")

    # ── Drawing helpers ──

    def _section_title(self, title: str):
        self.ln(6)
        self.set_font(self._fn, "B", 9)
        self.set_text_color(*C_TEXT_LIGHT)
        self.cell(0, 6, title.upper(), new_x="LMARGIN", new_y="NEXT")
        y = self.get_y()
        self.set_draw_color(*C_SECTION_LINE)
        self.set_line_width(0.3)
        self.line(10, y, self.w - 10, y)
        self.ln(4)

    def _rich_text(self, text: str, size: float = 9, color=C_TEXT, line_height: float = 5):
        """Write text with **bold** support."""
        self.set_font(self._fn, "", size)
        self.set_text_color(*color)

        parts = re.split(r"(\*\*.*?\*\*)", text)
        x_start = self.get_x()
        for part in parts:
            if part.startswith("**") and part.endswith("**"):
                self.set_font(self._fn, "B", size)
                self.write(line_height, part[2:-2])
                self.set_font(self._fn, "", size)
            else:
                self.write(line_height, part)
        self.ln(line_height)

    def _card(self, x, y, w, h, title: str, content: str):
        """Draw a card with border, title and content."""
        # Border
        self.set_draw_color(*C_CARD_BORDER)
        self.set_fill_color(*C_WHITE)
        self.set_line_width(0.3)
        self.rect(x, y, w, h, "DF")

        # Title
        self.set_xy(x + 3, y + 3)
        self.set_font(self._fn, "B", 9)
        self.set_text_color(*C_TEXT)
        self.multi_cell(w - 6, 5, title, new_x="LEFT", new_y="NEXT")

        # Content
        self.set_x(x + 3)
        self.set_font(self._fn, "", 8)
        self.set_text_color(*C_TEXT_LIGHT)
        self.multi_cell(w - 6, 4.2, content)

    def _tag_pill(self, text: str):
        """Draw a tag pill and return its width."""
        self.set_font(self._fn, "", 7.5)
        tw = self.get_string_width(text) + 6
        x, y = self.get_x(), self.get_y()
        self.set_fill_color(*C_TAG_BG)
        self.set_draw_color(*C_CARD_BORDER)
        self.rect(x, y, tw, 7, "DF")
        self.set_text_color(*C_TEXT_LIGHT)
        self.set_xy(x + 3, y + 0.5)
        self.cell(tw - 6, 6, text)
        self.set_xy(x + tw + 2, y)
        return tw + 2

    # ── Page builders ──

    def build_page1(self, data: dict):
        """First page: header, title, intervenants, resume, themes grid."""
        self.add_page()

        # ── Top header bar ──
        self.set_fill_color(*C_HEADER_BG)
        self.rect(0, 0, self.w, 14, "F")
        self.set_xy(10, 3)
        self.set_font(self._fn, "", 8)
        self.set_text_color(*C_TEXT_LIGHT)

        emission = data.get("emission", "")
        station = data.get("station", "")
        date = data.get("date", "")
        duree = data.get("duree", "")
        header_left = f"{station}  ·  {emission}  ·  {date}  ·  {duree}"
        self.cell(self.w / 2 - 10, 8, header_left)

        # Category tags (right)
        cats = data.get("categories", [])
        if cats:
            cat_text = "  ·  ".join(cats)
            self.set_xy(self.w / 2, 3)
            self.set_font(self._fn, "I", 8)
            self.set_text_color(*self._accent)
            self.cell(self.w / 2 - 10, 8, cat_text, align="R")

        # ── Title ──
        self.set_y(20)
        self.set_font(self._fn, "B", 20)
        self.set_text_color(*C_TEXT)
        self.set_x(10)
        self.multi_cell(self.w - 20, 10, data.get("titre", "Sans titre"))

        # Subtitle
        sous_titre = data.get("sous_titre", "")
        if sous_titre:
            self.set_font(self._fn, "I", 10)
            self.set_text_color(*C_TEXT_LIGHT)
            self.set_x(10)
            self.multi_cell(self.w - 20, 6, sous_titre)

        # ── Intervenants ──
        intervenants = data.get("intervenants", [])
        if intervenants:
            self._section_title("INTERVENANTS")
            # Cards in 2 columns
            col_w = (self.w - 24) / 2
            y_start = self.get_y()
            max_h = 0

            for i, interv in enumerate(intervenants[:4]):
                col = i % 2
                row = i // 2
                x = 10 + col * (col_w + 4)
                y = y_start + row * 28

                name = interv.get("nom", "")
                role = interv.get("role", "")
                ouvrage = interv.get("ouvrage", "")

                self.set_draw_color(*C_CARD_BORDER)
                self.set_fill_color(*C_WHITE)
                self.rect(x, y, col_w, 24, "DF")

                self.set_xy(x + 3, y + 2)
                self.set_font(self._fn, "B", 10)
                self.set_text_color(*C_TEXT)
                self.cell(col_w - 6, 6, name)

                self.set_xy(x + 3, y + 8)
                self.set_font(self._fn, "", 8)
                self.set_text_color(*C_TEXT_LIGHT)
                self.multi_cell(col_w - 6, 4, role)

                if ouvrage:
                    self.set_x(x + 3)
                    self.set_font(self._fn, "I", 7.5)
                    self.set_text_color(*C_ACCENT_DARK)
                    self.cell(col_w - 6, 4, ouvrage[:60])

                max_h = max(max_h, y + 26)

            self.set_y(max_h + 2)

        # ── Resume general ──
        self._section_title("RESUME GENERAL")
        resume = data.get("resume_general", "")
        if resume:
            self.set_x(10)
            self._rich_text(resume, size=9, line_height=5)
            self.ln(2)

    def build_themes(self, data: dict):
        """Themes as full-width sections — no truncation."""
        themes = data.get("themes_developpes", [])
        if not themes:
            return

        self._section_title("THEMES DEVELOPPES")

        for i, theme in enumerate(themes):
            titre = theme.get("titre", "")
            contenu = theme.get("contenu", "")

            if self.get_y() > self.h - 40:
                self.add_page()
                self.ln(8)

            # Theme number + title
            self.set_x(10)
            self.set_font(self._fn, "B", 10)
            self.set_text_color(*self._accent)
            self.cell(8, 6, f"{i + 1}.")
            self.set_font(self._fn, "B", 10)
            self.set_text_color(*C_TEXT)
            self.multi_cell(self.w - 28, 6, titre)
            self.ln(1)

            # Full content — no truncation
            self.set_x(18)
            self.set_font(self._fn, "", 9)
            self.set_text_color(*C_TEXT_LIGHT)
            self.multi_cell(self.w - 28, 4.8, contenu)
            self.ln(4)

            # Subtle separator between themes
            if i < len(themes) - 1:
                self.set_draw_color(230, 225, 218)
                self.set_line_width(0.2)
                y = self.get_y()
                self.line(18, y, self.w - 18, y)
                self.ln(3)

    def build_chronologie(self, data: dict):
        """Timeline with date badges."""
        chrono = data.get("chronologie", [])
        if not chrono:
            return

        self._section_title("CHRONOLOGIE CLE")

        for item in chrono:
            if self.get_y() > self.h - 30:
                self.add_page()
                self.ln(8)

            date = str(item.get("date", ""))
            evenement = item.get("evenement", "")
            detail = item.get("detail", "")

            y = self.get_y()

            # Date badge
            self.set_fill_color(*C_DATE_BG)
            self.set_font(self._fn, "B", 8)
            dw = max(self.get_string_width(date) + 6, 16)
            self.rect(10, y, dw, 8, "F")
            self.set_xy(10, y + 1)
            self.set_text_color(*C_WHITE)
            self.cell(dw, 6, date, align="C")

            # Event text
            self.set_xy(10 + dw + 4, y)
            self.set_font(self._fn, "B", 9)
            self.set_text_color(*C_TEXT)
            self.cell(0, 5, evenement)

            if detail:
                self.set_xy(10 + dw + 4, y + 5)
                self.set_font(self._fn, "", 8)
                self.set_text_color(*C_TEXT_LIGHT)
                self.multi_cell(self.w - 30 - dw, 4, detail)

            self.set_y(max(self.get_y(), y + 12))
            self.ln(2)

    def build_citations(self, data: dict):
        """Quotes with italic text and attribution."""
        citations = data.get("citations", [])
        if not citations:
            return

        self._section_title("CITATIONS REMARQUABLES")

        for cit in citations:
            if self.get_y() > self.h - 35:
                self.add_page()
                self.ln(8)

            texte = cit.get("texte", "")
            auteur = cit.get("auteur", "")
            contexte = cit.get("contexte", "")

            # Quote text
            self.set_x(14)
            self.set_font(self._fn, "I", 9)
            self.set_text_color(*C_TEXT)
            self.multi_cell(self.w - 28, 5, texte)

            # Attribution
            attrib = auteur
            if contexte:
                attrib += f" — {contexte}"
            self.set_x(14)
            self.set_font(self._fn, "", 7.5)
            self.set_text_color(*C_TEXT_MUTED)
            self.cell(0, 5, attrib, new_x="LMARGIN", new_y="NEXT")
            self.ln(5)

    def build_apport(self, data: dict):
        """Main contribution section."""
        apport = data.get("apport_principal", "")
        if not apport:
            return

        self._section_title("APPORT PRINCIPAL")
        self.set_x(10)
        self._rich_text(apport, size=9, line_height=5)
        self.ln(3)

    def build_tags(self, data: dict):
        """Keyword tag pills at the bottom."""
        mots = data.get("mots_cles", [])
        if not mots:
            return

        self.ln(4)
        if self.get_y() > self.h - 25:
            self.add_page()
            self.ln(8)

        # Tags in rows
        self.set_x(10)
        x_start = 10
        max_x = self.w - 10

        for mot in mots:
            self.set_font(self._fn, "", 7.5)
            tw = self.get_string_width(mot) + 8
            if self.get_x() + tw > max_x:
                self.ln(9)
                self.set_x(x_start)
            self._tag_pill(mot)

    def build_fiche_recap(self, data: dict):
        """Fiche recapitulative concentree — concepts cles en bref."""
        themes = data.get("themes_developpes", [])
        mots = data.get("mots_cles", [])
        citations = data.get("citations", [])
        chrono = data.get("chronologie", [])
        if not themes:
            return

        self.add_page()
        self.ln(4)

        # Title bar
        self.set_fill_color(*self._accent)
        self.rect(10, self.get_y(), self.w - 20, 10, "F")
        self.set_font(self._fn, "B", 12)
        self.set_text_color(*C_WHITE)
        self.set_x(14)
        self.cell(0, 10, "FICHE RECAPITULATIVE — L'ESSENTIEL EN UN COUP D'OEIL")
        self.ln(14)

        # Concepts cles (from themes — titre only)
        self.set_font(self._fn, "B", 9)
        self.set_text_color(*C_ACCENT_DARK)
        self.cell(0, 6, "CONCEPTS CLES", new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

        for theme in themes:
            titre = theme.get("titre", "")
            contenu = theme.get("contenu", "")
            # Extract first sentence as summary
            first_sentence = contenu.split(".")[0] + "." if "." in contenu else contenu[:100]

            self.set_x(14)
            self.set_font(self._fn, "B", 8.5)
            self.set_text_color(*C_TEXT)
            self.cell(4, 5, "\u2022")
            self.cell(0, 5, titre)
            self.ln(5)
            self.set_x(18)
            self.set_font(self._fn, "", 8)
            self.set_text_color(*C_TEXT_LIGHT)
            self.multi_cell(self.w - 28, 4, first_sentence)
            self.ln(1)

        # Chiffres cles (extract numbers from resume)
        resume = data.get("resume_general", "")
        if resume:
            self.ln(3)
            self.set_font(self._fn, "B", 9)
            self.set_text_color(*C_ACCENT_DARK)
            self.cell(0, 6, "CHIFFRES CLES", new_x="LMARGIN", new_y="NEXT")
            self.ln(1)

            import re as regex
            # Find all sentences with numbers
            sentences = regex.split(r"(?<=[.!?])\s+", resume)
            number_sentences = [s for s in sentences if regex.search(r"\d", s)]
            for s in number_sentences[:8]:
                clean = regex.sub(r"\*\*(.+?)\*\*", r"\1", s)
                self.set_x(14)
                self.set_font(self._fn, "", 8)
                self.set_text_color(*C_TEXT)
                self.cell(4, 4.5, "\u2022")
                self.multi_cell(self.w - 28, 4.5, clean.strip())
                self.ln(1)

        # Key dates (condensed)
        if chrono:
            self.ln(3)
            self.set_font(self._fn, "B", 9)
            self.set_text_color(*C_ACCENT_DARK)
            self.cell(0, 6, "DATES CLES", new_x="LMARGIN", new_y="NEXT")
            self.ln(1)

            for item in chrono:
                date = str(item.get("date", ""))
                evt = item.get("evenement", "")
                self.set_x(14)
                self.set_font(self._fn, "B", 8)
                self.set_text_color(*self._accent)
                self.cell(22, 4.5, date)
                self.set_font(self._fn, "", 8)
                self.set_text_color(*C_TEXT)
                self.cell(0, 4.5, evt, new_x="LMARGIN", new_y="NEXT")

        # Best citation
        if citations:
            self.ln(3)
            self.set_font(self._fn, "B", 9)
            self.set_text_color(*C_ACCENT_DARK)
            self.cell(0, 6, "CITATION A RETENIR", new_x="LMARGIN", new_y="NEXT")
            self.ln(1)
            best = citations[0]
            self.set_x(14)
            self.set_font(self._fn, "I", 9)
            self.set_text_color(*C_TEXT)
            self.multi_cell(self.w - 28, 5, f"\u00ab {best.get('texte', '')} \u00bb")
            self.set_x(14)
            self.set_font(self._fn, "", 7.5)
            self.set_text_color(*C_TEXT_MUTED)
            self.cell(0, 5, f"— {best.get('auteur', '')}")

    def build_footer_bar(self, data: dict):
        """Bottom metadata bar."""
        self.ln(8)
        y = self.get_y()
        if y > self.h - 20:
            return

        self.set_draw_color(*C_SECTION_LINE)
        self.line(10, y, self.w - 10, y)
        self.set_y(y + 2)

        station = data.get("station", "")
        emission = data.get("emission", "")
        date = data.get("date", "")

        self.set_font(self._fn, "", 7)
        self.set_text_color(*C_TEXT_MUTED)
        self.set_x(10)
        self.cell(self.w / 2 - 10, 5, f"{station}  ·  {emission}  ·  {date}  ·  Groq whisper + Llama")
        self.cell(self.w / 2 - 10, 5, f"{station}  ·  radiofrance.fr", align="R")


def markdown_to_pdf(md_path: Path, pdf_path: Path | None = None) -> Path:
    """Convertit un fichier de résumé (YAML ou Markdown) en PDF professionnel."""
    if pdf_path is None:
        pdf_path = md_path.with_suffix(".pdf")

    data = _parse_yaml_summary(md_path)

    if not data:
        # Fallback: fichier Markdown classique — generer un PDF basique
        return _fallback_md_to_pdf(md_path, pdf_path)

    accent = _get_accent(data.get("categories", []))
    pdf = FichePDF(accent=accent)
    pdf.alias_nb_pages()

    pdf.build_page1(data)
    pdf.build_themes(data)
    pdf.build_chronologie(data)
    pdf.build_citations(data)
    pdf.build_apport(data)
    pdf.build_fiche_recap(data)
    pdf.build_tags(data)
    pdf.build_footer_bar(data)

    pdf.output(str(pdf_path))
    return pdf_path


def _fallback_md_to_pdf(md_path: Path, pdf_path: Path) -> Path:
    """Fallback pour les fichiers Markdown non-YAML."""
    content = md_path.read_text(encoding="utf-8")
    pdf = FichePDF()
    pdf.alias_nb_pages()
    pdf.add_page()

    for line in content.split("\n"):
        line = line.rstrip()
        if not line:
            pdf.ln(3)
        elif line.startswith("# "):
            pdf.set_font(pdf._fn, "B", 16)
            pdf.set_text_color(*C_TEXT)
            pdf.multi_cell(0, 9, line[2:].strip())
            pdf.ln(3)
        elif line.startswith("## "):
            pdf._section_title(line[3:].strip())
        elif line.startswith("### "):
            pdf.set_font(pdf._fn, "B", 10)
            pdf.set_text_color(*C_TEXT)
            pdf.multi_cell(0, 6, line[4:].strip())
            pdf.ln(2)
        elif line.startswith("> "):
            pdf.set_font(pdf._fn, "I", 9)
            pdf.set_text_color(*C_TEXT_LIGHT)
            pdf.set_x(14)
            pdf.multi_cell(pdf.w - 28, 5, line[2:].strip())
            pdf.ln(3)
        elif line.startswith("- "):
            text = re.sub(r"\*\*(.+?)\*\*", r"\1", line[2:].strip())
            pdf.set_font(pdf._fn, "", 9)
            pdf.set_text_color(*C_TEXT)
            pdf.set_x(14)
            pdf.cell(4, 5, "\u2022")
            pdf.multi_cell(0, 5, text)
            pdf.ln(1)
        else:
            text = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
            text = re.sub(r"\*(.+?)\*", r"\1", text)
            if text.strip():
                pdf.set_font(pdf._fn, "", 9)
                pdf.set_text_color(*C_TEXT)
                pdf.multi_cell(0, 5, text)
                pdf.ln(1)

    pdf.output(str(pdf_path))
    return pdf_path


def convert_all_summaries() -> list[Path]:
    """Convertit tous les résumés .md du dossier summaries/ en PDF."""
    pdf_paths = []
    for md_file in sorted(SUMMARIES_DIR.glob("*.md")):
        pdf_path = markdown_to_pdf(md_file)
        pdf_paths.append(pdf_path)
    return pdf_paths
