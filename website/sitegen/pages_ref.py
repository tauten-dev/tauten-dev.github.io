"""Reference pages: the rules index, one page per rule, and the crates."""

from __future__ import annotations

import re

from .common import registry_links, crate_cards, crate_prose, evidence_table, ratchet_html, version_label
from .render import code_html, copy_line, diag_html, esc, inline_md, level_chip, panel, status_badge, table
from .site import Site, ref_layout
from .source import ENFORCERS, FAMILIES, TIERS, exceptions_label, level

EXC_TEXT = {"expect": "<code>#[expect]</code> + reason", "never": "never"}


def _family(rule_id: str) -> str:
    return rule_id[4]


def rules_index(site: Site) -> None:
    rules = site.data.rules
    n = len(rules)
    by = {k: site.count_by(k) for k in ("clippy", "rustc", "tauten", "convention")}
    never = len(site.no_exception_rules)
    conv = f", {by['convention']} by convention" if by["convention"] else ""
    counts = (f"{n} rules: {by['clippy']} enforced by Clippy, {by['rustc']} by rustc, {by['tauten']} by a tauten "
              f"structural check{conv}. {never} admit no exception.")
    rows, attrs = [], []
    families = []
    current = None
    body_rows = []
    for r in rules:
        fam = _family(r["id"])
        if fam != current:
            current = fam
            families.append(fam)
            body_rows.append(f'<tr class="fam" data-fam="{fam}"><th colspan="8" scope="colgroup" id="family-{fam.lower()}">'
                             f'{fam} · {FAMILIES.get(fam, fam)}</th></tr>')
        exc = exceptions_label(r)
        lv = {t: level(r, t) for t in TIERS}
        cells = [f'<a class="id" href="/rules/{r["id"].lower()}/">{r["id"]}</a>', inline_md(r["title"]),
                 *(level_chip(lv[t]) for t in TIERS), "yes" if r.get("in_tests", True) else "no",
                 EXC_TEXT[exc], ENFORCERS[r["enforced_by"]]]
        data = "".join(f' data-{t}="{lv[t]}"' for t in TIERS)
        body_rows.append(f'<tr data-id="{r["id"]}" data-fam="{fam}" data-by="{r["enforced_by"]}" data-exc="{exc}"{data}>'
                         + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
    headers = ["ID", "Rule", "kernel", "core", "edge", "Tests", "Exceptions", "Enforced by"]
    thead = "".join(f'<th scope="col">{h}</th>' for h in headers)
    tbl = (f'<div class="table-scroll" tabindex="0" role="region" aria-label="Rule table">'
           f'<table id="rules" class="sticky"><caption>Generated from <code>crates/tauten-check/rules.toml</code> at '
           f'<code>{site.short}</code>; the same columns as <code>docs/RULES.md</code>.</caption>'
           f'<thead><tr>{thead}</tr></thead><tbody>{"".join(body_rows)}</tbody></table></div>')
    notes_line = next(line for line in site.data.core.blob("docs/RULES.md").splitlines()
                      if line.startswith("In `kernel` crates no profile rule admits exceptions"))
    enforcer_opts = "".join(f'<option value="{k}">{ENFORCERS[k]}</option>' for k in ("clippy", "rustc", "tauten") if by[k])
    filters = f"""<form id="rule-filters" class="filters" hidden onsubmit="return false" aria-label="Filter rules">
<label>Search<input type="search" name="q" placeholder="ID, title or lint"></label>
<label>Applies in tier<select name="tier"><option value="">any</option><option>kernel</option><option>core</option><option>edge</option></select></label>
<label>Enforced by<select name="by"><option value="">any</option>{enforcer_opts}</select></label>
<label class="cb"><input type="checkbox" name="nx"> No exceptions</label>
<span id="rule-count" class="muted" aria-live="polite"></span></form>"""
    body = f"""<div class="wrap page-head"><p class="eyebrow">Rule reference</p><h1>Rules</h1>
<p class="lede">{counts} Each rule has a stable ID; <code>cargo tauten explain &lt;ID&gt;</code> prints it in the terminal.</p>
<p>What a rule cannot catch is listed on <a href="/enforcement/">Enforcement</a>.</p></div>
{ref_layout([(f"family-{f.lower()}", f"{f} · {FAMILIES.get(f, f)}") for f in families],
            filters + tbl + f'<p class="small">{inline_md(notes_line)}</p>', "Families")}"""
    site.add("/rules/", "Rules", f"The {n} rules of the tauten profile, with level per tier, test scope, exceptions and what enforces each.",
             body, scripts=("rules.js",))


def rule_pages(site: Site) -> None:
    rules = site.data.rules
    warnings_cap = site.captures["check-fixtures-warnings"]
    for i, r in enumerate(rules):
        rid = r["id"]
        exc = exceptions_label(r)
        toc = [("why", "Why"), ("fix", "Fix")]
        parts = [f'<h2 id="why">Why</h2><p>{inline_md(r["why"])}</p>', f'<h2 id="fix">Fix</h2><p>{inline_md(r["fix"])}</p>']
        detail = []
        if r.get("lints"):
            detail.append(f'<p><strong>Lints:</strong> {", ".join(f"<code>{esc(x)}</code>" for x in r["lints"])}</p>')
        for api in (a for a in site.data.apis if a["rule"] == rid):
            items = ", ".join(f"<code>{esc(p)}</code>" for p in api["paths"])
            head = f'Banned in {", ".join(api["tiers"])} ({esc(api["note"])}), {len(api["paths"])} {api["kind"]}{"s" if len(api["paths"]) != 1 else ""}'
            if len(api["paths"]) > 12:
                detail.append(f"<details><summary>{head}</summary><p>{items}</p></details>")
            else:
                detail.append(f"<p><strong>{head}:</strong> {items}</p>")
        if detail:
            toc.append(("what", "What it checks"))
            parts.append('<h2 id="what">What it checks</h2>' + "".join(detail))
        seen = [f for f in site.data.fixtures if rid in f.expect]
        if seen:
            toc.append(("fixtures", "Seen in fixtures"))
            figs = []
            for f in seen:
                blocks = [b for b in warnings_cap.blocks() if b["id"] == rid and b["crate"] == f.name]
                if not blocks:
                    continue
                marks = {b["line"]: b["column"] for b in blocks if b["line"]}
                text = "\n\n".join(b["text"] for b in blocks)
                figs.append(f'<figure><div class="pair">{site.fixture_panel(f, marks=marks)}'
                            f'{site.capture_panel("check-fixtures-warnings", text, title="$ cargo tauten check", label=f"Output for {f.name}")}'
                            f'</div><figcaption><span class="chip prov">Captured</span> Fixture <code>{f.name}</code> '
                            f'({f.tier or "no tier"}); it expects {", ".join(f.expect)}.</figcaption></figure>')
            parts.append('<h2 id="fixtures">Seen in fixtures</h2>' + "".join(figs))
        toc.append(("explain", "In the terminal"))
        parts.append(f'<h2 id="explain">In the terminal</h2>{copy_line(f"cargo tauten explain {rid}")}')
        prev = rules[i - 1] if i else None
        nxt = rules[i + 1] if i + 1 < len(rules) else None
        pn = '<nav class="pn" aria-label="Previous and next rule">'
        pn += f'<a href="/rules/{prev["id"].lower()}/">← {prev["id"]}</a>' if prev else "<span></span>"
        pn += f'<a href="/rules/{nxt["id"].lower()}/">{nxt["id"]} →</a>' if nxt else "<span></span>"
        pn += "</nav>"
        levels = " ".join(f'<span class="small muted">{t}</span> {level_chip(level(r, t))}' for t in TIERS)
        head = f"""<p class="eyebrow"><a href="/rules/">Rules</a> / <span class="id">{rid}</span></p>
<h1 id="{rid}">{inline_md(r["title"])}</h1>
<div class="facts"><span class="chip">enforced by {ENFORCERS[r["enforced_by"]]}</span> {levels}</div>
<div class="facts small"><span>Applies to tests: <strong>{"yes" if r.get("in_tests", True) else "no"}</strong></span>
<span>Exceptions: <strong>{EXC_TEXT[exc]}</strong></span></div>"""
        body = f'<div class="wrap page-head"></div>{ref_layout(toc, head + "".join(parts) + pn)}'
        site.add(f"/rules/{rid.lower()}/", f"{rid}: {re.sub(r'`', '', r['title'])}",
                 f"{rid}: {r['title']}. {r['why']}", body)


# ------------------------------------------------------------------ crates ---

def crates_index(site: Site) -> None:
    legend = _legend()
    body = f"""<div class="wrap page-head"><p class="eyebrow">The family</p><h1>Crates</h1>
<p class="lede">Four crates, one profile. Each card says what the crate is, its own tier, and how far it has got.</p></div>
<div class="wrap">{crate_cards(site)}<h2 style="margin-top:48px" id="legend">How far an item has got</h2>{legend}</div>"""
    site.add("/crates/", "Crates", "The tauten crates: cargo-tauten, tauten-check, tauten and tauten-macros, with tier and status.", body)


def _legend() -> str:
    from .render import badge
    return (f'<ul class="small"><li>{badge("specified", "Specified")} written down only.</li>'
            f'<li>{badge("implemented", "Implemented")} code exists.</li>'
            f'<li>{badge("exercised", "Exercised")} ran against real input in the repository; the evidence is named.</li></ul>')


def _facts(site: Site, c: dict) -> str:
    feats = ", ".join(f"<code>{esc(k)}</code> = [{', '.join(esc(x) for x in v)}]" for k, v in c["features"].items()) or "none"
    rows = [["Version", esc(version_label(site, c))], ["rust-version", c["rust_version"]], ["Edition", c["edition"]],
            ["License", c["license"]], ["Tier", f'<code>{c["tier"]}</code>'],
            ["Features", feats], ["Dependencies", ", ".join(f"<code>{esc(x)}</code>" for x in c["dependencies"]) or "none"]]
    if c["dev_dependencies"]:
        rows.append(["Dev-dependencies", ", ".join(f"<code>{esc(x)}</code>" for x in c["dev_dependencies"])])
    if c["proc_macro"]:
        rows.append(["Kind", "procedural macro crate"])
    return table(["Fact", "Value"], rows, label=f"{c['name']} facts",
                 caption=f'From {site.src(c["path"])} at <code>{site.short}</code>.')


def _does_not(items: list[str], verbatim_from: str | None = None) -> str:
    lis = "".join(f"<li>{x}</li>" for x in items)
    src = f'<p class="small muted">{verbatim_from}</p>' if verbatim_from else ""
    return f'<div class="doesnot"><h2 id="does-not">What it does not do</h2><ul>{lis}</ul>{src}</div>'


def _pair_files(site: Site, rs: str, stderr: str, caption: str) -> str:
    src = site.data.core.blob(rs).rstrip("\n")
    err = site.data.core.blob(stderr).rstrip("\n")
    return (f'<figure><div class="pair">{panel(code_html(src, "rust"), title=esc(rs.split("crates/tauten/")[1]), label=f"Source of {rs}", provenance="From the repo")}'
            f'{panel(diag_html(err, site.rule_ids), title=esc(stderr.split("crates/tauten/")[1]), label=f"Expected compiler output {stderr}", provenance="From the repo", diag=True)}'
            f'</div><figcaption><span class="chip prov">Compile-fail test (trybuild)</span> {caption} The expected output is '
            f'committed beside the test and checked on every gate run.</figcaption></figure>')


def _crate_page(site: Site, name: str, examples: list[tuple[str, str, str]], does_not: str, evidence_keys: list[str],
                extra_evidence: str = "") -> None:
    c = site.data.crates[name]
    prose = crate_prose(site)[name]
    item = site.status_map[name]
    toc = [("what", "What it does")] + [(i, t) for i, t, _ in examples] + [("does-not", "What it does not do"),
                                                                       ("evidence", "Evidence"), ("facts", "Facts")]
    head = f"""<p class="eyebrow"><a href="/crates/">Crates</a> / tier {c["tier"]}</p>
<h1 class="id">{name}</h1>
<div class="facts"><span class="chip chip-tier {c["tier"][0]}">{c["tier"]}</span>{status_badge(item)}{registry_links(site, name)}</div>
<p class="lede">{esc(c["description"])}</p>"""
    parts = [f'<h2 id="what">What it does</h2><p class="prose">{inline_md(prose["does"])}</p>']
    parts += [f'<h2 id="{i}">{t}</h2>{html}' for i, t, html in examples]
    parts.append(does_not)
    parts.append(f'<h2 id="evidence">Evidence</h2>{evidence_table(site, evidence_keys)}{extra_evidence}')
    parts.append(f'<h2 id="facts">Facts</h2>{_facts(site, c)}')
    body = f'<div class="wrap page-head"></div>{ref_layout(toc, head + "".join(parts))}'
    site.add(f"/crates/{name}/", name, f"{name}: {c['description']}", body)


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


def crate_pages(site: Site) -> None:
    d = site.data
    caps = site.captures
    prose = crate_prose(site)

    # cargo-tauten -----------------------------------------------------------
    check = caps["check-fixtures"]
    pieces = [check.block("TAU-P001", "rej-unwrap")["text"], check.block("TAU-A001", "rej-ambient-clock")["text"],
              check.block("TAU-S001", "rej-stub")["text"]]
    tail = check.body.rstrip("\n").split("\n\n")[-1]
    elide = '<span class="line elide">…</span>'
    check_html = elide.join(diag_html(p, site.rule_ids) for p in pieces) + elide + diag_html(tail, site.rule_ids)
    rej, acc = site.fixture_counts()
    check_panel = panel(check_html, title="$ cargo tauten check", label="Excerpt of cargo tauten check over the fixtures",
                        provenance="Captured", diag=True,
                        foot=f"Three of the blocks and the summary, run over the {rej + acc} fixture crates; … marks omitted blocks.")
    clock = next(f for f in d.fixtures if f.name == "rej-ambient-clock")
    excused = next(f for f in d.fixtures if f.name == "rej-stub-excused")
    cb = check.block("TAU-A001", "rej-ambient-clock")
    xb = check.block("TAU-X004", "rej-stub-excused")
    prof = caps["profile-kernel"].body.split("\n")
    cut = prof.index("# clippy.toml for kernel") + 6
    profile_panel = site.capture_panel("profile-kernel", "\n".join(prof[:cut]) + "\n…", label="Start of cargo tauten profile kernel")
    examples = [
        ("commands", "Commands", _subcommands(site)),
        ("check", "Check", f'<figure>{check_panel}</figure>'
            f'<h3>Ambient authority in a core crate</h3><figure><div class="pair">{site.fixture_panel(clock, marks={cb["line"]: cb["column"]})}'
            f'{site.capture_panel("check-fixtures", cb["text"], title="$ cargo tauten check")}</div></figure>'
            f'<h3>An exception that is refused</h3><figure><div class="pair">{site.fixture_panel(excused, marks={xb["line"]: xb["column"]})}'
            f'{site.capture_panel("check-fixtures", xb["text"], title="$ cargo tauten check")}</div>'
            f'<figcaption><span class="chip prov">Captured</span> A reason does not excuse a stub: TAU-S001 admits no exceptions, in any tier.</figcaption></figure>'),
        ("explain", "Explain and profile", f'{site.capture_panel("explain-p001")}<div style="height:16px"></div>{profile_panel}'),
        ("init", "Init", f'<p>Run on a workspace with no tiers declared. Nothing is written without <code>--write</code>.</p>{site.capture_panel("init")}'),
        ("ratchet", "Ratchet", ratchet_html(site)),
    ]
    _crate_page(site, "cargo-tauten", examples,
                _does_not([inline_md(x) for x in prose["cargo-tauten"]["does_not"]]),
                ["cargo-tauten", "init", "ratchet"])

    # tauten-check -------------------------------------------------------------
    struct = site.snippets["diag-struct"]["code"]
    fields = re.findall(r"    /// (.*?)\n(?:    #\[serde\(rename = \"(\w+)\"\)\]\n)?    pub (\w+): ([^\n]+),", struct)
    field_rows = [[f"<code>{esc(ren or name)}</code>", f"<code>{esc(ty)}</code>", inline_md(doc)] for doc, ren, name, ty in fields]
    status_md = d.core.blob("docs/STATUS.md")
    decisions = [b for b in re.findall(r"^- (\*\*.*?)(?=^- |^\n|\Z)", status_md, re.M | re.S)
                 if b.startswith("**Lints compile at warn level") or b.startswith("**No rustc `forbid`")]
    if len(decisions) != 2:
        raise RuntimeError("STATUS design decisions not found")
    dec_html = "".join(f"<li>{inline_md(' '.join(x.split()))}</li>" for x in decisions)
    quality = re.search(r"- Mutation testing.*?(?=\n\n|\n## )", status_md, re.S).group(0)
    examples = [
        ("rule-data", "A rule, as data", site.snippet_panel("rule-p001", title="crates/tauten-check/rules.toml")),
        ("schema", "The diagnostic schema", site.snippet_panel("diag-enforced", title="crates/tauten-check/src/diag.rs") + "<div style=\"height:16px\"></div>"
            + site.snippet_panel("diag-struct", title="crates/tauten-check/src/diag.rs")
            + "<div style=\"height:16px\"></div>"
            + table(["JSON field", "Type", "Doc comment"], field_rows, label="Diagnostic fields",
                    caption="The fields of <code>Diagnostic</code>, read from the struct above.")
            + site.snippet_panel("diag-severity", title="crates/tauten-check/src/diag.rs")),
        ("decisions", "Two design decisions", f'<ul class="prose">{dec_html}</ul><p class="small muted">From <code>docs/STATUS.md</code>, Design decisions.</p>'),
    ]
    _crate_page(site, "tauten-check", examples,
                _does_not([inline_md(x) for x in prose["tauten-check"]["does_not"]]),
                ["tauten-check", "rule-table"],
                f'<p>{inline_md(" ".join(quality.lstrip("- ").split()))}</p>')

    # tauten -------------------------------------------------------------------------
    lib = d.core.blob("crates/tauten/src/lib.rs")
    m = re.search(r"//! What this crate does \*\*not\*\* do: (.*?)\n\n", lib.replace("\n//!\n", "\n\n"), re.S)
    sentence = " ".join(line.removeprefix("//!").strip() for line in m.group(1).splitlines())
    api = [
        ["<code>Authority::acquire() -&gt; Authority</code>", "Only edge crates may call this (TAU-A002). It cannot be cloned."],
        ["<code>Authority::clock(&amp;self) -&gt; SystemClock</code>", "The system clock."],
        ["<code>Authority::env(&amp;self) -&gt; Env</code>", "A snapshot of the process environment, taken now."],
        ["<code>Authority::dir(&amp;self, path) -&gt; io::Result&lt;cap_std::fs::Dir&gt;</code>", "Feature <code>fs</code>. Everything below it, nothing above it."],
        ["<code>trait Clock { fn now_ms(&amp;self) -&gt; u64; }</code>", "Milliseconds since the Unix epoch."],
        ["<code>ManualClock::at(now_ms)</code>, <code>advance(ms)</code>", "A clock for tests."],
        ["<code>Env::from_pairs(..)</code>, <code>Env::get(name)</code>", "Read-only environment variables; <code>from_pairs</code> builds one for tests."],
    ]
    examples = [
        ("capabilities", "Capabilities", site.snippet_panel("cap-doc-example", title="crates/tauten/src/cap.rs (module docs, doc-tested)")
            + "<div style=\"height:16px\"></div>"
            + table(["API", "Doc comment, shortened"], api, label="tauten::cap API",
                    caption=f'From {site.src("crates/tauten/src/cap.rs")} at <code>{site.short}</code>.')),
        ("forged", "A forged Authority does not compile",
            _pair_files(site, "crates/tauten/tests/ui/forged_authority.rs", "crates/tauten/tests/ui/forged_authority.stderr",
                        "<code>Authority</code> has a private field, so outside the crate it can only come from <code>acquire()</code>.")),
    ]
    _crate_page(site, "tauten", examples,
                _does_not([inline_md(sentence)], verbatim_from="Verbatim from the crate documentation, <code>crates/tauten/src/lib.rs</code>."),
                ["tauten"])

    # tauten-macros --------------------------------------------------------------------
    ui = [
        ("newtype_mixup", "Two IDs with the same representation are different types."),
        ("refined_field_unreachable", "Even the defining module cannot build <code>Percent(200)</code>."),
        ("refined_public_field", "A public field is rejected: it would let callers skip the check."),
        ("refined_derive_default", "Derives that could construct a value without the check are rejected."),
        ("refined_interior_mutability", "A <code>Cell</code> inside a refined type could change after the check, so it is rejected."),
        ("refined_custom_clone", "A user-written <code>Clone</code> could break the predicate, so the inner type must be <code>Frozen</code>."),
        ("contract_needs_result", "Contracts need a <code>Result</code> return type to return a violation."),
        ("old_needs_copy", "<code>old(..)</code> snapshots only <code>Copy</code> values."),
    ]
    present = {p.rsplit("/", 1)[1].removesuffix(".rs") for p in d.core.ls("crates/tauten/tests/ui") if p.endswith(".rs")}
    missing = present - {n for n, _ in ui} - {"forged_authority"}
    if missing:
        raise RuntimeError(f"compile-fail tests not shown on the site: {sorted(missing)}")
    grid = "".join(_pair_files(site, f"crates/tauten/tests/ui/{n}.rs", f"crates/tauten/tests/ui/{n}.stderr", cap) for n, cap in ui)
    examples = [
        ("refined", "Refinements and newtypes",
            site.snippet_panel("refined-percent", "newtype-userid", title="crates/tauten/tests/behaviour.rs")
            + "<div style=\"height:16px\"></div>" + site.snippet_panel("refined-asserts", title="crates/tauten/tests/behaviour.rs (refinement_checks_at_construction)")),
        ("contracts", "Contracts",
            '<p>The error type must accept a <code>ContractViolation</code>, because a violation is returned, not raised.</p>'
            + site.snippet_panel("contract-withdraw", title="crates/tauten/tests/behaviour.rs")
            + "<div style=\"height:16px\"></div>" + site.snippet_panel("contract-asserts", title="crates/tauten/tests/behaviour.rs (preconditions_reject_before_the_body)")),
        ("compile-fail", "What does not compile", grid),
    ]
    _crate_page(site, "tauten-macros", examples,
                _does_not([inline_md(x) for x in prose["tauten-macros"]["does_not"]]), ["tauten-macros"])
