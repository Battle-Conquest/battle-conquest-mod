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

## Setup

Follow the Development section of [`README.md`](./README.md): run
`tools/install_dev.py`, start the client once. After that, saving a file under
`src/` reloads the mod in place, without restarting the game.

## Branches

- Never work on `main`; never delete `main`.
- One branch per issue, created from `main`, named after it:
  `feat/<num>-<slug>`, `fix/<num>-<slug>`, `chore/<num>-<slug>`.

## Commits

Format: `<type>(#<num>): <description>`, where `<num>` is the issue's number in
Battle-Conquest/Battle-Conquest.

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

`tools/release.py` reads these subjects: `feat` bumps the minor version,
anything else the patch version, and `feat` / `perf` / `fix` make the changelog.
A subject that does not follow the format still counts, but stays out of the
changelog.

## Checks (before every commit)

```bash
python2.7 tools/selftest.py
```

- The suite must pass: every change comes with a check in `tools/checks/`.
- Once a change has reloaded in the client, read `game.log`.
- When packaging is touched (`tools/build_release.py`, `res/`, the entry
  points), build the package and check it:

```bash
python tools/build_release.py --version x.y.z
python2.7 tools/release_check.py dist/eu.battle-conquest_x.y.z.wotmod
```

## Pull requests

- Title in the commit format: `<type>(#<num>): <description>`.
- The description holds:
  - `Closes Battle-Conquest/Battle-Conquest#<num>` (the issue lives in the other
    repository);
  - a summary of the changes;
  - the **actual results** of the checks (selftest, and build + release check when
    relevant), not a generic promise;
  - what is left to test in game, if anything.
- Merged with **squash**: the PR title becomes the commit on `main`.
- A change to the API contract lands on the server first (Battle-Conquest,
  `docs/mod-battles-api.md`), then here.

## Versions and releases

- Pull requests do **not** bump the version. `tools/release.py` derives it from
  the commits since the last `vX.Y.Z` tag, drafts the changelog (opened in an
  editor to be read over), builds, tags, and creates the GitHub release as a
  **draft**.
- A release is published only once it has captured a battle in a real client:
  `gh release edit vX.Y.Z --draft=false`.
