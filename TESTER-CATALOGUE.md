# Private catalogue tester — Battle-Conquest #834

This build is for one informed, server-authorized tester. It is not a normal
release and must not be distributed or submitted to WGMods. The standard build
contains no catalogue collection code: the three modules live under `tester/`,
outside `src/`, and only the separate builder adds them to a staged package.

## Build and install

```bash
rtk proxy python3 tools/build_catalog_tester.py --version 1.2.0 --game-version 2.4.1.0
```

Choose the source revision's mod version and the installed game's version.
If Python 2.7 is not detected, pass `--python27 /path/to/python2.7`.
The output is `dist/battle-conquest-catalog-tester_<version>.zip`.
The server must already provide `/api/mod/vehicle-catalog`, apply migration 0065,
and set `MOD_CATALOG_TESTER_USER_ID` to your internal Battle-Conquest user ID.
That setting defaults to disabled. No extra secret is needed.

Close the game. Remove the standard Battle-Conquest `.wotmod`, then unzip the
private tester archive into the game folder. **Do not install both together:**
they share their Python entry point. Existing account linking remains usable.
The settings page explicitly says **Battle-Conquest TESTER**.

## Manual collection

At the loaded garage, link the current game account and enable sending.
Click **Collect** in the mod settings, or **Collect and send catalogue** in the
garage's notification centre. No extra settings mod is required for that link.
No catalogue is read or sent at startup or after battles. No client path is asked
for: the collector reads the running client's national vehicle lists directly.

The status reports progress, completion or errors. A second click while busy
cancels; double start calls cannot stack collectors. Account changes, unlinking,
pause and session shutdown invalidate pending responses. Temporary failures retry
up to three times in the same session; after restart you must click again.
Without the optional settings window, garage notifications announce collection,
sending and retry delays, without posting a message for every extraction slice.
A partial extraction never uploads. A successful upload still needs admin review.
Identical uploads are deduplicated by the server.

On `/admin/mod-vehicle-catalog`, compare each proposed classification with the
running client before accepting. Preserve the raw tags and client version as
evidence. Unknown or ambiguous cases stay unaccepted. At least one real vehicle
per category (tech tree, premium, reward, collector) must be checked in game;
offline fixtures do not establish those real classifications.

To restore the public mod, close the client, remove the tester package and
reinstall the standard one. The server can disable uploads with the tester ID
set to `0`, without changing accepted classifications.

## Contract and evidence

The server's [`docs/mod-vehicle-catalog.md`](https://github.com/Battle-Conquest/Battle-Conquest/blob/main/docs/mod-vehicle-catalog.md)
defines the schema 2 payload, canonical SHA-256, limits and error codes.
Battle reports keep schema 1. Every upload is bound to the currently linked
account, region and HTTPS destination; the server independently checks access.

The adapter uses `items.vehicles.g_list.getList(nation_id)` and descriptor
`compactDescr`, `name`, `tags`, plus `helpers.getClientVersion()`. These surfaces
were inspected in the EU client scripts at commit
[`ed377b7`](https://github.com/izeberg/wot-src/tree/ed377b7bc5e8c232cf41bd0887bcfa0d75005fcb).
Actual descriptor availability and the reference vehicles still need a live test.
No inventory restriction, guessed paths, clone pairing or reskin inference is used.

## Local checks

```bash
rtk proxy python2.7 tools/selftest.py
rtk proxy python3 tools/test_catalog_packaging.py
rtk proxy python2.7 tools/release_check.py dist/eu.battle-conquest-catalog-tester_1.2.0.wotmod
```

Also build and run `release_check.py` on the standard package. The packaging test
checks that standard staging contains none of the private modules or activation.
The selftest checks manual start, incomplete extraction, shared PHP/Python
fingerprint, account changes, retries, visible errors, settings callback identity,
and session teardown. It never contacts a server.
