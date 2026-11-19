# tauten.dev

Source of the website for [tauten](https://github.com/tauten-dev/tauten), a strictness
profile for Rust written by AI agents. Most pages are generated from the core
repository at one pinned commit; nothing is copied by hand.

## Build and preview

Needs Python 3.11+ and [uv](https://docs.astral.sh/uv/). The core repository
must be checked out next to this one (`../tauten`), or pass `--core`.

```console
$ uv run --with markdown --with pygments python website/build.py
$ python3 -m http.server 8000 --bind 127.0.0.1 --directory public
```

`--check` runs every check without writing `public/`. The pinned commit and
the release switches live in `website/config.toml`:

| Key | Meaning |
|---|---|
| `core_ref` | Full SHA of the core commit the site is built from. Every core file is read with `git show <sha>:<path>`. |
| `published` | `true`: crates are on crates.io; show `cargo install --locked cargo-tauten` plainly and link crates.io / docs.rs. `false`: the command carries an "available from the first release" note and there are no registry links. |
| `repo_public` | `true`: core paths link to github.com at the pinned SHA. `false`: paths are plain text and the GitHub nav/footer links are left out. |

## Re-pin the core

1. Set `core_ref` in `website/config.toml` to the new full SHA.
2. Re-capture the CLI output (needs the core's Rust toolchain with clippy; runs
   locally, never in CI, and never inside the core's working tree):
   ```console
   $ python3 website/capture.py
   ```
3. Rebuild. The build fails if any capture was made at another commit
   (`--allow-stale-captures` exists for local preview only; `publish.py`
   refuses its output).

`website/og.py` regenerates `website/assets/og.png` (committed) with Playwright.

## Drift checks (the build fails on any)

1. Rule IDs and titles in `rules.toml` equal the `docs/RULES.md` table.
2. Every `TAU-…` ID in the generated HTML exists in `rules.toml`.
3. Every fixture's expected IDs exist in `rules.toml`.
4. Every snippet marker resolves (`website/snippets.toml`); every capture was
   made at the pinned SHA and its `= rule:` / `= fix:` text equals `rules.toml`;
   every status row in `website/status-map.toml` resolves to exactly one
   STATUS.md row with a known state.
5. `website/data/results.json` validates (a pending file must have no runs;
   every run needs model, date, n, CI, commit and raw data link).
6. Banned wording (prevents, sandbox, formally verified, significant, …) and
   claim tags (`Measured` needs a results run; `Proved` needs a proofs gate).
   Only exact sentences reproduced from core files are allow-listed.
7. Internal links and anchors resolve, ids are unique per page, and nothing
   is loaded from a third party.

Also checked: WCAG AA contrast of every colour pair in both themes
(`website/contrast.py`), the CSS budget (20 KB) and the home page budget
(60 KB gzipped). Numbers that STATUS.md states and the build can compute
(rule and fixture counts) are compared and reported, not fatal.

## Content rules

- Every fact is reproduced from a core file at the pinned commit, computed by
  the build, or captured CLI output. Nothing is asserted from memory.
- Status badges come only from STATUS.md through `status-map.toml`.
- Lint and convention rules "flag" or "reject"; nothing "prevents".
- Benchmark numbers come only from `website/data/results.json`. A [0, 0]
  interval over all-zero counts is labelled "insufficient defect events to
  assess improvement", never plotted as a result.
- The home page stays short: pitch, install, the three tiers, the status
  line and links. The status page carries every rule as an expandable row:
  a fixture that triggers it with its captured `check --warnings` output, or,
  where no fixture exists, the captured `cargo tauten explain` text marked
  "No fixture yet". `capture.py` records one `explain-rule-<id>` per rule.
- Palettes: paper (light) and paper-dark, shared with the sibling sites; the
  theme select offers System, Paper and Paper dark.

## Publish

Deployment is upload-only: CI never builds Rust or runs `build.py`.

**One-time switch (owner).** Pages for this repository currently uses the
legacy branch build from `main` (`build_type: legacy`). Before pushing this
`main`, set Settings → Pages → Source to **GitHub Actions**; otherwise the
legacy build would serve the repository root, which no longer has an
`index.html`. Keep the custom domain `tauten.dev` and enforce HTTPS.

Then, for each publication:

```console
$ uv run --with markdown --with pygments python website/build.py
$ git push origin main                 # the workflow must exist on main
$ python3 website/publish.py
```

`publish.py` checks `public/` (index, CNAME, no symlinks, no stale captures),
commits it to the `published-site` branch without force-pushing, and
dispatches `.github/workflows/pages.yml` with that commit's full SHA. The
workflow checks out exactly that commit and uploads it. The pinned action
SHAs are the ones writfold uses; confirm them against upstream before first
use.

## License

MIT. See [LICENSE](LICENSE).
