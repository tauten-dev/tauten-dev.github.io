#!/usr/bin/env python3
"""WCAG contrast check for the colour tokens in website/assets/site.css.

    python3 website/contrast.py

Body-size text needs 4.5:1; borders and rails that carry meaning need 3:1.
build.py runs the same check and fails on any pair below its threshold.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

CSS = Path(__file__).resolve().parent / "assets" / "site.css"

TEXT = ["text", "muted", "accent-text", "err", "warn", "ok"]
SYNTAX = ["sx-k", "sx-f", "sx-t", "sx-s", "sx-m", "sx-a", "sx-c"]


def tokens(css: str) -> dict[str, dict[str, str]]:
    light = re.search(r":root\{(.*?)\}", css, re.S)
    dark = re.search(r':root\[data-theme="dark"\]\{(.*?)\}', css, re.S)
    if not light or not dark:
        raise SystemExit("contrast: token blocks not found in site.css")
    parse = lambda block: dict(re.findall(r"--([\w-]+):(#[0-9A-Fa-f]{6})", block))
    return {"light": parse(light.group(1)), "dark": parse(dark.group(1))}


def rgb(hex_: str) -> tuple[float, float, float]:
    return tuple(int(hex_[i:i + 2], 16) / 255 for i in (1, 3, 5))


def mix(a: str, b: str, share: float) -> str:
    """color-mix(in srgb, a share, b)."""
    ca, cb = rgb(a), rgb(b)
    return "#" + "".join(f"{round((x * share + y * (1 - share)) * 255):02X}" for x, y in zip(ca, cb))


def luminance(hex_: str) -> float:
    def channel(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(c) for c in rgb(hex_))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(a: str, b: str) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def pairs(t: dict[str, str]) -> list[tuple[str, str, str, str, float]]:
    """(foreground name, fg, background name, bg, minimum)."""
    out = []
    backs = {"bg": t["bg"], "surface": t["surface"], "card": t["card"],
             "hl-line": mix(t["err"], t["card"], 0.10),
             "banner": mix(t["warn"], t["bg"], 0.07)}
    for fg in TEXT:
        for name, bg in backs.items():
            out.append((fg, t[fg], name, bg, 4.5))
    out.append(("err", t["err"], "deny-chip", mix(t["err"], t["card"], 0.12), 4.5))
    out.append(("accent-ink", t["accent-ink"], "accent-text", t["accent-text"], 4.5))
    # subsumed[...] in diagnostics (.d-sub) on the output panel
    out.append(("d-sub (ok)", t["ok"], "card", t["card"], 4.5))
    for fg in SYNTAX:
        for name in ("card", "hl-line"):
            out.append((fg, t[fg], name, backs[name], 4.5))
    for ui in ("accent", "border-strong", "warn", "ok"):
        for name in ("bg", "card"):
            out.append((ui, t[ui], name, backs[name], 3.0))
    return out


def check(verbose: bool = False) -> list[str]:
    failures = []
    for theme, t in tokens(CSS.read_text()).items():
        for fg_name, fg, bg_name, bg, minimum in pairs(t):
            r = ratio(fg, bg)
            line = f"{theme:5} {fg_name:>13} {fg} on {bg_name:<11} {bg}  {r:5.2f}:1 (min {minimum})"
            if verbose:
                print(line)
            if r < minimum:
                failures.append(line)
    return failures


if __name__ == "__main__":
    bad = check(verbose=True)
    if bad:
        print("\nBelow threshold:\n" + "\n".join(bad))
        sys.exit(1)
    print("\nAll pairs pass.")
