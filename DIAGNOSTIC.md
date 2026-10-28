# Diagnostic des résultats personnels — #953 / #772

Cette version sert à établir les mesures réelles du client avant le nouveau
contrat des quêtes. Le diagnostic est désactivé par défaut et reste local.
La collecte et les envois habituels gardent leur contrat et leur déduplication.
Un échec du diagnostic ne bloque pas ces rapports.

## Installer la version à tester

Depuis la branche de la PR, avec Python 3 et Python 2.7 disponibles :

```bash
python3 tools/build_release.py --version 0.0.953 --python27 /chemin/vers/python2.7
python2.7 tools/release_check.py dist/eu.battle-conquest_0.0.953.wotmod
```

`0.0.953` est une version locale de test, sans tag ni release publiée. Extraire
`dist/battle-conquest-mod_0.0.953.zip` dans le dossier du jeu (WoT 2.4.1.0).
Garder un seul paquet Battle-Conquest installé : déplacer d’abord l’ancien
`.wotmod` hors du dossier `mods/<version>/`, puis le remettre après la recette.
La version de test peut déclencher la notification habituelle de mise à jour
du site ; elle ne signifie pas que le diagnostic a échoué.

Autre possibilité pour un client de développement : utiliser le bootstrap
décrit dans le README. Aucun changement du bootstrap n’est nécessaire.

## Activer et arrêter

Dans le dossier du jeu, créer `mods/configs/battle_conquest/diagnostics.json` :

```json
{"enabled": true}
```

Le fichier doit être en ASCII ou UTF-8 sans BOM, de moins de 1 025 octets.
Seul le booléen JSON `true` active le diagnostic ; la chaîne `"true"` ou le
nombre `1` ne l’activent pas. Exemple PowerShell depuis le dossier du jeu :

```powershell
New-Item -ItemType Directory -Force mods\configs\battle_conquest | Out-Null
'{"enabled":true}' | Set-Content -Encoding ASCII mods\configs\battle_conquest\diagnostics.json
```

L’activation est relue à chaque arrivée de résultats ou annonce d’une bataille
terminée, sans redémarrage ni dépendance à modsSettingsApi/modsListApi. Les
lignes `battle_conquest.results_diagnostic` de `game.log` indiquent l’état et
les captures. Le diagnostic peut demander les résultats des batailles annoncées
même sans liaison, pendant une pause des envois ou pour un mode que le site ne
demande pas. Il faut un compte WoT identifié pour conserver une observation.
Les règles habituelles d’envoi au site continuent de s’appliquer.

Pour arrêter immédiatement les prochaines captures :

```powershell
'{"enabled":false}' | Set-Content -Encoding ASCII mods\configs\battle_conquest\diagnostics.json
```

Un fichier absent ou invalide désactive aussi le diagnostic. La désactivation
conserve les observations déjà écrites ; elles peuvent être copiées puis
supprimées manuellement lorsque le jeu est fermé.

## Lire les observations

Les fichiers se trouvent dans `mods/configs/battle_conquest/` :

| Fichier | Contenu |
|---|---|
| `results-diagnostic.jsonl` | Une observation JSON par ligne, maximum 2 Mio |
| `results-diagnostic.jsonl.1` | Rotation précédente, maximum 2 Mio ; remplacée à la rotation suivante |

La conservation est donc limitée à 4 Mio ; copier les fichiers après chaque
scénario utile avant qu’ils ne soient remplacés. Une observation dépassant
128 Kio est refusée avec un avertissement. Les structures numériques sont
limitées à six niveaux et 128 éléments, l’inventaire à 256 noms par résultat
personnel et la capture à 64 entrées de véhicules, avec un budget global de
4 096 valeurs numériques visitées. Un dépassement de ces 64
entrées refuse la capture ; les autres limites sont signalées dans les données
ou le journal. Une erreur de disque laisse la collecte habituelle continuer.
Un arrêt brutal peut laisser une dernière ligne JSON incomplète : l’ignorer ;
les observations suivantes sont écrites sur des lignes distinctes.

- `observed_at` est l’heure UTC de capture, **pas** la fin de bataille.
- `common` conserve les valeurs brutes présentes de `arenaCreateTime`,
  `duration`, `bonusType`, `winnerTeam` et `arenaTypeID`. Aucun horaire absent
  n’est remplacé par l’heure courante et aucune fin n’est inventée.
- `mode_as_current_mod` est la classification actuelle du mod, à vérifier avec
  le `bonusType` brut. Elle ne constitue pas la future règle d’éligibilité :
  certaines variantes d’entraînement partagent actuellement une famille.
- `arena_unique_id` est une chaîne conservant tous les chiffres. `account`
  identifie le compte WoT courant, `region` sa région, `mod_version` le paquet
  et `source` le chemin d’arrivée. Ces données permettent de distinguer les
  observations lors d’un changement de compte ou d’une réouverture des résultats.
- `vehicles` garde séparément chaque entrée personnelle ; `personal_key` est
  sa clé numérique brute, sans la certifier comme identifiant de char. Le
  `typeCompDescr`, lorsqu’il existe, est conservé parmi les champs. `avatar`
  reste séparé : ses éventuels totaux ne sont jamais ajoutés aux véhicules.
- `fields` retient les compteurs actuels et les candidats utiles : champs dont
  le nom contient `xp` ou `credits` (casse ignorée), tirs/touches/pénétrations,
  assistance, char, équipe, survie, coûts de réparation/réapprovisionnement et
  marqueurs premium explicitement autorisés. Les sous-structures numériques
  conservent leurs valeurs et leur organisation, sans interprétation des unités.
- Une clé absente reste absente, `null` reste `null`, zéro reste zéro, une valeur
  négative reste négative. Un type non numérique, un nombre non fini ou une
  structure trop grande/profonde donne un marqueur `diagnostic_omitted` ; ce
  marqueur n’est jamais une mesure. Les booléens restent des booléens.
- `available_fields` inventorie les noms techniques présents sans conserver
  les autres valeurs. `field_names_truncated` signale une limite atteinte.
  Si une mesure semble correspondre à un champ hors sélection, signaler son
  nom pour adapter la capture au lieu de déduire sa valeur d’un autre champ.

Une même bataille peut apparaître plusieurs fois : événement du compte,
réponse du cache, publication ou réouverture des résultats. **Ce sont des
observations, jamais des lignes à additionner.** Les conserver permet de voir
si un chemin apporte des champs supplémentaires. Le redémarrage ne supprime
pas ces fichiers. Aucun inventaire complet du compte ni valeur des autres
joueurs, clé de liaison ou objet client n’est sérialisé. Les fichiers ne sont
jamais ajoutés à la file d’envoi ni transmis automatiquement au site.

## Recette en jeu

Pour chaque scénario, noter mode, char(s), heure et fuseau d’affichage,
bonus/premium/réserves actifs, stock utilisé, choix de réapprovisionnement,
soldes avant/après et absence d’autres transactions pendant la mesure.
Conserver les écrans détaillés de résultats, économie et XP et les lignes JSON
correspondantes, identifiées par compte et arène. Dans les éléments partagés,
expurger toute information étrangère à la recette et ne jamais joindre
`link.json`, `.env.local` ou la file des rapports refusés.

| Scénario | Comparaisons attendues |
|---|---|
| Diagnostic désactivé puis activé | Pas de fichier diagnostic sans activation ; collecte et envois habituels identiques, une bataille comptée une fois côté site |
| Résultats ouverts et jamais ouverts | Capture par les deux parcours, chiffres et arène cohérents ; rouvrir pour comparer les éventuelles observations supplémentaires |
| Aléatoire, classé, Assaut, Bastion, Ligne de front disponibles | `bonusType`, horaires et char(s) comparés aux écrans ; noter les modes indisponibles sans les remplacer par un autre |
| Entraînement et mode inconnu disponible | Type brut conservé ; diagnostic seul n’élargit pas les modes envoyés ni leur éligibilité future |
| Sans bonus puis avec bonus/premium | Identifier gains de crédits de base sans bonus/premium, XP de base et XP de char totale avec bonus ; ne pas présumer le sens du seul champ `xp` |
| Achat effectif de munitions/consommables et réparation | Rapprocher gains, débits effectifs et variation réelle du compte ; distinguer les devises des éventuels tableaux de coûts |
| Munitions/consommables en stock | Vérifier l’absence de débit effectif pour le stock consommé ; ne pas utiliser sa valeur théorique comme dépense |
| Perte nette de crédits | Rapprochement signé, y compris un résultat net négatif ; aucun écrêtage à zéro |
| Bataille multichars | Tous les chars réellement joués et leurs champs conservés séparément ; déterminer si certains champs sont des totaux ou des données par véhicule, sans les additionner avant validation |
| Réouverture, redémarrage et changement de compte | Observations identifiables, compte courant correct, aucune écriture attribuée au compte précédent ; file et envois inchangés |
| Coupure réseau puis retour | Captures locales disponibles lorsque le client possède les résultats, envois habituels repris ; aucune nouvelle mesure envoyée |
| Rotation et erreur disque | Conservation bornée et avertissement en cas d’échec ; résultats du jeu et rapports habituels disponibles |

Le but est de prouver les correspondances, pas de donner déjà une formule de
calcul. En particulier, les crédits nets visés sont la variation effective du
compte attribuable à la bataille : bonus inclus, seuls débits effectifs déduits,
sans valoriser le stock consommé. La capture n’affirme pas qu’un champ candidat
correspond à cette définition. Si un coût est différé, si les soldes incluent
une autre opération, si un champ manque ou si le rapprochement est ambigu,
consigner le cas et revenir à l’utilisateur ; aucune substitution silencieuse.

Les tests hors jeu utilisent des données **synthétiques** pour contrôler la
projection, les erreurs, la confidentialité et la compatibilité. Ils ne
valident aucune définition économique. Les fixtures de référence seront
extraites des observations réelles expurgées après validation en jeu, avant
le lot 1. La recette complète et les résultats restent suivis dans
[#953](https://github.com/Battle-Conquest/Battle-Conquest/issues/953) ;
[#772](https://github.com/Battle-Conquest/Battle-Conquest/issues/772) reste ouverte.


## Identité des résultats — première étape #964

Cette étape prépare la correction multicomptes ; elle ne corrige pas encore les
liaisons ou la file. **Mettre les envois en pause pour cette recette** : le
chemin historique peut encore attribuer une réponse au compte connecté à sa
réception. Aucun tag ni release publique n’est nécessaire.

Construire le paquet de test pour WoT 2.4.1.1 :

```bash
python3 tools/build_release.py --version 0.0.964 --python27 /chemin/vers/python2.7
python2.7 tools/release_check.py dist/eu.battle-conquest_0.0.964.wotmod
```

Installer le ZIP généré selon la procédure ci-dessus, avec un seul paquet du
mod. Activer explicitement les deux options dans `diagnostics.json` :

```json
{"enabled": true, "identity_enabled": true}
```

Le nouveau bloc `identity` reste local dans les mêmes fichiers JSONL, avec les
mêmes limites et rotation. Un échec ne bloque ni le jeu ni la capture normale.
`identity_enabled` absent, `false`, `1` ou `"true"` ne l’active pas ; le commutateur
principal `enabled` reste nécessaire. La désactivation conserve les fichiers.

- `status: unverified` rappelle qu’aucun propriétaire n’est certifié.
- `contexts.request` est le compte/région lu au départ de la demande au cache,
  conservé dans sa callback, même après expiration. `contexts.receipt` est le
  compte lisible dans le client à réception ; il peut être inconnu. Aucun des
  deux ne constitue à lui seul le propriétaire du résultat. Une arrivée par un
  hook sans demande du mod garde un contexte de demande `null`.
- Le champ historique `account` de l’observation reste le dernier compte connu
  du suivi du mod ; ne pas le confondre avec ces contextes ou avec une preuve
  de propriété. Avec cette option, une observation peut aussi avoir `account: null`.
- `sections` contient les formes de `personal`, `players` et `avatars` présents.
  Les clés de collection et toutes les valeurs scalaires deviennent des
  références `refN`. Un entier et sa chaîne décimale ont la même référence.
  Deux chemins portant la même référence désignent une correspondance candidate.
  Les références sont recréées à chaque observation, sans corrélation historique.
- Seuls les noms techniques candidats explicitement autorisés sont lisibles
  (`accountDBID`, `databaseID`, `avatarID`, `name`, etc.). Ces noms ne prouvent pas
  leur sens réel. Les clés inconnues restent opaques ; les champs de secrets
  sont exclus. Les objets client ne sont jamais sérialisés ou convertis en texte.
  Aucune liste d’identifiants ou de pseudos de participants n’est conservée.
- Le contexte de chaque compte utilisateur conserve son identifiant en clair,
  sa région et la référence correspondante pour comparer les chemins. Les
  pseudos des résultats restent opaques : après un changement de pseudo,
  vérifier à nouveau la correspondance entre l’identifiant WG et le contexte,
  sans comparer les numéros `refN` entre observations.
- Chaque entrée personnelle reste distincte, y compris `avatar` et multichars.
  Les marqueurs `omitted` et `truncated` signalent les limites (128 éléments,
  six niveaux et budget global de 4 096 valeurs). Les champs candidats
  d’identité sont examinés avant les autres champs d’un résultat, pour éviter
  qu’une longue liste de mesures les masque à la limite des 128 éléments.
  Une identité absente,
  contradictoire ou plusieurs candidats restent des observations, sans sélection.
- Les réponses tardives des réparations #954/#956 peuvent être observées après
  changement de compte, mais restent exclues de la capture normale comme avant.

Recette à effectuer avec les envois en pause :

| Parcours | Observation attendue |
|---|---|
| Diagnostic désactivé, puis identité activée | Aucun bloc `identity` sans double activation ; captures locales avec activation |
| Bataille sous A, réponse sous A | Chemins candidats reliant les résultats personnels au compte A ; vérifier où se trouve son pseudo |
| Demande sous A, connexion de B avant réponse | Contexte de demande A, réception B ou inconnue ; aucune certification automatique |
| Demande expirée, puis réponse tardive | Le contexte initial reste A même si une autre demande a commencé |
| Arrêt ou rechargement du mod avant la réponse | Une réponse de l’ancienne session est ignorée, sans capture, écriture diagnostic ni nouvelle demande au cache |
| A → B → A, puis redémarrage | Contextes distinguables ; observations conservées ; aucune déduction depuis l’ancien `link.json` |
| Résultats ouverts, automatiques et réouverts | Comparer les chemins et références, sans additionner les observations |
| Aléatoire, classé, Assaut, Bastion, Ligne de front et autres modes disponibles | Identifier pour chaque mode le chemin WG, le champ pseudo et le lien avec `personal` ; noter les modes indisponibles |
| Résultat multichars | Tous les résultats personnels renvoient au même propriétaire vérifié, sans choisir un participant arbitraire |
| Identité absente, contradictoire, pseudo changé | Absence/contradiction explicite ; attribution par identifiant/région, jamais par pseudo |
| Erreur disque, limites, réseau coupé | Erreurs contenues et observations bornées ; aucune donnée diagnostic envoyée |

Copier les observations utiles avant rotation, expurger les identifiants du
contexte utilisateur et de l’arène avant partage, et ne jamais joindre
`link.json`. Consigner les correspondances réellement constatées et les modes
validés dans #964 sans cocher ses cases. Les fixtures synthétiques ne valident
aucun champ WoT. **Point d’arrêt : validation en jeu avant extraction du
propriétaire, liaisons par compte, migration et isolation de la file.**
