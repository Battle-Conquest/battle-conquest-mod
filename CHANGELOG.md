# Changelog

## 1.2.0

Official release repackaged for World of Tanks EU **2.4.1.1**. In-game acceptance was completed on 2.4.1.0; this update changes the installation folder only.

### Added

- Optional local battle-results diagnostics to help validate quest measurements. Diagnostics are disabled by default and do not send diagnostic files to the site.
- Saved-link verification and installed mod version reporting at startup.
- Stable release update checks at startup and every 30 minutes, even while sending is paused. A garage warning opens the mod page in your browser, once per newer target per session. The optional settings page shows the installed version, WGMods and GitHub versions, and the recommended source.
- WGMods remains the recommended update whenever its approved version is newer than the installed mod; releases available only on GitHub also trigger an alert. Older servers remain compatible.
- Additional quest measurements, explicit missing evidence and recovery for active sessions. Unsupported economic values are never invented.
- A synchronized garage quest panel with FR/EN labels, username search, shared player selections, keyboard controls, drag/collapse and scrolling. The panel waits for the loaded garage and preserves unsaved edits across temporary overlays.
- Immediate provisional last-battle feedback, replaced by the figures stored by Battle-Conquest after delivery. Official progress and rewards remain controlled by the server. Active choices and the latest finished quest or challenge remain available in the tracker.

### Fixed

- Cluster switches and reconnections no longer appear as a battle return. A real battle return without an announced result expires after sixty seconds; late results still enter the durable delivery queue.
- Preserve delivery and receipt refreshes across restored queues, concurrent settings saves and account/link changes. Native GUI callbacks remain disabled to avoid the client KeyEvent crash; input uses session-owned game hooks.

### Installation

1. Deploy the matching quest server, including [server PR #997](https://github.com/Battle-Conquest/Battle-Conquest/pull/997), and apply pending versioned migrations with `php scripts/migrate.php`. Keep `quest_sessions_tick` running. This mod release adds no server migration; quest access remains controlled by the server configuration.
2. Fully close the game, remove the previous Battle-Conquest `.wotmod` and disable any development bootstrap. Keep only one Battle-Conquest package installed.
3. Extract `battle-conquest-mod_1.2.0.zip` into your World of Tanks directory, or place `eu.battle-conquest_1.2.0.wotmod` in `mods/2.4.1.1/`.
4. Start the game, confirm the account link and check that a completed battle reaches Battle-Conquest.

Diagnostics remain optional and disabled by default; see [DIAGNOSTIC.md](DIAGNOSTIC.md). Do not share `link.json` or authentication secrets. GitHub publication does not imply WGMods approval.

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
