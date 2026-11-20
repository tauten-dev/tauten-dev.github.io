"""Reference pages: the rules index and one page per rule."""

from __future__ import annotations

import re

from .render import copy_line, esc, inline_md, level_chip
from .site import Site, ref_layout
from .source import ENFORCERS, FAMILIES, TIERS, exceptions_label, level

EXC_TEXT = {"expect": "<code>#[expect]</code> + reason", "never": "never"}


def _family(rule_id: str) -> str:
    return rule_id[4]


def rules_index(site: Site) -> None:
    rules = site.data.rules
    n = len(rules)
    by = {k: site.count_by(k) for k in ("clippy", "rustc", "tauten", "convention")}
    never = len(site.no_exception_rules)
    conv = f", {by['convention']} by convention" if by["convention"] else ""
    counts = (f"{n} rules: {by['clippy']} decided by Clippy, {by['rustc']} by rustc, {by['tauten']} by a tauten "
              f"structural check{conv}. {never} admit no exception.")
    rows, attrs = [], []
    families = []
    current = None
    body_rows = []
    for r in rules:
        fam = _family(r["id"])
        if fam != current:
            current = fam
            families.append(fam)
            body_rows.append(f'<tr class="fam" data-fam="{fam}"><th colspan="8" scope="colgroup" id="family-{fam.lower()}">'
                             f'{fam} · {FAMILIES.get(fam, fam)}</th></tr>')
        exc = exceptions_label(r)
        lv = {t: level(r, t) for t in TIERS}
        cells = [f'<a class="id" href="/rules/{r["id"].lower()}/">{r["id"]}</a>', inline_md(r["title"]),
                 *(level_chip(lv[t]) for t in TIERS), "yes" if r.get("in_tests", True) else "no",
                 EXC_TEXT[exc], ENFORCERS[r["enforced_by"]]]
        data = "".join(f' data-{t}="{lv[t]}"' for t in TIERS)
        body_rows.append(f'<tr data-id="{r["id"]}" data-fam="{fam}" data-by="{r["enforced_by"]}" data-exc="{exc}"{data}>'
                         + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
    headers = ["ID", "Rule", "kernel", "core", "edge", "Tests", "Exceptions", "Decided by"]
    thead = "".join(f'<th scope="col">{h}</th>' for h in headers)
    tbl = (f'<div class="table-scroll" tabindex="0" role="region" aria-label="Rule table">'
           f'<table id="rules" class="sticky"><caption>Generated from <code>crates/tauten-check/rules.toml</code> at '
           f'<code>{site.short}</code>; the same columns as <code>docs/RULES.md</code>.</caption>'
           f'<thead><tr>{thead}</tr></thead><tbody>{"".join(body_rows)}</tbody></table></div>')
    notes_line = next(line for line in site.data.core.blob("docs/RULES.md").splitlines()
                      if line.startswith("In `kernel` crates no profile rule admits exceptions"))
    enforcer_opts = "".join(f'<option value="{k}">{ENFORCERS[k]}</option>' for k in ("clippy", "rustc", "tauten") if by[k])
    filters = f"""<form id="rule-filters" class="filters" hidden onsubmit="return false" aria-label="Filter rules">
<label>Search<input type="search" name="q" placeholder="ID, title or lint"></label>
<label>Applies in tier<select name="tier"><option value="">any</option><option>kernel</option><option>core</option><option>edge</option></select></label>
<label>Decided by<select name="by"><option value="">any</option>{enforcer_opts}</select></label>
<label class="cb"><input type="checkbox" name="nx"> No exceptions</label>
<span id="rule-count" class="muted" aria-live="polite"></span></form>"""
    body = f"""<div class="wrap page-head"><p class="eyebrow">Rule reference</p><h1>Rules</h1>
<p class="lede">{counts} Each rule has a stable ID; <code>cargo tauten explain &lt;ID&gt;</code> prints it in the terminal.</p></div>
{ref_layout(filters + tbl + f'<p class="small">{inline_md(notes_line)}</p>')}"""
    site.add("/rules/", "Rules", f"The {n} rules of the tauten profile, with level per tier, test scope, exceptions and what decides each.",
             body, scripts=("rules.js",))


def rule_pages(site: Site) -> None:
    rules = site.data.rules
    warnings_cap = site.captures["check-fixtures-warnings"]
    for i, r in enumerate(rules):
        rid = r["id"]
        exc = exceptions_label(r)
        parts = [f'<h2 id="why">Why</h2><p>{inline_md(r["why"])}</p>', f'<h2 id="fix">Fix</h2><p>{inline_md(r["fix"])}</p>']
        detail = []
        if r.get("lints"):
            detail.append(f'<p><strong>Lints:</strong> {", ".join(f"<code>{esc(x)}</code>" for x in r["lints"])}</p>')
        for api in (a for a in site.data.apis if a["rule"] == rid):
            items = ", ".join(f"<code>{esc(p)}</code>" for p in api["paths"])
            head = f'Banned in {", ".join(api["tiers"])} ({esc(api["note"])}), {len(api["paths"])} {api["kind"]}{"s" if len(api["paths"]) != 1 else ""}'
            if len(api["paths"]) > 12:
                detail.append(f"<details><summary>{head}</summary><p>{items}</p></details>")
            else:
                detail.append(f"<p><strong>{head}:</strong> {items}</p>")
        if detail:
            parts.append('<h2 id="what">What it checks</h2>' + "".join(detail))
        seen = [f for f in site.data.fixtures if rid in f.expect]
        if seen:
            figs = []
            for f in seen:
                blocks = [b for b in warnings_cap.blocks() if b["id"] == rid and b["crate"] == f.name]
                if not blocks:
                    continue
                marks = {b["line"]: b["column"] for b in blocks if b["line"]}
                text = "\n\n".join(b["text"] for b in blocks)
                figs.append(f'<figure class="ex">{site.fixture_panel(f, marks=marks)}'
                            f'{site.capture_panel("check-fixtures-warnings", text, title="$ cargo tauten check", label=f"Output for {f.name}")}'
                            f'<figcaption>Fixture <code>{f.name}</code> ({f.tier or "no tier"}) expects '
                            f'{", ".join(f.expect)}. Output captured at <code>{site.short}</code>.</figcaption></figure>')
            parts.append('<h2 id="fixtures">Seen in fixtures</h2>' + "".join(figs))
        explain = site.captures.get(f"explain-rule-{rid.lower()}")
        shown = site.capture_panel(explain.name, label=f"cargo tauten explain {rid}") if explain else ""
        parts.append(f'<h2 id="explain">In the terminal</h2>{copy_line(f"cargo tauten explain {rid}")}{shown}')
        prev = rules[i - 1] if i else None
        nxt = rules[i + 1] if i + 1 < len(rules) else None
        pn = '<nav class="pn" aria-label="Previous and next rule">'
        pn += f'<a href="/rules/{prev["id"].lower()}/">← {prev["id"]}</a>' if prev else "<span></span>"
        pn += f'<a href="/rules/{nxt["id"].lower()}/">{nxt["id"]} →</a>' if nxt else "<span></span>"
        pn += "</nav>"
        levels = " ".join(f'<span class="small muted">{t}</span> {level_chip(level(r, t))}' for t in TIERS)
        head = f"""<p class="eyebrow"><a href="/rules/">Rules</a> / <span class="id">{rid}</span></p>
<h1 id="{rid}">{inline_md(r["title"])}</h1>
<div class="facts"><span class="chip">decided by {ENFORCERS[r["enforced_by"]]}</span> {levels}</div>
<div class="facts small"><span>Applies to tests: <strong>{"yes" if r.get("in_tests", True) else "no"}</strong></span>
<span>Exceptions: <strong>{EXC_TEXT[exc]}</strong></span></div>"""
        body = f'<div class="wrap page-head"></div>{ref_layout(head + "".join(parts) + pn)}'
        site.add(f"/rules/{rid.lower()}/", f"{rid}: {re.sub(r'`', '', r['title'])}",
                 f"{rid}: {r['title']}. {r['why']}", body)
