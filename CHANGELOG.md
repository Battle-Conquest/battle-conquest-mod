# Changelog

## 1.2.0

Experimental prerelease for World of Tanks EU **2.4.1.0**, including the local diagnostics from [PR #15](https://github.com/Battle-Conquest/battle-conquest-mod/pull/15) and the mod update warnings from merged [PR #17](https://github.com/Battle-Conquest/battle-conquest-mod/pull/17). In-game validation is pending.

### Added

- Optional local battle-results diagnostics to help validate quest measurements. Diagnostics are disabled by default and do not send diagnostic files to the site.
- Saved-link verification and installed mod version reporting at startup.
- Stable release update checks at startup and every 30 minutes, even while sending is paused. A garage warning opens the mod page in your browser, once per newer target per session. The optional settings page shows the installed version, WGMods and GitHub versions, and the recommended source.
- WGMods remains the recommended update whenever its approved version is newer than the installed mod; releases available only on GitHub also trigger an alert. Older servers remain compatible.

### Install and test

1. Close the game. Move your existing Battle-Conquest `.wotmod` out of the mods folder, and disable any development bootstrap. Keep only one Battle-Conquest package installed.
2. Extract `battle-conquest-mod_1.2.0.zip` into your World of Tanks directory. It installs `mods/2.4.1.0/eu.battle-conquest_1.2.0.wotmod`.
3. Create `mods/configs/battle_conquest/diagnostics.json` as ASCII or UTF-8 without BOM, containing `{"enabled":true}`.
4. Play battles and follow the [diagnostic test procedure](https://github.com/Battle-Conquest/battle-conquest-mod/blob/825285e1840095f64f6dfbac860f12d93c5a9f4c/DIAGNOSTIC.md). Results are saved locally in `mods/configs/battle_conquest/results-diagnostic.jsonl` and `results-diagnostic.jsonl.1`; also check `game.log`. Copy useful observations after each scenario, before rotation replaces them.
5. When finished, set `{"enabled":false}`, close the game, remove this test package and restore your usual package.

Existing battle reports retain their current format. Offline checks use synthetic data and do not validate economic field meanings; those must be verified in game. Do not share `link.json` or authentication secrets with diagnostic observations.

## 1.1.0

### Added

- Include the played vehicle in each battle report.

### Fixed

- Keep account linking and battle counters up to date in the settings menu.
- Remove decorative separators from settings headings.
- Package the mod for World of Tanks EU 2.4.1.0.

## 1.0.0

The first release of the Battle-Conquest mod, built from the battle capture of
unicum.gg-mod and nothing else.

### Added

- Your battles sent to Battle-Conquest from the garage, shortly after they end, including those whose results screen you never opened. Only the modes the site scores are kept.
- Link your account in one click from the garage: a notification says the game is not linked yet, and its link opens your browser on the site, where you confirm.
- With modsSettingsApi and modsListApi installed, a settings page in the mods list: see what is sent, when the last batch left and how many battles wait, pause sending, or unlink.
- The link is checked with the site now and then: a key revoked on the site stops showing as linked, and a mode the site starts scoring is picked up without linking again.
- Installs beside unicum.gg-mod: the two share no file, package or setting.
