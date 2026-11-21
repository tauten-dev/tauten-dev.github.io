"""Shared context and the page shell."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from .render import code_html, diag_html, esc, panel
from .source import Capture, Data, exceptions_label

NAV = [("Start", "/start/"), ("Proofs", "/proofs/"), ("Rules", "/rules/"), ("Status", "/status/")]


@dataclass
class Site:
    root: Path
    config: dict
    data: Data
    captures: dict[str, Capture]
    snippets: dict[str, dict]
    status_map: dict[str, dict]
    results: dict
    built_at: str
    pages: dict[str, str] = field(default_factory=dict)
    redirects: dict[str, str] = field(default_factory=dict)
    extra_files: dict[str, bytes] = field(default_factory=dict)

    # ------------------------------------------------------------ facts ---
    @property
    def ref(self) -> str:
        return self.data.core.ref

    @property
    def short(self) -> str:
        return self.data.core.short

    @property
    def published(self) -> bool:
        return bool(self.config["published"])

    @property
    def repo_public(self) -> bool:
        return bool(self.config["repo_public"])

    @property
    def docs_url(self) -> str:
        """The versioned docs.rs page of the `tauten` library crate."""
        return f"https://docs.rs/tauten/{self.config['latest_release']}/tauten/"

    @property
    def rule_ids(self) -> set[str]:
        return set(self.data.rule_by_id)

    def count_by(self, enforcer: str) -> int:
        return sum(1 for r in self.data.rules if r["enforced_by"] == enforcer)

    @property
    def no_exception_rules(self) -> list[dict]:
        return [r for r in self.data.rules if exceptions_label(r) == "never"]

    def fixture_counts(self) -> tuple[int, int]:
        rej = sum(1 for f in self.data.fixtures if f.kind == "reject")
        return rej, len(self.data.fixtures) - rej

    # ----------------------------------------------------------- links ----
    def gh_url(self, path: str, line: int | None = None) -> str | None:
        """A link into the core repository at the pinned commit, once it is public."""
        if not self.repo_public:
            return None
        anchor = f"#L{line}" if line else ""
        return f"https://github.com/{self.config['repository']}/blob/{self.ref}/{path}{anchor}"

    def src(self, path: str, text: str | None = None, line: int | None = None) -> str:
        """A repository path shown in mono, linked when the repository is public."""
        label = f"<code>{esc(text or path)}</code>"
        url = self.gh_url(path, line)
        return f'<a href="{esc(url)}">{label}</a>' if url else label

    # ------------------------------------------------------- components ---
    def snippet_panel(self, *names: str, title: str | None = None, tier: str | None = None,
                      marks: dict | None = None, label: str | None = None, tail: str | None = None) -> str:
        """Excerpts from snippets.toml, numbered with their real line numbers; `tail` is a muted last line."""
        snips = [self.snippets[n] for n in names]
        lang = snips[0]["lang"]
        parts = []
        for i, s in enumerate(snips):
            if i:
                parts.append('<span class="line elide">…</span>')
            parts.append(code_html(s["code"], lang, numbers=True, marks=marks, first_line=s["first_line"]))
        if tail:
            parts.append(f'<span class="line elide">{esc(tail)}</span>')
        path = snips[0]["path"]
        return panel("".join(parts), caption=self.src(path, title), label=label or f"Code from {path}", tier=tier)

    def capture_panel(self, name: str, text: str | None = None, *, title: str | None = None,
                      label: str | None = None) -> str:
        cap = self.captures[name]
        body = cap.body.rstrip("\n") if text is None else text
        return panel(diag_html(body, self.rule_ids), caption=esc(title or f"$ {cap.cmd}"),
                     label=label or f"Output of {cap.cmd}", diag=True)

    def fixture_panel(self, fixture, *, marks: dict[int, int] | None = None) -> str:
        return panel(code_html(fixture.src, "rust", numbers=bool(marks), marks=marks),
                     caption=self.src(fixture.src_path, fixture.src_path.removeprefix("fixtures/cases/")),
                     label=f"Source of fixture {fixture.name}", tier=fixture.tier)

    # ------------------------------------------------------------ shell ---
    def asset_version(self) -> str:
        h = hashlib.sha1()
        for name in ("site.css", "theme.js", "copy.js", "rules.js"):
            h.update((self.root / "website" / "assets" / name).read_bytes())
        return h.hexdigest()[:8]

    def add(self, path: str, title: str, description: str, body: str, *, scripts: tuple[str, ...] = (),
            full_title: bool = False) -> None:
        self.pages[path] = self.shell(path, title, description, body, scripts=scripts, full_title=full_title)

    def redirect(self, path: str, target: str, what: str) -> None:
        """A page that has moved: a meta refresh plus a visible link. Not in the sitemap."""
        external = target.startswith("https:")
        url = target if external else self.config["site_url"] + target
        canonical = "" if external else f'<link rel="canonical" href="{esc(url)}">\n'
        self.redirects[path] = target
        self.pages[path] = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Moved · tauten</title>
<meta name="robots" content="noindex">
{canonical}<meta http-equiv="refresh" content="0; url={esc(target)}">
</head>
<body>
<main id="main"><p>{esc(what)} moved to <a href="{esc(target)}">{esc(url)}</a>.</p></main>
</body>
</html>
"""

    def shell(self, path: str, title: str, description: str, body: str, *, scripts=(), full_title=False) -> str:
        v = self.asset_version()
        site = self.config["site_url"]
        page_title = title if full_title else f"{title} · tauten"
        canonical = site + path
        nav = []
        for label, href in NAV:
            current = ' aria-current="page"' if path.startswith(href) else ""
            nav.append(f'<li><a href="{href}"{current}>{label}</a></li>')
        gh = f"https://github.com/{self.config['repository']}"
        if self.repo_public:
            nav.append(f'<li><a href="{gh}">GitHub</a></li>')
        footer = ["<li>MIT</li>", '<li><a href="/changelog/">Changelog</a></li>']
        if self.repo_public:
            footer.append(f'<li><a href="{gh}">GitHub</a></li>')
            footer.append(f'<li><a href="{gh}/issues/new/choose">Feedback</a></li>')
        if self.published:
            footer.append('<li><a href="https://crates.io/crates/cargo-tauten">crates.io</a></li>')
            footer.append(f'<li><a href="{self.docs_url}">docs.rs</a></li>')
        built = f"<code>{self.short}</code>"
        if self.repo_public:
            built = f'<a href="{gh}/tree/{self.ref}">{built}</a>'
        footer.append(f"<li>built from tauten@{built}</li>")
        footer.append('<li><label class="theme" hidden>Theme <select id="theme-select"><option value="system">System</option>'
                      '<option value="light">Paper</option><option value="dark">Paper dark</option></select></label></li>')
        script_tags = "".join(f'<script src="/assets/{s}?v={v}" defer></script>' for s in ("copy.js", *scripts))
        d = esc(description)
        t = esc(page_title)
        return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{t}</title>
<meta name="description" content="{d}">
<link rel="canonical" href="{canonical}">
<meta property="og:title" content="{t}">
<meta property="og:type" content="website">
<meta property="og:url" content="{canonical}">
<meta property="og:description" content="{d}">
<meta property="og:image" content="{site}/assets/og.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="The tauten mark and the headline: A discipline for Rust, with proofs over the shipped code.">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" media="(prefers-color-scheme: light)" content="#F8F8F3">
<meta name="theme-color" media="(prefers-color-scheme: dark)" content="#151D19">
<link rel="icon" href="/assets/favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="/assets/site.css?v={v}">
<script src="/assets/theme.js?v={v}"></script>
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="site-header"><div class="wrap bar">
<a class="brand" href="/"><img class="logo-light" src="/assets/tauten-icon.svg" width="24" height="24" alt=""><img class="logo-dark" src="/assets/tauten-icon-dark.svg" width="24" height="24" alt="">tauten</a>
<nav class="site-nav" aria-label="Primary"><ul>{"".join(nav)}</ul></nav>
</div></header>
<main id="main">
{body}
</main>
<footer class="site-footer"><div class="wrap"><ul>{"".join(footer)}</ul></div></footer>
{script_tags}
</body>
</html>
"""


def ref_layout(body: str) -> str:
    """Reference pages use the same single column as every other page."""
    return f'<div class="wrap">{body}</div>'
