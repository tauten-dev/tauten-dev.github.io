"""The home page (spec section 4)."""

from __future__ import annotations

from . import md
from .common import crate_cards, install_block, results_html, tier_meanings
from .render import code_html, esc, inline_md, panel, rule_chip, status_badge
from .site import Site

CARDS = [
    ("Unwrap on input", "TAU-P001", "card-unwrap"),
    ("Unchecked arithmetic", "TAU-N001", "card-overflow"),
    ("A stub left behind", "TAU-S001", "card-stub"),
    ("A dropped error", "TAU-E001", "card-ignored"),
    ("A wildcard arm", "TAU-M001", "card-wildcard"),
    ("Reading the clock", "TAU-A001", "card-clock"),
]

NOT_ENFORCED = [
    "Capability discipline, not containment. Dependencies, <code>unsafe</code>, FFI and build scripts keep ambient access.",
    "Panic rules are syntactic. Panics inside dependencies and allocation failure are not covered.",
    "Contracts and refinements are runtime checks. Nothing is proved statically yet.",
    "Rust cannot express per-function effect rows; tiers are a coarse stand-in.",
    "An agent can still add <code>.clone()</code> to quiet the borrow checker, or a reasoned <code>#[expect]</code> (visible in review).",
    "Async cancellation safety is not enforceable.",
    'The placeholder-comment rule (<a href="/rules/tau-s002/">TAU-S002</a>) is a heuristic.',
]


def build(site: Site) -> None:
    d = site.data
    sm = site.status_map
    rules = d.rules
    n = len(rules)
    unwrap = next(f for f in d.fixtures if f.name == "rej-unwrap")
    block = site.captures["check-fixtures"].block("TAU-P001", "rej-unwrap")

    first = site.config["first_release"]
    source = ("the source is on GitHub" if site.repo_public else "the source repository is not public yet")
    registry = (f'Version {first} is on <a href="https://crates.io/crates/cargo-tauten">crates.io</a>; {source}.'
                if site.published else "Not on crates.io yet.")
    publication = (f"Publication: {first} is on crates.io; {source}."
                   if site.published else
                   f'Publication: the release workflow is {status_badge(sm["publication"])}; nothing is on crates.io yet.')
    hero = f"""
<section class="hero"><div class="wrap">
<p class="eyebrow">A strictness profile for Rust · pre-release</p>
<h1>Strict Rust for code written by agents. <span class="second">Every rule names what enforces it.</span></h1>
<p class="lede">Agents rarely get memory safety wrong in Rust: the compiler stops them. What gets through is everything else: <code>unwrap</code> on input, unchecked arithmetic, <code>todo!()</code> left behind, errors silently dropped, library code that quietly reads the clock. tauten turns those into checked rules, sorted by how much authority a crate holds, each with a stable ID and a repair hint an agent can act on.</p>
<div class="actions"><a class="btn" href="/start/">Get started</a><a href="/rules/">Read the {n} rules</a><a href="/enforcement/">What is not enforced</a></div>
<p class="maturity"><span class="badge b-planned">Pre-release</span> <span>{registry} A dev-split pilot has run; no held-out benchmark result yet. <a href="/benchmark/">Benchmark</a></span></p>
<figure class="hero-fig">
<div class="pair">
{site.fixture_panel(unwrap, marks={block["line"]: block["column"]}, title="rej-unwrap/src/lib.rs")}
{site.capture_panel("check-fixtures", block["text"], title="$ cargo tauten check", label="cargo tauten check output for rej-unwrap")}
</div>
<figcaption><span class="chip prov">Captured</span> A test fixture from the tauten repository and the output <code>cargo tauten check</code> printed for it at <code>{site.short}</code>. It was not written by an agent; agent behaviour has not been measured yet.</figcaption>
</figure>
</div></section>"""

    cards = []
    for title, rid, snip in CARDS:
        rule = d.rule_by_id[rid]
        s = site.snippets[snip]
        code = panel(code_html(s["code"], "rust"), label=f"Excerpt from {s['path']}",
                     title=esc(s["path"].removeprefix("fixtures/cases/")))
        cards.append(f'<div class="card"><div class="top">{rule_chip(rid)}</div><h3>{title}</h3>'
                     f'<p class="mini-why">{inline_md(rule["why"])}</p>{code}</div>')
    mistakes = f"""
<section class="section"><div class="wrap">
<p class="eyebrow">01 / What gets through</p>
<h2>Six mistakes the compiler accepts</h2>
<p class="lede">Each compiles. Each is a fixture in the tauten repository, and <code>cargo tauten check</code> flags it with the rule shown.</p>
<div class="grid-3">{"".join(cards)}</div>
</div></section>"""

    meanings = tier_meanings(site)
    cols = []
    excerpts = {
        "edge": site.snippet_panel("edge-main", tier="edge", compact=True, title="acc-edge/src/main.rs"),
        "core": site.snippet_panel("core-load", "core-stamp", tier="core", compact=True, title="acc-core/src/lib.rs"),
        "kernel": site.snippet_panel("kernel-head", "kernel-withdraw", tier="kernel", compact=True, title="acc-kernel/src/lib.rs"),
    }
    for i, tier in enumerate(("edge", "core", "kernel")):
        meaning, rejected = meanings[tier]
        if i:
            cols.append('<div class="arrow" aria-hidden="true">depends on</div>')
        cols.append(f'<div class="tcol tier-{tier}"><h3><span class="chip chip-tier {tier[0]}">{tier}</span></h3>'
                    f'<dl><dt>Meaning</dt><dd>{inline_md(meaning)}</dd><dt>Examples of what is rejected</dt>'
                    f'<dd>{inline_md(rejected)}</dd></dl>{excerpts[tier]}</div>')
    forged = next(f for f in d.fixtures if f.name == "rej-forged-capability")
    fblock = site.captures["check-fixtures"].block("TAU-A002", "rej-forged-capability")
    tiers = f"""
<section class="section"><div class="wrap">
<p class="eyebrow">02 / Tiers</p>
<h2>Rules follow authority</h2>
<p class="lede">Each crate declares how much of the world it may touch. The less it can touch, the stricter its rules.</p>
{panel(code_html(md.section(d.core.blob("README.md"), "How it works").split("```toml", 1)[1].split("```", 1)[0].strip(), "toml"), title="Cargo.toml", label="Tier declaration in a crate manifest", provenance="From the repo")}
<figure>
<div class="tiers">{"".join(cols)}</div>
<figcaption>Three accept fixtures. <code>cargo tauten check</code> reports no profile errors for them. The Meaning and Rejected cells are from the tauten README.</figcaption>
</figure>
<p class="boundary">Dependencies point inward only: edge → core → kernel (<a href="/rules/tau-t002/">TAU-T002</a>).</p>
<h3>A structural rule: authority minted in a core crate</h3>
<figure><div class="pair">
{site.snippet_panel("forged-sneaky", tier="core", title="rej-forged-capability/src/lib.rs", numbers=True, marks={fblock["line"]: fblock["column"]})}
{site.capture_panel("check-fixtures", fblock["text"], title="$ cargo tauten check", label="cargo tauten check output for rej-forged-capability")}
</div><figcaption><span class="chip prov">Captured</span> A fixture defines its own <code>Authority::acquire</code> and calls it from library code. The check reports the call by name in a core crate.</figcaption></figure>
</div></section>"""

    json_line = site.captures["check-fixtures-json"]
    import json as _json
    p001 = next(_json.loads(line) for line in json_line.body.splitlines()
                if '"TAU-P001"' in line and '"rej-unwrap"' in line)
    pretty = _json.dumps(p001, indent=2, ensure_ascii=False)
    readme = d.core.blob("README.md")
    loop = f"""
<section class="section"><div class="wrap">
<p class="eyebrow">03 / The loop</p>
<h2>Diagnostics an agent can act on</h2>
<ol class="workflow">
<li><div><h3>One diagnostic per line</h3><p><code>cargo tauten check --format json</code> prints one JSON object per finding: the rule ID, where it is, why the rule exists, how to fix it, and what enforces it.</p><p class="small muted">Shown pretty-printed for reading; the CLI prints it on one line.</p></div>
<div>{panel(code_html(pretty, "json"), title="$ cargo tauten check --format json", label="One JSON diagnostic", provenance="Captured", wrapped=True)}</div></li>
<li><div><h3>The rule, on demand</h3><p><code>cargo tauten explain TAU-P001</code> prints the full rule: why, the fix, the level per tier, and the lints behind it.</p></div>
<div>{site.capture_panel("explain-p001")}</div></li>
<li><div><h3>The profile cannot be loosened from inside the project</h3>
<p>The CLI owns the profile: it runs one <code>cargo check</code> with itself as the workspace rustc wrapper, adding each crate's tier lints and a generated clippy configuration. Deleting or loosening a project's own <code>clippy.toml</code> or <code>[lints]</code> table does not weaken the check.</p>
<p>Exceptions are possible only as <code>#[expect(lint, reason = "...")]</code> on the smallest item, and never for stubs, <code>unsafe</code> outside the edge, or anything in a kernel crate.</p></div>
<div><p class="boundary small">Quoted from the tauten README at <code>{site.short}</code>.</p></div></li>
</ol>
</div></section>"""
    assert "does not weaken the check" in " ".join(readme.split()), "README wording drifted"

    groups = []
    for key, label in (("rustc", "rustc"), ("clippy", "Clippy, at levels the profile sets"), ("tauten", "tauten structural checks")):
        members = [r for r in rules if r["enforced_by"] == key]
        links = ", ".join(f'<a href="/rules/{r["id"].lower()}/">{inline_md(r["title"])}</a>' for r in members[:4])
        groups.append(f'<li><span class="count">{label}: {len(members)} rules.</span> <span class="small">{links}{" …" if len(members) > 4 else ""}</span></li>')
    never = len(site.no_exception_rules)
    groups.append(f'<li><span class="count">{never} rules admit no exception;</span> in kernel crates, none do (<a href="/rules/tau-x004/">TAU-X004</a>).</li>')
    gaps = "".join(f"<li>{g}</li>" for g in NOT_ENFORCED)
    gaps += "<li><strong>Only a dev-split pilot has measured agent behaviour, and it could not separate the arms. Nothing here supports a claim that agents make fewer mistakes.</strong></li>"
    ledger = f"""
<section class="section"><div class="wrap">
<p class="eyebrow">04 / Enforced, and not</p>
<h2>What is enforced, and what is not</h2>
<div class="ledger">
<div><h3>Enforced</h3><ul>{"".join(groups)}</ul></div>
<div class="gap"><h3>Not enforced</h3><ul>{gaps}</ul></div>
</div>
<p><a href="/enforcement/">The full table →</a></p>
</div></section>"""

    family = f"""
<section class="section"><div class="wrap">
<p class="eyebrow">05 / The family</p>
<h2>Four crates, one profile</h2>
{crate_cards(site, compact=True)}
<p><a href="/crates/">All crates →</a></p>
</div></section>"""

    rej, acc = site.fixture_counts()
    sm = site.status_map
    evidence = f"""
<section class="section"><div class="wrap">
<p class="eyebrow">06 / Evidence</p>
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
<li>Pilot with a real agent: {status_badge(sm["bench-pilot"])}</li>
<li>Proof tier: {status_badge(sm["proof-tier"])}</li>
<li>Contracts for <code>async fn</code> and generic newtypes; Kani lowering.</li>
<li>{publication}</li>
</ul></div>
</div>
<h3 style="margin-top:32px">Benchmark results</h3>
{results_html(site, compact=True)}
</div></section>"""

    closing = f"""
<section class="section"><div class="wrap">
<h2>Try it on a workspace</h2>
{install_block(site)}
<div class="actions"><a class="btn" href="/start/">Get started</a><a href="/rules/">Rules</a><a href="/status/">Status</a></div>
</div></section>"""

    body = hero + mistakes + tiers + loop + ledger + family + evidence + closing
    site.add("/", "tauten: strict Rust for code written by agents",
             "A strictness profile for Rust written by AI agents: tiered rules, each with a stable ID, a repair hint and what enforces it. Pre-release.",
             body, full_title=True)
