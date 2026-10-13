# What this is

A World of Tanks client mod for [Battle-Conquest](https://battle-conquest.eu): it captures the results of the battles the player plays and sends them to the site, which scores tournaments and quests from them. Client 2.4.0.x EU, Python 2.7 inside the game. The site is the only destination; the contract is Battle-Conquest's `docs/mod-battles-api.md`.

Derived from unicum.gg-mod (AGPL-3.0, see `NOTICE`), reduced to its battle capture. Read `README.md` for what a player sees, `CONTRIBUTING.md` for commits.

# Layout

- **`dev/mod_battle_conquest_dev.py.in`**, the dev bootstrap. The only file a dev client loads, packaged once as a `.wotmod`. It watches `src/` and reloads the package in place. Changing it needs a client restart; nothing else in the repo does. `dev/mod_battle_conquest.py.in` is the released entry point.
- **`src/battle_conquest/`**, everything reloadable.
  - `__init__.py`: `start()` / `stop()`. Builds the shared services and installs each piece, in dependency order.
  - `runtime/session.py`: the ownership registry, see [Hot reload](#hot-reload).
  - The capture: `battle_reports.py` (where a battle is captured from, and whether anything wants it), `battle_report.py` (one report read out of the results dict), `results_dict.py` (finding that dict in whatever the client hands over), `results_request.py` (asking the server for the battles whose results screen was never opened), `service_hooks.py` (what the client offers to sit on, logged by name), `modes.py` (`MODES`, and which mode an arena bonus type is).
  - The sending: `report_queue.py` (the queue on disk, one report per arena), `report_sender.py` (batches to the site, what a refusal costs, the status the page shows).
  - The link: `destinations.py` (the one destination, its secret, modes and pause, in `link.json`), `site_link.py` (linking in one click through the player's browser, unlinking, and checking the link with `/api/mod/me`), `account.py` (the Wargaming account logged in).
  - The page: `settings_window.py` (the modsSettingsApi page), `mods_list.py` (the modsListApi entry that opens it). Both APIs are optional and never shipped.
  - `notices.py`: the garage's notification while the game is not linked, whose link starts the linking (a patched notification actions handler), and the word on how linking ended. It is how a client without modsSettingsApi links at all.
  - `config.py`: the site's address, the region, the config folder. `local_settings.py`, gitignored, points `SITE` at a local server.
- **`res/`**: shipped as it is inside the `.wotmod` (the menu icon).
- **`tools/`**: `install_dev.py`, `build_release.py`, `release_check.py`, `release.py`, `selftest.py` + `checks/`.

# Commands

| Command | What it does |
|---|---|
| `python tools/install_dev.py --game "C:/Games/World_of_Tanks_EU"` | Installs the bootstrap and `res/` into a client. Python 3. |
| `python2.7 tools/selftest.py` | The test suite, Python 2.7, against fake client modules. Offline. |
| `python tools/build_release.py --version x.y.z` | Builds `dist/eu.battle-conquest_<version>.wotmod` (the package compiled with Python 2.7, `res/`) and `dist/battle-conquest-mod_<version>.zip` (it, laid out as the game folder). |
| `python2.7 tools/release_check.py dist/eu.battle-conquest_<version>.wotmod` | Loads the built package the way the client does, and checks nothing in it is named after unicum.gg-mod. |
| `python tools/release.py` | Version and changelog from the commits since the last tag, build, checks, tag, and a **draft** GitHub release, published by hand after an in-game test. |

Logs go to `game.log` in the game directory (not `python.log`), under loggers named `battle_conquest.*`. Read it after every change: a reload that failed says so there and nowhere else.

# Hot reload

The whole design rests on one property: after `stop()`, every game function is back, by identity. So nothing takes ownership of anything directly. Every patch, callback, subscription, request and teardown goes through the `Session` handed to `install()`, and `Session.close()` gives it all back before the package is purged and reimported.

- **Patch with `session.patch(holder, name, build)`.** It restores what the owner's `__dict__` held, which is what makes classmethods and inherited methods come back right. A hook that survives a reload stacks under the next one and runs code whose module globals are gone; the log then says `LEAK`, and only a client restart clears it.
- **Never `BigWorld.callback` or `BigWorld.fetchURL` directly.** Use `session.callback` / `session.fetch`, which are gated on `session.alive`.
- **Share, don't duplicate, services.** One `Queue` for the capture and the sender: two objects over one file each hold their own copy of it, and whichever saved last drops what the other learned.
- **`start()` rolls back on failure**, so a half-installed load never orphans its patches.
- Saving a file mid-edit triggers a reload of a broken state. That is expected and recovers on the next save; do not "fix" the watcher.

# Rules learned the hard way

**Where the capture sits has been a guess, and wrong, twice.** `onResultPosted` existed, reported itself attached, and never fired; `postResult` fires only as the results screen is built. A battle whose screen is never opened is captured only because `results_request.py` asks the server for it. Keep every way in, and keep `service_hooks.describe` logging what the client offers.

**A client's events accept `+=` and may refuse `-=`.** Detaching is best effort and logged, never assumed.

**Final means final.** The site answers each report accepted, duplicate or rejected; all three settle it. Only an answer that asking again could change (no answer, 401, 408, 429, 5xx) is retried, after a back-off. A rejected battle offered again every five minutes would spend the player's quota forever.

**One account at a time.** A report is stamped with the account at capture and sent only while that account is logged in. A battle credited to whoever is logged in the next evening is credited to the wrong player.

**A secret never travels, and never goes to another site.** It is drawn in the client; only its SHA-256 reaches the site, at linking. A `link.json` made for one site is ignored by a build pointed at another.

# Conventions

- Keep files under ~400 lines. When one grows past that, split it into modules instead of letting it sprawl.
- No section divider comments (e.g. `# --- X ---`). Split the file instead.
- English only: code, comments, commits, PRs, release notes, and anything shown in the client.
- Branches, commits and PRs follow Battle-Conquest's conventions (`<type>(#<issue>): <description>`, the issue living in Battle-Conquest/Battle-Conquest): see `CONTRIBUTING.md`. Never work on `main`.
- Python 2.7 in `src/` and `tools/checks/`, Python 3 in the other tools.
- Comments explain why, and keep the history of a decision when the obvious alternative was tried and failed.
- A change comes with a check in `tools/checks/`, and the suite passes before a commit.
