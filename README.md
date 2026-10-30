# battle-conquest-mod

World of Tanks client mod for [Battle-Conquest](https://battle-conquest.eu). It
reads the results of the battles you play and sends them to the site, for the
tournaments and quests that score them: Onslaught, which Wargaming's public API
does not cover at all, and random battles one by one, so a quest objective
reached within its battle cap counts even if you keep playing.

Not affiliated with Wargaming.net. Derived from
[unicum.gg-mod](https://github.com/unicum-gg/unicum.gg-mod), see
[NOTICE](./NOTICE).

## Install

1. Link your Wargaming account on [battle-conquest.eu](https://battle-conquest.eu)
   first: until it is, every battle the mod sends is refused.
2. Prefer the **Wargaming-approved version on WGMods**, linked from the
   [Battle-Conquest mod page](https://battle-conquest.eu/my-mod). Place its
   `.wotmod` file in `mods/<game version>/` inside your World of Tanks folder,
   or use the WGMods application.
   For the very latest version, download `battle-conquest-mod_<version>.zip`
   from the [latest GitHub release](https://github.com/Battle-Conquest/battle-conquest-mod/releases/latest)
   and unzip it into your World of Tanks folder. It holds one file,
   `mods/<game version>/eu.battle-conquest_<version>.wotmod`. GitHub may be ahead
   while Wargaming reviews the WGMods submission; the site shows both versions
   when they are available.
3. Start the game. Once in the garage, a notification says the game is not
   linked yet: click **Link my account** in it. Your browser opens on the site,
   you confirm, and the mod writes its configuration itself. Nothing to type.
4. Play. Battles leave from the garage shortly after they end, including those
   whose results screen you never opened.

## The settings page

Optional. With [modsSettingsApi](https://github.com/izeberg/modssettingsapi)
and [modsListApi](https://gitlab.com/wot-public-mods/mods-list) installed (most
modpacks carry them; this mod does not ship them), Battle-Conquest has an entry
in the mods list (the icon at the top of the garage) that opens this page:

| Line | What it says or does |
|---|---|
| Account | linked, not linked, or waiting for you to confirm in the browser; **Link**, **Unlink** or **Cancel** |
| Sending | the modes the site scores, or *paused* |
| Your battles on the site | **Open** shows your page on the site, where a link is revoked |
| Last sent | when the last batch left this session, and what the site made of it |
| Waiting to be sent | battles of the account logged in still in the queue |
| Mod updates | installed version, known WGMods and GitHub versions, and the recommended download source |

The page's own box (enabled) pauses sending: battles played meanwhile are not
kept. **Unlink** forgets the current account's key; other accounts and queued reports are preserved. Revoke it on the site too.

Without those two mods there is no page, and nothing is lost but pausing and
unlinking from the game: the garage notification links the game, and a key is
revoked from your page on the site, after which the mod forgets it by itself.
At startup the mod checks any saved key with the site. A revoked key is removed
and the garage offers **Link my account** again. If the site is temporarily
unreachable, the saved link is kept and checked again later.
The check runs at startup and every 30 minutes, even while sending is paused.
It announces the installed version and reads the site's optional update status.
A newer stable release, including one available only on GitHub, raises a garage
warning once per target version per session. If you are in battle it waits for
the garage. **Update my mod** opens `/my-mod` in your own browser. WGMods remains
the recommended download whenever its approved version can update your installation;
GitHub can carry a still newer release. Servers without optional update information remain compatible. Account linking
requires the identity metadata delivered by Battle-Conquest#1012.

## What is sent, and what is not

- Only the modes the site says it scores, read from the site when you link and
  checked again now and then.
- Per battle: its owner WG account ID and region, arena id, mode, end time, outcome, whether you survived, and
  your own counters (damage, kills, spotting, XP...). Nothing about the other
  players.
- The battles of the account logged in only, proven by a key the mod draws
  itself. Only its SHA-256 ever reaches the site, so a site that is breached
  leaks nothing that can send battles in your name.

The contract is described in Battle-Conquest's
[`docs/mod-battles-api.md`](https://github.com/Battle-Conquest/Battle-Conquest/blob/main/docs/mod-battles-api.md),
and any client may implement it.

## Files

Everything the mod writes is in `mods/configs/battle_conquest/`:

| File | |
|---|---|
| `link.json` | schema 2: separate keys, modes and pause state per site, region and WG account |
| `battle-reports.json` | schema 2: owner-scoped pending battles and isolated reports with unverified ownership |
| `battle-reports-refused.json` | the last batch the site could not read, kept for whoever has to find out why |

An optional local results diagnostic is available for the quest measurements
work in [#953](https://github.com/Battle-Conquest/Battle-Conquest/issues/953).
It is disabled by default. See the [in-game diagnostic procedure (French)](./DIAGNOSTIC.md)
for activation, files, limits and the comparisons to record. These observations
are never sent to the site and do not change the existing battle reports.

## Multiple game accounts (#964)

Result ownership is always read from the personal `accountDBID` fields, even
with diagnostics disabled. A result received after a login switch retains its
owner. Different accounts in the same arena have independent queue entries,
acknowledgements and a 500-report limit each. Only the logged-in account's
reports leave, using its own saved key. Linking B no longer replaces A.

A legacy key is migrated only after `/api/mod/me` returns its WG ID and region.
Legacy reports without verifiable owner evidence are retained in isolation,
not attributed from their old login stamp. Missing or conflicting ownership
also isolates a report. The settings page reports the count and `game.log`
explains the reason. An `account_mismatch` or revoked key suspends that link;
link the same account again to resume its pending reports. Pause, unlink and
revocation do not purge another account's backlog.

See [installation, migration and verification (French)](OWNER-ISOLATION.md).
`identity_enabled` only writes optional local diagnostic observations; leave
both diagnostic options false for normal play.

## With unicum.gg-mod installed

Both mods load side by side: they share no file, package or setting. If
unicum.gg-mod also sends battles to Battle-Conquest one day, each battle
arrives twice and the second copy is answered `duplicate` (the site keys a
battle by player and arena). Nothing is counted twice.

## Development

For the release commands, ZIP contents and publication steps, see the
[release guide (French)](./RELEASING.md).

Python 2.7 in `src/`, as the client runs it. Read [`AGENTS.md`](./AGENTS.md)
before changing anything, above all how hot reload stays safe.

```bash
python tools/install_dev.py --game "C:/Games/World_of_Tanks_EU"   # once per client
python2.7 tools/selftest.py                                       # before every commit
python tools/build_release.py --version x.y.z                     # dist/
python2.7 tools/release_check.py dist/eu.battle-conquest_x.y.z.wotmod
python tools/release.py                                           # tag, build, draft release
```

`install_dev.py` installs a small bootstrap that loads `src/` and reloads it
whenever a file changes, so the client keeps running across edits. Logs go to
`game.log` in the game directory, under loggers named `battle_conquest.*`.

To point a dev build at another server, put `SITE = 'https://...'` in a
gitignored `src/battle_conquest/local_settings.py`. A link made for one site is
never presented to another.

## License

[AGPL-3.0](./LICENSE), as the code it derives from.


## Additional quest measurements (#954)

Reports now include optional `quest_details`: actual battle start, complete
vehicle ids when known, distinct base/total XP, direct shot counters and
conditional gross/net credits. Missing measurements stay absent. The seven
historical counters and current quest proof keep their meaning. Numeric raw
observations remain separate per vehicle; premium and respawn totals are not
inferred. Support and its verified scenarios are announced on the first linked
`/api/mod/me` response, even before any battle and while sending is paused.

Deploy the [server contract](https://github.com/Battle-Conquest/Battle-Conquest/blob/feat/954-mod-measures/docs/mod-battles-api.md)
and migration `0055_add_mod_quest_details.php` first. Then use the normal build
and installation commands. Optional diagnostics remain local and opt-in.
The two observed SU-130PM battles from 22 October 2026 are regression fixtures;
all account/arena ids have been removed. Premium, other bonuses, negative net
and respawn totals still need live verification. A reopened result may enrich
an accepted report but cannot replace known values or reopen a rejection.


Missing quest evidence (#956)
-----------------------------
When the linked site reports missing quest fields, the mod polls
`/api/mod/quest-repairs` every 60 seconds in the garage, authenticated with the
current account and link. Requests are paged, bounded to 20 arenas at a time,
and each arena is retried once per load/link through the existing results cache.
Recovered results follow normal capture and the server’s missing-only merge.
Account/link changes, paused sending and entering battle stop further repair
requests. A late response passes the same result-owner checks as any capture;
it can never be stamped with the new login.
No missing premium or multi-vehicle total is guessed. Deploy the site’s migration
0057 before this mod; a server without this endpoint simply returns an error and
normal capture continues. No automatic release is needed for this branch.

### Event/fun challenges

The quest detail capability now includes `other`. Positive bonus types outside
the historical families can supply their actual start, vehicles and observed
measurements to a player-created Other challenge. Existing training/tournament
exclusions remain; Other is not a wildcard for random or training. Missing data
stays missing, and no event credit formula is inferred. Deploy the matching
server contract before this package. In-game event evidence still requires live
acceptance; this does not extend the verified economy scenarios.

### Shared quest tracking in the garage (#958)

The mod follows the language selected for your account on the website (French
or English). The authenticated `/api/mod/me` and garage responses carry that
preference and its WG account ID. A garage refresh, every 15 seconds or with
Reload, updates cards, buttons, errors, settings and new notifications without
restarting or losing an open player draft. The server supplies individual quest
titles in the account language, using the site's available translations.
Usernames and user-written session titles stay as written. Offline responses
keep the last valid session language; another
account or link clears it. Older servers remain compatible with English as
the fallback. Deploy the matching server preference fields before this build;
no new migration or configuration is needed.

A native BigWorld GUI panel works without either optional menu API. Its dark
card has a draggable header and a separate `Collapse` / `Expand` button.
The selected quest and each player have separate cards. Official results and
indicative mod estimates have their own labels and progress bars; unknown or
incomparable values never become invented progress. The palette uses opaque
dark backgrounds, white body text and warm accents, with at least 4.5:1 text
contrast. Native DDS surfaces carry their actual colours, including a fully
transparent content texture, rather than relying on tinting a white texture.
`Change quest` cycles through active individual quests and joined/already
selected sessions. The mode button selects automatic platoon tracking or a
manual list. Click `Edit players`, type at least two characters of a
Battle-Conquest username, then choose a suggestion by clicking or with the arrow
keys and Enter. Up to five suggestions are shown; type more characters to narrow
the search. Select up to four other players, remove a selected name with `×`,
then click `Save`. Enter selects a suggestion, or saves when the search is empty.
Escape closes the search first, then cancels the draft; `Clear` removes the
selected players without saving. Failed searches preserve the selected names,
and outdated replies cannot replace the current suggestions. The website uses
the same name search; IDs remain internal to the saved configuration. Deploy
the server `/api/mod/quest-garage/players` route and `manual_players` metadata
before this package; no additional migration or configuration is needed.
Your account is always included in the five-player limit. The expanded window
has a fixed 520-pixel height, reduced to fit smaller screens. Its content and
player editor scroll with the mouse wheel, a click on the scrollbar track or
a drag of its thumb. Actions and connection status stay pinned below the
viewport. Keyboard navigation keeps the active suggestion visible; clipped rows
cannot receive clicks. Refreshing scores preserves the reading position.

Compact cards show the selected quest, names and progress; official and
indicative mod figures sit in separate columns when both exist. Unknown and
incomparable values, incomplete data, battle counts and the no-reward status
remain explicit. The duplicated quest overview and raw UTC dates are omitted
from the panel; full quest/session details remain on the website.
The panel starts at a pixel offset inside the visible GUI viewport. Its position
is clamped again when its content or the resolution changes; older saved clip
coordinates are migrated automatically. Native text retains its automatic size;
legacy text dimensions are converted into pixels for the window layout.
Native coordinate modes and anchors use `GUI.Simple` enum constants, as in
the client scripts; string names are not used. `game.log` records `geometry ready-v12`
and drag start/stop positions. Session-owned hooks route mouse press, movement
and release before garage Scaleform input, consuming only panel interactions.
They delegate while hidden or in battle and are restored when the mod stops.
Every native GUI component is passive: no script or key, mouse, drag or drop
focus is registered with the native GUI event bridge. The current client
reported `TypeError: Unregistered type : BW::KeyEvent` followed by a native
crash with that second input path enabled. Only the game input hooks dispatch
panel actions; the log confirms `game-hooks-only`. Local tests model the failing
conversion boundary and verify that clicking, dragging and typing work without
entering it. The first live retest no longer crashed; stability over longer
use remains part of in-game acceptance.
The native garage font is isolated under `system/fonts/battle_conquest/` and
ships its own DejaVu-derived glyph atlas. Explicit Unicode ranges avoid the
Windows code-page interpretation of legacy byte ranges, keeping French accents,
ligatures and punctuation distinct. The game needs no font installation and
the mod does not replace any shared client font. Text is normalized to Unicode
NFC before measuring/rendering. The log records `garage font: bundled-unicode`.
The editor retains its draft until the site acknowledges the save, including
after a timeout or validation error. Typing while a save is in flight is kept.

Quest selection, mode and manual list synchronize with `/quest` on the site.
Concurrent edits produce a visible conflict: click `Reload` to accept the latest
configuration before editing again. A private session becomes readable after its
share link has been opened under the same BC account on the site; tracking never
enrolls anyone or grants rewards. The site also lets you select a session by ID.

The panel waits for the hangar space to load and the client waiting overlay to
close before it appears or captures input. Transient waiting overlays preserve
the selected names, typed query and draft version; an interrupted search resumes
when the panel is visible and expanded again. This display gate is independent
of the account gate used to request and send results during the return. The
sender checks its local queue every five seconds, including when results arrive
after the account-becomes-player event. Empty ticks send no HTTP requests; the
existing 15-minute refusal backoff is retained. A `sending ... battle(s)` log
line separates the start of a request from its acceptance or refusal. A transport
setup failure retains the report and releases the sender for a later retry after
the usual backoff, without requiring a client restart.

The panel refreshes every 15 seconds in the garage and after reports are sent.
Data age uses `hh:mm:ss` with cumulative hours (for example `25:01:02`),
including while offline. Missing timestamps remain explicitly unknown.
It hides during battle and restores its position/fold state on return. Offline
responses retain the last values, their age and an offline indication. Switching
accounts or links clears the old data and discards replies still in flight.
Folding the editor keeps its draft and returns keyboard input to the garage;
mouse clicks outside the panel remain available while editing.
Official values and comparable mod estimates are labelled separately. Other
players' estimates use the current attempt/session period and carry no rewards.
Unavailable values and incomparable historical XP are shown explicitly.

Requires the server changes and migration in Battle-Conquest#958, delivered as
part of #772 before this mod. The server feature switch remains off until the
combined release is validated. Native rendering, keyboard input and the current
client's platoon adapter still need the in-game acceptance test.

The native layout uses nested `GUI.Window` components: BigWorld only translates
child positions with a Window parent, and pixel coordinates start at its top
left. See the [engine GUI documentation](https://howarduong.github.io/github.io/doc/api_python/client_python_api/doc/WindowGUIComponent.html).
Regenerate the flat DDS surfaces after palette changes with
`python3 tools/build_garage_theme.py`; the selftests check their pixels/alpha
and contrast, and the release check verifies that every surface is packaged.
To regenerate the font, install `tools/font-requirements.txt` in a development
environment, then run `python3 tools/build_garage_font.py --source /path/to/DejaVuSans.ttf`.
Use the source SHA-256 pinned in that tool. The shipped XML/DDS and licence are
checked by the Python 2.7 tests and release checker; Pillow is only a build tool.

### Immediate post-battle feedback (#958)

The garage shows one last-battle card as soon as WoT supplies its result, with
provisional local measurements and an explicit delivery state. Capture schedules
sending on the next frame; it never performs HTTP work inside a native result
hook. The five-second queue timer remains a fallback, and network-error backoff
is unchanged. Result discovery also has a five-second fallback; cache cooldown
and centre-disconnection refusals still wait twenty seconds between attempts.

After each batch answer, the garage requests `receipt_arena` from the authenticated
server API. The stored receipt replaces local figures, including when they differ.
Official quest totals always come from Battle-Conquest; receipt of a battle does
not prove quest eligibility, completion or rewards. A read already in flight at
delivery cannot consume the required fresh read. Only one battle is displayed,
old result screens cannot replace a newer one, and account/link changes clear it.

Only an observed battle avatar starts post-battle retrieval: a cluster switch
or reconnection keeps the last confirmed card. If no result has been announced,
the retrieval placeholder expires after sixty seconds. Announced requests keep
their existing retries; the display timeout never cancels capture or delivery,
so a late result can still replace the placeholder.

The server keeps active choices plus one latest finished quest/challenge in the
tracker. Closed challenges explicitly say that final results are still arriving,
or that results are final after settlement. The full history stays on the site.
Deploy the matching server update before installing this build. No new migration
or configuration is needed. Expected log marker: `garage geometry feedback-v14`.

### Recovery after an interruption

The mod records arena IDs at battle entry in `battle-recovery.json`, separately
from captured reports. Entries keep their original account and region; unknown
origins remain isolated. Recovery waits five seconds after an announcement or
return to the garage and shares one cache scheduler with quest evidence repair.
Each owner has at most 50 entries, five attempts per arena and seven days of
retention. Abandoned entries retain their attempt budget until expiry or
bounded eviction, so repeated announcements cannot restart recovery. Pausing suspends collection and recovery; a revoked link keeps data
until linking again (explicit local diagnostics can still retrieve results).

A report leaves the sending queue only with a valid individual server verdict.
Unreadable or partial responses keep unconfirmed reports for a later retry.
The recovery delay reduces collisions with the results screen and other mods;
notification behaviour and frame-time impact still require in-game testing.
Valid results of unwanted modes and successfully saved standalone diagnostics
do not consume repeated cache attempts; pauses and storage failures retain recovery work.
