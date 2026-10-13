# vendor

The `.wotmod` files bundled beside the mod in the release archive, under their
own file names, so a copy a modpack installed is overwritten rather than loaded
twice:

| File | Project | What the mod uses it for |
|---|---|---|
| `izeberg.modssettingsapi_<version>.wotmod` | [izeberg/modssettingsapi](https://github.com/izeberg/modssettingsapi/releases) | the settings page |
| `poliroid.modslistapi_<version>.wotmod` | [wot-public-mods/mods-list](https://gitlab.com/wot-public-mods/mods-list/-/releases) | the menu entry that opens it |

`tools/build_release.py` puts every `*.wotmod` found here into the archive, and
`tools/install_dev.py` into a dev client. Update one by replacing its file.

They are other authors' work, unchanged, under their own terms: see `NOTICE`.
