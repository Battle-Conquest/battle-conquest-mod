# Contribuer

Ce dépôt suit les conventions de [Battle-Conquest](https://github.com/Battle-Conquest/Battle-Conquest)
(`docs/CONVENTIONS.md`), adaptées à un mod client en Python 2.7.

Lire [`AGENTS.md`](./AGENTS.md) d'abord : il contient les règles non évidentes qui
comptent pour un changement sûr, avant tout la façon dont le rechargement à chaud
reste sûr.

## Langues

- **Français** : commits, titres et descriptions de PR, issues, ce fichier.
- **Anglais** : le code, ses commentaires, et tout ce que le joueur voit dans le
  client (la page de réglages, les messages du garage). Le mod n'a pas d'i18n.

## Issues

Les issues du mod sont suivies dans le dépôt
[Battle-Conquest/Battle-Conquest](https://github.com/Battle-Conquest/Battle-Conquest/issues),
avec le label **Mod Battle-Conquest** : une évolution du mod va presque toujours de
pair avec le serveur (contrat `/api/mod/battles`, stockage, preuve des quêtes).
Ce qu'il faut au mod est décrit dans la section « Côté mod » de l'issue.

## Mise en place

Suivre la section Development du [`README.md`](./README.md) : lancer
`tools/install_dev.py`, démarrer le client une fois. Ensuite, enregistrer un fichier
sous `src/` recharge le mod sans redémarrer le jeu.

## Branches

- Ne jamais travailler sur `main` ; ne jamais supprimer `main`.
- Une branche par issue, créée depuis `main`, avec le numéro de l'issue :
  `feat/<num>-<slug>`, `fix/<num>-<slug>`, `chore/<num>-<slug>`.

## Commits

Format : `<type>(#<num>): <description>`, où `<num>` est le numéro de l'issue dans
Battle-Conquest/Battle-Conquest.

```text
feat(#813): ajouter le char joué à chaque rapport de bataille
fix(#842): ne plus renvoyer une bataille après une reconnexion
chore(#819): adopter les conventions de commit de Battle-Conquest
```

- Types : `feat` (nouvelle capacité), `fix` (correctif), `perf` (amélioration
  sensible pour le joueur), `refactor`, `docs`, `test`, `chore`.
- Description en minuscule, à l'infinitif ou au présent, qui dit ce qui change.
- Un commit par changement logique ; plusieurs commits par PR si les étapes sont
  distinctes.
- Sans issue (rare), `<type>: <description>`.

`tools/release.py` lit ces sujets : `feat` fait monter la version mineure, le reste
la version de correctif, et `feat` / `perf` / `fix` alimentent le changelog. Un sujet
qui ne suit pas le format compte quand même, mais n'apparaît pas au changelog.

## Vérifications (avant tout commit)

```bash
python2.7 tools/selftest.py
```

- La suite doit passer : tout changement vient avec un check dans `tools/checks/`.
- Après un changement rechargé dans le client, relire `game.log`.
- Packaging touché (`tools/build_release.py`, `res/`, `vendor/`, points d'entrée) :
  construire puis contrôler le paquet.

```bash
python tools/build_release.py --version x.y.z
python2.7 tools/release_check.py dist/eu.battle-conquest_x.y.z.wotmod
```

## Pull requests

- Titre au format des commits : `<type>(#<num>): <description>`.
- Le corps contient :
  - `Closes Battle-Conquest/Battle-Conquest#<num>` (l'issue vit dans l'autre dépôt) ;
  - un résumé des changements ;
  - le **résultat réel** des vérifications (selftest, et build + release check si
    concerné), pas une promesse générique ;
  - ce qui reste à tester en jeu, le cas échéant.
- Fusion en **squash** : le titre de la PR devient le commit sur `main`.
- Un changement du contrat d'API se fait d'abord côté serveur (Battle-Conquest,
  `docs/mod-battles-api.md`), puis ici.

## Versions et releases

- La version n'est **pas** bumpée dans les PR : `tools/release.py` la déduit des
  commits depuis le dernier tag `vX.Y.Z`, prépare le changelog (en anglais, pour les
  joueurs : il s'ouvre dans un éditeur pour être relu et traduit), construit, tague
  et crée la release GitHub **en brouillon**.
- Une release n'est publiée qu'après avoir capturé une bataille dans un vrai
  client : `gh release edit vX.Y.Z --draft=false`.
