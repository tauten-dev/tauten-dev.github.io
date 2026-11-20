"""The home page: pitch, install, three examples, what tauten does not do."""

from __future__ import annotations

import json
import re

from . import md
from .common import install_block, status_line
from .errors import BuildError
from .render import diag_html, esc, inline_md, panel
from .site import Site

PITCH = ("A strict way to write Rust. Library code takes the clock, files and environment as parameters, "
         "says so in its signature, and its pure core can be proved in Lean.")


def mapping_limit(site: Site) -> str:
    """The capability gap, verbatim from the docs/MAPPING.md row."""
    m = re.search(r'Not confinement:.*?never "sandbox"\.', site.data.core.blob("docs/MAPPING.md"))
    if not m:
        raise BuildError("docs/MAPPING.md no longer carries the 'Not confinement' sentence")
    return inline_md(m.group(0))


def gap(site: Site, starts: str) -> str:
    """One Known gaps bullet from docs/STATUS.md, verbatim, as Markdown source."""
    gaps = md.section(site.data.core.blob("docs/STATUS.md"), "Known gaps")
    m = re.search(rf"^- ({re.escape(starts)}.*?)(?=^- |^\n|^#|\Z)", gaps, re.M | re.S)
    if not m:
        raise BuildError(f"Known gaps bullet starting {starts!r} not found")
    return " ".join(m.group(1).split())


def _limit(text: str) -> str:
    return f'<p class="limit"><strong>Limit.</strong> {text}</p>'


def _diag(site: Site, text: str, label: str) -> str:
    return panel(diag_html(text, site.rule_ids), caption="$ cargo tauten check", label=label, diag=True)


def _authority(site: Site) -> str:
    block = site.captures["check-fixtures"].block("TAU-A001", "rej-ambient-clock")
    before = site.snippet_panel("ambient-clock", title="rej-ambient-clock/src/lib.rs", tier="core",
                                marks={block["line"]: block["column"]}, label="A core crate that reads the clock")
    after = site.snippet_panel("effects-age", title="acc-effects/src/lib.rs", tier="core",
                               label="A core crate that takes the clock as a parameter")
    return f"""<h3 id="authority">Authority is a parameter</h3>
<p>Core crates may not read the clock, the filesystem or the environment. They take them as arguments, and only the edge crate creates them.</p>
<figure class="ex">{before}{_diag(site, block["text"], "cargo tauten check output for rej-ambient-clock")}
<p class="then">Accepted: the clock arrives as an argument, and <code>cargo tauten check</code> reports nothing.</p>
{after}</figure>
{_limit(mapping_limit(site) + ' <span class="muted">(docs/MAPPING.md)</span>')}"""


def _effects(site: Site) -> str:
    block = site.captures["check-fixtures"].block("TAU-F001", "rej-effects")
    lines = block["text"].split("\n")
    if not lines[-1].startswith("  = fix: "):
        raise BuildError("TAU-F001 block no longer ends with its fix line")
    shown = diag_html("\n".join(lines[:-1]), site.rule_ids) + '<span class="line elide">  = fix: …</span>'
    src = site.snippet_panel("effects-load", title="rej-effects/src/lib.rs", tier="core",
                             marks={block["line"]: block["column"]}, label="A function that declares more than it is given")
    out = panel(shown, caption="$ cargo tauten check", label="cargo tauten check output for rej-effects", diag=True)
    return f"""<h3 id="effects">Effects are in the signature</h3>
<p><code>#[effects(..)]</code> states what a function may do. The check compares it with the parameters and return type. Here a read-only directory cannot grant <code>fs_write</code>, and the crate sets <code>effects = "required"</code>, so the mismatch is an error. New in {esc(site.config["latest_release"])}.</p>
<figure class="ex">{src}{out}</figure>
{_limit('Parameter types are classified by name, and the effects of called functions are not seen (<a href="/rules/tau-f001/">TAU-F001</a>).')}"""


def _proof(site: Site) -> str:
    cap = site.captures["check-proofs-subsume"]
    chunks = cap.body.rstrip("\n").split("\n\n")
    first = next((c for c in chunks if c.startswith("subsumed[TAU-N001]") and "lib.rs:8:" in c), None)
    kept = next((c for c in chunks if c.startswith("error[TAU-N001]") and "lib.rs:21:" in c), None)
    summary = chunks[-1]
    if not first or not kept or not summary.startswith("tauten: "):
        raise BuildError("capture check-proofs-subsume no longer has the blocks the home page shows")
    out = panel(diag_html(first, site.rule_ids) + '<span class="line elide">…</span>'
                + diag_html(kept, site.rule_ids) + '<span class="line"> </span>' + diag_html(summary, site.rule_ids),
                caption=f"$ {esc(cap.cmd)}", label="cargo tauten check output for the proof fixture", diag=True)
    claims = json.loads(site.data.core.blob("fixtures/proofs-subsume/proofs/claims.json"))["claims"]
    double = next(c for c in claims if c["function"] == "double")
    marks = {}
    for c in (first, kept):
        m = re.search(r"lib\.rs:(\d+):(\d+)", c)
        marks[int(m.group(1))] = int(m.group(2))
    src = site.snippet_panel("sub-add-capped", "sub-double", title="sub-kernel/src/lib.rs", tier="kernel",
                             marks=marks, label="Two kernel functions with arithmetic")
    thm = site.snippet_panel("sub-theorem", title="proofs/Proofs/SubKernel.lean", tail="  …",
                             label="The Lean theorem about add_capped")
    return f"""<h3 id="proofs">A proof replaces a finding</h3>
<p>In a kernel crate, a function proved in Lean never to fail has its arithmetic and indexing findings reported as subsumed. Without such a proof they stay errors.</p>
<figure class="ex">{src}
<p class="then">The theorem about <code>add_capped</code> has no hypotheses, so it covers every input.</p>
{thm}{out}</figure>
<p><code>double</code> stays an error. Its claim's outcome is <code>{esc(double["outcome"])}</code>: “{esc(double["detail"])}.”</p>
{_limit(inline_md(gap(site, "tauten trusts the project's gate output")) + ' <span class="muted">(docs/STATUS.md, Known gaps)</span>')}"""


def build(site: Site) -> None:
    gh = f"https://github.com/{site.config['repository']}/tree/{site.ref}/fixtures"
    prov = (f'<a href="{gh}">Fixtures</a>' if site.repo_public else "Fixtures") + \
        f" and output from tauten@<code>{site.short}</code>."
    body = f"""
<section class="hero"><div class="wrap">
<h1><img class="logo-light" src="/assets/tauten-icon.svg" width="44" height="44" alt=""><img class="logo-dark" src="/assets/tauten-icon-dark.svg" width="44" height="44" alt="">tauten</h1>
<p class="pitch">{PITCH}</p>
<p class="status">{status_line(site)}</p>
{install_block(site)}
</div></section>
<div class="wrap">
<section id="does"><h2>What it does</h2>
{_authority(site)}
{_effects(site)}
{_proof(site)}
<p class="small muted">{prov}</p>
</section>
<section id="does-not"><h2>What it does not do</h2>
<ul>
<li>It is a discipline for the code you write. Dependencies, <code>unsafe</code> and FFI keep ambient access.</li>
<li>Only the listed theorems are proved. Charon, Aeneas and Lean are trusted.</li>
<li>We measured defect reduction and did not find it. <a href="/status/#benchmark">Status</a>.</li>
</ul>
</section>
<p class="next"><a href="/start/">Get started</a> · <a href="/proofs/">Proofs</a> · <a href="/rules/">All {len(site.data.rules)} rules</a></p>
</div>"""
    site.add("/", "tauten: a strict discipline for Rust, with Lean proofs", PITCH, body, full_title=True)
