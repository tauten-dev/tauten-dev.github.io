#!/usr/bin/env python3
"""Re-capture the CLI output shown on the site, at the pinned core commit.

    python3 website/capture.py                      # core and ref from config.toml
    python3 website/capture.py --core ../tauten --core-ref <full sha>

It exports the commit with `git archive` into a temporary directory, builds
`cargo-tauten` there with `--locked`, and runs each command against the
exported `fixtures/cases` or against a scratch workspace copied from
website/scratch/. It never runs inside the core repository's working tree and
writes nothing there. It needs the core's pinned Rust toolchain with clippy,
so it runs locally, never in CI.

Each capture is website/captures/<name>.txt: a header of `# key: value`
lines, a `# ---` line, then the output exactly as printed (stdout and stderr
interleaved, as a terminal shows them).
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAPTURES = HERE / "captures"
SCRATCH = HERE / "scratch"


def load_config() -> dict:
    return tomllib.loads((HERE / "config.toml").read_text())


def export(core: Path, ref: str, dest: Path) -> None:
    dest.mkdir(parents=True)
    archive = subprocess.run(["git", "-C", str(core), "archive", ref], check=True, capture_output=True).stdout
    subprocess.run(["tar", "-x", "-C", str(dest)], input=archive, check=True)


def write_capture(name: str, ref: str, cmd: str, cwd: str, code: int, body: str, notes: list[str]) -> None:
    lines = [f"# core: {ref}", f"# cmd: {cmd}", f"# cwd: {cwd}", f"# exit: {code}"]
    lines += [f"# note: {n}" for n in notes]
    lines.append("# ---")
    (CAPTURES / f"{name}.txt").write_text("\n".join(lines) + "\n" + body)
    print(f"captured {name} (exit {code})")


def run(argv: list[str], cwd: Path, env: dict) -> tuple[int, str]:
    proc = subprocess.run(argv, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return proc.returncode, proc.stdout


def main() -> None:
    config = load_config()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--core", default=str((HERE.parent / config["core"]).resolve()))
    parser.add_argument("--core-ref", default=config["core_ref"])
    args = parser.parse_args()
    ref = args.core_ref
    if not re.fullmatch(r"[0-9a-f]{40}", ref):
        sys.exit(f"--core-ref must be a full 40-character commit SHA, got {ref!r}")
    core = Path(args.core).resolve()
    CAPTURES.mkdir(exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="tauten-capture-") as tmp:
        tmp = Path(tmp)
        src = tmp / "core"
        export(core, ref, src)
        env = dict(os.environ)
        env["CARGO_TARGET_DIR"] = str(tmp / "target")
        subprocess.run(["cargo", "build", "--locked", "-p", "cargo-tauten"], cwd=src, env=env, check=True)
        env.pop("CARGO_TARGET_DIR")
        env["PATH"] = f"{tmp / 'target' / 'debug'}{os.pathsep}{env['PATH']}"
        toolchain = src / "rust-toolchain.toml"

        def cap(name: str, args: list[str], cwd: Path, shown_cwd: str, notes: list[str] | None = None) -> None:
            code, out = run(["cargo", "tauten", *args], cwd, env)
            write_capture(name, ref, "cargo tauten " + " ".join(args), shown_cwd, code, out, notes or [])

        fixtures = src / "fixtures" / "cases"
        cap("check-fixtures", ["check"], fixtures, "fixtures/cases")
        cap("check-fixtures-warnings", ["check", "--warnings"], fixtures, "fixtures/cases")
        cap("check-fixtures-json", ["check", "--format", "json"], fixtures, "fixtures/cases")
        cap("explain-p001", ["explain", "TAU-P001"], src, ".")
        # One explain capture per rule, for the status page's rule table.
        rules = tomllib.loads((src / "crates" / "tauten-check" / "rules.toml").read_text())["rule"]
        for rule in rules:
            cap(f"explain-rule-{rule['id'].lower()}", ["explain", rule["id"]], src, ".")
        cap("profile-kernel", ["profile", "kernel"], src, ".")

        # init: a three-crate workspace with no tiers declared.
        ws = tmp / "init"
        shutil.copytree(SCRATCH / "init", ws)
        shutil.copy(toolchain, ws)
        cap("init", ["init"], ws, "website/scratch/init")

        # The ratchet, step by step, on a one-crate workspace.
        ws = tmp / "ratchet"
        shutil.copytree(SCRATCH / "ratchet", ws)
        shutil.copy(toolchain, ws)
        crate = ws / "crates" / "parse"
        (crate / "src").mkdir()
        lib = crate / "src" / "lib.rs"
        shown = "website/scratch/ratchet"
        shutil.copy(crate / "step1.rs", lib)
        cap("ratchet-1-baseline", ["baseline", "--output", "tauten-baseline.json"], ws, shown,
            ["src/lib.rs is step1.rs: one unwrap"])
        shutil.copy(crate / "step2.rs", lib)
        cap("ratchet-2-check", ["check"], ws, shown, ["src/lib.rs is step2.rs: a second unwrap added"])
        cap("ratchet-3-refused", ["baseline", "--output", "tauten-baseline.json"], ws, shown,
            ["src/lib.rs is still step2.rs"])
        shutil.copy(crate / "step3.rs", lib)
        cap("ratchet-4-stale", ["check"], ws, shown, ["src/lib.rs is step3.rs: both unwraps gone"])


if __name__ == "__main__":
    main()
