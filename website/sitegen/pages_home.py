"""The home page: pitch, install, the four ideas, the cadence, links.
Everything else lives on /discipline/, /proofs/, /start/ and /status/."""

from __future__ import annotations

from .common import ideas, install_block, status_line
from .site import Site


def build(site: Site) -> None:
    block = site.captures["check-fixtures"].block("TAU-A001", "rej-ambient-clock")

    idea_items = "".join(f'<li><a href="/discipline/#{key}">{title}</a> {state} <span class="muted">{line}</span></li>'
                         for key, title, state, line in ideas(site)[:4])
    _, ptitle, pstate, pline = ideas(site)[4]
    gh = f"https://github.com/{site.config['repository']}"
    links = [("/discipline/", "Discipline", "each idea with a before/after, what enforces it, and the honest gap"),
             ("/proofs/", "Proofs", "Lean theorems over the shipped Rust; what is proved and what is trusted"),
             ("/start/", "Start", "install, tiers, check, adopt gradually, the agent profile"),
             ("/rules/", "Rules", f"all {len(site.data.rules)} rules, each with a stable ID"),
             ("/status/", "Status", "what has been exercised, what is planned, and the benchmark")]
    if site.published:
        links.append((site.docs_url, "docs.rs", f"the <code>tauten</code> library API, {site.config['latest_release']}"))
        links.append(("https://crates.io/crates/cargo-tauten", "crates.io", "cargo-tauten and the support crates"))
    if site.repo_public:
        links.append((gh, "GitHub", site.config["repository"]))
    link_items = "".join(f'<li><a href="{href}">{label}</a> <span class="muted">{desc}</span></li>'
                         for href, label, desc in links)

    body = f"""
<section class="hero"><div class="wrap home">
<h1><img class="logo-light" src="/assets/tauten-icon.svg" width="52" height="52" alt=""><img class="logo-dark" src="/assets/tauten-icon-dark.svg" width="52" height="52" alt="">tauten</h1>
<p class="pitch">A discipline for Rust: authority passed explicitly, effects visible in signatures, checked evidence, refinement types, and proofs over the shipped code (Aeneas → Lean), with bounded model checking (TLC) for protocols.</p>
<p class="small muted">Written for code that agents write and maintain. Agents are the audience, not the claim.</p>
<p class="maturity"><span class="badge b-planned">Pre-release</span> <span>{status_line(site)}</span></p>

<h2>Use it</h2>
{install_block(site)}
<pre class="cmds"><code><span class="prompt">$</span> cargo tauten check                  <span class="muted"># every edit</span>
<span class="prompt">$</span> cargo tauten ship                   <span class="muted"># end of feature (planned 0.1)</span>
<span class="prompt">$</span> cargo tauten verify --level full    <span class="muted"># nightly (planned 0.1)</span>
<span class="prompt">$</span> cargo tauten verify --level release <span class="muted"># on a tag (planned 0.1)</span></code></pre>
{site.capture_panel("check-fixtures", block["text"], title="$ cargo tauten check", label="cargo tauten check output for the rej-ambient-clock fixture")}
<p class="small muted">Captured from the <code>rej-ambient-clock</code> fixture in the tauten repository at <code>{site.short}</code>: a core crate read the clock instead of taking it as a parameter.</p>

<h2>Four ideas</h2>
<ul class="home-links">{idea_items}</ul>
<p><a href="/proofs/"><strong>{ptitle}.</strong></a> {pstate} <span class="muted">{pline}</span></p>

<h2>More</h2>
<ul class="home-links">{link_items}</ul>
</div></section>"""
    site.add("/", "tauten: a discipline for Rust, with proofs over the shipped code",
             "A discipline for Rust: authority passed explicitly, effects visible in signatures, checked evidence, refinement types, and Lean proofs over the shipped code. Pre-release.",
             body, full_title=True)
