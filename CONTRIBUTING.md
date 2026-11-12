# Contributing

This repository follows the conventions of
[Battle-Conquest](https://github.com/Battle-Conquest/Battle-Conquest)
(`docs/CONVENTIONS.md`), adapted to a client mod written in Python 2.7.

Read [`AGENTS.md`](./AGENTS.md) first. It holds the non-obvious rules that matter
for a safe change, above all how hot reload stays safe.

## Language

Everything in this repository is in **English**: code, comments, commits, pull
requests, release notes, and everything the player sees in the client (the
settings page, the garage messages). The mod has no i18n.

## Issues

The mod's issues are tracked in
[Battle-Conquest/Battle-Conquest](https://github.com/Battle-Conquest/Battle-Conquest/issues)
under the **Mod Battle-Conquest** label: a change to the mod nearly always goes
with one on the server (the `/api/mod/battles` contract, storage, quest proof).
What the mod needs is described in the issue's "Côté mod" section. Those issues
are written in French, like the rest of that repository.

Standalone mod issues may also live in this repository. Link the actual issue
in commits and PRs; do not substitute a similarly numbered site issue.

## Setup

Follow the Development section of [`README.md`](./README.md): run
`tools/install_dev.py`, start the client once. After that, saving a file under
`src/` reloads the mod in place, without restarting the game.

## Branches

- Never work on `main`; never delete `main`.
- One branch per issue, created from `main`, named after it:
  `feat/<num>-<slug>`, `fix/<num>-<slug>`, `chore/<num>-<slug>`.

## Commits

Format: `<type>(#<num>): <description>`, where `<num>` is the linked issue's
number, in Battle-Conquest/Battle-Conquest or in this repository.

```text
feat(#813): add the tank played to each battle report
fix(#842): stop sending a battle again after a reconnect
chore(#819): adopt Battle-Conquest's contribution conventions
```

- Types: `feat` (a new capability), `fix` (a bug fix), `perf` (an improvement the
  player notices), `refactor`, `docs`, `test`, `chore`.
- Lowercase, imperative description that says what changes.
- One commit per logical change; several commits per PR when the steps are
  distinct.
- Without an issue (rare): `<type>: <description>`.

Release proposals read these subjects for their `feat` / `perf` / `fix` notes.
Automation refreshes the active prerelease without changing its number;
otherwise it always increments the patch, including for `feat` commits.

## Checks (before every commit)

```bash
python2.7 tools/selftest.py
```

The `Mod CI` GitHub Actions workflow runs the same suite with Python 2.7.18
on every pull request and push to `main`. It can also be started manually.
The source is mounted read-only in the test container, with networking disabled.

- The suite must pass: every change comes with a check in `tools/checks/`.
- Release automation runs with Python 3 on the Actions runner, outside the
  game. Its offline tests and packaging checks run with
  `python3 -B -m unittest discover -s tools -p 'test_*.py'` in `Mod CI`.
- Once a change has reloaded in the client, read `game.log`.
- When packaging is touched (`tools/build_release.py`, `res/`, the entry
  points), build the package and check it:

```bash
python tools/build_release.py --version x.y.z
python2.7 tools/release_check.py dist/eu.battle-conquest_x.y.z.wotmod
python3 tools/bundle_check.py dist/battle-conquest-mod_x.y.z.zip dist/eu.battle-conquest_x.y.z.wotmod --game-version 2.4.1.1
```

## Pull requests

- Title in the commit format: `<type>(#<num>): <description>`.
- The description holds:
  - `Closes #<num>` for a mod issue, or `Closes Battle-Conquest/Battle-Conquest#<num>`
    for an issue tracked on the site;
  - a summary of the changes;
  - the **actual results** of the checks (selftest, and build + release check when
    relevant), not a generic promise;
  - what is left to test in game, if anything.
- Merged with **squash**: the PR title becomes the commit on `main`.
- A change to the API contract lands on the server first (Battle-Conquest,
  `docs/mod-battles-api.md`), then here.

## Versions and releases

- Feature and fix PRs do **not** bump the version. Changes on `main` maintain
  one `release/next` PR containing a release plan and changelog. Merging it
  manually builds, tests and publishes the approved version.
- An active prerelease is refreshed in place, retaining its version, release
  identity and testing status. Without one, the latest stable version gets a
  patch increment. Stable releases are never replaced. Multiple active
  prereleases block automation until a maintainer selects one.
- Review notes and perform the relevant in-game acceptance before merging a
  stable release. A prerelease stays in testing until manually promoted.
  Same-version refreshes need a new download; version-based update warnings
  cannot distinguish them.
- WoT folder changes alone do not create releases. Players move the mod and
  shared Gameface dependency into their current `mods/<game version>/` folder.
- See [RELEASING.md](RELEASING.md) for setup and recovery. The old interactive
  `tools/release.py` remains a manual fallback; do not run it alongside an
  active automated release plan.
- After publishing the GitHub release, submit the tested complete
  `dist/battle-conquest-mod_X.Y.Z.zip` to WGMods for review, with its SHA-256 and
  installation instructions. The standalone Battle-Conquest `.wotmod` does not
  contain OpenWG's Python module or JavaScript libraries. Follow the
  [submission checklist](RELEASING.md#wgmods-submission); GitHub publication
  does not mean Wargaming approval.
- Configure the site's `MOD_WGMODS_URL` with the exact WGMods listing URL.
  The site discovers the highest published, visible version automatically.
  `MOD_WGMODS_VERSION=X.Y.Z` is the fallback when WGMods cannot be reached:
  update it **only after Wargaming approves the submission**, and keep the
  previous approved version while review is pending. Check `/my-mod`: WGMods comes first, and the
  GitHub-ahead notice disappears once the approved and latest versions match.
