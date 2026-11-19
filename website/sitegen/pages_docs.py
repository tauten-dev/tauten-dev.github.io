"""Start, enforcement, agents, benchmark, proofs, status and 404."""

from __future__ import annotations

import re

from . import md
from .common import install_block, results_html, tiers_figure
from .errors import BuildError
from .render import badge, code_html, esc, inline_md, panel, status_badge
from .site import Site
from .source import parse_state


def _md(site: Site, text: str, path: str, **kw) -> str:
    return md.render(text, source_path=path, link=lambda p: site.gh_url(p), **kw)


def _bullet(text: str, starts: str) -> str:
    """One `- ` bullet (possibly wrapped) from a Markdown list, verbatim."""
    m = re.search(rf"^- ({re.escape(starts)}.*?)(?=^- |^\n|^#|\Z)", text, re.M | re.S)
    if not m:
        raise BuildError(f"bullet starting {starts!r} not found")
    return " ".join(m.group(1).split())


def _repro(site: Site, path: str) -> str:
    return f'<p class="small muted">Reproduced from <code>{path}</code> at <code>{site.short}</code>.</p>'


# -------------------------------------------------------------------- start ---

def start(site: Site) -> None:
    d = site.data
    readme = d.core.blob("README.md")
    manifest = md.section(readme, "How it works").split("```toml", 1)[1].split("```", 1)[0].strip()
    check = site.captures["check-fixtures"]
    excerpt = check.block("TAU-P001", "rej-unwrap")["text"] + "\n\n" + check.body.rstrip("\n").split("\n\n")[-1]
    import json
    json_p001 = json.dumps(next(json.loads(line) for line in site.captures["check-fixtures-json"].body.splitlines()
                                if '"TAU-P001"' in line and '"rej-unwrap"' in line), indent=2, ensure_ascii=False)
    readme_flat = " ".join(readme.split())
    if "does not weaken the check" not in readme_flat:
        raise BuildError("README no longer says that loosening the project's lints does not weaken the check")
    steps = [
        ("install", "Install",
         "<p><code>cargo-tauten</code> is a Cargo subcommand. Install it once; it brings its own profile, so there is nothing to configure in your project.</p>",
         install_block(site)),
        ("tiers", "Declare tiers",
         "<p>Every crate declares a tier in its manifest. <code>cargo tauten init</code> proposes one for each crate that has none and prints the plan; <code>--write</code> applies it.</p>"
         "<ul><li>a <code>no_std</code> library is proposed as <code>kernel</code>;</li><li>a library as <code>core</code>;</li><li>a binary-only crate as <code>edge</code>.</li></ul>"
         "<p>With <code>--write</code> it also writes <code>AGENTS.tauten.md</code>, the agent profile. Review the proposals: a library that does IO directly belongs at the edge, or should be split.</p>",
         panel(code_html(manifest, "toml"), title="Cargo.toml", label="Tier declaration", provenance="From the repo")
         + '<div style="height:16px"></div>' + site.capture_panel("init")),
        ("check", "Check",
         "<p><code>cargo tauten check</code> runs clippy and the structural checks with each crate's own tier. Error-level findings fail the run with exit code 1.</p>"
         "<p>Add <code>--format json</code> for one diagnostic per line, the form an agent should read. <code>--warnings</code> lists each warning instead of a per-rule summary.</p>",
         site.capture_panel("check-fixtures", excerpt, title="$ cargo tauten check",
                            label="One block and the summary of cargo tauten check over the fixtures")
         + '<p class="small muted">One block and the summary line, from a run over the tauten fixture crates.</p>'
         + panel(code_html(json_p001, "json"), title="$ cargo tauten check --format json", label="One JSON diagnostic",
                 provenance="Captured", wrapped=True)
         + '<p class="small muted">The same finding as JSON, pretty-printed for reading; the CLI prints it on one line.</p>'),
        ("profile", "The profile is the CLI's",
         "<p>The CLI owns the profile: it runs one <code>cargo check</code> with itself as the workspace rustc wrapper, adding each crate's tier lints and a generated clippy configuration. Deleting or loosening a project's own <code>clippy.toml</code> or <code>[lints]</code> table does not weaken the check.</p>"
         "<p><code>cargo tauten explain &lt;ID&gt;</code> prints a rule: why, the fix, the level per tier, and the lints behind it.</p>",
         site.capture_panel("explain-p001")),
        ("adopt", "Adopt gradually",
         "<p><code>cargo tauten baseline</code> records today's error-level findings in <code>tauten-baseline.json</code>. Later checks accept up to that many per rule and file, and report anything new.</p>"
         "<p>The baseline may only shrink. A slot that is no longer needed is itself an error (TAU-R001), and recording more findings is refused without <code>--allow-increase</code>. "
         'The whole sequence is on the <a href="/crates/cargo-tauten/#ratchet">cargo-tauten page</a>.</p>',
         site.capture_panel("ratchet-1-baseline") + '<div style="height:16px"></div>' + site.capture_panel("ratchet-2-check")),
        ("agent", "Tell the agent",
         '<p>Point your <code>AGENTS.md</code> or <code>CLAUDE.md</code> at <code>AGENTS.tauten.md</code>. It tells the agent that <code>cargo tauten check</code> must pass before it reports a task as done, and how to fix a finding instead of hiding it. <a href="/agents/">Read the agent profile</a>.</p>',
         panel(code_html(d.core.blob("crates/tauten-check/agents.md").split("\n\n", 1)[1].split("\n\n", 1)[0], "text"),
               title="AGENTS.tauten.md (first paragraph)", label="Start of the agent profile", provenance="From the repo", wrapped=True)),
        ("exceptions", "Exceptions",
         '<p>When a finding is wrong for one item, excuse it there: <code>#[expect(lint, reason = "...")]</code> on the smallest item. <code>#[allow]</code> is itself a finding (TAU-X001), and so is a crate-wide exception (TAU-X002).</p>'
         "<p>Some rules admit none: stubs, <code>unsafe</code> outside the edge, and anything in a kernel crate (TAU-X004).</p>",
         site.block_panel("TAU-X004", "rej-stub-excused", capture="check-fixtures")),
    ]
    items = "".join(f'<li id="{i}"><div><h2>{t}</h2>{left}</div><div>{right}</div></li>' for i, t, left, right in steps)
    body = f"""<div class="wrap page-head"><p class="eyebrow">Getting started</p><h1>Getting started</h1>
<p class="lede">Install the CLI, declare a tier per crate, check, and adopt gradually with a baseline. Every output below was captured at <code>{site.short}</code>.</p></div>
<div class="wrap"><ol class="workflow">{items}</ol>
<section id="tier-examples"><h2>What each tier looks like</h2>
{tiers_figure(site)}</section></div>"""
    site.add("/start/", "Getting started", "Install cargo-tauten, declare tiers, check a workspace and adopt the profile gradually.", body)


# --------------------------------------------------------------- enforcement ---

def enforcement(site: Site) -> None:
    d = site.data
    mapping = d.core.blob("docs/MAPPING.md")
    head, sep, dropped = mapping.partition("\nDropped as not portable to Rust")
    if not sep:
        raise BuildError("MAPPING.md: 'Dropped as not portable to Rust' paragraph not found")
    status = d.core.blob("docs/STATUS.md")
    body = f"""<div class="wrap page-head"><p class="eyebrow">Enforcement</p><h1>What is enforced, and what is not</h1>
<p class="lede">Every mechanism, what enforces it, how far it has got, and the honest gap. The table is the core repository's, reproduced unedited.</p></div>
<div class="wrap">
<p class="small muted">Reproduced from <code>docs/MAPPING.md</code> at <code>{site.short}</code>. Strength codes are explained in its first paragraphs.</p>
<div class="prose wide">{_md(site, head, "docs/MAPPING.md", table_label="Enforcement table", table_cls="mapping", sticky=True)}</div>
<h2 id="known-gaps">Known gaps</h2>
{_repro(site, "docs/STATUS.md")}
<div class="prose">{_md(site, md.section(status, "Known gaps"), "docs/STATUS.md")}</div>
<h2 id="dropped">Dropped as not portable to Rust</h2>
<div class="prose">{_md(site, "Dropped as not portable to Rust" + dropped, "docs/MAPPING.md")}</div>
</div>"""
    site.add("/enforcement/", "Enforcement", "What tauten enforces, with what, and what it does not enforce: the mapping table and known gaps.", body)


# -------------------------------------------------------------------- agents ---

def agents(site: Site) -> None:
    d = site.data
    raw = d.core.blob("crates/tauten-check/agents.md")
    site.extra_files["agents/AGENTS.tauten.md"] = raw.encode()
    bench = d.core.blob("bench/README.md")
    body = f"""<div class="wrap page-head"><p class="eyebrow">Agent profile</p><h1>The agent profile</h1>
<p class="lede">This is the text an adopting project gives its agent. <code>cargo tauten init --write</code> writes it to <code>AGENTS.tauten.md</code>; point your <code>AGENTS.md</code> or <code>CLAUDE.md</code> at it.</p>
<p><span class="tag">Designed</span>Whether it changes agent behaviour: development pilot completed; held-out benefit not established (<a href="/benchmark/">benchmark</a>).</p></div>
<div class="wrap">
<div class="actions"><button class="copy-btn" type="button" hidden data-src="/agents/AGENTS.tauten.md">Copy as Markdown</button><a href="/agents/AGENTS.tauten.md">Raw file</a></div>
{_repro(site, "crates/tauten-check/agents.md")}
<div class="card prose" style="max-width:76ch">{_md(site, raw, "crates/tauten-check/agents.md", shift=1)}</div>
<h2 id="arms" style="margin-top:48px">Three arms</h2>
<p class="prose">Whether instructions alone help is an open question, and the benchmark tests it: arm B gets the same rules in prose, without the check.</p>
{_repro(site, "bench/README.md")}
<div class="prose">{_md(site, md.section(bench, "Arms"), "bench/README.md", table_label="Benchmark arms")}</div>
</div>"""
    site.add("/agents/", "Agent profile", "The instructions an adopting project gives its coding agent, written by cargo tauten init --write.", body)


# ----------------------------------------------------------------- benchmark ---

def benchmark(site: Site) -> None:
    d = site.data
    bench = d.core.blob("bench/README.md")
    prereg = d.core.blob("bench/PREREGISTRATION.md")
    plan = d.core.blob("docs/PLAN.md")
    status = d.core.blob("docs/STATUS.md")
    banner = "Pilot on the dev split only (2026-11-18, Claude Sonnet 5.5, 36 trials): no held-out result yet."
    if f"**{banner}**" not in bench:
        raise BuildError("bench/README.md no longer carries the benchmark status line the site quotes")
    question = re.search(r"^\*\*Question\.\*\*.*?(?=\n\n)", bench, re.M | re.S).group(0)
    harness = site.status_map["bench-harness"]
    limits = _bullet(md.section(status, "Known gaps"), "The benchmark's dev split")
    body = f"""<div class="wrap page-head"><p class="eyebrow">Benchmark</p><h1>Does the profile reduce escaped defects?</h1></div>
<div class="wrap">
<div class="banner-pending" role="note"><p><span class="badge b-pending">Pilot</span> <strong>{banner}</strong> The dev tasks hit a ceiling: no defect escaped in any arm, so the primary outcome cannot separate the arms. In the secondary outcome, half the plain-Rust trials left unchecked arithmetic in core code, and none of the enforced ones did. Harder held-out tasks are being written.</p></div>
<div class="prose">{_md(site, question, "bench/README.md")}</div>
{_repro(site, "bench/README.md")}
<h2 id="arms">Arms</h2>
<div class="prose">{_md(site, md.section(bench, "Arms"), "bench/README.md", table_label="Benchmark arms")}</div>
<h2 id="measured">What is measured</h2>
<div class="prose">{_md(site, md.section(bench, "Measurements (every arm)"), "bench/README.md")}</div>
<h2 id="results">Results</h2>
{results_html(site)}
<h2 id="validation" style="margin-top:48px">Harness validation with built-in agents (not a result about AI agents)</h2>
<p>{status_badge(harness)} <span class="small muted">dated 2026-11-18 in <code>bench/README.md</code></span></p>
<p class="prose">Three built-in agents check the harness itself before any model is paid for. <strong>reference</strong> applies the task's known-good solution, <strong>null</strong> changes nothing, and <strong>sloppy</strong> applies a hand-written plausible solution with the typical mistake. A task is admitted only when each produces what the table requires: the oracle must pass the reference and catch the other two, and the profile must name the sloppy mistake.</p>
<div class="prose">{_md(site, md.section(bench, "Validation (no model budget)"), "bench/README.md", table_label="Harness validation", shift=1)}</div>
<section id="preregistration">
<h2 style="margin-top:48px">Preregistration <span class="badge b-planned">Draft, not frozen</span></h2>
{_repro(site, "bench/PREREGISTRATION.md")}
<div class="prose">{_md(site, prereg.split("\n", 1)[1], "bench/PREREGISTRATION.md", table_label="Preregistered design", shift=1)}</div>
</section>
<h2 id="limits" style="margin-top:48px">Limits</h2>
<p class="prose">{inline_md(limits)}</p>
<p class="small muted">From <code>docs/STATUS.md</code>, Known gaps.</p>
<h2 id="kill">Kill criteria</h2>
<p class="prose">Publishing the conditions under which the project stops is part of the plan.</p>
{_repro(site, "docs/PLAN.md")}
<div class="prose">{_md(site, md.section(plan, "9. Kill criteria"), "docs/PLAN.md")}</div>
</div>"""
    site.add("/benchmark/", "Benchmark", "The tauten benchmark: arms, measurements, the dev-split pilot, harness validation and preregistration. No held-out result yet.", body)


# -------------------------------------------------------------------- proofs ---

def proofs(site: Site) -> None:
    import json
    from .render import table
    d = site.data
    claims = json.loads(d.core.blob("proofs/claims.json"))["claims"]
    status = d.core.blob("docs/STATUS.md")
    caveat = _bullet(md.section(status, "Known gaps"), "The kernel's arithmetic")
    gh = f"https://github.com/{site.config['repository']}/blob/{d.core.ref}"
    proved = [c for c in claims if c["outcome"] == "proved"]
    if not proved:
        raise BuildError("proofs/claims.json lists no proved claim")

    def rows(group):
        out = []
        for c in group:
            theorems = "<br>".join(f"<code>{esc(t.split('.')[-1])}</code>" for t in c["theorems"])
            src = f'<a href="{gh}/{esc(c["file"])}"><code>{esc(c["crate"])}::{esc(c["function"])}</code></a>'
            out.append([src, theorems, str(len(c["mutants"])), badge("exercised", "Proved")])
        return out

    own = [c for c in proved if c["crate"] != "tauten-proof-instances"]
    inst = [c for c in proved if c["crate"] == "tauten-proof-instances"]
    headers = ["Function", "Theorems", "Mutants killed", "Outcome"]
    own_tbl = table(headers, rows(own), label="Proved claims about tauten's own decisions",
                    caption=f"From <code>proofs/claims.json</code> at <code>{d.core.short}</code>.")
    inst_tbl = table(headers, rows(inst), label="Proved claims about macro output",
                     caption="Proved for these listed instances only.") if inst else ""
    flow = [
        ("1 · extract", "Charon and Aeneas translate the kernel crate to Lean."),
        ("2 · drift", "The extraction must match the committed <code>proofs/Extracted/</code>."),
        ("3 · build", "<code>lake build</code> checks every proof."),
        ("4 · audit", "<code>Audit.lean</code>: axioms only <code>propext</code>, <code>Classical.choice</code>, <code>Quot.sound</code>; every extracted function covered by a claim."),
        ("5 · mutants", "Each deliberately broken copy of the Rust must fail its named theorems."),
    ]
    steps = "".join(f"<li><b>{a}</b>{b}</li>" for a, b in flow)
    body = f"""<div class="wrap page-head"><p class="eyebrow">Proof tier</p><h1>Proofs over the shipped Rust</h1>
<p>{status_badge(site.status_map["proof-tier"])}</p></div>
<div class="wrap prose-wrap">
<p class="prose">The code that decides whether your build passes (tier rules, severity, exceptions, the baseline ratchet and rule-table validation) lives in a small <code>no_std</code> crate, <code>tauten-check-kernel</code>. Charon and Aeneas translate that exact crate to Lean, and the theorems below are proved about the translation. A CI workflow re-runs the whole gate whenever the kernel, the macros or the proofs change.</p>
<h2 id="pipeline">The gate</h2>
<ol class="flow" aria-label="Proof gate">{steps}</ol>
<h2 id="own">Proved: tauten's own decisions</h2>
{own_tbl}
<h2 id="macros">Proved for listed instances: macro output</h2>
<p class="prose">These theorems are about the code that <code>#[refined]</code>, <code>#[requires]</code> and <code>#[ensures]</code> generate for the example types and functions in <code>crates/tauten-proof-instances</code>, plus lemmas about the general shape of that code. The macros themselves are not verified: a different predicate or body is a different instance.</p>
{inst_tbl}
<h2 id="not">Not proved</h2>
<p class="prose">Source scanning, the mapping from compiler diagnostics to rule IDs, the rustc wrapper, workspace loading and the CLI are tested, not proved. So is the authority check (TAU-A002): a proof of a wrong model would have passed, as review showed. Charon, Aeneas, Lean and the steps around them are trusted; the list is in <a href="{gh}/proofs/TRUST.md"><code>proofs/TRUST.md</code></a>.</p>
<h2 id="yours">Proofs for your kernel crates</h2>
<p class="prose"><code>cargo tauten init --proofs</code> sets up the same gate for your own <code>kernel</code> crates, and <code>cargo tauten proofs</code> runs it and records one outcome per claim in <code>proofs/claims.json</code>. When a claim is proved and its source has not changed since, arithmetic and indexing findings (TAU-N001, TAU-P003) inside that function are reported as subsumed by the named theorem rather than as errors. Any edit makes the record stale and the findings return.</p>
<p class="boundary">{inline_md(caveat)} <span class="small muted">(docs/STATUS.md, Known gaps)</span></p>
<h2 id="writfold">Modelled on writfold</h2>
<p class="prose">The gate generalises the one <a href="https://writfold.dev">writfold</a> uses for its own kernel, with the same pinned Lean, Aeneas and Charon versions.</p>
</div>"""
    site.add("/proofs/", "Proof tier", f"Lean proofs over tauten's decision code: {len(own)} proved claims, plus macro output proved for listed instances.", body)


# -------------------------------------------------------------------- status ---

# Moved here from the home page.
NOT_ENFORCED = [
    "Capability discipline, not containment. Dependencies, <code>unsafe</code>, FFI and build scripts keep ambient access.",
    "Panic rules are syntactic. Panics inside dependencies and allocation failure are not covered.",
    "Contracts and refinements are runtime checks. Nothing is proved statically yet.",
    "Rust cannot express per-function effect rows; tiers are a coarse stand-in.",
    "An agent can still add <code>.clone()</code> to quiet the borrow checker, or a reasoned <code>#[expect]</code> (visible in review).",
    "Async cancellation safety is not enforceable.",
    'The placeholder-comment rule (<a href="/rules/tau-s002/">TAU-S002</a>) is a heuristic.',
]


def _rule_example(site: Site, rule: dict) -> str:
    """The expanded view of one rule: a fixture and its captured output, or the explain text."""
    rid = rule["id"]
    warnings_cap = site.captures["check-fixtures-warnings"]
    seen = []
    for f in site.data.fixtures:
        if rid not in f.expect:
            continue
        blocks = [b for b in warnings_cap.blocks() if b["id"] == rid and b["crate"] == f.name]
        if blocks:
            seen.append((f, blocks))
    links = f'<a href="/rules/{rid.lower()}/">Rule page</a> · <code>cargo tauten explain {rid}</code>'
    if not seen:
        explain = site.captures[f"explain-rule-{rid.lower()}"]
        return (f'<p class="small"><span class="chip">No fixture yet</span> No fixture in the tauten repository triggers '
                f'this rule, so there is no captured diagnostic to show. This is what <code>cargo tauten explain</code> prints.</p>'
                f'{site.capture_panel(explain.name, label=f"cargo tauten explain {rid}")}<p class="small">{links}</p>')
    # The shortest fixture reads best; the others are named.
    seen.sort(key=lambda x: (len(x[0].src.splitlines()), x[0].name))
    f, blocks = seen[0]
    marks = {b["line"]: b["column"] for b in blocks if b["line"]}
    text = "\n\n".join(b["text"] for b in blocks)
    others = ", ".join(f"<code>{o.name}</code>" for o, _ in seen[1:])
    also = f" Also triggered by {others}." if others else ""
    return (f'<div class="pair">{site.fixture_panel(f, marks=marks)}'
            f'{site.capture_panel("check-fixtures-warnings", text, title="$ cargo tauten check", label=f"Output for {f.name}")}</div>'
            f'<p class="small muted"><span class="chip prov">Captured</span> Fixture <code>{f.name}</code> ({f.tier or "no tier"}) '
            f'and the output <code>cargo tauten check --warnings</code> printed for it at <code>{site.short}</code>.{also} {links}</p>')


def rule_table(site: Site) -> str:
    from .render import level_chip
    from .source import ENFORCERS, FAMILIES, TIERS, level
    rows, current = [], None
    for r in site.data.rules:
        fam = r["id"][4]
        if fam != current:
            current = fam
            rows.append(f'<p class="rt-fam" id="family-{fam.lower()}">{fam} · {FAMILIES.get(fam, fam)}</p>')
        has = any(r["id"] in f.expect for f in site.data.fixtures)
        lv = "".join(f'<span class="rt-lv"><span class="rt-t">{t}</span>{level_chip(level(r, t))}</span>' for t in TIERS)
        ex = '<span class="rt-ex">example</span>' if has else '<span class="rt-ex none">no fixture</span>'
        rows.append(f'<details class="rt-row" id="{r["id"].lower()}"><summary><span class="id">{r["id"]}</span>'
                    f'<span class="rt-title">{inline_md(r["title"])}</span><span class="rt-lvs">{lv}</span>'
                    f'<span class="rt-by">{ENFORCERS[r["enforced_by"]]}</span>{ex}</summary>'
                    f'<div class="rt-body">{_rule_example(site, r)}</div></details>')
    head = ('<div class="rt-head" aria-hidden="true"><span>ID</span><span>Rule</span>'
            '<span class="rt-lvs">kernel · core · edge</span><span>Enforced by</span><span></span></div>')
    return f'<div class="rtable">{head}{"".join(rows)}</div>'


def _status_milestones(site: Site) -> str:
    text = site.data.core.blob("docs/STATUS.md")
    lines = text.split("\n")
    badges: dict[str, str] = {}
    in_table = False
    for i, line in enumerate(lines):
        if line.startswith("| # | Item | State | Evidence |"):
            in_table = True
            continue
        if in_table and line.startswith("|") and not line.startswith("|---"):
            cells = line.strip().strip("|").split("|")
            kind, _label, word, qual = parse_state(cells[2].strip(), strict=False)
            key = f"STATEBADGE{len(badges)}X"
            q = f' <span class="qual">{esc(qual)}</span>' if qual else ""
            badges[key] = badge(kind, word[:1].upper() + word[1:]) + q
            cells[2] = f" {key} "
            lines[i] = "|" + "|".join(cells) + "|"
        elif in_table and not line.startswith("|"):
            in_table = False
    out = _md(site, "\n".join(lines), "docs/STATUS.md", table_label="Milestones")
    for key, html in badges.items():
        out = out.replace(key, html)
    return out


def status(site: Site) -> None:
    from .common import status_line
    d = site.data
    sm = site.status_map
    rej, acc = site.fixture_counts()
    n = len(d.rules)
    first = site.config["first_release"]
    publication = (f"Publication: {site.config['latest_release']} is on crates.io."
                   if site.published else
                   f'Publication: the release workflow is {status_badge(sm["publication"])}; nothing is on crates.io yet.')
    legend = (f'<ul class="small legend"><li>{badge("specified", "Specified")} written down only.</li>'
              f'<li>{badge("implemented", "Implemented")} code exists.</li>'
              f'<li>{badge("exercised", "Exercised")} ran against real input in the repository; the evidence is named.</li></ul>')
    covered = sum(1 for r in d.rules if any(r["id"] in f.expect for f in d.fixtures))

    groups = []
    for key, label in (("rustc", "rustc"), ("clippy", "Clippy, at levels the profile sets"), ("tauten", "tauten structural checks")):
        members = [r for r in d.rules if r["enforced_by"] == key]
        groups.append(f'<li><span class="count">{label}:</span> {len(members)} rules.</li>')
    never = len(site.no_exception_rules)
    groups.append(f'<li><span class="count">{never} rules admit no exception;</span> in kernel crates, none do (<a href="/rules/tau-x004/">TAU-X004</a>).</li>')
    gaps = "".join(f"<li>{g}</li>" for g in NOT_ENFORCED)
    gaps += "<li><strong>Development pilot completed; held-out benefit not established.</strong></li>"

    body = f"""<div class="wrap page-head"><p class="eyebrow">Status</p><h1>Status</h1>
<p class="lede">What tauten checks, what each check prints, and how far each part has got.</p>
<p class="maturity"><span class="badge b-planned">Pre-release</span> <span>{status_line(site)}</span></p>{legend}</div>
<div class="wrap">
<section id="rules">
<h2>Rules and what they report</h2>
<p class="prose">{n} rules. Open a row to see a fixture crate from the tauten repository that triggers the rule and the diagnostic <code>cargo tauten check</code> printed for it. {covered} rules have a fixture; for the other {n - covered} the row shows <code>cargo tauten explain</code> instead. Levels are per tier; <a href="/rules/">the rule reference</a> has the full table with filters.</p>
{rule_table(site)}
</section>
<section id="exercised">
<h2>What has been exercised</h2>
<div class="status-grid">
<div class="card"><div class="top">{status_badge(sm["tauten-check"])}</div><ul>
<li>{rej} reject and {acc} accept fixture crates, each producing exactly its expected rule IDs. <span class="ev">{site.src("crates/cargo-tauten/tests/fixtures.rs")}</span></li>
<li>tauten passes its own profile on every gate run. <span class="ev">scripts/gate</span></li>
<li><span class="tag">Observed</span>Dry run on a throwaway clone of writfold: 2,883 findings, and four defects found in tauten itself, since fixed. <span class="ev">{site.src("docs/dry-runs/writfold-2026-11-18.md")}</span></li>
<li>Mutation testing of <code>tauten-check</code>: 14 of 137 viable mutants missed on the first run, 0 after new tests. <span class="ev">docs/STATUS.md, Quality</span></li>
<li>Benchmark harness: 4 dev tasks admitted with built-in agents. <span class="ev">{site.src("bench/README.md")}</span></li>
</ul></div>
<div class="card"><div class="top"><span class="badge b-pending">Pending</span></div><ul>
<li>Pilot with a real agent (dev split): {status_badge(sm["bench-pilot"])} Held-out benefit not established.</li>
<li>Proof tier: {status_badge(sm["proof-tier"])}</li>
<li>Contracts for <code>async fn</code> and generic newtypes; Kani lowering.</li>
<li>{publication}</li>
</ul></div>
</div>
<h3 style="margin-top:32px">Benchmark, dev-split pilot</h3>
{results_html(site, compact=True)}
<p><a href="/benchmark/">The benchmark →</a></p>
</section>
<section id="enforced">
<h2>Enforced, and not</h2>
<div class="ledger">
<div><h3>Enforced</h3><ul>{"".join(groups)}</ul></div>
<div class="gap"><h3>Not enforced</h3><ul>{gaps}</ul></div>
</div>
<p><a href="/enforcement/">The full enforcement table →</a></p>
</section>
<section id="status-doc">
{_repro(site, "docs/STATUS.md")}<div class="prose wide">{_status_milestones(site)}</div>
</section>
</div>"""
    site.add("/status/", "Status", "Every tauten rule with an example and the diagnostic it prints, what has been exercised, and what is still planned.", body)


def not_found(site: Site) -> None:
    body = """<div class="wrap page-head"><p class="eyebrow">404</p><h1>Not found</h1>
<p class="lede">There is no page at this address. Try the <a href="/">home page</a>, the <a href="/rules/">rules</a> or <a href="/start/">getting started</a>.</p></div>"""
    site.add("/404.html", "Not found", "No page at this address.", body)
