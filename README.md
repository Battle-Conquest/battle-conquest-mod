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

The page's own box (enabled) pauses sending: battles played meanwhile are not
kept. **Unlink** makes this game forget its key; revoke it on the site too.

Without those two mods there is no page, and nothing is lost but pausing and
unlinking from the game: the garage notification links the game, and a key is
revoked from your page on the site, after which the mod forgets it by itself.

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

## With unicum.gg-mod installed

Both mods load side by side: they share no file, package or setting. If
unicum.gg-mod also sends battles to Battle-Conquest one day, each battle
arrives twice and the second copy is answered `duplicate` (the site keys a
battle by player and arena). Nothing is counted twice.

## Development

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
