"""Start, proofs, status, redirects for retired pages, and 404."""

from __future__ import annotations

import json
import re

from . import md
from .common import install_block, measured_sentence, status_line, tier_rows
from .errors import BuildError
from .pages_home import gap
from .render import badge, code_html, esc, inline_md, panel, table
from .site import Site


def _head(title: str, lede: str) -> str:
    return f'<div class="wrap page-head"><h1>{title}</h1><p class="lede">{lede}</p></div>'


def _commands(site: Site) -> str:
    """Subcommands and the first sentence of their doc comments, parsed from the clap definitions in main.rs."""
    main = site.data.core.blob("crates/cargo-tauten/src/main.rs")
    enum = re.search(r"enum Command \{(.*?)\n\}", main, re.S).group(1)
    rows = []
    for doc, variant in re.findall(r"((?:    ///.*\n)+)    (\w+) \{", enum):
        text = " ".join(line.strip().removeprefix("///").strip() for line in doc.splitlines())
        first = re.split(r"(?<=[.;])\s(?=[A-Z])", text, maxsplit=1)[0].rstrip(";.").replace("`", "")
        rows.append((f"cargo tauten {variant.lower()}", first))
    if not rows:
        raise BuildError("no subcommands found in crates/cargo-tauten/src/main.rs")
    lines = "\n".join(f"{c}\n    {d}" for c, d in rows)
    return panel(esc(lines), caption=f'Parsed from {site.src("crates/cargo-tauten/src/main.rs")}',
                 label="cargo tauten subcommands", wrapped=True)


# -------------------------------------------------------------------- start ---

def start(site: Site) -> None:
    d = site.data
    readme_flat = " ".join(d.core.blob("README.md").split())
    if "does not weaken the check" not in readme_flat:
        raise BuildError("README no longer says that loosening the project's lints does not weaken the check")
    if "without Docker or the image nothing is checked and nothing passes" not in readme_flat:
        raise BuildError("README no longer says that without Docker nothing is checked and nothing passes")
    raw = d.core.blob("crates/tauten-check/agents.md")
    site.extra_files["agents/AGENTS.tauten.md"] = raw.encode()
    tiers = table(["Tier", "Meaning", "Examples of what is rejected"],
                  [[f"<code>{t}</code>", inline_md(m), inline_md(r)] for t, m, r in tier_rows(site)],
                  label="Tiers", caption="From the tauten README.")
    check = site.captures["check-fixtures"].block("TAU-P001", "rej-unwrap")
    docs = (f' The library API is on <a href="{site.docs_url}">docs.rs</a>.') if site.published else ""
    body = f"""{_head("Getting started", "Install the CLI, give each crate a tier, and run the check.")}
<div class="wrap">
<section id="install"><h2>Install</h2>
<p><code>cargo-tauten</code> is a Cargo subcommand and brings its own profile.{docs}</p>
{install_block(site)}</section>

<section id="tiers"><h2>Declare tiers</h2>
<p>Each crate declares a tier. <code>kernel</code> is pure and can be proved, <code>core</code> takes its effects as parameters, <code>edge</code> is the only place that touches the world.</p>
{site.snippet_panel("tier-manifest", title="Cargo.toml", label="Tier declaration")}
{tiers}
<p>Dependencies point inward only: edge → core → kernel (<a href="/rules/tau-t002/">TAU-T002</a>). <code>cargo tauten init</code> proposes a tier for each crate that has none; <code>--write</code> applies it.</p></section>

<section id="check"><h2>Check</h2>
<p>Run <code>cargo tauten check</code> on every edit. Error-level findings exit with code 1. The CLI owns the profile, so loosening your own <code>clippy.toml</code> or <code>[lints]</code> does not weaken it. <code>--format json</code> prints one diagnostic per line, the form an agent should read.</p>
{site.snippet_panel("check-commands", title="README.md", label="Check commands")}
{site.capture_panel("check-fixtures", check["text"], title="$ cargo tauten check", label="One finding from cargo tauten check")}
<p>To excuse one item, put <code>#[expect(lint, reason = "...")]</code> on it. <code>#[allow]</code> is itself a finding (<a href="/rules/tau-x001/">TAU-X001</a>), and some rules admit no exception.</p></section>

<section id="adopt"><h2>Adopt gradually</h2>
<p><code>cargo tauten baseline</code> records today's findings. Later checks report only new ones. The baseline may only shrink.</p>
{site.capture_panel("ratchet-2-check", title="$ cargo tauten check")}
<p class="small muted">A new <code>unwrap</code> after the baseline was recorded: it is an error, and the recorded findings are accepted. Recording more findings needs <code>--allow-increase</code>.</p></section>

<section id="prove"><h2>Prove a kernel function</h2>
<p><code>cargo tauten init --proofs &lt;crate&gt; --write</code> sets up the gate. <code>cargo tauten proofs</code> runs it and records one outcome per claim. Without Docker or the image nothing is checked and nothing passes. What counts as proved: <a href="/proofs/">Proofs</a>.</p>
{site.snippet_panel("proof-commands", title="README.md", label="Proof commands")}</section>

<section id="agent"><h2>Tell the agent</h2>
<p><code>cargo tauten init --write</code> adds <code>AGENTS.tauten.md</code>. Point your <code>AGENTS.md</code> or <code>CLAUDE.md</code> at it.</p>
{panel(code_html(raw.split(chr(10) * 2, 1)[1].split(chr(10) * 2, 1)[0], "text"), caption=site.src("crates/tauten-check/agents.md", "AGENTS.tauten.md") + " (first paragraph)", label="Start of the agent profile", wrapped=True)}
<p><a href="/agents/AGENTS.tauten.md">The whole file</a></p></section>

<section id="commands"><h2>Commands</h2>
{_commands(site)}
<p><code>cargo tauten explain &lt;ID&gt;</code> prints any rule; they are all on <a href="/rules/">Rules</a>.</p></section>
</div>"""
    site.add("/start/", "Getting started", "Install cargo-tauten, give each crate a tier, run the check, adopt gradually, prove kernel functions and tell the agent.", body)


# -------------------------------------------------------------------- proofs ---

def proofs(site: Site) -> None:
    d = site.data
    data = json.loads(d.core.blob("proofs/claims.json"))
    claims = data["claims"]
    proved = [c for c in claims if c["outcome"] == "proved"]
    if not proved:
        raise BuildError("proofs/claims.json lists no proved claim")
    gh = f"https://github.com/{site.config['repository']}/blob/{d.core.ref}"
    recorded = data.get("commit", "")[:7]

    rows = []
    for c in claims:
        names = "".join(f"<li><code>{esc(t)}</code></li>" for t in c["theorems"])
        thm = f'<details><summary>{len(c["theorems"])}</summary><ul class="names">{names}</ul></details>'
        fn = f'<code>{esc(c["crate"])}::{esc(c["function"])}</code>'
        if site.repo_public:
            fn = f'<a href="{gh}/{esc(c["file"])}">{fn}</a>'
        outcome = badge("proved", "Proved") if c["outcome"] == "proved" else esc(c["outcome"])
        rows.append([fn, thm, str(len(c["mutants"])), outcome])
    tbl = table(["Function", "Theorems", "Mutants killed", "Outcome"], rows, label="Claims",
                caption=f"From <code>proofs/claims.json</code> at <code>{d.core.short}</code>.")
    flow = [
        ("Extract", "Charon and Aeneas translate the kernel crate to Lean."),
        ("Drift", "The translation must match the committed <code>proofs/Extracted/</code>."),
        ("Build", "<code>lake build</code> checks every proof."),
        ("Audit", "<code>Audit.lean</code>: axioms only <code>propext</code>, <code>Classical.choice</code>, <code>Quot.sound</code>; every extracted function is covered by a claim."),
        ("Mutants", "Each deliberately broken copy of the Rust must fail its named theorems."),
    ]
    steps = "".join(f"<li><strong>{a}.</strong> {b}</li>" for a, b in flow)
    trust = f'<a href="{gh}/proofs/TRUST.md"><code>proofs/TRUST.md</code></a>' if site.repo_public else "<code>proofs/TRUST.md</code>"
    body = f"""{_head("Proofs", "Proved means a Lean theorem about the Charon/Aeneas translation of the crate that ships, checked by the five steps below.")}
<div class="wrap">
<p>tauten's own decisions (tiers, severity, exceptions, the baseline ratchet, the effects verdict) live in the <code>no_std</code> crate <code>tauten-check-kernel</code> and are proved this way. <code>cargo tauten init --proofs</code> sets up the same gate for your kernel crates.</p>
<section id="gate"><h2>The gate</h2>
<ol class="steps">{steps}</ol></section>
<section id="claims"><h2>Claims</h2>
<p><strong>{len(proved)} of {len(claims)} claims proved</strong>, recorded on <code>{esc(recorded)}</code>. Claims about <code>tauten-proof-instances</code> cover the code <code>#[refined]</code>, <code>#[requires]</code> and <code>#[ensures]</code> generate for listed examples. The macros themselves are not verified.</p>
{tbl}</section>
<section id="not"><h2>Not proved, and trusted</h2>
<p>Source scanning, diagnostic mapping, the rustc wrapper, workspace loading and the CLI are tested, not proved; so is the authority check (TAU-A002). Charon, Aeneas, Lean and the steps around them are trusted: {trust}.</p></section>
</div>"""
    site.add("/proofs/", "Proofs", f"Lean proofs over tauten's decision code: {len(proved)} of {len(claims)} claims proved, and what is trusted.", body)


# -------------------------------------------------------------------- status ---

# Known gaps bullets that are about one adopting project, or that the
# benchmark section already states. Matched by their first words.
SKIP_GAPS = ("The kernel's arithmetic", "Mutant counting differs", "The benchmark hits a ceiling",
             "Finding validity", "**No defect-reduction benefit")


def _known_gaps(site: Site) -> str:
    text = md.section(site.data.core.blob("docs/STATUS.md"), "Known gaps")
    items = []
    for bullet in re.findall(r"^- (.*?)(?=^- |\Z)", text, re.M | re.S):
        line = " ".join(bullet.split())
        if line.startswith(SKIP_GAPS):
            continue
        line = re.sub(r" \((?:[Ww]ritfold)[^)]*\)", "", line)
        if "writfold" in line.lower():
            raise BuildError(f"Known gaps bullet mentions writfold; add it to SKIP_GAPS or trim it: {line[:60]}")
        items.append(f"<li>{inline_md(line)}</li>")
    return f"<ul>{''.join(items)}</ul>"


def status(site: Site) -> None:
    gh = f"https://github.com/{site.config['repository']}/blob/{site.ref}"
    docs = [("docs/STATUS.md", "milestones and evidence"), ("docs/ROADMAP.md", "what comes next"),
            ("CHANGELOG.md", "what each release changed"), ("bench/README.md", "the benchmark harness and reports")]
    for path, _ in docs:
        site.data.core.blob(path)  # fails the build if a linked file is gone
    pages = {"CHANGELOG.md": '<a href="/changelog/">Changelog</a>'}  # core files the site renders as a page
    links = "".join(f"<li>{pages.get(p) or site.src(p)}: {w}</li>" for p, w in docs)
    body = f"""{_head("Status", status_line(site))}
<div class="wrap">
<section id="benchmark"><h2>Benchmark</h2>
<p class="limit">{measured_sentence(site)} tauten makes no defect-reduction claim.</p>
<p>Agents without the profile almost never shipped a defect the hidden tests catch, so the held-out run was stopped by its preregistered rule. The profile does change the code; on these tasks that code was not wrong. Design, pilot and audit: {site.src("bench/README.md")}.</p></section>
<section id="gaps"><h2>Known gaps</h2>
{_known_gaps(site)}
<p class="small muted">From {site.src("docs/STATUS.md")}, Known gaps, at <code>{site.short}</code>.</p></section>
<section id="more"><h2>More</h2>
<ul>{links}</ul></section>
</div>"""
    site.add("/status/", "Status", "The benchmark result (no defect-reduction claim), the known gaps, and where the milestones and roadmap live.", body)


# ----------------------------------------------------------------- redirects ---

def redirects(site: Site) -> None:
    site.redirect("/discipline/", "/", "The discipline page")
    site.redirect("/benchmark/", "/status/#benchmark", "The benchmark page")
    site.redirect("/enforcement/", "/rules/", "The enforcement page")
    site.redirect("/agents/", "/start/#agent", "The agent profile")
    docs = site.docs_url if site.published else "/start/"
    site.redirect("/crates/", docs, "The crates page")
    for name in site.data.crates:
        target = (f"https://docs.rs/{name}/{site.config['latest_release']}/"
                  if site.published and name != "cargo-tauten" else "/start/#commands")
        site.redirect(f"/crates/{name}/", target, f"The {name} page")


def not_found(site: Site) -> None:
    body = _head("Not found", 'There is no page at this address. Try the <a href="/">home page</a> or <a href="/start/">getting started</a>.')
    site.add("/404.html", "Not found", "No page at this address.", body)
