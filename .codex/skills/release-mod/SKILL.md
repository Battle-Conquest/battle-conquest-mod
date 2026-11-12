---
name: release-mod
description: "Préparer ou reprendre la PR de release automatisée du mod Battle-Conquest. Pour une demande de release du mod ou $release-mod, pas pour une release du site."
---

# Release du mod Battle-Conquest

Cible : `Battle-Conquest/battle-conquest-mod`. Suivre
[RELEASING.md](../../../RELEASING.md), les workflows et les scripts actuels.
La voie normale est l'unique PR **`release/next`**, avec plan et changelog.
Sa fusion manuelle déclenche construction, contrôles et publication ; elle
ne crée pas simplement un brouillon à publier plus tard.

## Préparer la proposition

1. Lire `AGENTS.md`, vérifier le dépôt et récupérer `origin/main` et les tags.
   Utiliser un worktree propre basé sur `origin/main`, sans changer le checkout
   principal. Vérifier `gh auth status` et Python 3.10+.
2. Examiner les releases publiées et brouillons, l'éventuelle PR `release/next`
   et `.github/release-plan.json`. Réutiliser la proposition existante.
   Un plan fusionné non terminé relève de la reprise ci-dessous.
3. Depuis ce worktree, prévisualiser sans mutation :

   ```bash
   rtk proxy python3 -B tools/release_pr.py --dry-run
   ```

   Une prérelease active garde **le même numéro et le même statut**. Sinon,
   la plus haute stable reçoit un incrément **patch**, même avec des `feat`.
   Plusieurs préreleases actives, une version ambiguë ou un brouillon occupant
   le numéro bloquent la proposition : expliquer le blocage, sans choisir un
   autre numéro ni écraser un tag. Sans changement, rendre le constat sans release.
4. La demande de préparer une release autorise sa proposition, pas sa fusion.
   Créer ou actualiser la PR avec le script courant :

   ```bash
   rtk proxy python3 -B tools/release_pr.py
   ```

   Le script committe le plan et le changelog, pousse `release/next` avec une
   garde sur sa révision et crée ou actualise la PR. Ne pas créer une seconde
   branche de release ni modifier manuellement le plan pour forcer une version.
5. Relire les notes pour les joueurs, en anglais. Les notes sont régénérées à
   partir de `main` à chaque proposition ; les retouches propres à la branche
   se font juste avant la fusion. Préserver les notes et cases utilisateur
   hors de la section gérée de la description. PR et échanges en français.

Le dossier du ZIP vient de `GAME_VERSION` dans `tools/build_release.py`.
Un changement WoT seul ne justifie ni release ni question systématique sur la
version du jeu : le joueur adapte les chemins. Pour une recette ou une soumission
WGMods demandée, confirmer le client effectivement ciblé si cette information
manque, sans prétendre que renommer le dossier démontre la compatibilité.

## Vérifier et livrer

- Lancer les contrôles locaux adaptés de `RELEASING.md` avant de livrer des
  changements. Ne pas répéter les contrôles déjà réussis sans raison.
  Pour construire localement, utiliser Python 2.7, disponible sur ce serveur
  à `~/.local/bin/python2.7`, puis vérifier le `.wotmod` **et le ZIP complet**.
- Le ZIP public contient le mod, Gameface 1.2.2 au chemin partagé
  `mods/<version>/net.openwg/` et sa licence. Le `.wotmod` autonome ne suffit
  pas pour la carte intégrée. Le test de recette en jeu reste distinct.
- Ne pas fusionner, promouvoir une prérelease, soumettre à WGMods ou modifier
  le site sans demande explicite correspondante. Une stable et son tag ne
  sont jamais remplacés.
- **Ne jamais consulter, surveiller ou attendre la CI**, y compris après un
  lancement manuel de workflow. Terminer avec le lien de la PR, la version,
  son statut prévu et les résultats ou limites des contrôles locaux.
  L'utilisateur vérifie la CI et décide de la fusion.

## Reprise ou secours exceptionnel

Lire la section de reprise de `RELEASING.md` avant toute action. Une publication
incomplète se reprend par `release.yml` avec **le même commit de fusion**.
Un plan périmé dont la publication n'a pas commencé peut être remplacé via
`release-pr.yml` avec `replace_pending=true`. Ne pas incrémenter le numéro,
déplacer un tag ou supprimer un plan pour masquer un échec. Une demande de
reprise de publication autorise cette reprise précise, pas une autre release.

`tools/release.py` reste réservé à un secours manuel **explicitement demandé**,
hors livraison automatisée active. Il utilise l'ancien calcul (`feat` → mineure,
sinon patch), construit, committe, tague, pousse et crée un brouillon : ne pas
le substituer silencieusement au plan automatique. Son éditeur facultatif
`scripts/notes_editor.py` lit les notes préparées depuis `RELEASE_MOD_NOTES`
et s'utilise via `EDITOR` ; son test est `scripts/test_notes_editor.py`.
Ce chemin exceptionnel ne dispense pas de vérifier le ZIP complet.
