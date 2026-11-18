#!/usr/bin/env python3
"""Build tauten.dev into public/ from the site sources and one pinned core commit.

    uv run --with markdown --with pygments python website/build.py
    uv run --with markdown --with pygments python website/build.py --check
    python3 -m http.server 8000 --bind 127.0.0.1 --directory public

--core and --core-ref default to website/config.toml. Every core file is read
with `git show <ref>:<path>`; the working tree of the core repository is never
read. --check runs every drift check without writing public/. The build fails
on any drift (spec section 7.6); see README.md for the list.
"""

from __future__ import annotations

import argparse
import datetime as dt
import gzip
import json
import shutil
import sys
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = ROOT / "public"
sys.path.insert(0, str(HERE))

from sitegen import checks, pages_docs, pages_home, pages_ref  # noqa: E402
from sitegen.errors import BuildError  # noqa: E402
from sitegen.site import Site  # noqa: E402
from sitegen.source import Core, load, load_captures, load_results, load_snippets, status_item  # noqa: E402

import contrast  # noqa: E402

BRAND = ["tauten-icon.svg", "tauten-icon-dark.svg", "favicon.svg"]
ASSETS = ["site.css", "theme.js", "copy.js", "rules.js"]
CSS_BUDGET = 20 * 1024
HOME_BUDGET = 60 * 1024


def build(args: argparse.Namespace) -> int:
    config = tomllib.loads((HERE / "config.toml").read_text())
    core_path = Path(args.core) if args.core else (ROOT / config["core"])
    ref = args.core_ref or config["core_ref"]
    core = Core(core_path.resolve(), ref)
    data = load(core)
    status_map = {k: status_item(data, v["milestone"], v["item_contains"])
                  for k, v in tomllib.loads((HERE / "status-map.toml").read_text()).items()}
    site = Site(
        root=ROOT, config=config, data=data,
        captures=load_captures(HERE / "captures"),
        snippets=load_snippets(core, HERE / "snippets.toml"),
        status_map=status_map,
        results=load_results(HERE / "data" / "results.json"),
        built_at=dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
    )

    pages_home.build(site)
    pages_docs.start(site)
    pages_ref.crates_index(site)
    pages_ref.crate_pages(site)
    pages_ref.rules_index(site)
    pages_ref.rule_pages(site)
    pages_docs.enforcement(site)
    pages_docs.agents(site)
    pages_docs.benchmark(site)
    pages_docs.proofs(site)
    pages_docs.status(site)
    pages_docs.not_found(site)

    files = {f"assets/{n}" for n in ASSETS + BRAND} | set(site.extra_files)
    if (HERE / "assets" / "og.png").is_file():
        files.add("assets/og.png")

    problems: list[str] = []
    stale, stale_warn = checks.captures(site, args.allow_stale_captures)
    groups = [
        ("1 rules.toml vs docs/RULES.md", checks.rules_vs_markdown(site)),
        ("2 rule IDs in generated HTML", checks.rule_ids_in_html(site)),
        ("3 fixture expectations", checks.fixture_ids(site)),
        ("4 snippets, captures, status rows", stale),
        ("5 results.json", []),  # validated while loading; a failure stops the build earlier
        ("6 wording and claim tags", checks.wording(site)),
        ("7 links, anchors, ids, third-party requests", checks.links(site, files)),
        ("+ colour contrast (WCAG AA)", contrast.check()),
    ]
    css_size = (HERE / "assets" / "site.css").stat().st_size
    if css_size > CSS_BUDGET:
        groups.append(("+ CSS budget", [f"site.css is {css_size} bytes; the budget is {CSS_BUDGET}"]))
    for name, found in groups:
        mark = "ok" if not found else f"FAILED ({len(found)})"
        print(f"check {name}: {mark}")
        for line in found:
            print(f"    {line}")
        problems += found
    for line in stale_warn:
        print(f"warning: {line}")
    upstream = checks.status_counts(site)
    for line in upstream:
        print(f"upstream drift (reported, not fatal): {line}")
    home_parts = [site.pages["/"].encode()] + [(HERE / "assets" / n).read_bytes() for n in ("site.css", "theme.js", "copy.js")]
    home = sum(len(gzip.compress(b)) for b in home_parts) + sum(len(core.blob_bytes(f"assets/brand/{n}")) for n in BRAND[:2])
    if home > HOME_BUDGET:
        problems.append(f"home page transfers {home} bytes gzipped; the budget is {HOME_BUDGET}")
    print(f"home page weight: {home} bytes gzipped, excluding og.png (budget {HOME_BUDGET}); site.css {css_size} bytes")
    if problems:
        print(f"\nbuild failed: {len(problems)} problem(s)", file=sys.stderr)
        return 1
    if args.check:
        print(f"\ncheck passed: {len(site.pages)} pages at tauten@{core.short}; public/ not written")
        return 0

    if OUT.exists():
        shutil.rmtree(OUT)
    for path, page in site.pages.items():
        target = OUT / (path.lstrip("/") + "index.html" if path.endswith("/") else path.lstrip("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(page)
    (OUT / "assets").mkdir(exist_ok=True)
    for name in ASSETS:
        shutil.copy(HERE / "assets" / name, OUT / "assets" / name)
    for name in BRAND:
        (OUT / "assets" / name).write_bytes(core.blob_bytes(f"assets/brand/{name}"))
    if (HERE / "assets" / "og.png").is_file():
        shutil.copy(HERE / "assets" / "og.png", OUT / "assets" / "og.png")
    for rel, content in site.extra_files.items():
        (OUT / rel).parent.mkdir(parents=True, exist_ok=True)
        (OUT / rel).write_bytes(content)
    (OUT / "CNAME").write_text(config["domain"] + "\n")
    (OUT / ".nojekyll").write_text("")
    rej, acc = site.fixture_counts()
    info = {"core_commit": core.ref, "core_date": core.date, "built_at": site.built_at,
            "rules": len(data.rules), "fixtures": {"reject": rej, "accept": acc},
            "published": site.published, "allow_stale_captures": bool(args.allow_stale_captures)}
    (OUT / "build-info.json").write_text(json.dumps(info, indent=2) + "\n")
    urls = "".join(f"<url><loc>{config['site_url']}{p}</loc></url>" for p in sorted(site.pages) if p != "/404.html")
    (OUT / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n'
                                     f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n')
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {config['site_url']}/sitemap.xml\n")
    print(f"\nwrote {len(site.pages)} pages to {OUT} from tauten@{core.short} ({core.date})")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--core", help="path to the core repository (default: config.toml)")
    parser.add_argument("--core-ref", help="full commit SHA to build from (default: config.toml)")
    parser.add_argument("--check", action="store_true", help="run the drift checks without writing public/")
    parser.add_argument("--allow-stale-captures", action="store_true",
                        help="local preview only: accept captures made at another commit; publish.py refuses the result")
    args = parser.parse_args()
    try:
        sys.exit(build(args))
    except BuildError as error:
        print(f"build failed: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
