"""Turn a small markdown subset into readable terminal text."""

import re


def render_cli(source: str) -> str:
    lines = (source or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    blocks = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.strip().startswith("```"):
            code = []
            index += 1
            while index < len(lines) and not lines[index].strip().startswith("```"):
                code.append(lines[index])
                index += 1
            if index < len(lines):
                index += 1
            blocks.append("\n".join("  " + row for row in code))
            continue
        if _table_at(lines, index):
            headers = _cells(lines[index])
            index += 2
            rows = []
            while index < len(lines) and _is_row(lines[index]):
                rows.append(_cells(lines[index]))
                index += 1
            blocks.append(_format_table(headers, rows))
            continue
        heading = re.match(r"^#{1,3}\s+(.*)$", line)
        if heading:
            blocks.append(_inline(heading.group(1).strip()))
            index += 1
            continue
        if re.match(r"^[-*]\s+", line) or re.match(r"^\d+\.\s+", line):
            items = []
            while index < len(lines):
                bullet = re.match(r"^[-*]\s+(.*)$", lines[index])
                number = re.match(r"^(\d+)\.\s+(.*)$", lines[index])
                if bullet:
                    items.append("• " + _inline(bullet.group(1).strip()))
                elif number:
                    items.append(f"{number.group(1)}. " + _inline(number.group(2).strip()))
                else:
                    break
                index += 1
            blocks.append("\n".join(items))
            continue
        if not line.strip():
            index += 1
            continue
        paragraph = []
        while index < len(lines) and lines[index].strip() and not _special(lines, index):
            paragraph.append(_inline(lines[index].strip()))
            index += 1
        blocks.append("\n".join(paragraph))
    return "\n\n".join(block for block in blocks if block.strip())


def _special(lines: list[str], index: int) -> bool:
    line = lines[index]
    return (
        line.strip().startswith("```")
        or _table_at(lines, index)
        or re.match(r"^#{1,3}\s+", line) is not None
        or re.match(r"^[-*]\s+", line) is not None
        or re.match(r"^\d+\.\s+", line) is not None
    )


def _table_at(lines: list[str], index: int) -> bool:
    return (
        index + 1 < len(lines)
        and _is_row(lines[index])
        and _is_divider(lines[index + 1])
    )


def _is_row(line: str) -> bool:
    text = line.strip()
    return text.startswith("|") and text.endswith("|") and text.count("|") >= 2


def _is_divider(line: str) -> bool:
    return re.match(r"^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$", line.strip()) is not None


def _cells(line: str) -> list[str]:
    text = line.strip()
    if text.startswith("|"):
        text = text[1:]
    if text.endswith("|"):
        text = text[:-1]
    return [_plain(cell.strip()) for cell in text.split("|")]


def _format_table(headers: list[str], rows: list[list[str]]) -> str:
    width = max([len(headers), *[len(row) for row in rows]] or [0])
    headers = headers + [""] * (width - len(headers))
    rows = [row + [""] * (width - len(row)) for row in rows]
    sizes = [
        max(len(headers[column]), *(len(row[column]) for row in rows)) if rows else len(headers[column])
        for column in range(width)
    ]

    def paint(row: list[str]) -> str:
        return "  ".join(cell.ljust(sizes[column]) for column, cell in enumerate(row)).rstrip()

    body = [paint(headers), paint(["-" * size for size in sizes])]
    body.extend(paint(row) for row in rows)
    return "\n".join(body)


def _plain(text: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r"\1 (\2)", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"(?<!\*)\*([^\s*](?:[^*]*[^\s*])?)\*(?!\*)", r"\1", text)
    return text


def _inline(text: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r"\1 (\2)", text)
    text = re.sub(r"\*\*([^*]+)\*\*", lambda match: "\033[1m" + match.group(1) + "\033[0m", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"(?<!\*)\*([^\s*](?:[^*]*[^\s*])?)\*(?!\*)", r"\1", text)
    return text
