# Isolation des comptes — #964

Le serveur doit inclure Battle-Conquest/Battle-Conquest#1012 avant ce mod.
Aucune nouvelle migration DB, variable d’environnement ou option de diagnostic
n’est nécessaire. La protection du propriétaire est toujours active.

## Installation et migration

1. Fermer le jeu et sauvegarder `mods/configs/battle_conquest/` en lieu sûr.
   Ce dossier contient des secrets : ne jamais le joindre à une issue.
2. Construire un paquet de recette distinct de la première étape diagnostic :

   ```bash
   python3 tools/build_release.py --version 0.0.965 --python27 /chemin/vers/python2.7
   python2.7 tools/release_check.py dist/eu.battle-conquest_0.0.965.wotmod
   ```

3. Retirer l’ancien paquet Battle-Conquest du dossier `mods/<version du jeu>/`
   et installer le ZIP généré. Conserver un seul `.wotmod` Battle-Conquest.
   Le ZIP cible la version de jeu déclarée dans `tools/GAME_VERSION`.
4. Laisser `diagnostics.json` à `{"enabled":false,"identity_enabled":false}`.
   Au garage, l’ancien secret est interrogé uniquement sur son site d’origine
   via `/api/mod/me`. L’identifiant WG et la région retournés déterminent son
   propriétaire, même si un autre compte est connecté. La pause est conservée.
5. Si le compte courant n’a pas sa propre liaison, cliquer **Lier mon compte**
   et confirmer avec le même compte WoT sur le site. Une réponse de navigateur
   pour un autre compte ou une autre région n’est pas enregistrée.
6. Vérifier l’état dans les réglages facultatifs du mod et les lignes
   `battle_conquest.*` dans `game.log`. Une liaison suspendue demande de relier
   le compte ; ses rapports restent disponibles après réparation.

`link.json` passe au schéma 2 : `links` contient une entrée par site, région
et compte WG, avec son propre secret, ses modes et son `enabled`. Une pause
s’effectue depuis les réglages du mod. Pour une modification manuelle, jeu
fermé, ne modifier que `enabled` dans l’entrée du compte concerné ; conserver
le reste du fichier. Il n’existe plus de commutateur global au niveau racine.

`battle-reports.json` passe au schéma 2. Un ancien rapport ne prouve pas son
propriétaire par son seul champ `account` : il est conservé avec `quarantine`
et reste exclu des envois. Une nouvelle réception vérifiable peut produire
un rapport normal pour la même arène sans réattribuer l’ancien. Le serveur
assure l’absence de double comptage. Le nombre de rapports isolés apparaît
dans les réglages ; la cause est écrite dans `game.log` et dans le rapport.

Les fichiers sont remplacés après écriture complète, avec une copie précédente
`.bak`. Ne partager ni `link.json`, ni ses copies `.bak`/`.tmp`. Un fichier
illisible est préservé et bloque son écrasement ; restaurer sa sauvegarde, jeu
fermé, avant de réessayer. Pour revenir à une ancienne version du mod, restaurer
la sauvegarde prise avant migration : les anciens clients ne lisent pas le
schéma 2. Cette restauration ne réattribue pas les rapports incertains.

## Vérifications

Avec un seul compte : démarrer sans diagnostic, vérifier la liaison restaurée,
rouvrir un résultat et constater un seul comptage côté site. Mettre en pause
puis reprendre : le stock déjà capturé reste présent et reprend ses envois.
Redémarrer et vérifier que le compte retrouve sa liaison et son réglage.
Une pause ne conserve pas les nouvelles batailles jouées pendant celle-ci.

Les simulations locales couvrent A → B → A, réponses tardives, arène commune,
multichars contradictoire, compte sans liaison, refus `account_mismatch`,
révocation, panne réseau, migration et limites par propriétaire. Un refus de
liaison est conservé et suspendu jusqu’à réparation, sans boucle de réessais.
Les autres refus métier restent définitifs, comme auparavant.

L’observation réelle fournie pour #964 confirme `accountDBID` dans les résultats
personnels du mode `other` (`bonusType: 102`) sur WoT EU 2.4.1.1. Les références
anonymisées concordent avec le compte utilisateur et les clés `players` et
`avatars` sur les deux chemins cache/`postResult`. Les autres modes et le
changement réel entre deux comptes ne sont pas présentés comme testés en jeu.
La recette fournie a été acceptée par l’utilisateur pour poursuivre le développement.
