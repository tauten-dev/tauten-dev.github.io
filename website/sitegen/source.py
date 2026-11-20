"""Everything read from the core repository, always at the pinned commit."""

from __future__ import annotations

import json
import re
import subprocess
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .errors import BuildError

TIERS = ("kernel", "core", "edge")
ENFORCERS = {"rustc": "Rustc", "clippy": "Clippy", "tauten": "Tauten", "convention": "Convention", "proof": "Proof"}
FAMILIES = {
    "P": "Panics", "N": "Numbers", "E": "Errors", "M": "Matching", "S": "Stubs", "X": "Exceptions",
    "U": "Unsafe", "A": "Authority", "G": "Globals", "C": "Concurrency", "O": "Output", "L": "Loops",
    "K": "Kernel", "T": "Tiers", "D": "Docs", "R": "Ratchet",
}
CRATES = ("cargo-tauten", "tauten-check", "tauten", "tauten-macros")


class Core:
    """Reads files from one commit of the core repository with `git show`."""

    def __init__(self, path: Path, ref: str):
        if not re.fullmatch(r"[0-9a-f]{40}", ref):
            raise BuildError(f"--core-ref must be a full 40-character commit SHA, got {ref!r}")
        self.path = path
        self.ref = ref
        try:
            self.date = self._git("show", "-s", "--format=%cs", ref).strip()
            kind = self._git("cat-file", "-t", ref).strip()
        except subprocess.CalledProcessError as error:
            raise BuildError(f"cannot read {ref} in {path}: {error}") from error
        if kind != "commit":
            raise BuildError(f"{ref} is a {kind}, not a commit")
        self._cache: dict[str, str] = {}

    @property
    def short(self) -> str:
        return self.ref[:7]

    def _git(self, *args: str) -> str:
        return subprocess.check_output(["git", "-C", str(self.path), *args], text=True, stderr=subprocess.PIPE)

    def blob(self, path: str) -> str:
        if path not in self._cache:
            try:
                self._cache[path] = self._git("show", f"{self.ref}:{path}")
            except subprocess.CalledProcessError as error:
                raise BuildError(f"{path} does not exist at {self.short}") from error
        return self._cache[path]

    def blob_bytes(self, path: str) -> bytes:
        return subprocess.check_output(["git", "-C", str(self.path), "show", f"{self.ref}:{path}"])

    def ls(self, prefix: str) -> list[str]:
        out = self._git("ls-tree", "-r", "--name-only", self.ref, "--", prefix)
        return [line for line in out.splitlines() if line]


@dataclass
class Fixture:
    name: str
    tier: str | None
    expect: list[str]
    src_path: str          # repository path of the single source file
    src: str

    @property
    def kind(self) -> str:
        return "accept" if self.name.startswith("acc-") else "reject"


@dataclass
class Data:
    core: Core
    workspace: dict
    rules: list[dict]
    apis: list[dict]
    crates: dict[str, dict]
    fixtures: list[Fixture]
    rules_md_rows: list[tuple[str, str]]
    status_rows: list[dict]
    rule_by_id: dict[str, dict] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.rule_by_id = {r["id"]: r for r in self.rules}


def exceptions_label(rule: dict) -> str:
    """As `cargo tauten explain --markdown` prints it (output.rs, rules_markdown)."""
    if rule.get("exceptions", True) and rule["enforced_by"] != "tauten":
        return "expect"
    return "never"


def level(rule: dict, tier: str) -> str:
    return rule.get("levels", {}).get(tier, "-")


def load(core: Core) -> Data:
    workspace = tomllib.loads(core.blob("Cargo.toml"))
    profile = tomllib.loads(core.blob("crates/tauten-check/rules.toml"))
    rules = profile["rule"]
    apis = profile.get("api", [])

    crates = {}
    shared = workspace["workspace"]["package"]
    for name in CRATES:
        path = f"crates/{name}/Cargo.toml"
        manifest = tomllib.loads(core.blob(path))
        pkg = manifest["package"]
        resolved = {k: (shared[k] if isinstance(v, dict) and v.get("workspace") else v) for k, v in pkg.items()}
        crates[name] = {
            "name": pkg["name"],
            "path": path,
            "description": pkg["description"],
            "version": resolved["version"],
            "edition": resolved["edition"],
            "rust_version": resolved["rust-version"],
            "license": resolved["license"],
            "tier": pkg["metadata"]["tauten"]["tier"],
            "features": manifest.get("features", {}),
            "dependencies": list(manifest.get("dependencies", {})),
            "dev_dependencies": list(manifest.get("dev-dependencies", {})),
            "proc_macro": manifest.get("lib", {}).get("proc-macro", False),
            "raw": core.blob(path),
        }

    fixtures = []
    names = sorted({p.split("/")[2] for p in core.ls("fixtures/cases") if p.count("/") >= 3})
    for name in names:
        manifest = tomllib.loads(core.blob(f"fixtures/cases/{name}/Cargo.toml"))
        meta = manifest["package"].get("metadata", {})
        sources = [p for p in core.ls(f"fixtures/cases/{name}/src") if p.endswith(".rs")]
        if len(sources) != 1:
            raise BuildError(f"fixture {name} has {len(sources)} source files; the site expects one")
        fixtures.append(Fixture(
            name=name,
            tier=meta.get("tauten", {}).get("tier"),
            expect=meta.get("fixture", {}).get("expect", []),
            src_path=sources[0],
            src=core.blob(sources[0]),
        ))

    rules_md_rows = re.findall(r"^\| \[(TAU-[A-Z]\d{3})\]\(#tau-[a-z]\d{3}\) \| (.+?) \|", core.blob("docs/RULES.md"), re.M)
    return Data(core, workspace, rules, apis, crates, fixtures, rules_md_rows, parse_status(core.blob("docs/STATUS.md")))


def parse_status(text: str) -> list[dict]:
    """Rows of the milestone table in docs/STATUS.md."""
    rows = []
    in_table = False
    for line in text.splitlines():
        if line.startswith("| # | Item | State | Evidence |"):
            in_table = True
            continue
        if in_table:
            if not line.startswith("|"):
                break
            if line.startswith("|---"):
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) != 4:
                raise BuildError(f"STATUS.md milestone row has {len(cells)} cells: {line}")
            rows.append({"milestone": cells[0], "item": cells[1], "state": cells[2], "evidence": cells[3]})
    if not rows:
        raise BuildError("STATUS.md milestone table not found")
    return rows


STATE_WORDS = [
    ("exercised", "exercised", "Exercised"),
    ("implemented", "implemented", "Implemented"),
    ("done", "specified", "Specified"),
    ("not started", "planned", "Not started"),
    ("blocked on owner", "blocked", "Blocked on owner"),
    ("in progress", "progress", "In progress"),
]


def parse_state(cell: str, *, strict: bool) -> tuple[str, str, str, str]:
    """(css kind, badge label, verbatim keyword, qualifier) for a STATUS state cell.

    `strict` (status-map items) refuses states outside the STATUS vocabulary.
    """
    bold = re.search(r"\*\*(.+?)\*\*", cell)
    phrase = bold.group(1) if bold else cell
    outside = (cell[:bold.start()] + cell[bold.end():]).strip() if bold else ""
    low = phrase.lower().strip()
    for word, kind, label in STATE_WORDS:
        if low.startswith(word):
            if strict and kind == "progress":
                break
            qualifier = " ".join(x for x in (phrase.strip()[len(word):].strip(), outside) if x)
            return kind, label, phrase.strip()[:len(word)], qualifier
    raise BuildError(f"unknown STATUS state {cell!r}")


def status_item(data: Data, milestone: str, contains: str) -> dict:
    hits = [r for r in data.status_rows if r["milestone"] == milestone and contains in r["item"]]
    if len(hits) != 1:
        raise BuildError(f"status-map: {len(hits)} STATUS rows match {milestone} / {contains!r}")
    row = hits[0]
    kind, label, _word, qualifier = parse_state(row["state"], strict=True)
    return {**row, "kind": kind, "label": label, "qualifier": qualifier}


# ---------------------------------------------------------------- captures ---

@dataclass
class Capture:
    name: str
    header: dict[str, list[str]]
    body: str

    @property
    def cmd(self) -> str:
        return self.header["cmd"][0]

    def blocks(self) -> list[dict]:
        """Diagnostic blocks: `error[ID]: …` up to the blank line."""
        out = []
        for chunk in re.split(r"\n\n", self.body):
            first = chunk.split("\n", 1)[0]
            m = re.match(r"(error|warning)\[([^\]]+)\]: ", first)
            if not m:
                continue
            loc = re.search(r"^  --> (\S+?)(?::(\d+):(\d+))? \((\w+) crate `([^`]+)`\)$", chunk, re.M)
            rule = re.search(r"^  = rule: (.*) \(decided by (\w+)\)$", chunk, re.M)
            fix = re.search(r"^  = fix: (.*)$", chunk, re.M)
            out.append({
                "text": chunk.rstrip("\n"), "severity": m.group(1), "id": m.group(2),
                "file": loc.group(1) if loc else None,
                "line": int(loc.group(2)) if loc and loc.group(2) else None,
                "column": int(loc.group(3)) if loc and loc.group(3) else None,
                "crate": loc.group(5) if loc else None,
                "rule": rule.group(1) if rule else None, "enforced": rule.group(2) if rule else None,
                "fix": fix.group(1) if fix else None,
            })
        return out

    def block(self, rule_id: str, crate: str) -> dict:
        hits = [b for b in self.blocks() if b["id"] == rule_id and b["crate"] == crate]
        if not hits:
            raise BuildError(f"capture {self.name}: no {rule_id} block for crate {crate}")
        return hits[0]


def load_captures(directory: Path) -> dict[str, Capture]:
    out = {}
    for path in sorted(directory.glob("*.txt")):
        text = path.read_text()
        head, sep, body = text.partition("# ---\n")
        if not sep:
            raise BuildError(f"capture {path.name} has no '# ---' header end")
        header: dict[str, list[str]] = {}
        for line in head.splitlines():
            m = re.fullmatch(r"# (\w+): (.*)", line)
            if not m:
                raise BuildError(f"capture {path.name}: bad header line {line!r}")
            header.setdefault(m.group(1), []).append(m.group(2))
        out[path.stem] = Capture(path.stem, header, body)
    return out


# ---------------------------------------------------------------- snippets ---

def load_snippets(core: Core, spec_path: Path) -> dict[str, dict]:
    """Extract each excerpt from `start` to `end`, inclusive.

    `start` must occur exactly once in the file; `end` is the first line at or
    after `start` that equals it. A missing marker fails the build.
    """
    spec = tomllib.loads(spec_path.read_text())
    out = {}
    for name, s in spec.items():
        lines = core.blob(s["path"]).splitlines()
        starts = [i for i, line in enumerate(lines) if line == s["start"]]
        if len(starts) != 1:
            raise BuildError(f"snippet {name}: start marker occurs {len(starts)} times in {s['path']}")
        begin = starts[0]
        ends = [i for i in range(begin, len(lines)) if lines[i] == s["end"]]
        if not ends:
            raise BuildError(f"snippet {name}: end marker not found after start in {s['path']}")
        last = ends[0] + s.get("after", 0)
        begin -= s.get("before", 0)
        if begin < 0 or last >= len(lines):
            raise BuildError(f"snippet {name}: before/after reach outside {s['path']}")
        chunk = lines[begin:last + 1]
        strip = s.get("strip")
        if strip is not None:
            chunk = [line[len(strip):] if line.startswith(strip) else line.rstrip() for line in chunk]
            chunk = ["" if line == strip.rstrip() else line for line in chunk]
        if s.get("dedent"):
            indent = min((len(line) - len(line.lstrip()) for line in chunk if line.strip()), default=0)
            chunk = [line[indent:] for line in chunk]
        out[name] = {**s, "name": name, "code": "\n".join(chunk), "first_line": begin + 1}
    return out


# ----------------------------------------------------------------- results ---

def load_results(path: Path) -> dict:
    data = json.loads(path.read_text())
    problems = []
    status = data.get("status")
    runs = data.get("runs")
    if data.get("schema") != 1:
        problems.append("schema must be 1")
    if status not in ("pending", "pilot", "heldout"):
        problems.append(f"status {status!r} is not pending, pilot or heldout")
    if not isinstance(runs, list):
        problems.append("runs must be a list")
        runs = []
    if status == "pending" and runs:
        problems.append("status is pending but runs is not empty")
    if status != "pending":
        if not runs:
            problems.append("a non-pending status needs at least one run")
        for i, run in enumerate(runs):
            for key in ("model", "date", "tasks", "trials_per_task_arm", "core_commit", "raw_url", "kind", "label"):
                if run.get(key) in (None, ""):
                    problems.append(f"run {i} lacks {key}")
            if run.get("kind") == "heldout" and not run.get("preregistration_sha256"):
                problems.append(f"run {i} is held-out and lacks preregistration_sha256")
            for arm, values in (run.get("arms") or {}).items():
                if "n" not in values:
                    problems.append(f"run {i} arm {arm} lacks n")
            for j, diff in enumerate(run.get("diffs") or []):
                for key in ("metric", "arm", "base", "point", "ci_low", "ci_high"):
                    if diff.get(key) is None:
                        problems.append(f"run {i} diff {j} lacks {key}")
    if problems:
        raise BuildError("results.json: " + "; ".join(problems))
    return data
