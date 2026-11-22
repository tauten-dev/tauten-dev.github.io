"""Start, proofs, status, redirects for retired pages, and 404."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess

from . import md
from .common import install_block, measured_sentence, status_line, tier_rows
from .errors import BuildError
from .pages_home import gap
from .render import badge, code_html, esc, inline_md, panel, table
from .site import Site
from .source import Core


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


# ------------------------------------------------------- adoption routes ---

def _exit(site: Site, name: str) -> str:
    return site.captures[name].header["exit"][0]


def _advisory_release(site: Site) -> None:
    """The advisory route installs exactly the release the site describes."""
    code = site.snippets["adopt-advisory"]["code"]
    release = site.config["latest_release"]
    channel = re.search(r'^channel = "([^"]+)"', site.data.core.blob("rust-toolchain.toml"), re.M).group(1)
    if f"cargo +{channel} install --locked --version {release} cargo-tauten" not in code:
        raise BuildError(f"docs/ADOPTING.md: the advisory route does not install cargo-tauten {release} "
                         f"(latest_release) with the toolchain {channel} (rust-toolchain.toml)")
    if not any("unchanged" in n for n in site.captures["adopt-trial"].header.get("note", [])):
        raise BuildError("capture adopt-trial does not record that fixtures/adopt was unchanged; re-run capture.py")


def _json_findings(site: Site, name: str) -> str:
    """A JSON-lines capture, each line trimmed to the fields that locate a finding."""
    cap = site.captures[name]
    keep = ("id", "severity", "crate", "file", "line")
    lines = []
    for raw in cap.body.splitlines():
        if not raw.strip():
            continue
        try:
            finding = json.loads(raw)
        except json.JSONDecodeError as error:
            raise BuildError(f"capture {name}: a line is not JSON: {raw[:60]}") from error
        lines.append(json.dumps({k: finding.get(k) for k in keep}))
    if not lines:
        raise BuildError(f"capture {name} has no findings")
    note = (f'<p class="small muted">Exit code {esc(_exit(site, name))}. Each line is trimmed here to '
            '<code>id</code>, <code>severity</code>, <code>crate</code>, <code>file</code> and <code>line</code>; '
            'the full line also carries the message, the rule, why it exists and the fix.</p>')
    return panel(code_html("\n".join(lines), "json"), caption=esc(f"$ {cap.cmd}"),
                 label=f"Findings from {cap.cmd}", wrapped=True) + note


def lean_reuse(site: Site) -> dict:
    """The pinned Lean module of docs/ADOPTING.md, checked against the core repository.

    The pin must be a commit on the pinned history whose workspace version is
    the release the comment names, and each checksum must be the sha256 of
    the file the recipe downloads, read at that commit.
    """
    code = site.snippets["reuse-lean"]["code"]
    pin = re.search(r"^\$ TAUTEN=([0-9a-f]{40})   # tauten (\S+)$", code, re.M)
    if not pin:
        raise BuildError("docs/ADOPTING.md: no `TAUTEN=<full sha>   # tauten <version>` line in the Lean recipe")
    ref, version = pin.groups()
    core = site.data.core
    try:
        subprocess.run(["git", "-C", str(core.path), "merge-base", "--is-ancestor", ref, core.ref],
                       check=True, capture_output=True)
    except subprocess.CalledProcessError as error:
        raise BuildError(f"Lean recipe pin {ref[:12]} is not an ancestor of the pinned core commit") from error
    pinned = Core(core.path, ref)
    found = re.search(r'^version = "([^"]+)"', pinned.blob("Cargo.toml"), re.M)
    if not found or found.group(1) != version:
        raise BuildError(f"Lean recipe pin {ref[:12]} is not tauten {version}")
    fetched = dict(re.findall(r"^\$ curl -fsSLo (\S+) \$RAW/(\S+)$", code, re.M))
    sums = {path: digest for digest, path in re.findall(r"^([0-9a-f]{64})  (\S+)$", site.snippets["reuse-sha"]["code"], re.M)}
    if not fetched or set(fetched) != set(sums):
        raise BuildError("Lean recipe: the downloaded files and the checksum lines differ")
    for dest, source in fetched.items():
        if hashlib.sha256(pinned.blob_bytes(source)).hexdigest() != sums[dest]:
            raise BuildError(f"Lean recipe: the checksum of {dest} is not the sha256 of {source} at {ref[:12]}")
    module = next(src for src in fetched.values() if src.endswith(".lean"))
    license_path = next(src for src in fetched.values() if not src.endswith(".lean"))
    if pinned.blob(module) != pinned.blob("proofs/Tauten/Machine.lean"):
        raise BuildError(f"Lean recipe: {module} differs from proofs/Tauten/Machine.lean at {ref[:12]}")
    imports = re.findall(r"^import (\S+)$", pinned.blob(module), re.M)
    toolchain = pinned.blob(module.rsplit("/Proofs/", 1)[0] + "/lean-toolchain").strip()
    lean = toolchain.rsplit(":", 1)[-1]
    return {"ref": ref, "version": version, "module": module, "license": license_path, "imports": imports,
            "lean": lean}


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
    _advisory_release(site)
    docs = (f' The library API is on <a href="{site.docs_url}">docs.rs</a>.') if site.published else ""
    body = f"""{_head("Getting started", "Install the CLI, choose how far to adopt it, give each crate a tier, and run the check.")}
<div class="wrap">
<section id="install"><h2>Install</h2>
<p><code>cargo-tauten</code> is a Cargo subcommand and brings its own profile.{docs}</p>
{install_block(site)}</section>

<section id="routes"><h2>Choose a route</h2>
<p>Each route is complete on its own; none replaces a check the project already runs.</p>
<ul>
<li><a href="#trial">Advisory trial</a>: run the structural checks once on a disposable checkout. Nothing in the repository changes.</li>
<li><a href="#adopt">Opt-in CI check</a>: commit the tiers and a reviewed baseline, then require the full check in CI.</li>
<li><a href="/proofs/#reuse">Lean module only</a>: vendor one pinned Lean file into an existing proof project, without the CLI.</li>
</ul>
<p class="small muted">All three, with what each step changes: {site.src("docs/ADOPTING.md")}.</p></section>

<section id="trial"><h2>Advisory trial</h2>
<p>Install the exact release and the Rust toolchain it is built for. <code>init</code> without <code>--write</code> previews the tier plan; <code>--assume-tier</code> applies it for one run without editing a manifest.</p>
{site.snippet_panel("adopt-advisory", title="docs/ADOPTING.md", label="Advisory trial commands")}
{_json_findings(site, "adopt-trial")}
<ul>
<li><strong>Exit 1</strong> means at least one error-level finding under the assumed tiers. The code still builds. Exit 0: none from the checks that ran; exit 2: tauten could not run.</li>
<li><strong>Not run:</strong> <code>--structure-only</code> skips Clippy and rustc, so most rules they decide report nothing (the <code>unwrap</code> in this workspace is one, <a href="/rules/tau-p001/">TAU-P001</a>). <code>--no-baseline</code> ignores any baseline. No proof gate runs.</li>
<li><strong>Nothing changes:</strong> no manifest, baseline, agent profile or proof record is written. In the capture above, every file of {site.src("fixtures/adopt")} was compared before and after the run.</li>
<li><strong>A finding is not a defect</strong>, and their number is not a defect count (<a href="/status/#benchmark">benchmark</a>).</li>
<li><a href="/rules/tau-h001/">TAU-H001</a> appears in most workspaces. Turning release overflow checks on makes an overflow panic instead of wrap: a decision about release behaviour, not a step of the trial.</li>
</ul></section>

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

<section id="adopt"><h2>Opt-in CI check</h2>
<p>Commit the tiers and a reviewed baseline. <code>cargo tauten baseline</code> records today's error-level findings; later checks report only new ones, and the baseline may only shrink. <code>init --write</code> also turns release overflow checks on: keep that line only as a decision; without it, TAU-H001 goes into the baseline like any other finding.</p>
{site.snippet_panel("adopt-ci", title="docs/ADOPTING.md", label="Opt-in CI commands")}
{site.capture_panel("ratchet-1-check", title=f"$ cargo tauten check   # exit {_exit(site, 'ratchet-1-check')}: the reviewed baseline accepts today's findings")}
{site.capture_panel("ratchet-2-check", title=f"$ cargo tauten check   # exit {_exit(site, 'ratchet-2-check')}: one new unwrap")}
<ul>
<li><strong>In CI</strong>, install the same release and toolchain and run <code>cargo tauten check</code>. It also fails when a finding was fixed but the baseline still accepts it (<a href="/rules/tau-r001/">TAU-R001</a>); shrink the baseline in the same change.</li>
<li><strong>Never</strong> run <code>cargo tauten baseline</code> in CI or regenerate the baseline to make a check pass. Recording more findings needs <code>--allow-increase</code>, a reviewed local change.</li>
<li><strong>A lint check, not a proof gate.</strong> <code>cargo tauten check</code> runs no proof. A proof gate, tauten's or the project's own, stays a separate step.</li>
</ul></section>

<section id="prove"><h2>Prove a kernel function</h2>
<p><code>cargo tauten init --proofs &lt;crate&gt; --write</code> sets up the gate. <code>cargo tauten proofs</code> runs it and records one outcome per claim. Without Docker or the image nothing is checked and nothing passes. What counts as proved: <a href="/proofs/">Proofs</a>. To reuse one Lean module without the rest: <a href="/proofs/#reuse">Lean module only</a>.</p>
{site.snippet_panel("proof-commands", title="README.md", label="Proof commands")}</section>

<section id="agent"><h2>Tell the agent</h2>
<p><code>cargo tauten init --write</code> adds <code>AGENTS.tauten.md</code>. Point your <code>AGENTS.md</code> or <code>CLAUDE.md</code> at it.</p>
{panel(code_html(raw.split(chr(10) * 2, 1)[1].split(chr(10) * 2, 1)[0], "text"), caption=site.src("crates/tauten-check/agents.md", "AGENTS.tauten.md") + " (first paragraph)", label="Start of the agent profile", wrapped=True)}
<p><a href="/agents/AGENTS.tauten.md">The whole file</a></p></section>

<section id="commands"><h2>Commands</h2>
{_commands(site)}
<p><code>cargo tauten explain &lt;ID&gt;</code> prints any rule; they are all on <a href="/rules/">Rules</a>.</p></section>
</div>"""
    site.add("/start/", "Getting started", "Install cargo-tauten, try it without changing anything or make it a required CI check, give each crate a tier, prove kernel functions and tell the agent.", body)


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
    reuse = lean_reuse(site)
    lic_url = f"https://github.com/{site.config['repository']}/blob/{reuse['ref']}/{reuse['license']}"
    lic = f'<a href="{lic_url}">its license</a>' if site.repo_public else f"its license (<code>{esc(reuse['license'])}</code>)"
    imports = ", ".join(f"<code>{esc(i)}</code>" for i in reuse["imports"])
    body = f"""{_head("Proofs", "Proved means a Lean theorem about the Charon/Aeneas translation of the crate that ships, checked by the five steps below.")}
<div class="wrap">
<p>tauten's own decisions (tiers, severity, exceptions, the baseline ratchet, the effects verdict) live in the <code>no_std</code> crate <code>tauten-check-kernel</code> and are proved this way. <code>cargo tauten init --proofs</code> sets up the same gate for your kernel crates.</p>
<section id="gate"><h2>The gate</h2>
<ol class="steps">{steps}</ol></section>
<section id="claims"><h2>Claims</h2>
<p><strong>{len(proved)} of {len(claims)} claims proved</strong>, recorded on <code>{esc(recorded)}</code>. Claims about <code>tauten-proof-instances</code> cover the code <code>#[refined]</code>, <code>#[requires]</code> and <code>#[ensures]</code> generate for listed examples. The macros themselves are not verified.</p>
{tbl}</section>
<section id="reuse"><h2>Lean module only</h2>
<p>A Lean project that already builds against Aeneas can reuse <code>Tauten.Machine</code> (reachability, invariants, worlds and discharge for step machines) without the CLI or any Rust crate. Vendor the file at a pinned commit (tauten {esc(reuse["version"])}) with {lic}, and commit a checksum file for both. Fetching happens once, when the pin changes; the proof build needs no network.</p>
{site.snippet_panel("reuse-lean", title="docs/ADOPTING.md", label="Vendoring Tauten.Machine at a pinned commit")}
{site.snippet_panel("reuse-sha", title="docs/ADOPTING.md: TAUTEN.sha256", label="Checksum file")}
<p>The module imports {imports} and nothing else: Lean {esc(reuse["lean"])} with the Aeneas Lean library, as in the public proofs image. Keep the project's own gate and axiom audit unchanged; tauten's gate audits the same file, {site.src("proofs/Tauten/Machine.lean")}, to Lean's three standard axioms (the build compares the two). Change the pin and the checksums together, in one reviewed change.</p>
<p class="small muted">The build checks that the pin is a commit of tauten {esc(reuse["version"])} on the pinned history and that each checksum is the sha256 of the downloaded file at that commit.</p></section>
<section id="not"><h2>Not proved, and trusted</h2>
<p>Source scanning, diagnostic mapping, the rustc wrapper, workspace loading and the CLI are tested, not proved; so is the authority check (TAU-A002). Charon, Aeneas, Lean and the steps around them are trusted: {trust}.</p></section>
</div>"""
    site.add("/proofs/", "Proofs", f"Lean proofs over tauten's decision code: {len(proved)} of {len(claims)} claims proved, how to reuse one Lean module, and what is trusted.", body)


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
