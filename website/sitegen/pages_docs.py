"""Start, discipline, proofs, status, redirects for retired pages, and 404."""

from __future__ import annotations

import json
import re

from . import md
from .common import CADENCE, DISCIPLINE, install_block, measured_sentence, ratchet_html, tiers_figure
from .errors import BuildError
from .render import badge, code_html, esc, inline_md, panel, status_badge, table
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


def _subcommands(site: Site) -> str:
    """Subcommands, doc comments and flags, parsed from the clap definitions in main.rs."""
    main = site.data.core.blob("crates/cargo-tauten/src/main.rs")
    target = re.search(r"struct Target \{(.*?)\n\}", main, re.S).group(1)
    target_flags = [f"--{n.replace('_', '-')}" for n in re.findall(r"^    (\w+): ", target, re.M)]
    enum = re.search(r"enum Command \{(.*?)\n\}", main, re.S).group(1)
    rows = []
    for doc, variant, body in re.findall(r"    /// (.*?)\n    (\w+) \{(.*?)\n    \},", enum, re.S):
        flags = []
        for attrs, field in re.findall(r"((?:\s+(?:///.*|#\[.*\]))*)\n\s+(\w+): ", body):
            if "flatten" in attrs:
                flags += target_flags
            elif "long" in attrs:
                flags.append(f"--{field.replace('_', '-')}")
            else:
                flags.append(f"&lt;{field}&gt;")
        rows.append([f"<code>{variant.lower()}</code>", inline_md(doc), ", ".join(f"<code>{f}</code>" for f in flags) or "–"])
    return table(["Command", "Doc comment", "Arguments"], rows, label="cargo tauten subcommands",
                 caption=f'Parsed from the clap definitions in {site.src("crates/cargo-tauten/src/main.rs")} at <code>{site.short}</code>.')


# -------------------------------------------------------------------- start ---

def start(site: Site) -> None:
    d = site.data
    readme = d.core.blob("README.md")
    manifest = md.section(readme, "How it works").split("```toml", 1)[1].split("```", 1)[0].strip()
    check = site.captures["check-fixtures"]
    excerpt = check.block("TAU-P001", "rej-unwrap")["text"] + "\n\n" + check.body.rstrip("\n").split("\n\n")[-1]
    json_p001 = json.dumps(next(json.loads(line) for line in site.captures["check-fixtures-json"].body.splitlines()
                                if '"TAU-P001"' in line and '"rej-unwrap"' in line), indent=2, ensure_ascii=False)
    readme_flat = " ".join(readme.split())
    if "does not weaken the check" not in readme_flat:
        raise BuildError("README no longer says that loosening the project's lints does not weaken the check")
    raw = d.core.blob("crates/tauten-check/agents.md")
    site.extra_files["agents/AGENTS.tauten.md"] = raw.encode()
    docs = (f'<p>The library API (<code>tauten::cap</code>, <code>#[refined]</code>, contracts) is documented on '
            f'<a href="{site.docs_url}">docs.rs</a>.</p>') if site.published else ""
    steps = [
        ("install", "Install",
         "<p><code>cargo-tauten</code> is a Cargo subcommand. Install it once; it brings its own profile, so there is nothing to configure in your project.</p>" + docs,
         install_block(site)),
        ("tiers", "Declare tiers",
         "<p>Every crate declares a tier in its manifest. <code>cargo tauten init</code> proposes one for each crate that has none and prints the plan; <code>--write</code> applies it.</p>"
         "<ul><li>a <code>no_std</code> library is proposed as <code>kernel</code>: pure decisions, eligible for proofs;</li><li>a library as <code>core</code>: effects arrive as parameters;</li><li>a binary-only crate as <code>edge</code>: the only tier that may create authority.</li></ul>"
         "<p>With <code>--write</code> it also writes <code>AGENTS.tauten.md</code>, the agent profile.</p>",
         panel(code_html(manifest, "toml"), title="Cargo.toml", label="Tier declaration", provenance="From the repo")
         + '<div style="height:16px"></div>' + site.capture_panel("init")),
        ("check", "Check, on every edit",
         "<p><code>cargo tauten check</code> runs clippy and the structural checks with each crate's own tier. Error-level findings fail the run with exit code 1. "
         "The CLI owns the profile: deleting or loosening a project's own <code>clippy.toml</code> or <code>[lints]</code> table does not weaken the check.</p>"
         "<p><code>--format json</code> prints one diagnostic per line, the form an agent should read. <code>cargo tauten explain &lt;ID&gt;</code> prints a rule.</p>",
         site.capture_panel("check-fixtures", excerpt, title="$ cargo tauten check",
                            label="One block and the summary of cargo tauten check over the fixtures")
         + '<div style="height:16px"></div>'
         + panel(code_html(json_p001, "json"), title="$ cargo tauten check --format json", label="One JSON diagnostic",
                 provenance="Captured", wrapped=True)
         + '<p class="small muted">The same finding as JSON, pretty-printed; the CLI prints it on one line.</p>'),
        ("adopt", "Adopt gradually",
         "<p><code>cargo tauten baseline</code> records today's error-level findings in <code>tauten-baseline.json</code>. Later checks accept up to that many per rule and file, and report anything new.</p>"
         "<p>The baseline may only shrink. A slot that is no longer needed is itself an error (TAU-R001), and recording more findings is refused without <code>--allow-increase</code>.</p>",
         f'<details><summary>The ratchet, in four captured steps</summary>{ratchet_html(site)}</details>'),
        ("proofs", "Prove kernel functions",
         "<p><code>cargo tauten init --proofs &lt;kernel crate&gt; --write</code> sets up the proof gate for a kernel crate: <code>proofs/claims.toml</code>, the Lean project and the gate scripts. "
         "<code>cargo tauten proofs</code> runs it in the pinned image and records one outcome per claim. A fresh, proved, total claim discharges the arithmetic and indexing findings inside that function.</p>"
         f'<p>{badge("planned", "Planned (0.1)")} <code>cargo tauten ship</code> at the end of a feature re-runs only the proofs of stale claims; <code>verify --level full</code> runs everything nightly. <a href="/discipline/#proofs">The cadence</a>.</p>',
         panel(code_html("cargo tauten init --proofs my-kernel --write\nsh proofs/refresh.sh\ncargo tauten proofs", "console"),
               title="Proof tier", label="Proof tier commands", provenance="From the repo")),
        ("agent", "Tell the agent",
         '<p>Point your <code>AGENTS.md</code> or <code>CLAUDE.md</code> at <code>AGENTS.tauten.md</code>. It tells the agent that <code>cargo tauten check</code> must pass before it reports a task as done, and how to fix a finding instead of hiding it.</p>'
         f'<p>{badge("progress", "In progress")} A "Discipline" section (authority as a parameter, declared effects, evidence, refined values, kernel shape) joins the profile once the D0 trial passes.</p>'
         '<p><a href="/agents/AGENTS.tauten.md">Raw file</a></p>',
         panel(code_html(raw.split("\n\n", 1)[1].split("\n\n", 1)[0], "text"),
               title="AGENTS.tauten.md (first paragraph)", label="Start of the agent profile", provenance="From the repo", wrapped=True)
         + f'<details><summary>The whole profile</summary><div class="actions"><button class="copy-btn" type="button" hidden data-src="/agents/AGENTS.tauten.md">Copy as Markdown</button></div>'
         f'{_repro(site, "crates/tauten-check/agents.md")}<div class="card prose">{_md(site, raw, "crates/tauten-check/agents.md", shift=1)}</div></details>'),
        ("exceptions", "Exceptions",
         '<p>When a finding is wrong for one item, excuse it there: <code>#[expect(lint, reason = "...")]</code> on the smallest item. <code>#[allow]</code> is itself a finding (TAU-X001), and so is a crate-wide exception (TAU-X002).</p>'
         "<p>Some rules admit none: stubs, <code>unsafe</code> outside the edge, and anything in a kernel crate (TAU-X004).</p>",
         site.block_panel("TAU-X004", "rej-stub-excused", capture="check-fixtures")),
    ]
    items = "".join(f'<li id="{i}"><div><h2>{t}</h2>{left}</div><div>{right}</div></li>' for i, t, left, right in steps)
    body = f"""<div class="wrap page-head"><p class="eyebrow">Getting started</p><h1>Getting started</h1>
<p class="lede">Install the CLI, declare a tier per crate, check on every edit, adopt gradually with a baseline, and prove kernel functions. Every output below was captured at <code>{site.short}</code>.</p></div>
<div class="wrap"><ol class="workflow">{items}</ol>
<section id="commands"><h2>Commands</h2>
<p class="prose">docs.rs documents libraries, not binaries, so the CLI reference is here. <code>cargo tauten explain &lt;ID&gt;</code> prints any rule.</p>
{_subcommands(site)}</section>
<section id="tier-examples"><h2>What each tier looks like</h2>
{tiers_figure(site)}</section></div>"""
    site.add("/start/", "Getting started", "Install cargo-tauten, declare tiers, check a workspace, adopt gradually, prove kernel functions and tell the agent.", body)


# ---------------------------------------------------------------- discipline ---

STRENGTH_HELP = ("<strong>compiler</strong>: rustc rejects it. <strong>lint</strong>: a lint or tauten check, escapable only by a visible, reasoned "
                 "<code>#[expect]</code>. <strong>proved</strong>: a Lean theorem over the translation of the shipped code. "
                 "<strong>bounded</strong>: model-checked up to a bound; never counted as proved. <strong>convention</strong>: review only.")


def discipline(site: Site) -> None:
    sections = []
    for idea in DISCIPLINE:
        strength = "".join(f'<li><span class="chip">{k}</span> {what}</li>' for k, what in idea["strength"])
        states = "".join(f"<li>{badge(kind, label)} {what}</li>" for kind, label, what in idea["states"])
        if "snippet" in idea:
            right = site.snippet_panel(idea["snippet"], title="Before / after",
                                       provenance="Proposed API", label=f"Before and after: {idea['title']}")
        elif "code" in idea:
            right = panel(code_html(idea["code"], "rust"), title="Before / after", label=f"Before and after: {idea['title']}",
                          provenance="Proposed API",
                          foot="The <code>after</code> is the D0 spec's API (being built on the <code>discipline-d0</code> branch); the <code>before</code> is an illustration.")
        else:
            rows = [[f"<code>{lvl}</code>", f"<code>{cmd}</code>", when, runs, badge(*state)] for lvl, cmd, when, runs, state in CADENCE]
            right = table(["Level", "Command", "When", "Runs", "State"], rows, label="Run cadence",
                          caption="Levels from <code>docs/DISCIPLINE-PROPOSAL.md</code>, section 3.2.")
        src = f' <span class="small muted">({idea["gap_src"]})</span>' if idea.get("gap_src") else ""
        left = (f'<p>{idea["line"]}</p><ul class="small">{states}</ul>'
                f'<p class="small"><strong>Enforced by</strong></p><ul class="small">{strength}</ul>'
                f'<p class="boundary"><strong>Gap.</strong> {idea["gap"]}{src}</p>')
        sections.append(f'<li id="{idea["key"]}"><div><h2>{idea["title"]}</h2>{left}</div><div>{right}</div></li>')
    mapping = site.src("docs/MAPPING.md")
    status = site.src("docs/STATUS.md")
    proposal = site.src("docs/DISCIPLINE-PROPOSAL.md")
    site.extra_files["assets/writfold-wiring.svg"] = (site.root / "website" / "assets" / "writfold-wiring.svg").read_bytes()
    body = f"""<div class="wrap page-head"><p class="eyebrow">Discipline</p><h1>The discipline</h1>
<p class="lede">Four ideas carried into Rust, plus proofs over the code that ships. Each says what enforces it, how far it has got, and where it stops.</p>
<p class="small">{STRENGTH_HELP}</p></div>
<div class="wrap"><ol class="workflow">{"".join(sections)}</ol>
<section id="writfold"><h2>In practice: writfold</h2>
<p class="prose">How the cadence would wire into one real project. The left half is writfold today; the right half is the planned shape with tauten. The adoption is on a branch, not merged, and the commands on the right are planned.</p>
<figure><a href="/assets/writfold-wiring.svg"><img src="/assets/writfold-wiring.svg" width="1134" height="717" style="max-width:100%;height:auto;border:1px solid var(--border);border-radius:6px" alt="Two columns. Today: writfold's gate script drives two Docker images (tools, and an Aeneas/Lean proofs image whose gate takes 105 minutes), a TLA+ spec with no runner, archived Verus code, and an unmerged tauten adoption with its own adapters. With tauten: cargo tauten check on every edit, cargo tauten ship at the end of a feature, verify --level full nightly, all in one public proofs image; writfold keeps its theorems, mutants, claims and TLA+ specs and deletes its forked gate scripts."></a>
<figcaption>From <code>docs/diagrams/writfold-wiring.svg</code> in the tauten repository (2026-11-19). Line counts and timings are from the writfold checkout and the adoption worktree.</figcaption></figure></section>
<section id="sources"><h2>Sources</h2>
<p class="prose">The full mechanism table, with every rule and gap, is {mapping}; current gaps are listed under Known gaps in {status}; the plan is {proposal}.</p></section>
</div>"""
    site.add("/discipline/", "Discipline", "The tauten discipline: authority passed explicitly, effects in signatures, checked evidence, refinement types and proofs, each with what enforces it and the honest gap.", body)


# -------------------------------------------------------------------- proofs ---

def proofs(site: Site) -> None:
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
    body = f"""<div class="wrap page-head"><p class="eyebrow">Proofs</p><h1>Proofs over the shipped Rust</h1>
<p>{status_badge(site.status_map["proof-tier"])}</p></div>
<div class="wrap prose-wrap">
<p class="prose">"Proved" means: a Lean theorem about the Charon/Aeneas translation of the exact crate that ships, passing the five steps below. tauten's own build decisions (tier rules, severity, exceptions, the baseline ratchet, rule-table validation) live in the <code>no_std</code> crate <code>tauten-check-kernel</code> and are proved this way; <code>cargo tauten init --proofs</code> sets up the same gate for your kernel crates.</p>
<h2 id="pipeline">The gate</h2>
<ol class="flow" aria-label="Proof gate">{steps}</ol>
<h2 id="own">Proved: tauten's own decisions</h2>
{own_tbl}
<details id="macros"><summary>Proved for listed instances: macro output ({len(inst)} claims)</summary>
<p class="prose">Theorems about the code <code>#[refined]</code>, <code>#[requires]</code> and <code>#[ensures]</code> generate for the examples in <code>crates/tauten-proof-instances</code>. The macros themselves are not verified: a different predicate or body is a different instance.</p>
{inst_tbl}</details>
<h2 id="not">Not proved, and trusted</h2>
<p class="prose">Source scanning, diagnostic mapping, the rustc wrapper, workspace loading and the CLI are tested, not proved; so is the authority check (TAU-A002). Charon, Aeneas, Lean and the steps around them are trusted: <a href="{gh}/proofs/TRUST.md"><code>proofs/TRUST.md</code></a>.</p>
<p class="boundary">{inline_md(caveat)} <span class="small muted">(docs/STATUS.md, Known gaps)</span></p>
<h2 id="next">Next</h2>
<p class="prose">{badge("planned", "Planned (0.1)")} Per-claim fingerprints, so an edit stales only the claims it touches, and <code>cargo tauten ship</code> to re-prove them at the end of a feature. {badge("planned", "Planned")} TLC configurations as claims, labelled bounded. The gate generalises the one <a href="https://writfold.dev">writfold</a> uses; <a href="/discipline/#writfold">how it would wire in</a>.</p>
</div>"""
    site.add("/proofs/", "Proofs", f"Lean proofs over tauten's decision code: {len(own)} proved claims, plus macro output proved for listed instances.", body)


# -------------------------------------------------------------------- status ---

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


# The approved path (docs/DISCIPLINE-PROPOSAL.md, section 5 replaced). D0 is being built.
PATH = [
    ("D0", "Worked example with all four ideas and one proved claim; the attribute macros", ("progress", "In progress")),
    ("X1–X3", "One-day experiments: automatic Lean tactics, Charon facts, Kani on the audited findings", ("planned", "Planned")),
    ("D1", "One shared proof gate and public image, replacing forked scripts", ("planned", "Planned")),
    ("D2", "Cadence: <code>ship</code>, <code>verify --level</code>, per-claim fingerprints", ("planned", "Planned (0.1)")),
    ("D3", "Findings reframed as obligations: fixed, proved, justified or open", ("planned", "Planned (0.1)")),
    ("D4–D7", "Capabilities and effects ratchet, evidence, the refinement fragment, TLC claims", ("planned", "Planned")),
    ("D8", "This site, rustdoc on docs.rs, release 0.1.0", ("progress", "In progress")),
]


def status(site: Site) -> None:
    from .common import status_line
    sm = site.status_map
    rej, acc = site.fixture_counts()
    legend = (f'<ul class="small legend"><li>{badge("specified", "Specified")} written down only.</li>'
              f'<li>{badge("implemented", "Implemented")} code exists.</li>'
              f'<li>{badge("exercised", "Exercised")} ran against real input in the repository; the evidence is named.</li>'
              f'<li>{badge("progress", "In progress")} / {badge("planned", "Planned")} not released.</li></ul>')
    path = "".join(f"<li>{badge(*state)} <strong>{m}</strong> {what}</li>" for m, what, state in PATH)
    body = f"""<div class="wrap page-head"><p class="eyebrow">Status</p><h1>Status</h1>
<p class="maturity"><span class="badge b-planned">Pre-release</span> <span>{status_line(site)}</span></p>{legend}</div>
<div class="wrap">
<section id="exercised">
<div class="status-grid">
<div class="card"><h3>Exercised</h3><ul>
<li>{status_badge(sm["tauten-check"])} {len(site.data.rules)} rules; {rej} reject and {acc} accept fixture crates, each producing exactly its expected rule IDs. <span class="ev">{site.src("crates/cargo-tauten/tests/fixtures.rs")}</span></li>
<li>{status_badge(sm["proof-tier"])} Proof tier: tauten's own kernel and the user template. <a href="/proofs/">Proofs</a></li>
<li>{status_badge(sm["tauten-macros"])} <code>#[refined]</code>, <code>#[newtype]</code>, contracts.</li>
<li>{status_badge(sm["writfold"])} Writfold adoption, on a worktree: 151 claims proved, 142 findings subsumed, baseline 527. <span class="ev">docs/STATUS.md, M8</span></li>
<li>tauten passes its own profile on every gate run. <span class="ev">scripts/gate</span></li>
</ul></div>
<div class="card"><h3>The approved path</h3><ul>{path}</ul>
<p class="small muted">From {site.src("docs/DISCIPLINE-PROPOSAL.md")}; no step depends on a defect benchmark.</p></div>
</div>
</section>
<section id="benchmark">
<h2>Benchmark</h2>
<p class="boundary">{measured_sentence(site)} tauten makes no defect-reduction claim.</p>
<p class="prose">Agents without the profile almost never shipped a defect the hidden tests catch, so the held-out run was stopped by its preregistered rule. The profile does change the code; on these tasks that code was not wrong. The harness, design and pilot are in {site.src("bench/README.md")}; the audit is summarised under Known gaps in {site.src("docs/STATUS.md")}.</p>
</section>
<section id="status-doc">
<details><summary>Every milestone, from docs/STATUS.md</summary>
{_repro(site, "docs/STATUS.md")}<div class="prose wide">{_status_milestones(site)}</div></details>
</section>
<p>Every rule, with a fixture that triggers it and the diagnostic it prints: <a href="/rules/">Rules</a>.</p>
</div>"""
    site.add("/status/", "Status", "What tauten has exercised, the approved path with what is in progress and planned, and the benchmark result: no defect-reduction claim.", body)


# ----------------------------------------------------------------- redirects ---

def redirects(site: Site) -> None:
    site.redirect("/benchmark/", "/status/#benchmark", "The benchmark page")
    site.redirect("/enforcement/", "/discipline/", "The enforcement page")
    site.redirect("/agents/", "/start/#agent", "The agent profile")
    docs = site.docs_url if site.published else "/start/"
    site.redirect("/crates/", docs, "The crates page")
    for name in site.data.crates:
        target = (f"https://docs.rs/{name}/{site.config['latest_release']}/"
                  if site.published and name != "cargo-tauten" else "/start/#commands")
        site.redirect(f"/crates/{name}/", target, f"The {name} page")


def not_found(site: Site) -> None:
    body = """<div class="wrap page-head"><p class="eyebrow">404</p><h1>Not found</h1>
<p class="lede">There is no page at this address. Try the <a href="/">home page</a>, <a href="/discipline/">the discipline</a> or <a href="/start/">getting started</a>.</p></div>"""
    site.add("/404.html", "Not found", "No page at this address.", body)
