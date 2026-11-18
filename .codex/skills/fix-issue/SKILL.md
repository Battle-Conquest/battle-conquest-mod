---
name: fix-issue
description: "Résoudre une issue GitHub concernant le mod Battle-Conquest jusqu'à la PR liée : analyse, branche depuis main, implémentation Python 2.7, tests et commits. Pour « fix issue #X », « résous l'issue #X » ou $fix-issue dans ce dépôt ; pas pour corriger uniquement le site ni publier une release."
---

# Corriger une issue du mod Battle-Conquest

Adapté du skill `fix-issue` du projet frère Battle-Conquest. Invoquer avec
`$fix-issue 246` ou une URL d'issue. Lire `AGENTS.md` et `CONTRIBUTING.md`.
Préfixer toutes les commandes shell par `rtk`, conformément à `RTK.md`.

Cible de la PR : `Battle-Conquest/battle-conquest-mod`. Les issues peuvent
vivre dans ce dépôt ou dans `Battle-Conquest/Battle-Conquest`, notamment sous
le label **Mod Battle-Conquest**.

## 1. Identifier l'issue et préparer la branche

1. Respecter le dépôt indiqué par l'URL ou l'utilisateur. Pour un numéro seul,
   chercher d'abord dans le dépôt Git du dossier courant, identifié par son
   remote, donc `Battle-Conquest/battle-conquest-mod` dans ce projet.
   Si l'issue courante correspond à la demande, la retenir sans rechercher
   le même numéro ailleurs. Consulter le dépôt
   frère seulement si l'issue est absente ou si les références de la demande
   le justifient, et vérifier que l'issue concerne le mod (label, section
   « Côté mod », références). Demander une précision si l'identification reste
   ambiguë, avant toute mutation GitHub. Ne jamais substituer une issue de
   même numéro dans l'autre dépôt.
2. Lire titre, description, labels, commentaires et PR liées. Utiliser le
   connecteur GitHub s'il couvre l'opération, sinon `gh` avec un dépôt explicite :
   ```bash
   rtk gh issue view <num> --repo <depot-issue> --comments
   rtk gh pr list --repo Battle-Conquest/battle-conquest-mod --state open
   ```
   Séparer le travail côté mod des prérequis côté site. Consulter le contrat
   `docs/mod-battles-api.md` dans le projet frère si l'API est concernée.
   Une modification du contrat doit arriver sur le serveur avant son usage
   dans le mod ; ne pas élargir silencieusement la correction au site.
3. S'assigner l'issue identifiée. Avec `gh`, utiliser REST pour éviter les
   erreurs `projectCards` des mutations GraphQL de `gh issue edit` :
   ```bash
   rtk gh api user --jq .login
   rtk gh api repos/<depot-issue>/issues/<num>/assignees -X POST -f 'assignees[]=<login>'
   ```
   Remplacer `<login>` par le résultat réel. Préserver toutes les cases des
   issues du chantier cartes #817, parente et sous-issues, même après succès
   des tests ; consigner les résultats dans la PR sans modifier ces cases.
4. Examiner `rtk git status --short --branch` et les worktrees. Préserver les
   modifications sans rapport, notamment les réglages locaux et
   `src/battle_conquest/local_settings.py`. Utiliser un worktree isolé sans
   changer le checkout principal.
5. Créer une branche dans ce worktree depuis `origin/main`, jamais travailler sur `main` :
   ```bash
   rtk git fetch origin main
   rtk git worktree add -b fix/<num>-<slug> <chemin-worktree> origin/main
   rtk git -C <chemin-worktree> merge-base --is-ancestor origin/main HEAD
   rtk git -C <chemin-worktree> log --oneline origin/main..HEAD
   ```
   Exécuter la suite dans ce worktree avec le paramètre `workdir` des outils.
   Choisir `feat/` pour une fonctionnalité ou `chore/` pour de la maintenance.
   Vérifier le changement de branche avant toute édition. Pour une branche
   neuve, le contrôle d'ancêtre réussit et le journal est vide. Ne jamais
   récupérer un checkout avorté avec `git reset --hard`.
6. Reprendre une branche/PR existante correspondant à l'issue plutôt que la
   dupliquer. Examiner ses commits et sa base sans exiger un journal vide.
   Une branche empilée nécessite une base de PR adaptée et une explication.

## 2. Planifier

Établir un plan proportionné : cause, comportement attendu, modules concernés,
vérifications hors ligne et recette en jeu restante. Ne créer un fichier de
plan que sur demande explicite. Si un plan est demandé, le terminer par une
recommandation de modèle et d'effort parmi les options effectivement disponibles,
justifiée en une ligne ; ne pas prétendre modifier la session. Tracer autrement
les décisions utiles dans les commits et la PR.

## 3. Implémenter

- Garder Python 2.7 dans `src/`, `tester/`, les templates client,
  `tools/checks/`, `tools/selftest.py` et `tools/release_check.py` ; Python 3
  dans les autres outils. Code, commentaires et commits en anglais.
  Traduire les textes du client avec `i18n.tr()` et `translations_fr.py`,
  anglais en repli, selon la langue du compte authentifié sur le site.
  Les nouvelles issues et PR restent en français selon la préférence utilisateur.
  Lire les modules existants avant de choisir leurs points d'extension.
- Respecter le hot reload : après `stop()`, toutes les fonctions du client sont
  restaurées par identité. Faire passer patches, abonnements, callbacks,
  requêtes et nettoyages par la `Session` fournie à `install()`. Employer
  `session.patch`, `session.callback` et `session.fetch`, jamais directement
  `BigWorld.callback` ou `BigWorld.fetchURL`.
- Partager les services, notamment une seule `Queue` entre capture et envoi.
  Conserver le rollback de `start()` et le détachement au mieux, journalisé,
  des événements qui peuvent refuser `-=`. Ne pas modifier le watcher pour
  masquer un rechargement échoué pendant une sauvegarde intermédiaire.
- Préserver les différents chemins de capture et les logs de
  `service_hooks.describe` : l'écran de résultats ne s'ouvre pas toujours,
  `results_request.py` récupère aussi les batailles manquantes.
- Déduire le propriétaire des preuves du résultat personnel (`accountDBID`),
  jamais du compte connecté à sa réception. Isoler les identités absentes ou
  contradictoires ; envoyer uniquement les rapports du compte connecté.
  Préserver les migrations et écritures atomiques du stockage local ; lire
  `OWNER-ISOLATION.md` avant de le modifier.
  Les réponses accepted, duplicate et rejected sont définitives, sauf
  `account_mismatch`, qui suspend la liaison et conserve les rapports.
  HTTP 401 suspend aussi la liaison jusqu'à réparation ; temporiser les
  erreurs transitoires prévues par le contrat.
- Ne jamais exposer ni journaliser le secret brut. Seul son SHA-256 figure dans
  le lien navigateur ; les appels API utilisent `X-Mod-Secret` en HTTPS vers
  le site d'origine uniquement. Ignorer une liaison créée pour un autre site.
  Ne pas embarquer la configuration locale dans les commits ou les paquets.
- Garder les intégrations optionnelles (`modsSettingsApi`, `modsListApi`)
  optionnelles et non embarquées. Préserver les chemins sans ces APIs.
- Garder les fichiers sous environ 400 lignes, en séparant les responsabilités
  si nécessaire, sans commentaires séparateurs de sections.
- Ne pas changer la version ni publier de release dans une correction.
  Les changements sur `main` alimentent la PR automatisée `release/next` ;
  consulter `RELEASING.md` pour une modification de cette automatisation.

## 4. Vérifier localement

Pour un changement du mod, ajouter un contrôle de régression pertinent dans
`tools/checks/` et l'intégrer à `tools/selftest.py` si nécessaire. Vérifier le
comportement et le nettoyage au rechargement, pas seulement la forme du code.
Pour les outils Python 3, utiliser leurs tests `tools/test_*.py`.

Identifier Python 2.7 : essayer `~/.local/bin/python2.7`, puis `python2.7`
dans le PATH, et vérifier sa version. Utiliser le chemin trouvé dans les
commandes ci-dessous si nécessaire. Avant chaque commit, lancer :

```bash
rtk proxy python2.7 -B tools/selftest.py
```

Si les outils de release, le packaging ou l'automatisation changent, lancer
aussi les tests hors ligne Python 3 de `Mod CI` :

```bash
rtk proxy python3 -B -m unittest discover -s tools -p 'test_*.py'
```

Pour une modification de la carte du garage, consulter aussi les tests
Playwright `tools/test_*.mjs` et leurs prérequis dans `README.md`.

Si le packaging, `res/` ou les points d'entrée changent, construire et vérifier
les deux artefacts avec une version de test, sans tag ni publication :

```bash
rtk proxy python3 -B tools/build_release.py --version <version-test> --python27 <chemin-python27>
rtk proxy <chemin-python27> -B tools/release_check.py dist/eu.battle-conquest_<version-test>.wotmod
rtk proxy python3 -B tools/bundle_check.py dist/battle-conquest-mod_<version-test>.zip dist/eu.battle-conquest_<version-test>.wotmod --game-version <GAME_VERSION>
```

Lire `GAME_VERSION` dans `tools/build_release.py` pour ce contrôle local ;
ne pas le changer pour une simple correction. Les tests avec modules clients
simulés ne prouvent pas le fonctionnement dans WoT. Si un client de développement
est accessible, contrôler le scénario en jeu et lire `game.log` dans son dossier,
sous les loggers `battle_conquest.*`, après rechargement. Une modification du
bootstrap `dev/mod_battle_conquest_dev.py.in` ou des ressources indexées par
le jeu exige leur réinstallation et un redémarrage du client.
Si le jeu ou le log est inaccessible, le signaler et
décrire la recette restante sans annoncer un test en jeu réussi.

Corriger les échecs introduits. Signaler les contrôles bloqués avec leur cause
exacte, sans remplacer Python 2.7 par Python 3 pour valider le code client.
Pour une modification purement documentaire ou de skill, relire les instructions
et valider le skill avec `quick_validate.py` de `skill-creator` ; ne pas ajouter
de test artificiel dans `tools/checks/` pour des instructions Markdown.

## 5. Committer et ouvrir la PR

- Examiner le diff, puis indexer explicitement les seuls fichiers concernés
  avec `rtk git add <fichiers>`, jamais `git add .` ou `git add -A`.
- Commits anglais : `<type>(#<num>): <description>`, description en minuscules,
  à l'impératif, un commit par changement logique. Ne pas inventer de numéro.
- Pousser la branche et créer ou mettre à jour son unique PR vers `main` dans
  `Battle-Conquest/battle-conquest-mod`. Titre au format
  `<type>(#<num>): <description>`, description française concise. Avec `gh` :
  ```bash
  rtk git push -u origin <branche>
  rtk gh pr create --repo Battle-Conquest/battle-conquest-mod --base main --head <branche> --title '<type>(#<num>): <description>' --body-file <fichier-description>
  ```
- Écrire le corps dans un fichier temporaire hors du dépôt avec de vrais sauts
  de ligne. Lier l'issue exacte : `Closes #<num>` pour une issue du mod,
  `Closes Battle-Conquest/Battle-Conquest#<num>` pour une issue du site.
  Si la PR ne livre que le côté mod d'une issue plus large, utiliser `Refs`
  plutôt qu'une fermeture prématurée.
- Résumer le problème, la solution, les résultats locaux réels et leurs limites.
  Ajouter une checklist des vérifications utiles, renvoyer à la recette de
  l'issue et détailler seulement les contrôles supplémentaires ou restant en jeu.
  Inclure une section installation/déploiement uniquement si une intervention
  est nécessaire, avec les commandes exactes et prérequis côté serveur.

Terminer avec le lien de la PR, les résultats locaux et les limites pertinentes.
Ne jamais consulter, surveiller ni attendre la CI après un push ou une mise à
jour de PR. Ne pas merger automatiquement et ne pas invoquer de workflow du
site tel que `ready-to-merge` ou `release-production` pour livrer le mod.
