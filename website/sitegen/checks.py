"""Drift checks (spec section 7.6). Each returns a list of problems."""

from __future__ import annotations

import html
import re
from urllib.parse import urlsplit

from .site import Site

# Wording the site may not use (spec section 8.2).
BANNED = [
    r"\bprevent(s|ed|ing)?\b", r"\beliminat(e|es|ed|ing)\b", r"\bguarantee[sd]?\b",
    r"\bsandbox(es|ed|ing)?\b", r"\bconfinement\b", r"\bisolat(e|es|ed|ing)\b",
    r"formally verified", r"verified rust", r"provably safe",
    r"fewer mistakes", r"reduces bugs", r"safer code",
    r"production[- ]ready", r"battle[- ]tested", r"trusted by",
    r"\bsignificant(ly)?\b", r"\bproves\b",
    # No defect-reduction claim (docs/DISCIPLINE-PROPOSAL.md, section 6).
    r"\breduc(e|es|ed|ing) (escaped )?(defects|bugs)\b", r"\bfewer (escaped )?(defects|bugs)\b",
    # The site describes tauten, not one adopting project (owner, 2026-11-20).
    r"\bwritfold\b",
]

# Commands that are not released yet (`#[effects]`, `#[evidence]` and
# `#[derive(Cap)]` shipped in 0.0.4). A page that names one must
# also carry an "In progress" or "Planned" label.
UNRELEASED = ["cargo tauten ship", "verify --level", "effects.lock"]

# Exact sentences reproduced from core files that use those words in a
# negative sense. They are removed before the grep; nothing else is excused.
ALLOWED = [
    # docs/MAPPING.md
    'Not confinement: dependencies, unsafe, FFI, build scripts and unlisted crates keep ambient access. Claim "discipline", never "sandbox".',
    # docs/STATUS.md, Known gaps
    "The capability rule is discipline, not confinement (see MAPPING.md).",
    "Nothing here supports a claim that agents make fewer mistakes.",
    # docs/STATUS.md, milestone table (benchmark row)
    "nothing here supports a claim that the profile reduces escaped defects.",
    # crates/tauten/src/lib.rs
    "it does not sandbox anything.",
    # crates/tauten-check/rules.toml, TAU-U001
    "Every guarantee in this profile assumes safe Rust.",
]


def page_text(page: str) -> str:
    page = re.sub(r"<(script|style)\b.*?</\1>", " ", page, flags=re.S)
    page = re.sub(r"<head>.*?</head>", " ", page, flags=re.S)
    page = re.sub(r"<[^>]+>", "", page)
    return " ".join(html.unescape(page).split())


def rules_vs_markdown(site: Site) -> list[str]:
    toml = {(r["id"], r["title"]) for r in site.data.rules}
    mdset = set(site.data.rules_md_rows)
    out = []
    for item in sorted(toml - mdset):
        out.append(f"rules.toml has {item} but docs/RULES.md does not")
    for item in sorted(mdset - toml):
        out.append(f"docs/RULES.md has {item} but rules.toml does not")
    return out


def fixture_ids(site: Site) -> list[str]:
    ids = site.rule_ids
    return [f"fixture {f.name} expects unknown {x}" for f in site.data.fixtures for x in f.expect if x not in ids]


def captures(site: Site, allow_stale: bool) -> tuple[list[str], list[str]]:
    problems, warnings = [], []
    for cap in site.captures.values():
        core = cap.header.get("core", [""])[0]
        if core != site.ref:
            msg = f"capture {cap.name} was made at {core[:12]}, the site is pinned to {site.short}"
            (warnings if allow_stale else problems).append(msg)
        for block in cap.blocks():
            rule = site.data.rule_by_id.get(block["id"])
            if not block["id"].startswith("TAU-"):
                continue
            if rule is None:
                problems.append(f"capture {cap.name}: unknown rule {block['id']}")
                continue
            if block["rule"] != rule["title"]:
                problems.append(f"capture {cap.name}: {block['id']} rule title {block['rule']!r} differs from rules.toml")
            if block["fix"] != rule["fix"]:
                problems.append(f"capture {cap.name}: {block['id']} fix text differs from rules.toml")
    return problems, warnings


def rule_ids_in_html(site: Site) -> list[str]:
    ids = site.rule_ids
    out = []
    for path, page in site.pages.items():
        for found in sorted(set(re.findall(r"TAU-[A-Z]\d{3}", page_text(page))) - ids):
            out.append(f"{path} mentions {found}, which is not in rules.toml")
    return out


def wording(site: Site) -> list[str]:
    out = []
    has_runs = bool(site.results.get("runs"))
    for path, page in site.pages.items():
        text = page_text(page)
        for sentence in ALLOWED:
            text = text.replace(sentence, " ")
        for pattern in BANNED:
            for m in re.finditer(pattern, text, re.I):
                ctx = text[max(0, m.start() - 50):m.end() + 50]
                out.append(f"{path}: banned wording {m.group(0)!r} in “…{ctx}…”")
        for tag in re.findall(r'<span class="tag">(\w+)</span>', page):
            if tag == "Measured" and not has_runs:
                out.append(f"{path}: 'Measured' tag without a results.json run")
            elif tag == "Proved":
                out.append(f"{path}: 'Proved' tag without a named theorem in a proofs gate")
            elif tag not in ("Measured", "Observed", "Designed"):
                out.append(f"{path}: unknown claim tag {tag!r}")
    return out


def positioning(site: Site) -> list[str]:
    """The benchmark sentence is on /status/, and unreleased features carry a label."""
    from .common import MEASURED
    out = []
    status = page_text(site.pages.get("/status/", ""))
    if MEASURED not in status or "makes no defect-reduction claim" not in status:
        out.append("/status/ lacks the benchmark sentence and 'tauten makes no defect-reduction claim'")
    if "No defect-reduction claim" not in page_text(site.pages.get("/", "")):
        out.append("/ lacks 'No defect-reduction claim' in its status line")
    for path, page in site.pages.items():
        text = page_text(page)
        named = [u for u in UNRELEASED if u in text]
        if named and "Planned" not in text and "In progress" not in text and "planned" not in text:
            out.append(f"{path} names unreleased {named} without an In progress or Planned label")
    return out


def links(site: Site, files: set[str]) -> list[str]:
    """Internal links and anchors resolve; ids unique; nothing third-party is loaded."""
    out = []
    ids: dict[str, set[str]] = {}
    for path, page in site.pages.items():
        found = re.findall(r'\sid="([^"]+)"', page)
        dupes = {x for x in found if found.count(x) > 1}
        if dupes:
            out.append(f"{path}: duplicate ids {sorted(dupes)}")
        ids[path] = set(found)
    site_url = site.config["site_url"]
    for path, page in site.pages.items():
        refs = [(t.group(1), a, u, t.group(2)) for t in re.finditer(r"<(\w+)\b([^>]*)>", page)
                for a, u in re.findall(r'\s(href|src)="([^"]*)"', t.group(2))]
        for tag, attr, url, attrs in refs:
            url = html.unescape(url)
            if url.startswith("http:"):
                out.append(f"{path}: insecure URL {url}")
                continue
            parts = urlsplit(url)
            if url.startswith("https://docs.rs/") and f"/{site.config['latest_release']}/" not in url:
                out.append(f"{path}: docs.rs link {url} is not pinned to latest_release")
            if parts.scheme or url.startswith("//"):
                if tag == "a" or (tag == "link" and 'rel="canonical"' in attrs and url.startswith(site_url + "/")):
                    continue
                out.append(f"{path}: third-party {tag} {attr} {url}")
                continue
            target = parts.path
            if not target:
                target = path
            elif not target.startswith("/"):
                out.append(f"{path}: relative URL {url}; use root-relative links")
                continue
            if target in site.pages:
                key = target
            elif target.lstrip("/") in files:
                key = None
            else:
                out.append(f"{path}: broken link {url}")
                continue
            if parts.fragment and key is not None and parts.fragment not in ids[key]:
                out.append(f"{path}: missing anchor {url}")
    return out


def status_counts(site: Site) -> list[str]:
    """Numbers STATUS.md states that the build can compute. Reported, not fatal:
    the status page reproduces STATUS.md verbatim, so the owner fixes it upstream."""
    out = []
    rows = " ".join(r["item"] + " " + r["evidence"] for r in site.data.status_rows)
    m = re.search(r"(\d+) rules", rows)
    if m and int(m.group(1)) != len(site.data.rules):
        out.append(f"STATUS.md says {m.group(1)} rules; rules.toml has {len(site.data.rules)}")
    m = re.search(r"(\d+) reject \+ (\d+) accept", rows)
    rej, acc = site.fixture_counts()
    if m and (int(m.group(1)), int(m.group(2))) != (rej, acc):
        out.append(f"STATUS.md says {m.group(1)} reject + {m.group(2)} accept fixtures; fixtures/cases has {rej} + {acc}")
    return out
