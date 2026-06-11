"""PACIFIC — PDF report generation."""

from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console

from pacific.config import load_config

console = Console()

# Unicode → ASCII-safe replacements for core PDF fonts
_UNICODE_SUBS = {
    "\u2022": "-",   # •
    "\u2013": "-",   # –
    "\u2014": "--",  # —
    "\u2018": "'",   # '
    "\u2019": "'",   # '
    "\u201c": '"',   # "
    "\u201d": '"',   # "
    "\u2026": "...", # …
    "\u2192": "->",  # →
    "\u2190": "<-",  # ←
    "\u2264": "<=",  # ≤
    "\u2265": ">=",  # ≥
    "\u2260": "!=",  # ≠
    "\u00d7": "x",   # ×
    "\u00f7": "/",   # ÷
    "\u221a": "sqrt",# √
    "\u03b1": "alpha",
    "\u03b2": "beta",
    "\u03b3": "gamma",
    "\u03b4": "delta",
    "\u03c3": "sigma",
    "\u03bc": "mu",
    "\u03c0": "pi",
    "\u03c1": "rho",
    "\u0394": "Delta",
    "\u03a3": "Sigma",
}


def _safe_text(text: str) -> str:
    """Replace unsupported Unicode chars with ASCII equivalents for core PDF fonts."""
    for orig, repl in _UNICODE_SUBS.items():
        text = text.replace(orig, repl)
    # Strip any remaining non-latin1 characters
    return text.encode("latin-1", errors="replace").decode("latin-1")


def export_to_pdf(
    title: str,
    content: str,
    filename: Optional[str] = None,
    include_header: bool = True,
) -> str:
    """Export markdown-like content to a styled PDF report.

    Args:
        title: Report title.
        content: Report body text (will be auto-wrapped).
        filename: Output filename. Auto-generated if None.
        include_header: Whether to include PACIFIC branding header.

    Returns:
        Path to saved PDF.
    """
    try:
        from fpdf import FPDF
    except ImportError:
        console.print("[red]Missing dependency: pip install fpdf2[/red]")
        return ""

    cfg = load_config()
    out_dir = Path(cfg.get("output_dir", "~/.pacific/outputs")).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)

    if not filename:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title = title.lower().replace(" ", "_")[:30]
        filename = f"pacific_{safe_title}_{ts}.pdf"

    filepath = out_dir / filename

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    # ── Header ──
    if include_header:
        pdf.set_fill_color(27, 79, 114)  # Dark blue
        pdf.rect(0, 0, 210, 30, "F")
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 18)
        pdf.set_xy(10, 8)
        pdf.cell(0, 10, "PACIFIC", ln=False)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_xy(10, 18)
        pdf.cell(0, 6, "Elite Financial Intelligence · Powered by GRRN")
        pdf.set_text_color(0, 0, 0)
        pdf.ln(25)

    # ── Title ──
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 12, _safe_text(title), ln=True)
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(128, 128, 128)
    pdf.cell(0, 6, f"Generated: {datetime.now().strftime('%B %d, %Y at %H:%M')}", ln=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(6)

    # ── Horizontal rule ──
    pdf.set_draw_color(200, 200, 200)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(6)

    # ── Body ──
    in_code_block = False
    for line in content.split("\n"):
        stripped = line.strip()
        safe = _safe_text(stripped)

        # Code block toggle
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            if in_code_block:
                pdf.ln(2)
                pdf.set_font("Courier", "", 9)
                pdf.set_fill_color(240, 240, 240)
            else:
                pdf.ln(2)
                pdf.set_font("Helvetica", "", 10)
            continue

        if in_code_block:
            pdf.cell(8)
            pdf.cell(0, 5, _safe_text(line.rstrip()), ln=True, fill=True)
            continue

        # Headings
        if safe.startswith("### "):
            pdf.set_font("Helvetica", "B", 11)
            pdf.cell(0, 7, safe[4:], ln=True)
            pdf.set_font("Helvetica", "", 10)
        elif safe.startswith("## "):
            pdf.ln(3)
            pdf.set_font("Helvetica", "B", 13)
            pdf.cell(0, 8, safe[3:], ln=True)
            pdf.set_font("Helvetica", "", 10)
        elif safe.startswith("# "):
            pdf.ln(4)
            pdf.set_font("Helvetica", "B", 15)
            pdf.cell(0, 10, safe[2:], ln=True)
            pdf.set_font("Helvetica", "", 10)
        elif stripped.startswith("- ") or stripped.startswith("* "):
            pdf.set_font("Helvetica", "", 10)
            pdf.cell(8)
            pdf.cell(0, 6, f"- {safe[2:]}", ln=True)
        elif stripped.startswith("**") and stripped.endswith("**"):
            pdf.set_font("Helvetica", "B", 10)
            pdf.multi_cell(0, 6, safe.strip("*").strip())
            pdf.set_font("Helvetica", "", 10)
        elif safe == "":
            pdf.ln(3)
        else:
            pdf.set_font("Helvetica", "", 10)
            pdf.multi_cell(0, 6, safe)

    # ── Footer ──
    pdf.set_y(-20)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 10, f"PACIFIC v1.0 | Confidential | Page {pdf.page_no()}", align="C")

    pdf.output(str(filepath))
    console.print(f"[green]✓ PDF saved:[/green] {filepath}")
    return str(filepath)


def analysis_to_pdf(
    ticker: str,
    analysis_text: str,
    filename: Optional[str] = None,
) -> str:
    """Save a Pacific analysis response as a PDF report."""
    return export_to_pdf(
        title=f"{ticker} — Financial Analysis",
        content=analysis_text,
        filename=filename,
    )
