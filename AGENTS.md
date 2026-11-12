# Instructions Codex — mod Battle-Conquest

## Projet et références

Ce dépôt est le mod client de [Battle-Conquest](https://battle-conquest.eu),
pas le site PHP. Il capture les batailles WoT, transmet leurs résultats au
site et affiche le suivi des quêtes au garage. Le code du client fonctionne
en Python 2.7 ; les outils de construction utilisent Python 3.10+.
Le dossier WoT du paquet est défini par `GAME_VERSION` dans
`tools/build_release.py` : il ne prouve pas la compatibilité avec un nouveau client.

- [README.md](README.md) : installation et fonctions proposées aux joueurs.
- [CONTRIBUTING.md](CONTRIBUTING.md) : branches, commits et vérifications.
- [RELEASING.md](RELEASING.md) : proposition automatique, publication et reprise.
- [OWNER-ISOLATION.md](OWNER-ISOLATION.md) : migration des comptes et retour arrière.
- [DIAGNOSTIC.md](DIAGNOSTIC.md) : observations locales facultatives, jamais une preuve de recette en jeu.
- [TESTER-CATALOGUE.md](TESTER-CATALOGUE.md) : variante privée de collecte, exclue des releases publiques.

Le contrat serveur fait autorité :
[`docs/mod-battles-api.md`](https://github.com/Battle-Conquest/Battle-Conquest/blob/main/docs/mod-battles-api.md).
Déployer les évolutions nécessaires sur le site avant le mod. Ne pas importer
ici les conventions PHP, les migrations ou le versionnement du site.
Les anciennes mémoires Battle-Conquest servent de contexte ; vérifier leurs
affirmations contre le code et les workflows actuels, notamment pour les releases.

Le projet dérive d'unicum.gg-mod sous AGPL-3.0. Conserver `LICENSE`, `NOTICE`
et les licences des ressources et dépendances. Les références à Unicum dans
la cohabitation du garage et ses tests sont intentionnelles.

## Préférences de travail

- Répondre et rédiger les consignes internes en français. Code, commentaires,
  commits et notes de release en anglais. Issues et PR en français, concises,
  avec les résultats locaux réels et une recette utile sans répéter le diff.
- Le client est traduit en français et anglais : utiliser `i18n.tr()` et
  `translations_fr.py`, avec l'anglais comme repli. La langue vient du compte
  authentifié sur le site ; ne pas la conserver pour un autre compte ou secret.
- Utiliser `rtk` pour les commandes shell (`rtk proxy` si nécessaire), et `rg`
  pour les recherches. Préserver les modifications utilisateur et des autres agents.
- Travailler sur une branche dédiée depuis `origin/main`, jamais sur `main`.
  Utiliser un worktree distinct pour isoler la tâche ; vérifier sa base et
  exécuter les commandes dans ce worktree sans changer le checkout principal.
- Nommer explicitement les fichiers à indexer, sans `git add .` ni `git add -A`.
  Après les vérifications adaptées, committer le travail avant de le déclarer
  terminé, sauf demande contraire. Ne jamais inclure de secrets ou de changements étrangers.
- Avec une issue : branche `<type>/<num>-<slug>`, commit et titre de PR
  `<type>(#<num>): <description>`. Sans issue, `<type>: <description>` convient.
  Les issues peuvent appartenir à ce dépôt ou à `Battle-Conquest/Battle-Conquest` :
  lier le bon dépôt, sans confondre les numéros. Ouvrir les PR prêtes à relire,
  sauf demande explicite de brouillon ; leur fusion reste une action distincte.
- Ne jamais consulter, surveiller ou attendre la CI après un push ou une mise
  à jour de PR. Effectuer les contrôles locaux, fournir le lien et terminer ;
  l'utilisateur vérifie lui-même la CI.
- Pour le chantier cartes `Battle-Conquest/Battle-Conquest#817` et ses sous-issues,
  préserver toutes les cases de recette : seul l'utilisateur les coche ou décoche.
  Consigner les résultats sans modifier leur état.

## Organisation actuelle

- `dev/mod_battle_conquest_dev.py.in` : bootstrap de développement, surveille
  `src/` et recharge le package. `dev/mod_battle_conquest.py.in` : entrée publiée.
- `src/battle_conquest/__init__.py` : construit les services partagés et installe
  les fonctions dans l'ordre ; `runtime/session.py` possède leur cycle de vie.
- Capture : `battle_reports.py`, `battle_report.py`, `results_dict.py`,
  `results_identity.py`, `battle_owner.py`, `service_hooks.py`, `modes.py`.
  `quest_details.py`, `quest_economy.py` et `quest_repairs.py` enrichissent ou
  récupèrent les preuves disponibles sans inventer les mesures manquantes.
- Récupération : `results_request.py`, `results_cache.py`, `results_messages.py`
  et `recovery_journal.py` suivent les résultats, y compris sans ouvrir leur écran.
- Stockage et envoi : `local_store.py`, `report_queue.py`, `report_sender.py`,
  `report_wire.py`, `report_delivery.py` ; une seule file partagée par capture et envoi.
- Liaison : `account.py`, `destinations.py`, `site_link.py`, `mod_updates.py`.
  `config.py` fixe le site et le dossier local ; `local_settings.py`, ignoré par Git,
  permet de viser un serveur de développement.
- Garage : `garage_display.py` partage le contrôleur `quest_garage.py` entre
  la carte Gameface (`hangar_inject.py`, `hangar_resources.py`, `web/hangar/`)
  et la fenêtre native détaillée (`quest_garage_view.py` et modules associés).
  `display_preferences.py` isole leurs préférences par site, région et compte.
  `battle_feedback.py` actualise le suivi après capture et livraison.
- `settings_window.py` / `mods_list.py` utilisent des API facultatives non livrées.
  `notices.py` permet aussi la liaison et la restauration des affichages sans ces API.
- `res/` : ressources Gameface, textures DDS, police native et icône.
  `vendor/openwg/` : Gameface 1.2.2 et sa licence, inclus dans le ZIP complet,
  pas dans le `.wotmod` autonome. Sans lui, la fenêtre détaillée sert de secours.
- `tester/` et `tools/build_catalog_tester.py` : variante privée, jamais ajoutée
  à `src/` ni aux fichiers publics. Garder sa documentation tant que cet outil existe.
- `tools/checks/` : simulations Python 2.7 ; `tools/test_*.py` : tests Python 3 ;
  `tools/test_*.mjs` : tests navigateur de la carte et de la restauration d'Unicum.

## Rechargement et invariants

- Après `stop()`, chaque fonction du jeu doit être restaurée **par identité**.
  Utiliser `session.patch(holder, name, build)` : il préserve aussi les
  classmethods et les méthodes héritées. Un hook survivant peut provoquer `LEAK`
  et impose un redémarrage du client.
- Passer les callbacks, requêtes, abonnements et nettoyages par `Session`.
  Utiliser `session.callback` et `session.fetch`, jamais directement
  `BigWorld.callback` ou `BigWorld.fetchURL`. Les réponses tardives doivent
  également respecter le compte et la liaison qui les ont déclenchées.
- `start()` annule toute installation partielle en cas d'erreur. Le retrait
  d'un événement peut refuser `-=` : tenter le détachement et journaliser l'échec.
- Le bootstrap et les ressources indexées par le jeu nécessitent un redémarrage
  après modification ; les changements Python de `src/` sont rechargeables.
  Une sauvegarde intermédiaire invalide doit pouvoir récupérer au prochain edit :
  ne pas modifier le watcher pour masquer cette situation.
- Conserver tous les chemins de capture. `postResult` dépend de l'ouverture
  de l'écran ; `results_request.py` récupère les autres batailles.
  Un événement existant peut ne jamais se déclencher : garder les logs de
  `service_hooks.describe` et ne pas confondre hook attaché et capture observée.
- Le propriétaire vient des preuves du résultat personnel (`accountDBID`),
  jamais du compte connecté au moment de la réception. Une identité absente
  ou contradictoire isole le rapport. Une arène commune à deux comptes ne doit
  partager ni acquittement ni quota. Seuls les rapports du compte connecté sont envoyés.
- `link.json` et `battle-reports.json` sont au schéma local 2 ; le contrat
  des rapports HTTP reste au schéma 1. Préserver la migration, la quarantaine
  des anciens rapports et l'écriture atomique avec sauvegarde. Un fichier
  illisible ne doit pas être écrasé. Voir `OWNER-ISOLATION.md` avant tout changement.
- Les verdicts métier `accepted`, `duplicate`, `rejected` soldent un rapport,
  sauf `account_mismatch`, qui suspend la liaison et conserve les rapports.
  Un HTTP 401 suspend également la liaison jusqu'à réparation. Les pannes
  temporaires, 408, 429 et 5xx attendent avec temporisation ; ne pas créer de
  boucle sur un refus définitif ni marquer comme livré un verdict absent ou invalide.
- Le secret est généré dans le client. Seul son SHA-256 figure dans le lien
  du navigateur ; les appels API utilisent `X-Mod-Secret` en HTTPS vers son
  site d'origine uniquement. Ne jamais exposer secrets, fichiers de liaison
  ou sauvegardes dans les logs, issues, commits ou données Gameface.
- Distinguer résultats officiels et estimations du mod. Les valeurs inconnues,
  incomplètes ou non comparables restent explicites ; les simulations ne prouvent
  ni l'économie réelle d'un mode ni le rendu dans le client.

## Vérifications locales

```bash
rtk proxy python2.7 -B tools/selftest.py
rtk proxy python3 -B -m unittest discover -s tools -p 'test_*.py'
```

Sur ce serveur, Python 2.7 est disponible à `~/.local/bin/python2.7`.
Les tests sont hors ligne, avec de faux modules client. Ajouter un contrôle
de comportement pour une modification fonctionnelle : Python 2.7 dans
`tools/checks/`, Python 3 pour les outils. Une correction documentaire seule
ne nécessite pas un test qui vérifie son texte.

Si le packaging, les ressources ou les points d'entrée changent :

```bash
rtk proxy python3 -B tools/build_release.py --version X.Y.Z --python27 /chemin/vers/python2.7
rtk proxy python2.7 -B tools/release_check.py dist/eu.battle-conquest_X.Y.Z.wotmod
rtk proxy python3 -B tools/bundle_check.py dist/battle-conquest-mod_X.Y.Z.zip dist/eu.battle-conquest_X.Y.Z.wotmod --game-version 2.4.1.1
```

Adapter le dernier argument au `GAME_VERSION` des sources. Pour la carte,
voir les tests Playwright et leurs prérequis dans `README.md` ; ils restent
distincts de la recette en jeu. Après un rechargement réel, lire `game.log`
dans le dossier du jeu, loggers `battle_conquest.*`. Sans client disponible,
indiquer cette limite sans prétendre avoir validé les logs ou le rendu.

## Releases et conventions de code

- Les PR ordinaires ne changent pas de version. Sur `main`, le workflow
  maintient une seule PR `release/next` avec `.github/release-plan.json` et
  `CHANGELOG.md`. Sa fusion manuelle déclenche construction et publication.
- Une prérelease active conserve son numéro et son statut ; sinon la dernière
  stable reçoit un incrément patch, même pour une fonctionnalité. Ne jamais
  remplacer une stable. Relire `RELEASING.md` pour les reprises et la promotion.
- `tools/release.py` est un secours manuel exceptionnel, avec un autre calcul
  de version ; ne pas l'utiliser en parallèle de l'automatisation.
  Le skill local `release-mod` suit la procédure courante de `RELEASING.md`.
- Un changement de dossier WoT seul ne déclenche pas de release ; ne pas
  confondre version du mod et version du client. La soumission à WGMods reste
  manuelle, avec le ZIP complet testé et sa dépendance OpenWG.
- Python 2.7 dans `src/`, `tester/`, les templates client et `tools/checks/` ;
  Python 3 dans les autres outils, sauf `tools/selftest.py` et `tools/release_check.py`.
- Garder les fichiers sous environ 400 lignes ; séparer les responsabilités
  plutôt qu'ajouter des commentaires séparateurs. Les commentaires expliquent
  les raisons et les alternatives réellement essayées, sans raconter le diff.
