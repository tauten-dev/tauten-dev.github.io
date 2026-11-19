"""The home page: pitch, install, three tiers, status, links. Everything else
lives on the status page (rules with examples, evidence, gaps) and the docs."""

from __future__ import annotations

from .common import install_block, status_line, tier_meanings
from .render import inline_md
from .site import Site

TIER_ORDER = ("kernel", "core", "edge")


def build(site: Site) -> None:
    d = site.data
    n = len(d.rules)
    meanings = tier_meanings(site)
    block = site.captures["check-fixtures"].block("TAU-P001", "rej-unwrap")

    tiers = "".join(f'<li><span class="chip chip-tier {t[0]}">{t}</span> <span>{inline_md(meanings[t][0])}</span></li>'
                    for t in TIER_ORDER)
    gh = f"https://github.com/{site.config['repository']}"
    links = [("/status/", "Status", f"all {n} rules; open one for an example and the diagnostic it prints"),
             ("/rules/", "Rules", "the reference table, with filters"),
             ("/proofs/", "Proofs", "Lean proofs over tauten's own decision code"),
             ("/benchmark/", "Benchmark", "the dev-split pilot and the preregistered design"),
             ("/start/", "Docs", "getting started, tiers, the baseline ratchet")]
    if site.repo_public:
        links.append((gh, "GitHub", site.config["repository"]))
    if site.published:
        links.append(("https://crates.io/crates/cargo-tauten", "crates.io", "cargo-tauten and the support crates"))
    link_items = "".join(f'<li><a href="{href}">{label}</a> <span class="muted">{desc}</span></li>'
                         for href, label, desc in links)

    body = f"""
<section class="hero"><div class="wrap home">
<h1><img class="logo-light" src="/assets/tauten-icon.svg" width="52" height="52" alt=""><img class="logo-dark" src="/assets/tauten-icon-dark.svg" width="52" height="52" alt="">tauten</h1>
<p class="pitch">Strict Rust for code written by agents. The mistakes the compiler accepts (<code>unwrap</code> on input, unchecked arithmetic, stubs left behind, dropped errors, library code reading the clock) become checked rules, each with a stable ID and a repair hint.</p>
<p class="maturity"><span class="badge b-planned">Pre-release</span> <span>{status_line(site)}</span></p>

<h2>Use it</h2>
{install_block(site)}
<pre class="cmds"><code><span class="muted"># propose a tier for each crate</span>
<span class="prompt">$</span> cargo tauten init --write
<span class="prompt">$</span> cargo tauten check
<span class="muted"># one diagnostic per line, for agents</span>
<span class="prompt">$</span> cargo tauten check --format json</code></pre>
{site.capture_panel("check-fixtures", block["text"], title="$ cargo tauten check", label="cargo tauten check output for the rej-unwrap fixture")}
<p class="small muted">Captured from the <code>rej-unwrap</code> fixture in the tauten repository at <code>{site.short}</code>.</p>

<h2>What it is</h2>
<p>Each crate declares a tier; the less it may touch, the stricter its rules. Dependencies point inward only.</p>
<ul class="tier-list">{tiers}</ul>

<h2>More</h2>
<ul class="home-links">{link_items}</ul>
</div></section>"""
    site.add("/", "tauten: strict Rust for code written by agents",
             "A strictness profile for Rust written by AI agents: tiered rules, each with a stable ID, a repair hint and what enforces it. Pre-release.",
             body, full_title=True)
