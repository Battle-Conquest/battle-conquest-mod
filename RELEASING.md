# Releases du mod

Les changements intégrés sur `main` alimentent une seule PR automatique,
`release/next`. **Sa fusion reste manuelle** et déclenche la construction,
les contrôles puis la publication GitHub.

- Une prérelease active est actualisée **avec le même numéro et le même statut**,
  en remplaçant ses fichiers et en déplaçant uniquement son tag sur le commit
  fusionné. Une prérelease active porte un numéro supérieur à la dernière stable.
- Sans prérelease active, la version stable la plus élevée reçoit un incrément
  **patch**, même si les changements comprennent des fonctionnalités.
- Les releases stables et leurs tags ne sont jamais remplacés. Plusieurs
  préreleases actives, une version ambiguë ou un brouillon manuel occupant le
  numéro prévu bloquent la proposition, sans choisir une autre version.

Le dossier WoT du ZIP reste celui de `GAME_VERSION` dans `tools/build_release.py`.
Il ne sert pas à déterminer la version du mod. Il n'y a plus de surveillance
quotidienne ni d'issue demandant une release pour un changement de dossier WoT.
Après une mise à jour du jeu, le joueur déplace le `.wotmod` du mod et le dossier
partagé `net.openwg/` dans le dossier `mods/<version courante>/`, jeu fermé,
en conservant les chemins relatifs. Il laisse `mods/configs/battle_conquest/`
en place et ne conserve qu'un paquet Battle-Conquest. Ce déplacement ne garantit
pas la compatibilité avec une éventuelle modification des API du jeu.

## Activer l'automatisation

La politique de l'organisation doit d'abord autoriser la création de PR par
Actions : un administrateur l'active dans **Organization settings → Actions →
General → Workflow permissions → Allow GitHub Actions to create and approve
pull requests**. Tant que cette politique l'interdit, l'API du dépôt répond
`409 Conflict` et aucun réglage local au dépôt ne peut la contourner. La
modification par API de cette politique nécessite notamment le scope
`admin:org` avec un jeton classique ; sinon, utiliser l'interface GitHub.

Dans **Settings → Actions → General → Workflow permissions**, activer
**Allow GitHub Actions to create and approve pull requests**. Les workflows
demandent explicitement `contents: write`, `pull-requests: write` pour la
proposition et `actions: write` pour relancer la proposition après publication.
Aucun PAT ni secret supplémentaire n'est nécessaire.
La permission peut également être configurée avec :

```bash
gh api repos/Battle-Conquest/battle-conquest-mod/actions/permissions/workflow \
  --method PUT -F can_approve_pull_request_reviews=true
```

Après fusion du changement installant les workflows, **Mod release proposal**
réagit aux pushes sur `main`. Pour reprendre une proposition manuellement :

```bash
gh workflow run release-pr.yml --repo Battle-Conquest/battle-conquest-mod --ref main
```

La création ou l'actualisation d'une PR par `GITHUB_TOKEN` peut demander une
approbation manuelle des workflows selon la politique GitHub. La publication
exécute de toute façon ses propres tests avant toute modification des fichiers
distribués. Voir les [règles GitHub de déclenchement](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow).
Les deux workflows sont désactivés sur les forks.

## Relire, tester et fusionner

La PR contient `.github/release-plan.json` et `CHANGELOG.md`. Le plan fige la
version, le statut de test, les sources et la release de départ. Le bot ne
fusionne aucune PR. Les changements suivants de `main` actualisent la même PR.
Sa description conserve les notes et cases utilisateur hors de la section
marquée ; les notes du changelog sont régénérées depuis `main`, donc les retouches
propres à la branche de release doivent être faites juste avant la fusion.

Pour une version stable, effectuer la recette utile avec les sources à publier
avant de fusionner : liaison, panneau du garage, bataille prise en charge et
réception unique sur le site. La publication automatique vérifie le paquet
compilé mais ne remplace pas ce test en jeu.

Une prérelease représente un test en cours. Chaque actualisation impose de
**télécharger de nouveau le ZIP**, même si son numéro est identique ; les alertes
du mod fondées sur les numéros ne distinguent pas ces reconstructions. Refaire
la recette pertinente sur ce ZIP. Après acceptation, promouvoir manuellement :

```bash
gh release edit vX.Y.Z --repo Battle-Conquest/battle-conquest-mod --prerelease=false --latest
```

Une promotion intervenue pendant la revue bloque une ancienne proposition qui
aurait remplacé cette prérelease : la stable validée reste protégée. Relancer
la proposition pour recalculer la suite.

## Construction et reprise après échec

**Mod release** démarre après la fusion manuelle de `release/next`. Il extrait
le commit fusionné, vérifie qu'il appartient à `main` et que les sources n'ont
pas changé depuis la proposition, puis lance les tests Python 3, les selftests
Python 2.7, la construction et le contrôle du `.wotmod` compilé. Python 2.7.18
s'exécute dans un conteneur sans réseau, avec les sources en lecture seule.

Les deux fichiers distribués sont :

```text
eu.battle-conquest_X.Y.Z.wotmod
battle-conquest-mod_X.Y.Z.zip
```

Le ZIP est l'installation complète et le fichier à soumettre à WGMods.
Le `.wotmod` autonome ne contient pas OpenWG : sans cette dépendance, la carte
intégrée est indisponible et la fenêtre détaillée sert de secours. La construction
et les deux voies de publication vérifient le ZIP : paquet du mod identique au
fichier autonome, OpenWG Gameface 1.2.2 épinglé par SHA-256, module Python,
bibliothèques JavaScript, imports de la carte et licence. Un contrôle en échec
bloque la publication avant toute modification des tags ou des releases.

Un reçu `release-build.json` consigne le plan, le commit, le dossier WoT et les
SHA-256 des fichiers. Il est joint après les autres fichiers ; une nouvelle
stable reste en brouillon jusqu'à la fin des envois. Une prérelease peut être
momentanément incomplète pendant le remplacement de ses fichiers.

Après publication, une nouvelle proposition est demandée sur `main` pour
reprendre les changements éventuellement arrivés pendant les envois. Une
reprise d'un plan déjà terminé redemande également cette proposition sans
reconstruire ni remplacer les fichiers. Le reçu ne vaut validation que si son
commit correspond encore au tag ; un déplacement ultérieur du tag bloque
l'automatisation au lieu de masquer une incohérence entre sources et fichiers.

Une publication incomplète bloque la prochaine proposition. Ne pas incrémenter
le numéro pour masquer cet échec : relancer **Mod release** pour le **même commit
de fusion**, depuis la branche `main` :

```bash
gh workflow run release.yml --repo Battle-Conquest/battle-conquest-mod --ref main \
  -f commit=<SHA_COMPLET_DU_COMMIT_DE_FUSION>
```

La reprise complète la même version et ne publie pas une seconde fois un plan
déjà terminé. Un tag déplacé hors de cette opération, une release promue ou une
PR fusionnée avec des sources devenues différentes font échouer la publication
avant remplacement des fichiers. Résoudre cet état explicitement ; ne pas forcer
un tag stable ni supprimer le plan fusionné pour débloquer le bot.

Si les sources ont changé pendant la revue ou si la prérelease a été promue,
la publication n'a pas commencé. Préparer un nouveau plan à relire et fusionner
manuellement avec :

```bash
gh workflow run release-pr.yml --repo Battle-Conquest/battle-conquest-mod --ref main \
  -f replace_pending=true
```

Cette option refuse de remplacer un plan dont la publication a déjà déplacé le
tag ; reprendre alors la publication d'origine. Un brouillon occupant le numéro
prévu doit également être terminé avec son plan d'origine.

## Vérifications locales et procédure manuelle

Python 3.10+, Python 2.7 et `gh` authentifié sont nécessaires hors Actions :

```bash
git fetch origin main --tags
python3 -B tools/release_pr.py --dry-run
python3 -B -m unittest discover -s tools -p 'test_*.py'
python2.7 -B tools/selftest.py
python3 tools/build_release.py --version X.Y.Z --python27 /chemin/vers/python2.7
python2.7 -B tools/release_check.py dist/eu.battle-conquest_X.Y.Z.wotmod
python3 -B tools/bundle_check.py dist/battle-conquest-mod_X.Y.Z.zip dist/eu.battle-conquest_X.Y.Z.wotmod --game-version 2.4.1.1
```

La prévisualisation ne modifie aucun fichier ni GitHub. Le script historique
`tools/release.py` reste disponible comme procédure interactive exceptionnelle
avec brouillon ; il conserve son ancien calcul (`feat` → mineure, sinon patch).
Ne pas l'utiliser pendant une livraison automatisée. La soumission à WGMods
reste manuelle ; suivre [CONTRIBUTING.md](CONTRIBUTING.md#versions-and-releases).
Une publication GitHub ne vaut pas approbation par Wargaming.

## WGMods submission

La soumission reste manuelle et utilise **le ZIP complet testé**, pas le seul
`.wotmod`. Le dossier indiqué ci-dessous doit correspondre à `GAME_VERSION` et
au client de recette ; après un changement WoT, refaire la recette du ZIP destiné
à la soumission avec les chemins adaptés.

```text
battle-conquest-mod_X.Y.Z.zip
├── mods/2.4.1.1/eu.battle-conquest_X.Y.Z.wotmod
├── mods/2.4.1.1/net.openwg/net.openwg.gameface_1.2.2.wotmod
└── LICENSE-openwg-gameface.txt
```

1. Exécuter `bundle_check.py` avec la commande ci-dessus et conserver son SHA-256.
   Installer ce ZIP sur un client propre, sans OpenWG préalable : vérifier la
   carte, ses actions, la liaison et la réception unique d'une bataille.
2. Tester une mise à jour avec OpenWG 1.2.2 déjà installé au chemin partagé :
   une seule copie de chaque paquet, liaison et configuration conservées dans
   `mods/configs/battle_conquest/`. Pour une autre version OpenWG, vérifier les
   exigences des autres mods avant remplacement ; ne pas activer deux versions.
3. Vérifier le secours sans dépendance et la restauration des panneaux compte
   et Twitch d'Unicum après masquage, réaffichage et retrait du mod, aux trois
   résolutions de l'[issue #56](https://github.com/Battle-Conquest/battle-conquest-mod/issues/56).
4. Joindre le ZIP dont l'empreinte correspond au fichier testé. La description,
   le changelog et le [guide d'installation](README.md#install) accessibles depuis
   la soumission doivent annoncer OpenWG **inclus dans le ZIP**, préciser ces
   chemins, le redémarrage et la conservation de la configuration lors d'une mise à jour.
5. Attendre la décision de Wargaming avant de modifier la version approuvée
   affichée sur le site. Ne pas remplacer une release stable pour cette correction.
