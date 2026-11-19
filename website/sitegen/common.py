"""Components shared by several pages."""

from __future__ import annotations

import re
import tomllib

from .errors import BuildError
from .render import badge, code_html, copy_line, esc, inline_md, panel, status_badge, table
from .site import Site

METRICS = [
    ("escaped_defect", "Escaped-defect rate", True),
    ("panic", "Reachable-panic rate", False),
    ("visible_ok", "Visible tests pass", False),
    ("tamper", "Test tampering", False),
    ("stubs", "Stubs added", False),
    ("tauten_errors", "Profile errors in the final repo", False),
    ("seconds", "Agent wall time (s)", False),
]
MINUS = "−"


def status_line(site: Site) -> str:
    """The one honest status sentence the home and status pages share."""
    registry = (f'Version {site.config["latest_release"]} is on <a href="https://crates.io/crates/cargo-tauten">crates.io</a>.'
                if site.published else "Not on crates.io yet.")
    return (f'{registry} No defect-reduction benefit established '
            f'(<a href="/benchmark/">benchmark</a>).')


def crate_prose(site: Site) -> dict:
    return tomllib.loads((site.root / "website" / "pages" / "crates.toml").read_text())


def tier_meanings(site: Site) -> dict[str, tuple[str, str]]:
    """Meaning and rejected examples per tier, from the README table."""
    rows = re.findall(r"^\| `(kernel|core|edge)` \| (.+?) \| (.+?) \|$", site.data.core.blob("README.md"), re.M)
    if len(rows) != 3:
        raise BuildError("README tier table not found")
    return {t: (m, r) for t, m, r in rows}


def tiers_figure(site: Site) -> str:
    """Three accept fixtures side by side, one per tier (moved from the home page)."""
    meanings = tier_meanings(site)
    excerpts = {
        "edge": site.snippet_panel("edge-main", tier="edge", compact=True, title="acc-edge/src/main.rs"),
        "core": site.snippet_panel("core-load", "core-stamp", tier="core", compact=True, title="acc-core/src/lib.rs"),
        "kernel": site.snippet_panel("kernel-head", "kernel-withdraw", tier="kernel", compact=True, title="acc-kernel/src/lib.rs"),
    }
    cols = []
    for i, tier in enumerate(("edge", "core", "kernel")):
        meaning, rejected = meanings[tier]
        if i:
            cols.append('<div class="arrow" aria-hidden="true">depends on</div>')
        cols.append(f'<div class="tcol tier-{tier}"><h3><span class="chip chip-tier {tier[0]}">{tier}</span></h3>'
                    f'<dl><dt>Meaning</dt><dd>{inline_md(meaning)}</dd><dt>Examples of what is rejected</dt>'
                    f'<dd>{inline_md(rejected)}</dd></dl>{excerpts[tier]}</div>')
    return (f'<figure><div class="tiers">{"".join(cols)}</div>'
            f'<figcaption>Three accept fixtures. <code>cargo tauten check</code> reports no profile errors for them. '
            f'The Meaning and Rejected cells are from the tauten README.</figcaption></figure>'
            f'<p class="boundary">Dependencies point inward only: edge → core → kernel (<a href="/rules/tau-t002/">TAU-T002</a>).</p>')


def version_label(site: Site, crate: dict) -> str:
    return crate["version"] if site.published else f'{crate["version"]} (unpublished)'


def registry_links(site: Site, name: str) -> str:
    """crates.io and docs.rs links, once the crates are published."""
    if not site.published:
        return ""
    return (f'<a href="https://crates.io/crates/{name}">crates.io</a>'
            f'<a href="https://docs.rs/{name}">docs.rs</a>')


def crate_cards(site: Site, compact: bool = False) -> str:
    prose = crate_prose(site)
    cards = []
    for name, c in site.data.crates.items():
        item = site.status_map[name]
        top = f'<div class="top"><span class="chip chip-tier {c["tier"][0]}">{c["tier"]}</span>{status_badge(item)}</div>'
        title = f'<h3><a class="id" href="/crates/{name}/">{name}</a></h3>'
        if compact:
            cards.append(f'<div class="card tier-{c["tier"]}">{title}{top}<p>{esc(c["description"])}</p></div>')
            continue
        foot = (f'<div class="foot"><span>{esc(version_label(site, c))}</span><span>rust-version {c["rust_version"]}</span>'
                f'<span>{c["license"]}</span>{registry_links(site, name)}<a href="/crates/{name}/">Crate page →</a></div>')
        cards.append(f'<div class="card tier-{c["tier"]}">{title}{top}<p>{esc(c["description"])}</p>'
                     f'<p class="small"><strong>Use it for:</strong> {inline_md(prose[name]["use_for"])}</p>{foot}</div>')
    sm = site.status_map
    planned = [
        f'<div class="card planned"><h3><a href="/proofs/">Proof tier</a></h3><div class="top">{status_badge(sm["proof-tier"])}</div>'
        f'<p>Charon/Aeneas → Lean for kernel crates. Planned (M3); nothing of it exists yet.</p></div>',
        f'<div class="card planned"><h3><a href="/benchmark/">Benchmark</a></h3><div class="top">{status_badge(sm["bench-harness"])} '
        f'{badge("pending", "Pilot only")}</div><p>Does working under the profile reduce the defects that escape an agent\'s "done"? A dev-split pilot has run; held-out tasks are being written.</p></div>',
    ]
    return f'<div class="grid-2">{"".join(cards)}</div><div class="grid-2" style="margin-top:24px">{"".join(planned)}</div>'


def install_block(site: Site) -> str:
    rv = site.data.workspace["workspace"]["package"]["rust-version"]
    cmd = copy_line("cargo install --locked cargo-tauten")
    if site.published:
        return f"{cmd}<p class=\"small muted\">Needs Rust {rv} or newer, with clippy.</p>"
    first = site.config["first_release"]
    return (f'<p><span class="chip">Not published yet</span></p>{cmd}'
            f'<p class="small muted">Available from the first release ({first}). Nothing is on crates.io yet, '
            f'so this command does not work today. It will need Rust {rv} or newer, with clippy.</p>')


def evidence_table(site: Site, keys: list[str]) -> str:
    rows = []
    for key in keys:
        item = site.status_map[key]
        rows.append([f'{item["milestone"]}', inline_md(item["item"]), status_badge(item), inline_md(item["evidence"]) or "–"])
    return table(["#", "Item", "State", "Evidence"], rows, label="Status rows",
                 caption=f'Reproduced from <code>docs/STATUS.md</code> at <code>{site.short}</code>; the badge is derived from the State cell.')


def scratch_panel(site: Site, rel: str, title: str) -> str:
    text = (site.root / "website" / "scratch" / rel).read_text()
    return panel(code_html(text.rstrip("\n"), "rust" if rel.endswith(".rs") else "toml"), title=esc(title),
                 label=f"Capture workspace file {title}", tier="core", provenance="Capture input")


def ratchet_html(site: Site) -> str:
    steps = [
        ("One existing violation, recorded.", "ratchet/crates/parse/step1.rs", "ratchet-1-baseline"),
        ("A new <code>unwrap</code> is an error; the baseline still accepts the old one.", "ratchet/crates/parse/step2.rs", "ratchet-2-check"),
        ("Recording the new finding is refused without <code>--allow-increase</code>.", None, "ratchet-3-refused"),
        ("Both fixed: the unused slot is reported (TAU-R001) until the baseline is tightened.", "ratchet/crates/parse/step3.rs", "ratchet-4-stale"),
    ]
    out = []
    for i, (text, src, cap) in enumerate(steps, 1):
        left = scratch_panel(site, src, "crates/parse/src/lib.rs") if src else ""
        out.append(f'<h3 class="small">{i}. {text}</h3><div class="pair">{left}{site.capture_panel(cap)}</div>')
    return ('<div class="ratchet">' + "".join(out) + '</div><p class="small muted">Captured on a one-crate scratch '
            f'workspace (<code>website/scratch/ratchet</code> in the site repository) with <code>cargo-tauten</code> built at <code>{site.short}</code>.</p>')


# ------------------------------------------------------------------ results ---

def _fmt(v) -> str:
    if isinstance(v, float):
        s = f"{v:.2f}"
    else:
        s = str(v)
    return s.replace("-", MINUS)


def _interval(diff: dict) -> str:
    lo, hi, pt = diff["ci_low"], diff["ci_high"], diff["point"]
    a, b = min(lo, 0.0), max(hi, 0.0)
    pad = (b - a) * 0.1 or 0.1
    a, b = a - pad, b + pad
    w, x0, x1 = 300, 10, 290
    sx = lambda v: x0 + (v - a) / (b - a) * (x1 - x0)
    label = f'{_fmt(pt)} [{_fmt(lo)}, {_fmt(hi)}]'
    title = f'{diff["arm"]} {MINUS} {diff["base"]}, {diff["metric"]}: {label}, 95% CI; 0 = no difference'
    return (f'<svg class="ival" viewBox="0 0 {w} 46" width="{w}" height="46" role="img"><title>{esc(title)}</title>'
            f'<line x1="{sx(0):.1f}" y1="4" x2="{sx(0):.1f}" y2="30" stroke-dasharray="2 2"/>'
            f'<line x1="{sx(lo):.1f}" y1="17" x2="{sx(hi):.1f}" y2="17" stroke-width="2"/>'
            f'<circle cx="{sx(pt):.1f}" cy="17" r="4"/>'
            f'<text x="{x0}" y="43">{esc(label)}</text><text x="{sx(0) + 4:.1f}" y="10">0 = no difference</text></svg>')


INSUFFICIENT = "Insufficient defect events to assess improvement"


def no_events(run: dict, diff: dict) -> bool:
    """A [0, 0] interval over all-zero counts says nothing; it is labelled, not plotted."""
    values = [run["arms"].get(a, {}).get(diff["metric"]) for a in (diff["arm"], diff["base"])]
    return (diff["point"] == diff["ci_low"] == diff["ci_high"] == 0
            and all(v == 0 for v in values))


def verdict(diff: dict) -> str:
    if diff["ci_low"] <= 0 <= diff["ci_high"]:
        return "No measured difference (95% CI includes 0)"
    return f'Point estimate {_fmt(diff["point"])}, 95% CI [{_fmt(diff["ci_low"])}, {_fmt(diff["ci_high"])}]'


def results_html(site: Site, compact: bool = False) -> str:
    res = site.results
    headers = ["Metric", "A", "B", "C", f"C {MINUS} A (95% CI)", f"B {MINUS} A (95% CI)"]
    dash = '<span class="dash" aria-label="not measured">—</span>'
    if res["status"] == "pending":
        rows = [[f'{label}{" <span class=\"chip\">primary</span>" if primary else ""}'] + [dash] * 5
                for _key, label, primary in METRICS]
        tbl = table(headers, rows, label="Benchmark results (not measured)", cls="results",
                    caption="What will be reported for each run. Nothing has been measured.")
        return (f'<div class="pending"><p><span class="badge b-pending">Pending</span> {esc(res["note"])}</p>{tbl}'
                f'</div>')
    out = []
    for run in res["runs"]:
        kind = run["kind"]
        chip = badge("pending", "Pilot") if kind == "pilot" else badge("implemented", "Held-out")
        raw = f'<a href="{esc(run["raw_url"])}">raw data</a>'
        pre = f' · preregistration <code>{esc(run["preregistration_sha256"][:12])}</code>' if run.get("preregistration_sha256") else ""
        head = (f'<p>{chip} <strong>{esc(run["label"])}</strong> · {esc(run["model"])} · {esc(run["date"])} · '
                f'{run["tasks"]} tasks × {run["trials_per_task_arm"]} trials · core <code>{esc(run["core_commit"][:7])}</code> · {raw}{pre}</p>')
        diffs = {(d["metric"], d["arm"]): d for d in run.get("diffs", [])}
        rows = []
        for key, label, primary in METRICS:
            cells = [f'{label}{" <span class=\"chip\">primary</span>" if primary else ""}']
            for arm in ("A", "B", "C"):
                v = run["arms"].get(arm, {}).get(key)
                cells.append(_fmt(v) if v is not None else dash)
            for arm in ("C", "B"):
                d = diffs.get((key, arm))
                if d and no_events(run, d):
                    cells.append(f'<span class="small">{INSUFFICIENT}</span>')
                else:
                    cells.append(f'{_fmt(d["point"])} [{_fmt(d["ci_low"])}, {_fmt(d["ci_high"])}]' if d else dash)
            rows.append(cells)
        tbl = table(headers, rows, label=f'Results for {run["label"]}', cls="results",
                    caption="n per arm: " + ", ".join(f'{a} {v["n"]}' for a, v in run["arms"].items()))
        plots = "".join(f'<figure>{_interval(d)}<figcaption>{esc(d["arm"])} {MINUS} {esc(d["base"])}, {esc(d["metric"])}: '
                        f'{esc(verdict(d))}.</figcaption></figure>' for d in run.get("diffs", []) if not no_events(run, d))
        skipped = sorted({d["metric"] for d in run.get("diffs", []) if no_events(run, d)})
        if skipped:
            plots += (f'<p class="small">{", ".join(esc(m) for m in skipped)}: no arm had a single event, so no interval is '
                      f'shown. {INSUFFICIENT}.</p>')
        pilot = ""
        if kind == "pilot":
            ev = site.status_map["bench-pilot"]["evidence"]
            m = re.search(r"unchecked arithmetic \((A \d+/\d+, B \d+/\d+, C \d+/\d+) trials\)", ev)
            if not m:
                raise BuildError("STATUS.md pilot row no longer states the unchecked-arithmetic counts")
            pilot = ("<p><strong>Pilot on the dev split: used for tuning, not evidence.</strong> No defect escaped in any arm, "
                     f"so the primary outcome has insufficient defect events to assess improvement. Trials that left unchecked "
                     f'arithmetic (<a href="/status/#tau-n001">TAU-N001</a>) in core code: {m.group(1)}.</p>')
        out.append(f'<div class="card">{head}{pilot}{tbl}{"" if compact else plots}</div>')
    return "".join(out)
