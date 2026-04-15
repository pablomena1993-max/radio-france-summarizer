"""Génération de PDF à partir des résumés Markdown."""

import re
from pathlib import Path

from fpdf import FPDF

from config import SUMMARIES_DIR

# Polices Windows avec support Unicode complet
FONT_DIR = Path("C:/Windows/Fonts")
FONT_REGULAR = FONT_DIR / "segoeui.ttf"
FONT_BOLD = FONT_DIR / "segoeuib.ttf"
FONT_ITALIC = FONT_DIR / "segoeuii.ttf"


class PodcastPDF(FPDF):
    """PDF stylisé pour les résumés de podcasts."""

    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=20)

        # Enregistrer les polices Unicode
        self.add_font("Segoe", "", str(FONT_REGULAR), uni=True)
        self.add_font("Segoe", "B", str(FONT_BOLD), uni=True)
        self.add_font("Segoe", "I", str(FONT_ITALIC), uni=True)

    def header(self):
        self.set_font("Segoe", "B", 10)
        self.set_text_color(130, 130, 130)
        self.cell(0, 8, "Radio France \u2014 Résumé de podcast", align="R", new_x="LMARGIN", new_y="NEXT")
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("Segoe", "I", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")

    def add_title(self, title: str):
        self.set_font("Segoe", "B", 18)
        self.set_text_color(20, 20, 80)
        self.multi_cell(0, 10, title)
        self.ln(2)

    def add_metadata(self, label: str, value: str):
        self.set_font("Segoe", "B", 10)
        self.set_text_color(80, 80, 80)
        self.cell(30, 6, f"{label} :")
        self.set_font("Segoe", "", 10)
        self.set_text_color(40, 40, 40)
        self.cell(0, 6, value, new_x="LMARGIN", new_y="NEXT")

    def add_section(self, title: str):
        self.ln(4)
        self.set_font("Segoe", "B", 13)
        self.set_text_color(30, 30, 100)
        self.multi_cell(0, 8, title)
        self.set_draw_color(30, 30, 100)
        self.line(10, self.get_y(), 80, self.get_y())
        self.ln(3)

    def add_subsection(self, title: str):
        self.ln(2)
        self.set_font("Segoe", "B", 11)
        self.set_text_color(50, 50, 50)
        self.multi_cell(0, 7, title)
        self.ln(1)

    def add_paragraph(self, text: str):
        self.set_font("Segoe", "", 10)
        self.set_text_color(30, 30, 30)
        self.multi_cell(0, 6, text)
        self.ln(2)

    def add_bullet(self, text: str):
        self.set_font("Segoe", "", 10)
        self.set_text_color(30, 30, 30)
        self.cell(8, 6, "\u2022")
        self.multi_cell(0, 6, text)
        self.ln(1)

    def add_quote(self, text: str):
        self.set_font("Segoe", "I", 10)
        self.set_text_color(80, 80, 80)
        self.set_x(15)
        self.multi_cell(175, 6, f"\u00ab {text} \u00bb")
        self.ln(2)


def markdown_to_pdf(md_path: Path, pdf_path: Path | None = None) -> Path:
    """Convertit un fichier Markdown de résumé en PDF structuré."""
    if pdf_path is None:
        pdf_path = md_path.with_suffix(".pdf")

    content = md_path.read_text(encoding="utf-8")
    lines = content.split("\n")

    pdf = PodcastPDF()
    pdf.alias_nb_pages()
    pdf.add_page()

    in_header = True  # Pour détecter les métadonnées en début de fichier

    for line in lines:
        line = line.rstrip()

        if not line:
            in_header = False
            continue

        # Titre principal (# ...)
        if line.startswith("# ") and not line.startswith("## "):
            pdf.add_title(line[2:].strip())
            in_header = True

        # Section (## ...)
        elif line.startswith("## "):
            in_header = False
            pdf.add_section(line[3:].strip())

        # Sous-section (### ...)
        elif line.startswith("### "):
            pdf.add_subsection(line[4:].strip())

        # Séparateur
        elif line.startswith("---") or line.startswith("==="):
            in_header = False
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(4)

        # Métadonnées (en début de fichier, format **clé** : valeur)
        elif in_header and (":" in line):
            clean = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
            parts = clean.split(":", 1)
            if len(parts) == 2:
                pdf.add_metadata(parts[0].strip(), parts[1].strip())

        # Citation
        elif line.startswith("> "):
            text = re.sub(r"\*\*(.+?)\*\*", r"\1", line[2:].strip())
            pdf.add_quote(text)

        # Liste à puces
        elif line.startswith("- ") or line.startswith("* "):
            text = line[2:].strip()
            text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
            pdf.add_bullet(text)

        # Paragraphe normal
        else:
            text = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
            text = re.sub(r"\*(.+?)\*", r"\1", text)
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
