"""Compare public WoT version sources with the ZIP players actually download.

Python 3, standard library only. --dry-run performs reads without issue writes.
"""
import argparse
import io
import json
import os
from pathlib import Path
import re
import sys
from urllib.request import Request, urlopen
from xml.etree import ElementTree
import zipfile

from client_issue import gh_json, sync_issue


MIRROR = "https://raw.githubusercontent.com/izeberg/wot-src/EU/sources/paths.xml"
HUB = "https://wgmods.net/"
VERSION = re.compile(r"[0-9]+(?:\.[0-9]+){3}")
ASSET = re.compile(r"battle-conquest-mod_[0-9]+(?:\.[0-9]+){2}\.zip")
PACKAGE = re.compile(
    r"mods/([0-9]+(?:\.[0-9]+){3})/eu\.battle-conquest_[0-9]+(?:\.[0-9]+){2}\.wotmod"
)
CHECKLIST = """

Recette de la nouvelle release (validation manuelle) :
- [ ] Adapter la version WoT ciblée et préparer la release selon [RELEASING.md](https://github.com/Battle-Conquest/battle-conquest-mod/blob/main/RELEASING.md).
- [ ] Installer le ZIP sur le client EU à jour, sans ancienne version du mod ni bootstrap de développement.
- [ ] Vérifier la liaison et le panneau des quêtes dans le garage.
- [ ] Jouer une bataille prise en charge et confirmer sa réception sur le site.
- [ ] Publier la release validée et soumettre le mod à WGMods.
"""


def numbers(value):
    if not VERSION.fullmatch(value):
        raise ValueError("invalid WoT version: %r" % value)
    return tuple(int(part) for part in value.split("."))


def fetch(url):
    request = Request(url, headers={"User-Agent": "battle-conquest-client-watch"})
    with urlopen(request, timeout=30) as response:
        return response.read()


def parse_mirror(payload):
    root = ElementTree.fromstring(payload)
    versions = set()
    for path in root.findall("./Paths/Path"):
        text = (path.text or "").strip()
        if text.startswith("./mods/"):
            version = text[len("./mods/"):]
            numbers(version)
            versions.add(version)
    if len(versions) != 1:
        raise ValueError("paths.xml must name exactly one mods version")
    return versions.pop()


def parse_hub(payload):
    # WGMods embeds JSON in a JS string; quotes currently arrive as \\u0022.
    # Restrict the read to gameVersions, never other version numbers on the page.
    text = re.sub(r"\\+u0022", '"', payload.decode("utf-8"))
    match = re.search(r'"gameVersions"\s*:\s*(\[[^\]]*\])', text)
    if not match:
        raise ValueError("WGMods gameVersions is missing")
    entries = json.loads(match.group(1))
    if not entries or not isinstance(entries, list):
        raise ValueError("WGMods gameVersions is empty or malformed")
    versions = [entry["version"] for entry in entries]
    return max(versions, key=numbers)


def read_sources(fetcher):
    versions = {}
    for name, url, parser in (("upstream", MIRROR, parse_mirror), ("hub", HUB, parse_hub)):
        try:
            versions[name] = parser(fetcher(url))
        except (OSError, ValueError, KeyError, TypeError, ElementTree.ParseError) as error:
            print("%s unavailable: %s" % (name, error), file=sys.stderr)
            versions[name] = None
    available = [value for value in versions.values() if value]
    if not available:
        raise ValueError("neither WoT version source could be read")
    versions["live"] = max(available, key=numbers)
    return versions


def shipped_version(payload):
    # Read filenames without extracting or executing anything from the archive.
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        packages = [name for name in archive.namelist() if name.endswith(".wotmod")]
    if len(packages) != 1:
        raise ValueError("release ZIP must contain exactly one .wotmod")
    match = PACKAGE.fullmatch(packages[0])
    if not match:
        raise ValueError("release ZIP has no valid mods/<WoT version>/ package path")
    return match.group(1)


def compare(repo, api=gh_json, fetcher=fetch):
    result = read_sources(fetcher)
    # GitHub's latest-release endpoint excludes drafts and prereleases.
    release = api(["repos/%s/releases/latest" % repo])
    assets = [asset for asset in release["assets"] if ASSET.fullmatch(asset["name"])]
    if len(assets) != 1:
        raise ValueError("latest stable release must have exactly one installation ZIP")
    url = assets[0]["browser_download_url"]
    if not url.startswith("https://github.com/%s/releases/download/" % repo):
        raise ValueError("unexpected release download URL")
    result.update(tag=release["tag_name"], asset_url=url,
                  shipped=shipped_version(fetcher(url)))
    result["news"] = numbers(result["live"]) > numbers(result["shipped"])
    result["disagree"] = (bool(result["upstream"] and result["hub"])
                          and numbers(result["upstream"]) != numbers(result["hub"]))
    return result


def report(result):
    text = (
        "Version WoT détectée : **{live}**. Le ZIP de la release **{tag}** cible "
        "`mods/{shipped}/`.\n\n"
        "[WGMods](" + HUB + ") : `{hub}` · [Miroir EU](" + MIRROR + ") : `{upstream}`.\n\n"
        "[Paquet vérifié]({asset_url})."
    ).format(**{key: value if value is not None else "indisponible"
                for key, value in result.items()})
    if result["news"]:
        text += "\n\nLe paquet cible un ancien dossier de mods ; une nouvelle release est nécessaire."
    elif numbers(result["shipped"]) == numbers(result["live"]):
        text += "\n\nLe paquet cible la version WoT détectée."
    else:
        text += "\n\nLe paquet est en avance sur les sources consultées ; aucune alerte."
    if result["disagree"]:
        text += "\n\nLes deux sources divergent ; l’une peut être en retard."
    return text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="read sources without writing issues")
    args = parser.parse_args()
    repo = os.environ.get("GH_REPO", "Battle-Conquest/battle-conquest-mod")
    try:
        result = compare(repo)
        text = report(result)
        print(text)
        if result["news"] and not args.dry_run:
            sync_issue(repo, result["live"], text,
                       "WoT %s : mettre à jour le paquet du mod" % result["live"],
                       suffix=CHECKLIST)
    except Exception:
        write_summary("Échec de la vérification : aucun verdict de compatibilité disponible.")
        raise
    write_summary(text)


def write_summary(text):
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with Path(path).open("a", encoding="utf-8") as handle:
            handle.write(text + "\n")


if __name__ == "__main__":
    main()
