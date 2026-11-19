"""Components shared by several pages."""

from __future__ import annotations

import re

from .errors import BuildError
from .render import badge, code_html, copy_line, esc, inline_md, panel
from .site import Site

MEASURED = ("We measured defect reduction and did not find it: 2 escaped defects in 200 unassisted trials; "
            "0 of 120 sampled findings were reachable defects.")


def measured_sentence(site: Site) -> str:
    """The one benchmark sentence the site carries, checked against the proposal at the pinned commit."""
    text = " ".join(site.data.core.blob("docs/DISCIPLINE-PROPOSAL.md").split())
    if MEASURED not in text:
        raise BuildError("docs/DISCIPLINE-PROPOSAL.md no longer carries the benchmark sentence the site quotes")
    return MEASURED


def status_line(site: Site) -> str:
    """The one honest status sentence the home and status pages share."""
    registry = (f'Version {site.config["latest_release"]} is on <a href="https://crates.io/crates/cargo-tauten">crates.io</a>; '
                'the discipline APIs are in progress.'
                if site.published else "Not on crates.io yet.")
    return f'{registry} No defect-reduction claim (<a href="/status/#benchmark">why</a>).'


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


def install_block(site: Site) -> str:
    rv = site.data.workspace["workspace"]["package"]["rust-version"]
    cmd = copy_line("cargo install --locked cargo-tauten")
    if site.published:
        return f"{cmd}<p class=\"small muted\">Needs Rust {rv} or newer, with clippy.</p>"
    first = site.config["first_release"]
    return (f'<p><span class="chip">Not published yet</span></p>{cmd}'
            f'<p class="small muted">Available from the first release ({first}). Nothing is on crates.io yet, '
            f'so this command does not work today. It will need Rust {rv} or newer, with clippy.</p>')


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


# ---------------------------------------------------------------- discipline ---
# The four ideas plus proofs, shared by the home page and /discipline/.
# States: "exercised" = released and run against real input; "progress" = being
# built on the core's discipline-d0 branch (milestone D0); "planned" = approved
# in docs/DISCIPLINE-PROPOSAL.md, not started.

EFFECTS_CODE = """// before: nothing in the signature says it reads the clock and a file
pub fn renew_now(slot: usize, ttl: u64) -> Result<(), LeaseError> { ... }
// after: capabilities as parameters, and the row declared
#[effects(clock, fs_read, fs_write, fail)]
pub fn renew_now<C: Clock>(caps: &LeaseCaps<'_, C>, slot: Slot, ttl: Ttl) -> Result<(), LeaseError> { ... }"""

DISCIPLINE = [
    {
        "key": "capabilities", "title": "Authority passed explicitly",
        "line": "Core code takes the clock, the environment or a directory as a parameter; only the edge creates them.",
        "strength": [("compiler", "capabilities have private constructors"), ("lint", "ambient APIs are banned outside the edge, and only the edge may mint authority")],
        "states": [("exercised", "Exercised", "<code>tauten::cap</code>, TAU-A001, TAU-A002 and TAU-G001, released"),
                   ("progress", "In progress", "a <code>Cap</code> marker trait, <code>#[derive(Cap)]</code> bundles and a read-only directory")],
        "snippet": "disc-cap",
        "gap": 'Not confinement: dependencies, <code>unsafe</code>, FFI, build scripts and unlisted crates keep ambient access. Claim "discipline", never "sandbox".',
        "gap_src": "docs/MAPPING.md",
    },
    {
        "key": "effects", "title": "Effects visible in signatures",
        "line": "Capability parameters, <code>Result</code> and <code>async</code> are a function's effect row; <code>#[effects(..)]</code> states it and a check compares the two.",
        "strength": [("compiler", "<code>fail</code> through <code>Result</code>, <code>suspend</code> through <code>async</code>"), ("lint", "declared row against the signature, matched by type name"), ("proved", "a kernel function's row is empty: its Aeneas translation is a pure Lean function")],
        "states": [("progress", "In progress", "<code>#[effects(..)]</code> and the signature check"),
                   ("planned", "Planned", "a committed <code>effects.lock</code> that fails when a public row widens")],
        "code": EFFECTS_CODE,
        "gap": "Rust cannot express per-function effect rows: a row derived from the signature is an upper bound with known holes, such as effects carried in closures or trait objects.",
    },
    {
        "key": "evidence", "title": "Checked evidence",
        "line": "A check returns evidence that borrows what it checked, so changing the state before acting on it does not compile.",
        "strength": [("compiler", "the evidence holds a borrow of the checked state"), ("bounded", "check-then-act against files or a database is model-checked with TLC, up to a bound")],
        "states": [("progress", "In progress", "<code>tauten::origin::Evidence</code> and <code>#[evidence]</code>")],
        "snippet": "disc-origin",
        "gap": "Freshness against external state cannot be typed, and once evidence is redeemed it no longer borrows the state; past that point it is convention.",
    },
    {
        "key": "refinements", "title": "Refinement types",
        "line": "A value with a rule is a type that can only be built through its check; in kernel crates that check is proved.",
        "strength": [("compiler", "construction only through <code>try_new</code>"), ("lint", "a <code>provable</code> type must stay inside a checkable predicate fragment"), ("proved", "per type in kernel crates; today, the macro output for listed instances")],
        "states": [("exercised", "Exercised", "<code>#[refined]</code>, <code>#[newtype]</code>, <code>#[requires]</code> and <code>#[ensures]</code>, released"),
                   ("planned", "Planned", "the <code>provable</code> fragment and drafted Lean statements")],
        "snippet": "disc-refine",
        "gap": "No static predicate propagation: <code>Percent + Percent</code> is checked again at runtime, and a predicate outside the fragment is tested, never proved.",
    },
    {
        "key": "proofs", "title": "Proofs over the shipped code, on a cadence",
        "line": "Kernel crates are translated to Lean with Charon and Aeneas; theorems about that translation are axiom-audited and calibrated with mutants.",
        "strength": [("proved", "Lean theorems over the Aeneas translation of the code that ships"), ("bounded", "TLC configurations for protocols; never counted as proved")],
        "states": [("exercised", "Exercised", "tauten's own kernel, and <code>cargo tauten proofs</code> for yours"),
                   ("planned", "Planned (0.1)", "<code>ship</code>, <code>verify --level</code> and per-claim fingerprints"),
                   ("planned", "Planned", "TLC configurations as claims")],
        "gap": "Only the listed theorems are proved; Charon, Aeneas and Lean are trusted, and Aeneas accepts a narrow subset of Rust, so kernel code has to be written in that shape.",
    },
]

CADENCE = [
    ("edit", "cargo tauten check", "every change", "lints, tiers, claim freshness; stable Rust, no Docker", ("exercised", "Exercised")),
    ("feature", "cargo tauten ship", "before the agent reports done", "re-extract, re-prove stale claims only, mutants for changed functions, quick TLC configs", ("planned", "Planned (0.1)")),
    ("full", "cargo tauten verify --level full", "merge or nightly", "every claim from a clean state, every mutant, all TLC configs", ("planned", "Planned (0.1)")),
    ("release", "cargo tauten verify --level release", "on a tag", "the full level in the pinned image by digest", ("planned", "Planned (0.1)")),
]


def state_badges(idea: dict, short: bool = False) -> str:
    seen, out = set(), []
    for kind, label, _what in idea["states"]:
        if short and label in seen:
            continue
        seen.add(label)
        out.append(badge(kind, label))
    return " ".join(out)


def ideas(site: Site) -> list[tuple[str, str, str, str]]:
    """(anchor, title, state badges, one line) per idea, for the home page."""
    return [(i["key"], i["title"], state_badges(i, short=True), i["line"]) for i in DISCIPLINE]
