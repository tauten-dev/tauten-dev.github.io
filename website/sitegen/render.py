"""HTML components: code and diagnostic panels, chips, badges, tables."""

from __future__ import annotations

import html
import re

from pygments.lexers import get_lexer_by_name
from pygments.token import STANDARD_TYPES

esc = html.escape

LEXERS = {"lean": "lean4", "rust": "rust", "toml": "toml", "json": "json", "console": "console", "text": "text", "yaml": "yaml"}


def _cls(ttype) -> str:
    while ttype not in STANDARD_TYPES:
        ttype = ttype.parent
    short = STANDARD_TYPES[ttype]
    return f"t-{short}" if short else ""


def lex_lines(code: str, lang: str) -> list[list[tuple[str, str]]]:
    """Tokens split per line, so lines can be numbered and marked."""
    lexer = get_lexer_by_name(LEXERS.get(lang, "text"), stripnl=False, ensurenl=False)
    lines: list[list[tuple[str, str]]] = [[]]
    for ttype, value in lexer.get_tokens(code):
        parts = value.split("\n")
        for i, part in enumerate(parts):
            if i:
                lines.append([])
            if part:
                lines[-1].append((_cls(ttype), part))
    if lines and not lines[-1] and code.endswith("\n"):
        lines.pop()
    return lines


def _tokens_html(tokens: list[tuple[str, str]], squiggle_from: int | None = None) -> str:
    """Render tokens; wrap columns >= squiggle_from (1-based) to end of line, trailing space excluded."""
    text = "".join(t for _, t in tokens)
    if squiggle_from is not None:
        end = len(text.rstrip())
        start = squiggle_from - 1
    out, pos = [], 0
    opened = False
    for cls, value in tokens:
        pieces = [(pos, value)]
        if squiggle_from is not None:
            cuts = sorted({c for c in (start, end) if pos < c < pos + len(value)})
            pieces, offset = [], pos
            for cut in cuts + [pos + len(value)]:
                pieces.append((offset, value[offset - pos:cut - pos]))
                offset = cut
        for at, piece in pieces:
            if squiggle_from is not None:
                if at == start and not opened:
                    out.append('<span class="squiggle">')
                    opened = True
                if at == end and opened:
                    out.append("</span>")
                    opened = False
            out.append(f'<span class="{cls}">{esc(piece)}</span>' if cls else esc(piece))
        pos += len(value)
    if opened:
        out.append("</span>")
    return "".join(out)


def code_html(code: str, lang: str, *, numbers: bool = False, marks: dict[int, int] | None = None,
              first_line: int = 1) -> str:
    marks = marks or {}
    rows = []
    for index, tokens in enumerate(lex_lines(code, lang)):
        number = first_line + index
        mark = marks.get(number)
        gutter = f'<span class="ln" aria-hidden="true">{number}</span>' if numbers else ""
        body = _tokens_html(tokens, mark) if tokens else " "
        cls = "line hl" if mark is not None else "line"
        rows.append(f'<span class="{cls}">{gutter}{body}</span>')
    return "".join(rows)


SEV = {"error": "err", "warning": "warn", "subsumed": "sub"}


def diag_html(text: str, rule_ids: set[str]) -> str:
    """Captured CLI text with colour and links; nothing is reworded."""
    rows = []
    for line in text.split("\n"):
        e = esc(line)
        hang = 0
        m = re.match(r"(error|warning|subsumed)(\[([^\]]+)\])?(:.*)$", line)
        if m:
            sev, ident = m.group(1), m.group(3)
            label = f'<span class="d-{SEV[sev]}">{sev}</span>'
            if ident:
                inner = esc(ident)
                if ident in rule_ids:
                    inner = f'<a href="/rules/{ident.lower()}/">{inner}</a>'
                label += f"[{inner}]"
            e = label + esc(m.group(4))
            hang = len(line.split(":", 1)[0]) + 2
        elif re.match(r"\s+--> ", line):
            pre = line.index("-->")
            e = esc(line[:pre]) + '<span class="d-mut">--&gt;</span>' + esc(line[pre + 3:])
            hang = pre + 4
        elif re.match(r"\s+= subsumed by proof ", line):
            pre = line.index("=")
            e = esc(line[:pre]) + '<span class="d-mut">=</span> <span class="d-lab">subsumed by proof</span>' + esc(line[pre + 19:])
            hang = pre + 2
        elif re.match(r"\s+= (rule|fix|note|help): ", line):
            pre = line.index("=")
            lab = re.match(r"\s+= (\w+):", line).group(1)
            rest = line[pre + 2 + len(lab) + 1:]
            e = esc(line[:pre]) + f'<span class="d-mut">=</span> <span class="d-lab">{lab}:</span>' + esc(rest)
            hang = pre + 2 + len(lab) + 2
        elif re.match(r"\s*(\d+\s*)?\|", line):
            e = f'<span class="d-mut">{e}</span>'
        style = f' style="padding-left:{hang}ch;text-indent:-{hang}ch"' if hang else ""
        rows.append(f'<span class="line"{style}>{e or " "}</span>')
    return "".join(rows)


def chip_tier(tier: str | None) -> str:
    if not tier:
        return '<span class="chip">untiered</span>'
    return f'<span class="chip chip-tier {tier[0]}">{esc(tier)}</span>'


GLYPHS = {"specified": "○", "implemented": "◐", "exercised": "●"}


def badge(kind: str, label: str) -> str:
    glyph = GLYPHS.get(kind)
    g = f'<span class="g" aria-hidden="true">{glyph}</span>' if glyph else ""
    return f'<span class="badge b-{kind}">{g}{esc(label)}</span>'


def level_chip(value: str) -> str:
    if value == "-":
        return '<span class="chip lvl lvl-none" aria-label="not applied">–</span>'
    return f'<span class="chip lvl lvl-{value}">{value}</span>'


def copy_line(command: str, label: str | None = None) -> str:
    return (f'<div class="copy-line"><span class="prompt" aria-hidden="true">$</span>'
            f'<code>{esc(command)}</code>'
            f'<button class="copy-btn" type="button" hidden data-copy="{esc(command)}"'
            f' aria-label="Copy command: {esc(label or command)}">Copy</button></div>')


def panel(inner: str, *, label: str, caption: str | None = None, tier: str | None = None,
          diag: bool = False, wrapped: bool = False) -> str:
    """A code or output panel: an optional caption line above (path and tier chip), then the block."""
    cap = ""
    if caption is not None or tier:
        chip = f" {chip_tier(tier)}" if tier else ""
        cap = f'<p class="cap">{caption or ""}{chip}</p>'
    classes = "panel" + (" diag" if diag else "") + (" wrapped" if wrapped else "")
    pre_cls = "diag-body" if diag else "code"
    return (f'{cap}<div class="{classes}"><pre class="{pre_cls}" tabindex="0" aria-label="{esc(label)}">'
            f'<code>{inner}</code></pre></div>')


def table(headers: list[str], rows: list[list[str]], *, caption: str | None = None, label: str,
          cls: str = "", sticky: bool = False, row_attrs: list[str] | None = None) -> str:
    cap = f"<caption>{caption}</caption>" if caption else ""
    head = "".join(f'<th scope="col">{h}</th>' for h in headers)
    body = []
    for i, row in enumerate(rows):
        attrs = row_attrs[i] if row_attrs else ""
        cells = "".join(f"<td>{c}</td>" for c in row)
        body.append(f"<tr{attrs}>{cells}</tr>")
    classes = " ".join(x for x in (cls, "sticky" if sticky else "") if x)
    return (f'<div class="table-scroll" tabindex="0" role="region" aria-label="{esc(label)}">'
            f'<table class="{classes}">{cap}<thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>')


def inline_md(text: str) -> str:
    """Backticks and bold only, for short strings taken from TOML or tables."""
    out = esc(text, quote=False)
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out)
    return out
