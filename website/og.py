#!/usr/bin/env python3
"""Render assets/og.png (1200x630) once; the result is committed.

    uv run --with playwright python website/og.py

It draws the brand mark (read from the core repository at the pinned commit),
the wordmark, the home page headline and the captured TAU-P001 block as text.
Set PLAYWRIGHT_CHROMIUM to a Chromium executable if Playwright's own is missing.
"""
import html
import os
import subprocess
import tomllib
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
config = tomllib.loads((HERE / "config.toml").read_text())
core = (HERE.parent / config["core"]).resolve()
mark = subprocess.check_output(["git", "-C", str(core), "show", f"{config['core_ref']}:assets/brand/tauten-icon.svg"], text=True)
body = (HERE / "captures" / "check-fixtures.txt").read_text().split("# ---\n", 1)[1]
block = next(b for b in body.split("\n\n") if b.startswith("error[TAU-P001]") and "rej-unwrap" in b)
lines = []
for line in block.split("\n"):
    e = html.escape(line)
    if line.startswith("error"):
        e = '<b style="color:#B3203A">error</b>' + e[5:]
    lines.append(e)
page = f"""<!doctype html><html><body style="margin:0;width:1200px;height:630px;background:#F7F5F1;color:#1B2230;
font-family:system-ui,sans-serif;display:flex;flex-direction:column;justify-content:center;padding:0 72px;box-sizing:border-box">
<div style="display:flex;align-items:center;gap:16px;font-size:44px;font-weight:650;letter-spacing:-.05em">
<div style="width:64px;height:64px">{mark}</div>tauten</div>
<h1 style="font-size:62px;line-height:1.08;letter-spacing:-.04em;margin:28px 0 30px;font-weight:650">Strict Rust for code written by agents.<br>
<span style="color:#A3421E">Every rule names what enforces it.</span></h1>
<pre style="margin:0;background:#FDFCFA;border:1px solid #8C8579;border-left:4px solid #C8552D;border-radius:6px;padding:18px 22px;
font:19px/1.6 'DejaVu Sans Mono',monospace;white-space:pre-wrap">{"<br>".join(lines)}</pre></body></html>"""
exe = os.environ.get("PLAYWRIGHT_CHROMIUM")
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
    tab = browser.new_page(viewport={"width": 1200, "height": 630})
    tab.set_content(page)
    tab.screenshot(path=str(HERE / "assets" / "og.png"))
    browser.close()
print("wrote", HERE / "assets" / "og.png")
