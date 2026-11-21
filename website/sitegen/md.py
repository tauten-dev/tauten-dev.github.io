"""Markdown from the core repository, rendered without changing its words."""

from __future__ import annotations

import html
import re

import markdown

from .render import code_html, panel

# Core documents that have a page of their own on the site.
SITE_PAGES = {
    "docs/MAPPING.md": "/enforcement/",
    "docs/STATUS.md": "/status/",
    "docs/RULES.md": "/rules/",
    "CHANGELOG.md": "/changelog/",
    "bench/README.md": "/benchmark/",
    "bench/PREREGISTRATION.md": "/benchmark/#preregistration",
    "crates/tauten-check/agents.md": "/agents/",
}


def slug(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text).lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "section"


def section(text: str, heading: str, level: int = 2) -> str:
    """The body under `## heading` (exact), up to the next heading of that level or higher."""
    marks = "#" * level
    m = re.search(rf"^{marks} {re.escape(heading)}\n(.*?)(?=^#{{1,{level}}} |\Z)", text, re.M | re.S)
    if not m:
        raise LookupError(heading)
    return m.group(1).strip("\n")


def render(text: str, *, source_path: str, link, shift: int = 1, id_prefix: str = "",
           table_label: str = "Table", table_cls: str = "", sticky: bool = False) -> str:
    """Render Markdown. `link(path) -> str | None` maps a repository path to a URL.

    Relative links are resolved against `source_path`; when `link` returns
    None the link text is kept and the anchor dropped. Headings move down by
    `shift` levels and get ids; tables get a scroll wrapper; fenced code gets
    the site's panels and build-time highlighting.
    """
    out = markdown.markdown(text, extensions=["tables", "fenced_code"], output_format="html")
    base = source_path.rsplit("/", 1)[0] if "/" in source_path else ""

    def fix_link(m: re.Match) -> str:
        href, body = html.unescape(m.group(1)), m.group(2)
        if re.match(r"[a-z]+:", href) or href.startswith("#"):
            return m.group(0)
        path, _, frag = href.partition("#")
        parts = (base + "/" + path).strip("/").split("/") if base else path.split("/")
        norm: list[str] = []
        for p in parts:
            if p == "..":
                norm.pop()
            elif p and p != ".":
                norm.append(p)
        repo_path = "/".join(norm)
        if repo_path in SITE_PAGES:
            return f'<a href="{SITE_PAGES[repo_path]}">{body}</a>'
        url = link(repo_path)
        if url is None:
            return body
        return f'<a href="{html.escape(url)}">{body}</a>'

    out = re.sub(r'<a href="([^"]+)">(.*?)</a>', fix_link, out, flags=re.S)

    def heading(m: re.Match) -> str:
        level = min(int(m.group(1)) + shift, 6)
        inner = m.group(2)
        return f'<h{level} id="{id_prefix}{slug(inner)}">{inner}</h{level}>'

    out = re.sub(r"<h([1-6])>(.*?)</h\1>", heading, out, flags=re.S)

    def code(m: re.Match) -> str:
        lang = m.group(1) or "text"
        raw = html.unescape(m.group(2))
        if raw.endswith("\n"):
            raw = raw[:-1]
        return panel(code_html(raw, lang), label=f"{lang} example", wrapped=lang in ("text", "console"))

    out = re.sub(r'<pre><code(?: class="language-([\w-]+)")?>(.*?)</code></pre>', code, out, flags=re.S)
    cls = f' class="{" ".join(x for x in (table_cls, "sticky" if sticky else "") if x)}"' if (table_cls or sticky) else ""
    out = out.replace("<table>", f'<div class="table-scroll" tabindex="0" role="region" aria-label="{html.escape(table_label)}"><table{cls}>')
    out = out.replace("</table>", "</table></div>")
    out = out.replace("<th>", '<th scope="col">').replace('<th style=', '<th scope="col" style=')
    return out
