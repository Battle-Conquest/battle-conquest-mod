# Changelog

## 1.2.3

### Changes in this build

- Maintenance updates to the mod and its release tooling.

## 1.2.2

Testing prerelease for **World of Tanks EU 2.4.1.1**. The target game version is unchanged.

### Added

- Premium-account XP support for individual quest tracking and the detailed garage window. Supported battles now use the XP counted by Wargaming, including account premium and excluding combat XP reserves. Challenge base XP and total XP keep their existing meanings.
- Gross and signed net credit measurements for the observed premium-account scenario. Net credits include the companion bonus and deduct actual credit expenses; a loss remains negative. The verified Tiger I example produces **-28,690 net credits**.
- Recovery of missing individual-quest measurements from results still available in the game cache, using the server's targeted requests. Enrichment preserves known values and never counts the same battle twice.

### Fixed

- Validate the complete installation ZIP before publication and require that tested ZIP for WGMods submission. OpenWG Gameface 1.2.2, its Python module and JavaScript libraries are included in the ZIP; the standalone Battle-Conquest file still requires that shared dependency. Installation and update instructions now distinguish both downloads.
- Restore Unicum account/Twitch positioning after a garage-layout failure, including with the shared scrolling column introduced by #55. Other mods' saved positions are preserved.
- Keep manual quest selection available when a sole active objective exists, including the latest finished result and its statistics. A valid saved choice survives refreshes and restarts.
- Improve garage-card readability with a 95% dark background, larger regular body text and opaque buttons. Pressed feedback ends on release; keyboard focus remains visible with Gameface-compatible styling.
- Replace the settings glyph with a vector gear and show the fallback notification only when no compatible settings menu opens. Discard delayed opening requests after an account, link or garage-context change or when the mod stops.

### Supported cases

The new premium normalization covers **random, single-vehicle battles with an explicitly applied 150% account-premium factor**. XP supports no first-win bonus and either no combat XP reserve or the observed +50% reserve, with no other unsupported XP modifier. Credits with event rewards remain unnormalized. Missing or unsupported measurements stay unknown; standard-account and Frontline behavior is preserved.

### Installation

If you installed an earlier 1.2.2 prerelease, download this ZIP again and replace that installation: the version number remains 1.2.2.

1. Deploy Battle-Conquest **2.3.7 or later**, including [premium support #1072](https://github.com/Battle-Conquest/Battle-Conquest/pull/1072) and [saved quest-selection support #1076](https://github.com/Battle-Conquest/Battle-Conquest/pull/1076), before this mod.
2. Fully close the game and back up `mods/configs/battle_conquest/` privately. Remove the previous Battle-Conquest package and disable any development bootstrap.
3. Extract the complete `battle-conquest-mod_1.2.2.zip` into the game directory. It contains `mods/2.4.1.1/eu.battle-conquest_1.2.2.wotmod`, the pinned Gameface dependency in `mods/2.4.1.1/net.openwg/`, and its licence. Keep only one Battle-Conquest package installed and preserve the shared dependency folder.
4. Start the game, verify the account link and play a supported battle. Confirm that it appears once on the site, compare individual-quest XP with the Wargaming tank-stat delta, and compare net credits with the actual wallet change.

### Validation

This prerelease packages the premium support reviewed in [mod PR #40](https://github.com/Battle-Conquest/battle-conquest-mod/pull/40), manual-selection fixes in [PR #42](https://github.com/Battle-Conquest/battle-conquest-mod/pull/42) and garage-card fixes in [PR #43](https://github.com/Battle-Conquest/battle-conquest-mod/pull/43). Python 2.7 selftests, 24 Python 3 client-tool tests, 12 FR/EN browser scenarios at three resolutions with and without native mission cards, and the built-package release check passed.

**Acceptance of the refreshed 1.2.2 binary in a real client remains pending.** Check manual quest selection, card readability and repeated button presses, keyboard focus, settings with and without optional menus, and return from battle. Existing numerical observations came from 1.2.1 diagnostics. This is not a WGMods-approved release.

### Changes in this build

- Allow the garage card to finish loading before fallback
- Make integrated card controls readable
- Automatiser les releases après les changements du mod

This refresh keeps the same version and prerelease status. Download the ZIP again to replace an earlier build. In-game acceptance must be repeated.

### Changes in this build

- Corriger les libellés et le secours de la carte du garage

This refresh keeps the same version and prerelease status. Download the ZIP again to replace an earlier build. In-game acceptance must be repeated.

### Changes in this build

- Afficher Battle-Conquest au-dessus d’Unicum
- Validate complete WGMods bundles and restore Unicum panels

This refresh keeps the same version and prerelease status. Download the ZIP again to replace an earlier build. In-game acceptance must be repeated.

## 1.2.1

Battle-Conquest for **World of Tanks EU 2.4.1.1**.

### Added

- An integrated garage card beneath the game's mission cards, with account linking, your own objectives, official progress and available mod estimates. The existing detailed comparison window remains available through **Details**.
- Independent, persistent visibility settings for the card and detailed window, scoped to the site, region and Wargaming account. Only the card is enabled initially; garage notifications can restore either display without optional mod menus. Display settings never pause battle delivery.
- Shared quest selection with the website: automatically follow a sole active individual quest or running challenge you participate in, while preserving the saved choice when another objective becomes active. When none is active, keep an accessible manually selected challenge; without a valid selection, show the latest result.
- The pinned MIT-licensed Gameface dependency in the installation ZIP, under the shared `net.openwg/` folder. If the card is unavailable, the native detailed window provides a session fallback.

### Fixed

- Keep concurrent selection changes explicit instead of silently adopting another client's settings. Preserve Gameface refreshes through temporary resource failures and disposed views, and respect dismissal of the fallback window.
- Report gross and signed net credits for the verified standard-account, no-bonus Frontline multivehicle scenario. The observed three-vehicle battle produces 157,530 gross and 99,961 net credits, including one vehicle with a 5,624-credit loss. Unknown costs remain unknown, and premium or other unverified bonuses are not inferred.
- Allow available Frontline results to complete previously accepted reports through existing targeted recovery, without replacing known values or counting a battle twice. Receipt deadlines and settled rankings remain enforced.
- Keep account links, pause settings and battle queues separate for each Wargaming account and region. Reports without verified ownership remain isolated instead of being sent for the next login.
- Recover battles missed before their results were captured, including after a client interruption. Recovery keeps its retry budget across restarts, with up to 50 entries per account, five attempts per arena and seven days of retention.
- Keep unconfirmed reports queued when the site returns an unreadable, incomplete or contradictory response. Missing HTTP callbacks no longer stall delivery indefinitely.
- Share result retrieval with quest-evidence repair and wait before automatic cache requests to reduce collisions with the results screen and other mods.
- Prevent callbacks and capture hooks from a closed mod session from overwriting current local data after a reload.

### Installation

If you installed an earlier 1.2.1 prerelease, download this ZIP again and replace that installation: the version number remains 1.2.1.

1. Deploy Battle-Conquest **2.3.4** with [shared garage selection support](https://github.com/Battle-Conquest/Battle-Conquest/pull/1056) before this mod. The server must also include [account-isolation support](https://github.com/Battle-Conquest/Battle-Conquest/pull/1012) and [Frontline credit support](https://github.com/Battle-Conquest/Battle-Conquest/pull/1051). This update adds no server migration or configuration requirement.
2. Fully close the game and back up `mods/configs/battle_conquest/`. Keep this backup private: it contains account-link secrets.
3. Remove the previous Battle-Conquest `.wotmod` and disable any development bootstrap. Extract the complete `battle-conquest-mod_1.2.1.zip` into the game directory. It contains `mods/2.4.1.1/eu.battle-conquest_1.2.1.wotmod`, `mods/2.4.1.1/net.openwg/net.openwg.gameface_1.2.2.wotmod` and the dependency licence. Preserve the shared `net.openwg/` location and keep only one Battle-Conquest package installed. The standalone Battle-Conquest asset requires this dependency for the integrated card; without it, the detailed window is used instead.
4. Start the game, verify the current account link and relink if requested. Check the garage card and shared selection, then play a supported battle and confirm that it appears once on Battle-Conquest.

Existing links and queues migrate automatically. Unverified older reports are preserved but not uploaded. See [account isolation and rollback](https://github.com/Battle-Conquest/battle-conquest-mod/blob/v1.2.1/OWNER-ISOLATION.md) before downgrading.

### Validation

Python 2.7 selftests, 28 Python 3 tooling tests and the built-package release check passed. Six FR/EN browser scenarios previously passed for the card at 1280×720, 1920×1080 and 2560×1440.

**In-game acceptance remains pending**: native Gameface rendering and input, Unicum coexistence, return from battle and the [#1047 recipe](https://github.com/Battle-Conquest/Battle-Conquest/issues/1047) still require a real client. Also test the Frontline credit recipe in [#1050](https://github.com/Battle-Conquest/Battle-Conquest/issues/1050) with diagnostics disabled, random battles and Onslaught, interruption recovery, account/pause isolation, notifications and the results window. The cache delay reduces collisions but does not guarantee their absence. GitHub publication does not imply WGMods approval.

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
