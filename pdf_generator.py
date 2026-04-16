"""Génération de PDF stylisés à partir des résumés Markdown."""

import re
from pathlib import Path

from fpdf import FPDF

from config import SUMMARIES_DIR

FONT_DIR = Path("C:/Windows/Fonts")
FONT_REGULAR = FONT_DIR / "segoeui.ttf"
FONT_BOLD = FONT_DIR / "segoeuib.ttf"
FONT_ITALIC = FONT_DIR / "segoeuii.ttf"

# Palette pastel par catégorie
THEME_COLORS = {
    "Info": (191, 219, 254),
    "Culture": (221, 214, 254),
    "Société": (253, 230, 138),
    "Sciences": (167, 243, 208),
    "Sciences et Savoirs": (167, 243, 208),
    "Politique": (254, 202, 202),
    "Musique": (251, 207, 232),
    "Sport": (254, 215, 170),
    "Humour": (233, 213, 255),
    "Monde": (186, 230, 253),
    "Environnement": (167, 243, 208),
    "Histoire": (253, 230, 138),
    "Autre": (229, 231, 235),
}

DEFAULT_COLOR = (191, 219, 254)


def _get_theme_color(themes_str: str) -> tuple:
    """Retourne la couleur pastel pour le premier thème reconnu."""
    for theme, color in THEME_COLORS.items():
        if theme.lower() in themes_str.lower():
            return color
    return DEFAULT_COLOR


def _darken(color: tuple, factor: float = 0.6) -> tuple:
    return tuple(int(c * factor) for c in color)


class PodcastPDF(FPDF):

    def __init__(self, theme_color=DEFAULT_COLOR):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=25)
        self._fn = "Helvetica"
        self._theme = theme_color
        self._dark = _darken(theme_color, 0.5)

        if FONT_REGULAR.exists() and FONT_BOLD.exists():
            try:
                self.add_font("Segoe", "", str(FONT_REGULAR))
                self.add_font("Segoe", "B", str(FONT_BOLD))
                if FONT_ITALIC.exists():
                    self.add_font("Segoe", "I", str(FONT_ITALIC))
                self._fn = "Segoe"
            except Exception:
                pass

    def header(self):
        # Barre de couleur en haut
        self.set_fill_color(*self._theme)
        self.rect(0, 0, self.w, 6, "F")

        if self.page_no() > 1:
            self.set_y(10)
            self.set_font(self._fn, "I", 8)
            self.set_text_color(150, 150, 150)
            self.cell(0, 6, "Radio France — Compte-rendu de podcast", align="R", new_x="LMARGIN", new_y="NEXT")
            self.ln(2)

    def footer(self):
        self.set_y(-15)
        self.set_font(self._fn, "I", 8)
        self.set_text_color(170, 170, 170)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")

    def cover(self, title: str, metadata: dict):
        """Page de couverture avec titre et métadonnées."""
        self.add_page()
        self.ln(30)

        # Barre décorative large
        self.set_fill_color(*self._theme)
        self.rect(20, 35, self.w - 40, 5, "F")

        # Titre
        self.set_font(self._fn, "B", 22)
        self.set_text_color(*self._dark)
        self.multi_cell(0, 11, title, align="C")
        self.ln(8)

        # Métadonnées dans un cadre
        self.set_fill_color(self._theme[0], self._theme[1], self._theme[2])
        y_start = self.get_y()
        box_h = 8 + len(metadata) * 7
        self.set_fill_color(248, 250, 252)
        self.set_draw_color(*self._theme)
        self.rect(30, y_start, self.w - 60, box_h, "DF")

        self.set_y(y_start + 4)
        for label, value in metadata.items():
            self.set_x(35)
            self.set_font(self._fn, "B", 10)
            self.set_text_color(100, 100, 100)
            self.cell(28, 6, f"{label} :")
            self.set_font(self._fn, "", 10)
            self.set_text_color(50, 50, 50)
            self.cell(0, 6, value, new_x="LMARGIN", new_y="NEXT")

        self.set_y(y_start + box_h + 8)

        # Petit trait de séparation
        self.set_draw_color(*self._theme)
        self.line(70, self.get_y(), self.w - 70, self.get_y())
        self.ln(6)

    def add_section(self, title: str):
        self.ln(5)
        # Barre de couleur à gauche du titre
        y = self.get_y()
        self.set_fill_color(*self._theme)
        self.rect(10, y, 4, 10, "F")
        self.set_x(18)
        self.set_font(self._fn, "B", 14)
        self.set_text_color(*self._dark)
        self.multi_cell(self.w - 28, 9, title)
        self.ln(2)

    def add_subsection(self, title: str):
        self.ln(3)
        self.set_font(self._fn, "B", 11)
        self.set_text_color(60, 60, 80)
        # Petit cercle de couleur
        y = self.get_y() + 2
        self.set_fill_color(*self._theme)
        self.circle(14, y + 1.5, 1.5, "F")
        self.set_x(18)
        self.multi_cell(self.w - 28, 7, title)
        self.ln(1)

    def add_paragraph(self, text: str):
        self.set_font(self._fn, "", 10)
        self.set_text_color(40, 40, 40)
        self.set_x(14)
        self.multi_cell(self.w - 28, 5.5, text)
        self.ln(2)

    def add_bold_paragraph(self, label: str, text: str):
        """Paragraphe avec label en gras."""
        self.set_x(14)
        self.set_font(self._fn, "B", 10)
        self.set_text_color(60, 60, 80)
        self.cell(self.get_string_width(label) + 2, 5.5, label)
        self.set_font(self._fn, "", 10)
        self.set_text_color(40, 40, 40)
        self.multi_cell(0, 5.5, text)
        self.ln(1)

    def add_bullet(self, text: str, bold_prefix: str = ""):
        self.set_x(18)
        self.set_font(self._fn, "", 10)
        self.set_text_color(*self._dark)
        self.cell(4, 5.5, "\u2022")
        if bold_prefix:
            self.set_font(self._fn, "B", 10)
            self.set_text_color(50, 50, 70)
            self.cell(self.get_string_width(bold_prefix) + 1, 5.5, bold_prefix)
            self.set_font(self._fn, "", 10)
            self.set_text_color(40, 40, 40)
            self.multi_cell(0, 5.5, text)
        else:
            self.set_text_color(40, 40, 40)
            self.multi_cell(0, 5.5, text)
        self.ln(1)

    def add_numbered(self, num: int, text: str):
        self.set_x(18)
        self.set_font(self._fn, "B", 10)
        self.set_text_color(*self._dark)
        self.cell(8, 5.5, f"{num}.")
        self.set_font(self._fn, "", 10)
        self.set_text_color(40, 40, 40)
        self.multi_cell(0, 5.5, text)
        self.ln(1)

    def add_quote(self, text: str):
        y = self.get_y()
        # Barre de citation colorée
        self.set_fill_color(*self._theme)
        self.rect(16, y, 3, 12, "F")
        self.set_x(22)
        self.set_font(self._fn, "I", 10)
        self.set_text_color(80, 80, 100)
        self.multi_cell(self.w - 36, 5.5, f"\u00ab {text} \u00bb")
        self.ln(3)

    def add_separator(self):
        self.set_draw_color(220, 220, 230)
        y = self.get_y()
        self.line(30, y, self.w - 30, y)
        self.ln(4)


def markdown_to_pdf(md_path: Path, pdf_path: Path | None = None) -> Path:
    """Convertit un fichier Markdown de résumé en PDF structuré et coloré."""
    if pdf_path is None:
        pdf_path = md_path.with_suffix(".pdf")

    content = md_path.read_text(encoding="utf-8")
    lines = content.split("\n")

    # Détecter les catégories dans les métadonnées
    theme_color = DEFAULT_COLOR
    for line in lines[:15]:
        if "catégories" in line.lower() or "categories" in line.lower():
            theme_color = _get_theme_color(line)
            break

    pdf = PodcastPDF(theme_color=theme_color)
    pdf.alias_nb_pages()

    # Première passe : extraire titre et métadonnées
    title = ""
    metadata = {}
    content_start = 0
    in_header = True
    numbered_counter = 0

    for i, line in enumerate(lines):
        line_stripped = line.rstrip()
        if not line_stripped:
            continue
        if line_stripped.startswith("# ") and not line_stripped.startswith("## "):
            title = line_stripped[2:].strip()
            content_start = i + 1
            continue
        if in_header and ":" in line_stripped and not line_stripped.startswith("#"):
            clean = re.sub(r"\*\*(.+?)\*\*", r"\1", line_stripped)
            parts = clean.split(":", 1)
            if len(parts) == 2 and len(parts[0].strip()) < 30:
                metadata[parts[0].strip()] = parts[1].strip()
                content_start = i + 1
                continue
        if line_stripped.startswith("---"):
            in_header = False
            content_start = i + 1
            continue
        if in_header:
            continue
        break

    # Page de couverture
    pdf.cover(title or md_path.stem, metadata)

    # Contenu principal
    for line in lines[content_start:]:
        line = line.rstrip()

        if not line:
            numbered_counter = 0
            continue

        # Section (## ...)
        if line.startswith("## "):
            numbered_counter = 0
            pdf.add_section(line[3:].strip())

        # Sous-section (### ...)
        elif line.startswith("### "):
            numbered_counter = 0
            pdf.add_subsection(line[4:].strip())

        # Séparateur
        elif line.startswith("---") or line.startswith("==="):
            pdf.add_separator()

        # Citation
        elif line.startswith("> "):
            text = re.sub(r"\*\*(.+?)\*\*", r"\1", line[2:].strip())
            pdf.add_quote(text)

        # Liste numérotée (1. ...)
        elif re.match(r"^\d+\.\s", line):
            text = re.sub(r"^\d+\.\s*", "", line)
            text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
            numbered_counter += 1
            pdf.add_numbered(numbered_counter, text)

        # Liste à puces avec gras au début
        elif line.startswith("- **") or line.startswith("* **"):
            text = line[2:].strip()
            match = re.match(r"\*\*(.+?)\*\*\s*:?\s*(.*)", text)
            if match:
                pdf.add_bullet(match.group(2), match.group(1) + " : ")
            else:
                clean = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
                pdf.add_bullet(clean)

        # Liste à puces simple
        elif line.startswith("- ") or line.startswith("* "):
            text = re.sub(r"\*\*(.+?)\*\*", r"\1", line[2:].strip())
            pdf.add_bullet(text)

        # Ligne avec label en gras (**Label** : texte)
        elif line.startswith("**"):
            match = re.match(r"\*\*(.+?)\*\*\s*:?\s*(.*)", line)
            if match:
                pdf.add_bold_paragraph(match.group(1) + " : ", match.group(2))
            else:
                text = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
                pdf.add_paragraph(text)

        # Paragraphe normal
        else:
            text = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
            text = re.sub(r"\*(.+?)\*", r"\1", text)
            if text.strip():
                pdf.add_paragraph(text)

    pdf.output(str(pdf_path))
    return pdf_path


def convert_all_summaries() -> list[Path]:
    """Convertit tous les résumés .md du dossier summaries/ en PDF."""
    pdf_paths = []
    for md_file in sorted(SUMMARIES_DIR.glob("*.md")):
        pdf_path = markdown_to_pdf(md_file)
        pdf_paths.append(pdf_path)
    return pdf_paths
