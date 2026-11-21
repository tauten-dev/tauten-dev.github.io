"""/changelog/: CHANGELOG.md at the pinned commit, one section per release."""

from __future__ import annotations

import re

from . import md
from .errors import BuildError
from .render import esc
from .site import Site

SOURCE = "CHANGELOG.md"

# `## 0.1.0 (2026-11-21)`, or `## Unreleased` (with or without a date).
HEADING = re.compile(r"^## (?:(?P<ver>\d+\.\d+\.\d+)(?: \((?P<date>\d{4}-\d{2}-\d{2})\))?|(?P<unrel>Unreleased)\b.*)$", re.M)

# The site describes tauten, not an adopting project (README, Content rules).
# Clauses of CHANGELOG.md that name one are left out (each maps to the
# punctuation that replaces it), and the page says so. Any other mention of
# an adopting project fails the build.
OMIT = {
    "; `docs/LAYERS.md` writes writfold's crate graph as layers and states what layers cannot express (edge allowlists).": ".",
}
ADOPTERS = re.compile(r"\bwritfold\b", re.I)


def _version_key(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in v.split("."))


def releases(text: str, latest: str) -> list[dict]:
    """Split the changelog into releases, newest first, as the file orders them.

    A section is released when it has a version and a date and is not newer
    than `latest_release` in config.toml; anything else is labelled
    unreleased, never shown as shipped.
    """
    marks = list(HEADING.finditer(text))
    stray = [line for line in re.findall(r"^## .*$", text, re.M) if not HEADING.match(line)]
    if stray:
        raise BuildError(f"{SOURCE}: unrecognised release heading(s): {stray}")
    if not marks:
        raise BuildError(f"{SOURCE} has no release headings")
    out = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        ver, date = m.group("ver"), m.group("date")
        released = bool(ver and date and _version_key(ver) <= _version_key(latest))
        out.append({"version": ver, "date": date, "released": released,
                    "id": f"v{ver}" if ver else "unreleased", "body": text[m.end():end].strip("\n")})
    ids = [r["id"] for r in out]
    if len(set(ids)) != len(ids):
        raise BuildError(f"{SOURCE}: duplicate release headings")
    if latest not in {r["version"] for r in out if r["released"]}:
        raise BuildError(f"{SOURCE} has no dated section for latest_release {latest}")
    return out


def _omit(body: str) -> tuple[str, int]:
    flat = " ".join(body.split())
    omitted = 0
    for clause, replacement in OMIT.items():
        if clause in flat:
            # Re-flow only the paragraph that holds the sentence; Markdown does not care about line breaks.
            paras = body.split("\n\n")
            for j, para in enumerate(paras):
                joined = " ".join(para.split())
                if clause in joined:
                    paras[j] = joined.replace(clause, replacement)
                    omitted += 1
            body = "\n\n".join(paras)
    m = ADOPTERS.search(body)
    if m:
        ctx = " ".join(body[max(0, m.start() - 60):m.end() + 60].split())
        raise BuildError(f"{SOURCE} names an adopting project; add the sentence to OMIT in pages_changelog.py: …{ctx}…")
    return body, omitted


def changelog(site: Site) -> None:
    latest = site.config["latest_release"]
    repo = site.config["repository"]
    items = releases(site.data.core.blob(SOURCE), latest)
    index, sections, omitted = [], [], 0
    for r in items:
        rid = r["id"]
        label = r["version"] or "Unreleased"
        when = f'<time datetime="{r["date"]}">{r["date"]}</time>' if r["date"] else ""
        links = []
        if not r["released"]:
            links.append('<span class="chip">Unreleased</span>')
        elif site.repo_public:
            links.append(f'<a href="https://github.com/{repo}/releases/tag/v{r["version"]}">Release v{r["version"]}</a>')
        if r["released"] and r["version"] == latest and site.published:
            links.append(f'<a href="{site.docs_url}">docs.rs</a>')
        body, n = _omit(r["body"])
        omitted += n
        html = md.render(body, source_path=SOURCE, link=site.gh_url, shift=2, id_prefix=f"{rid}-",
                         table_label=f"Table in {label}")
        meta = " · ".join(x for x in (when, *links) if x)
        sections.append(f'<section class="release" id="{rid}" aria-labelledby="{rid}-h">'
                        f'<h2 id="{rid}-h"><a class="anchor" href="#{rid}">{esc(label)}</a></h2>'
                        f'<p class="release-meta small muted">{meta}</p>{html}</section>')
        tag = "" if r["released"] else ' <span class="chip">Unreleased</span>'
        index.append(f'<li><a href="#{rid}">{esc(label)}</a>{tag} {when}</li>')
    note = (f" {omitted} clause{'s' if omitted != 1 else ''} naming an adopting project "
            f"{'are' if omitted != 1 else 'is'} left out." if omitted else "")
    gh = site.src(SOURCE)
    body = f"""<div class="wrap page-head"><h1>Changelog</h1>
<p class="lede">What each release changed, from {gh} at <code>{site.short}</code>.</p></div>
<div class="wrap">
<nav aria-label="Releases"><ol class="releases">{"".join(index)}</ol></nav>
{"".join(sections)}
<p class="small muted">Reproduced from {gh} at <code>{site.short}</code>.{note}</p>
</div>"""
    site.add("/changelog/", "Changelog", f"What each tauten release changed, up to {latest}.", body)
