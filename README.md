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
kept. **Unlink** makes this game forget its key; revoke it on the site too.

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
GitHub can carry a still newer release. Older servers without this information
continue to link and send battles normally.

## What is sent, and what is not

- Only the modes the site says it scores, read from the site when you link and
  checked again now and then.
- Per battle: its arena id, mode, end time, outcome, whether you survived, and
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
| `link.json` | the key, the modes the site scores, and whether sending is paused |
| `battle-reports.json` | battles waiting to be sent |
| `battle-reports-refused.json` | the last batch the site could not read, kept for whoever has to find out why |

An optional local results diagnostic is available for the quest measurements
work in [#953](https://github.com/Battle-Conquest/Battle-Conquest/issues/953).
It is disabled by default. See the [in-game diagnostic procedure (French)](./DIAGNOSTIC.md)
for activation, files, limits and the comparisons to record. These observations
are never sent to the site and do not change the existing battle reports.

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
Account/link changes, paused sending and entering battle stop stale callbacks.
No missing premium or multi-vehicle total is guessed. Deploy the site’s migration
0057 before this mod; a server without this endpoint simply returns an error and
normal capture continues. No automatic release is needed for this branch.

### Shared quest tracking in the garage (#958)

A native BigWorld GUI panel works without either optional menu API. Click its
title to fold it, or drag the title to move it. `Next quest` cycles through active
individual quests and joined/already selected sessions. `Switch mode` selects
automatic platoon tracking or a manual list. Click `Manual IDs`, type up to four
other **Battle-Conquest account IDs** separated by commas, and press Enter to
save (Escape cancels). Your account is always included in the five-player limit.
The panel starts at a pixel offset inside the visible GUI viewport. Its position
is clamped again when its content or the resolution changes; older saved clip
coordinates are migrated automatically. Native text retains its automatic size;
legacy text dimensions are converted into pixels for the window layout.
`game.log` records `geometry pixel-v3`
and drag start/stop positions to diagnose a client that cannot move the title.
The editor retains its draft until the site acknowledges the save, including
after a timeout or validation error. Typing while a save is in flight is kept.

Quest selection, mode and manual list synchronize with `/quest` on the site.
Concurrent edits produce a visible conflict: click `Reload` to accept the latest
configuration before editing again. A private session becomes readable after its
share link has been opened under the same BC account on the site; tracking never
enrolls anyone or grants rewards. The site also lets you select a session by ID.

The panel refreshes every 15 seconds in the garage and after reports are sent.
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

The native layout uses a transparent `GUI.Window`: BigWorld only translates
child positions with a Window parent, and pixel coordinates start at its top
left. See the [engine GUI documentation](https://howarduong.github.io/github.io/doc/api_python/client_python_api/doc/WindowGUIComponent.html).
