import os
import re
import uuid
from datetime import datetime
from pathlib import Path

from config import Config


class PDFTool:
    """Turn markdown into a PDF report and save it under db/reports."""

    name = "create_pdf_report"
    description = (
        "Create a PDF report from markdown and give the user a file they can open. "
        "Use this when the user asks for a report, a summary document, or a PDF."
    )

    def spec(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Report title."},
                        "markdown": {
                            "type": "string",
                            "description": "Full report body in markdown.",
                        },
                    },
                    "required": ["title", "markdown"],
                },
            },
        }

    def run(self, title: str, markdown: str) -> dict:
        title = (title or "Report").strip() or "Report"
        markdown = markdown or ""
        if not markdown.strip():
            return _fail("markdown is empty.")

        from fpdf import FPDF

        regular, bold = _font_files()
        filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.pdf"
        path = Config.REPORTS_DIR / filename

        pdf = FPDF(format="A4")
        pdf.set_auto_page_break(auto=True, margin=18)
        pdf.set_margins(18, 18, 18)
        pdf.add_font("DejaVu", "", str(regular))
        pdf.add_font("DejaVu", "B", str(bold))
        pdf.set_title(title)
        pdf.set_author("Jinance Agent")
        pdf.add_page()
        _write_markdown(pdf, title, markdown)
        path.write_bytes(bytes(pdf.output()))

        return {
            "content": f"PDF report saved as {filename}. The user can open it from the chat.",
            "images": [],
            "files": [filename],
        }


def _font_files() -> tuple[Path, Path]:
    try:
        import matplotlib

        root = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
        regular = root / "DejaVuSans.ttf"
        bold = root / "DejaVuSans-Bold.ttf"
        if regular.is_file() and bold.is_file():
            return regular, bold
    except Exception:
        pass
    windows = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    regular = windows / "arial.ttf"
    bold = windows / "arialbd.ttf"
    if regular.is_file() and bold.is_file():
        return regular, bold
    raise FileNotFoundError("No Unicode font found for PDF reports.")


def _write_markdown(pdf, title: str, markdown: str):
    pdf.set_font("DejaVu", "B", 18)
    pdf.multi_cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    lines = markdown.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if lines and re.match(r"^#\s+", lines[0]) and _plain(lines[0][1:]).strip().lower() == title.lower():
        lines = lines[1:]

    in_code = False
    code_lines: list[str] = []
    paragraph: list[str] = []

    def flush_paragraph():
        nonlocal paragraph
        if not paragraph:
            return
        pdf.set_font("DejaVu", "", 11)
        pdf.multi_cell(0, 6, _plain(" ".join(paragraph)), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)
        paragraph = []

    def flush_code():
        nonlocal code_lines
        if not code_lines:
            pdf.ln(1)
            return
        pdf.set_font("DejaVu", "", 10)
        pdf.set_fill_color(30, 32, 36)
        pdf.set_text_color(231, 232, 234)
        pdf.multi_cell(0, 5, "\n".join(code_lines), fill=True, new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)
        pdf.ln(2)
        code_lines = []

    for line in lines:
        if line.strip().startswith("```"):
            flush_paragraph()
            if in_code:
                flush_code()
                in_code = False
            else:
                in_code = True
            continue
        if in_code:
            code_lines.append(line)
            continue

        heading = re.match(r"^(#{1,3})\s+(.*)$", line)
        if heading:
            flush_paragraph()
            level = len(heading.group(1))
            size = {1: 16, 2: 13, 3: 12}[level]
            pdf.ln(1)
            pdf.set_font("DejaVu", "B", size)
            pdf.multi_cell(0, 8, _plain(heading.group(2)), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)
            continue

        bullet = re.match(r"^[-*]\s+(.*)$", line)
        number = re.match(r"^(\d+)\.\s+(.*)$", line)
        if bullet or number:
            flush_paragraph()
            pdf.set_font("DejaVu", "", 11)
            prefix = "• " if bullet else f"{number.group(1)}. "
            text = bullet.group(1) if bullet else number.group(2)
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(0, 6, prefix + _plain(text), new_x="LMARGIN", new_y="NEXT")
            continue

        if not line.strip():
            flush_paragraph()
            continue
        paragraph.append(line.strip())

    if in_code:
        flush_code()
    flush_paragraph()


def _plain(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    return text.strip()


def _fail(content: str) -> dict:
    return {"content": content, "images": [], "files": []}
