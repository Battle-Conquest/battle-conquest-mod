# Générer et publier une release du mod

Ces commandes s'exécutent dans le dépôt **battle-conquest-mod**. Partir de
`main` avec les changements du mod à distribuer. La version du jeu et le
changelog sont livrés ensemble dans une seule PR de release.

Avec Codex sur le serveur Linux, demander « crée une release du mod » ou invoquer
[`$release-mod`](.codex/skills/release-mod/SKILL.md). Le skill demande la version
du jeu pour chaque release, prépare les notes en anglais, crée le brouillon et
la PR du changelog. Le test en jeu et la publication restent manuels.

## 1. Préparer l'environnement et la branche

Il faut Git, **Python 3.10+**, **Python 2.7** (pour compiler le mod et le tester),
GitHub CLI (`gh`) authentifié avec les droits de push et de création de release,
et un éditeur disponible (`nano` sous Linux, `notepad` sous Windows par défaut).

```bash
gh auth status
git status --short
git fetch origin main --tags
git worktree add -b release/mod-next ../battle-conquest-mod-release origin/main
cd ../battle-conquest-mod-release
```

Utiliser un nom de branche et un dossier libres pour chaque release. Ne pas
travailler directement sur `main`. Vérifier que le nouveau worktree est propre.
Sous Windows, remplacer `python3` par la commande de votre Python 3 si nécessaire.

Vérifier que `GAME_VERSION` dans [tools/build_release.py](tools/build_release.py)
correspond au dossier `mods/<version du jeu>/` du client ciblé. Si cette valeur
doit changer, la modifier sur cette branche, puis l'indexer :

```bash
git add -- tools/build_release.py
git diff --cached
```

Vérifier que seuls les changements de la release sont indexés. Le script les
committera avec le changelog après les tests ; aucune fusion préalable n'est
nécessaire pour construire le `.wotmod` et le ZIP depuis cette branche.

## 2. Prévisualiser la version

```bash
python3 tools/release.py --dry-run
```

Aucun fichier n'est modifié. La version est calculée depuis le dernier tag
`vX.Y.Z` : un commit `feat` augmente la mineure, sinon le correctif augmente.
Pour forcer le niveau, ajouter `--patch`, `--minor` ou `--major` **à la
prévisualisation et à la commande de génération**. Si le script indique
`nothing since ...`, aucun nouveau commit n'est disponible depuis le tag.

## 3. Générer les fichiers et le brouillon GitHub

Remplacer le chemin ci-dessous par celui de l'exécutable Python **2.7** installé
(par exemple `C:/Python27/python.exe` sous Windows).

```bash
python3 tools/release.py --python27 "/chemin/vers/python2.7"
```

Relire les notes proposées dans l'éditeur, les adapter en anglais, enregistrer
et fermer. Vider le fichier permet d'annuler avant la génération.

Le script met à jour `CHANGELOG.md`, construit les fichiers, exécute
`selftest.py` et `release_check.py`, puis committe le changelog, crée le tag,
pousse la branche et le tag, et crée une release GitHub **en brouillon** avec :

```text
dist/eu.battle-conquest_X.Y.Z.wotmod
dist/battle-conquest-mod_X.Y.Z.zip
```

Le ZIP contient `mods/<version du jeu>/eu.battle-conquest_X.Y.Z.wotmod`.
Les archives GitHub « Source code » ne remplacent pas ce ZIP compilé.

En cas d'échec, lire l'erreur et vérifier l'état des fichiers, du tag et du
brouillon avant de relancer : le script n'annule pas les étapes déjà effectuées.

## 4. Intégrer le changelog, tester et publier

Remplacer `X.Y.Z` par la version affichée par le script. Ouvrir une PR pour
conserver le changelog et l'éventuelle mise à jour de la version du jeu sur `main` :

```bash
gh pr create --base main --head release/mod-next --title "chore(release): X.Y.Z" --body "Intègre le changelog de la release X.Y.Z."
```

Décompresser le ZIP dans le dossier World of Tanks, sans ancienne version du
mod ni bootstrap de développement actif. Démarrer le jeu, vérifier la liaison,
jouer une bataille prise en charge et confirmer son arrivée sur le site.
Après validation, publier le brouillon :

```bash
gh release edit vX.Y.Z --draft=false
```

Le ZIP devient téléchargeable depuis la
[dernière release](https://github.com/Battle-Conquest/battle-conquest-mod/releases/latest).
Pour soumettre aussi le `.wotmod` à WGMods, suivre les
[consignes WGMods](CONTRIBUTING.md#versions-and-releases) ; la publication GitHub
ne vaut pas approbation par Wargaming.
