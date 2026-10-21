---
name: release-mod
description: "Créer une release du mod Battle-Conquest sur Linux : ZIP, .wotmod, brouillon GitHub et PR du changelog. Pour une demande de release du mod ou $release-mod, pas pour une release du site."
---

# Release du mod Battle-Conquest

Cible : `Battle-Conquest/battle-conquest-mod`. Livrer un **brouillon**, ses deux
fichiers et la PR du changelog vers `main`. Ne pas publier, merger, soumettre à
WGMods ou modifier le site. Échanges et PR en français ; notes et commits en anglais.

## Préparer

1. **À chaque nouvelle release**, demander la version exacte de World of Tanks
   EU ciblée (`mods/<version>/`), sauf si fournie pour cette release. Attendre
   avant tout build, commit de release ou tag ; préparer les lectures et le
   worktree pendant l'attente. Ne pas déduire la version actuelle du jeu de
   `GAME_VERSION` ni réutiliser une réponse d'une ancienne release.
2. Vérifier le dépôt, récupérer `origin/main` et les tags, créer un worktree
   propre et une branche `release/mod-<version>` depuis `origin/main`.
   Préserver les autres worktrees et les changements non fusionnés. Chercher
   un brouillon et une PR existants : pour la même livraison, reprendre ou
   rendre leurs liens plutôt que créer une autre version.
3. Vérifier `gh auth status`, Python 3.10+ et Python 2.7. Sur ce serveur,
   essayer `~/.local/bin/python2.7`, puis `command -v python2.7` ; vérifier sa
   version et conserver le chemin absolu dans `python27`.
4. Comparer la version du jeu confirmée à `GAME_VERSION` dans
   `tools/build_release.py`. Si différente, la modifier dans cette branche et
   indexer uniquement ce fichier. Le script de release committe les fichiers
   indexés avec le changelog après les contrôles : livrer le tout dans **une
   seule PR**, sans fusion préalable. Vérifier l'index pour exclure tout fichier
   étranger. Ne pas contourner le décalage en renommant le ZIP.

## Générer

Depuis le worktree, calculer une fois la version avec RTK :

```bash
rtk proxy python3 -B tools/release.py --dry-run
```

Accepter le calcul (`feat` → mineure, sinon correctif), sauf instruction contraire.
Appliquer le même `--patch`, `--minor` ou `--major` aux deux exécutions si demandé.
Si un numéro imposé est impossible avec ces options, signaler la limite avant
de taguer, sans substituer un numéro. Sans nouveau commit, terminer sans release.
Ajuster le nom de branche après le calcul si besoin.

Écrire les notes anglaises pour les joueurs depuis la prévisualisation dans un
fichier temporaire **hors du dépôt**, chemin absolu `notes_file`. Commencer par
`## X.Y.Z` correspondant au calcul. Traduire/corriger les sujets et retirer les
commentaires internes ; lire seulement les diffs nécessaires si ambigus.
Ne pas demander de validation supplémentaire des notes ou de la version.

L'éditeur fourni injecte ces notes sans interaction dans le script existant :

```bash
rtk proxy env EDITOR="$PWD/.codex/skills/release-mod/scripts/notes_editor.py" \
  RELEASE_MOD_NOTES="$notes_file" \
  python3 -B tools/release.py --python27 "$python27"
```

Le script construit depuis la branche avec la version du jeu mise à jour,
lance `selftest.py` et `release_check.py`, committe,
tague, pousse et crée le brouillon. Ne pas refaire les contrôles réussis.
Conserver le log hors du dépôt ; lire le résultat ou l'extrait utile en cas
d'échec. Ne pas réécrire le script de release ni son calcul de version.

## Livrer

- Contrôler localement que le ZIP contient le seul fichier
  `mods/<version confirmée>/eu.battle-conquest_X.Y.Z.wotmod`. Vérifier une fois
  `gh release view vX.Y.Z --json isDraft,url,assets` : brouillon et deux assets.
- Ouvrir/réutiliser l'unique PR de release (changelog et version du jeu) vers `main`, description française
  concise via `--body-file` : versions mod/jeu, lien du brouillon, résultats
  locaux réels et test en jeu restant. Ne pas inventer d'issue associée.
  **Ne jamais consulter, surveiller ou attendre la CI.**
- Terminer avec les liens brouillon/PR, versions et résultats. Rappeler que le
  test en jeu précède la publication manuelle ; ne pas attendre sa réalisation.

En cas d'échec partiel, examiner seulement les fichiers, commit, tag et brouillon
concernés. Ne pas relancer intégralement, remplacer un tag, écraser des assets
ou incrémenter pour masquer l'échec. Reprendre les étapes manquantes sans
écrasement ; si l'état est ambigu, exposer le point à résoudre. Lire la
[procédure humaine](../../../RELEASING.md) seulement si nécessaire.
