"""Turn the plan report (Markdown) into a branded PDF with fpdf2. No network, no extra dependencies."""
from __future__ import annotations

import html
import re
from datetime import date
from pathlib import Path

from fpdf import FPDF

LOGO = Path(__file__).resolve().parent / "assets" / "alwayshome-mark.png"
EMBER = (210, 96, 42)
INK = (17, 17, 17)
GREY = (110, 104, 98)

# The built-in PDF fonts are Latin-1 only: map common typographic characters, drop the rest.
_REPLACE = {"–": "-", "—": "-", "‘": "'", "’": "'", "“": '"', "”": '"', "…": "...",
            "•": "-", " ": " ", "≤": "<=", "≥": ">=", "→": "->", "▼": "", "≈": "~"}


def _latin1(text: str) -> str:
    for k, v in _REPLACE.items():
        text = text.replace(k, v)
    return text.encode("latin-1", "ignore").decode("latin-1")


def _inline(text: str) -> str:
    text = html.escape(_latin1(text), quote=False)
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)


def markdown_to_html(md: str) -> tuple[str, str]:
    """Return (title, body html) for the small Markdown subset the report uses."""
    title, out, list_tag = "Your AlwaysHome plan", [], None

    def close_list():
        nonlocal list_tag
        if list_tag:
            out.append(f"</{list_tag}>")
            list_tag = None

    for raw in md.splitlines():
        line = raw.rstrip()
        if not line.strip():
            close_list()
            continue
        if line.startswith("# "):
            close_list()
            title = _latin1(line[2:].strip())
            continue
        if line.startswith("## ") or line.startswith("### "):
            close_list()
            out.append(f'<h2><font color="#D2602A">{_inline(line.lstrip("#").strip())}</font></h2>')
            continue
        m_bullet = re.match(r"^\s*[-*]\s+(.*)", line)
        m_num = re.match(r"^\s*\d+\.\s+(.*)", line)
        if m_bullet or m_num:
            tag = "ul" if m_bullet else "ol"
            if list_tag != tag:
                close_list()
                out.append(f"<{tag}>")
                list_tag = tag
            out.append(f"<li>{_inline((m_bullet or m_num).group(1))}</li>")
            continue
        close_list()
        out.append(f"<p>{_inline(line.strip())}</p>")
    close_list()
    return title, "\n".join(out)


class _Doc(FPDF):
    def header(self):
        if LOGO.exists():
            self.image(str(LOGO), x=self.l_margin, y=10, h=10)
        self.set_xy(self.l_margin + 15, 11)
        self.set_font("Helvetica", "B", 15)
        self.set_text_color(*INK)
        self.cell(self.get_string_width("Always"), 8, "Always")
        self.set_text_color(*EMBER)
        self.cell(0, 8, "Home")
        self.set_draw_color(*EMBER)
        self.set_line_width(0.6)
        self.line(self.l_margin, 24, self.w - self.r_margin, 24)
        self.set_y(30)

    def footer(self):
        self.set_y(-14)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*GREY)
        self.cell(0, 6, "AlwaysHome - UCLA Anderson MSBA Vibathon 2026. Not insurance advice; costs and discounts are estimates.")
        self.cell(0, 6, f"Page {self.page_no()}/{{nb}}", align="R")


def report_pdf(markdown: str) -> bytes:
    title, body = markdown_to_html(markdown)
    pdf = _Doc(format="Letter")
    pdf.set_margins(18, 18, 18)
    pdf.set_auto_page_break(True, margin=20)
    pdf.alias_nb_pages()
    pdf.set_title(title)
    pdf.set_author("AlwaysHome")
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(*INK)
    pdf.multi_cell(0, 9, title, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*GREY)
    pdf.cell(0, 6, f"Prepared {date.today():%B %d, %Y}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    pdf.set_font("Helvetica", "", 10.5)
    pdf.set_text_color(*INK)
    pdf.write_html(body)
    return bytes(pdf.output())
