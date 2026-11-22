# tauten.dev

Source of the website for [tauten](https://github.com/tauten-dev/tauten), a strict
discipline for Rust with Lean proofs over the shipped code. Most pages are
generated from the core repository at one pinned commit; nothing is copied by
hand.

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
   The adoption routes: the advisory route installs exactly
   `latest_release` with the core's `rust-toolchain.toml` channel; the
   `adopt-trial` capture records that `fixtures/adopt` was unchanged; the
   Lean recipe's pin is an ancestor of `core_ref` whose workspace version is
   the release it names, each checksum is the sha256 of the downloaded file
   at that pin, and the vendored module equals `proofs/Tauten/Machine.lean`.
5. `website/data/results.json` validates (a pending file must have no runs;
   every run needs model, date, n, CI, commit and raw data link).
6. Banned wording (prevents, sandbox, formally verified, significant, any
   defect-reduction claim, …) and claim tags (`Measured` needs a results run;
   `Proved` needs a proofs gate). Only exact sentences reproduced from core
   files are allow-listed.
   6b. `/status/` carries the benchmark sentence from
   `docs/DISCIPLINE-PROPOSAL.md` and "tauten makes no defect-reduction claim";
   any page naming an unreleased command (`effects.lock`) carries a
   "Planned" label. (`#[effects]`, `#[evidence]` and `#[derive(Cap)]` shipped
   in 0.0.4; `cargo tauten ship` and `verify --level` in 0.0.5.)
7. Internal links and anchors resolve, ids are unique per page, nothing
   is loaded from a third party, and docs.rs links carry `latest_release`.

Also checked: WCAG AA contrast of every colour pair in both themes
(`website/contrast.py`), the CSS budget (20 KB) and the home page budget
(60 KB gzipped). Numbers that STATUS.md states and the build can compute
(rule and fixture counts) are compared and reported, not fatal.

## Content rules

- Every fact is reproduced from a core file at the pinned commit, computed by
  the build, or captured CLI output. Nothing is asserted from memory. Every
  code excerpt resolves through `website/snippets.toml`; every output panel
  comes from a capture.
- Few, sharp examples. The home page has exactly three, each a source panel,
  its captured output and one "Limit" line: authority as a parameter
  (TAU-A001), declared effects (TAU-F001), and a proof that subsumes a
  finding (`fixtures/proofs-subsume`).
- Two badges only: `Proved` in the claims table on `/proofs/`, and `Planned`
  where something unreleased must be named. Status badges, if any return,
  come only from STATUS.md through `status-map.toml` (currently empty).
- Lint and convention rules "flag" or "reject"; nothing "prevents".
- No defect-reduction claim. The benchmark appears as one sentence on
  `/status/#benchmark`, quoted from `docs/DISCIPLINE-PROPOSAL.md`; the bench
  design and reports stay in the core repository.
- The site describes tauten, not any adopting project.
- Pages, one column each: `/` (pitch, install, three examples, what it does
  not do), `/start/` (install; the three adoption routes of
  `docs/ADOPTING.md`: advisory trial, opt-in CI check, Lean module only;
  tiers, check, proofs, agent profile, commands), `/proofs/` (what "proved"
  means, the gate, the claims table, reusing one pinned Lean module, what
  is trusted), `/rules/` with one page per rule, `/status/` (benchmark,
  known gaps, links to STATUS.md, ROADMAP.md, the changelog and
  `bench/README.md`), `/changelog/` (`CHANGELOG.md` at the pinned commit,
  one anchored section per release, linked to its GitHub release; a section
  newer than `latest_release` or without a date is labelled Unreleased;
  clauses naming an adopting project are left out through `OMIT` in
  `sitegen/pages_changelog.py`, and any other mention fails the build). `/discipline/`, `/benchmark/`, `/enforcement/`,
  `/agents/` and `/crates/…` are redirects; `/agents/AGENTS.tauten.md` serves
  the raw agent profile; API docs live on docs.rs.
- The footer links the changelog and a Feedback link to the core
  repository's issue forms.
- Palettes: paper (light) and paper-dark, shared with the sibling sites; the
  theme select in the footer offers System, Paper and Paper dark.

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
SHAs must be confirmed against upstream before first use.

## License

MIT. See [LICENSE](LICENSE).
