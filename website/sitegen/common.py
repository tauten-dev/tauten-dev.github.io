"""Components shared by several pages."""

from __future__ import annotations

import re

from .errors import BuildError
from .render import copy_line
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
    """The one status sentence the home and status pages share."""
    if site.published:
        registry = (f'Version {site.config["latest_release"]} is on '
                    '<a href="https://crates.io/crates/cargo-tauten">crates.io</a>. Early release.')
    else:
        registry = "Not on crates.io yet."
    return f'{registry} No defect-reduction claim (<a href="/status/#benchmark">why</a>).'


def tier_rows(site: Site) -> list[tuple[str, str, str]]:
    """(tier, meaning, examples of what is rejected), from the README table."""
    rows = re.findall(r"^\| `(kernel|core|edge)` \| (.+?) \| (.+?) \|$", site.data.core.blob("README.md"), re.M)
    if len(rows) != 3:
        raise BuildError("README tier table not found")
    return rows


def install_block(site: Site) -> str:
    rv = site.data.workspace["workspace"]["package"]["rust-version"]
    cmd = copy_line("cargo install --locked cargo-tauten")
    if site.published:
        return (f'{cmd}<p class="small muted">Then run <code>cargo tauten check</code> in your workspace. '
                f'Needs Rust {rv} or newer, with clippy.</p>')
    first = site.config["first_release"]
    return (f'{cmd}<p class="small muted">Available from the first release ({first}). Nothing is on crates.io yet, '
            f'so this command does not work today. It will need Rust {rv} or newer, with clippy.</p>')
