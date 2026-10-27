# Propriétés MiOT du Mova PF10 (`mova.feeder.q2401`)

Clés `siid.piid` lues par `iotstatus/props`. Toutes les valeurs sont des chaînes ; l'API ne fournit ni nom ni unité.

Statuts : **CONFIRMÉ** (changement observé après une action faite dans l'app Mova, lecture seule de notre côté), **HYPOTHÈSE**, **NON TROUVÉ**.

Protocole d'observation (compte de test, 27/10/2026) : lecture de base, puis après une distribution d'1 portion depuis l'app, après modification du créneau de 18 h (5 puis 4 portions), puis après désactivation de ce créneau. Une seule différence de valeur est attribuée à une action quand les autres clés restent identiques.

## Table

| Clé | Nom interne | Valeur observée | Statut |
|---|---|---|---|
| 2.1 | `PROP_ONLINE` | `1` | Sens NON CONFIRMÉ (probable en ligne). L'état utilisé par l'intégration vient de `listV2.online` |
| 2.2 | `PROP_STATUS` | `0` | Sens NON CONFIRMÉ |
| 2.3 | - | `4` (dernière remontée début octobre) | Sens NON CONFIRMÉ (code d'état ou d'erreur ?) |
| 3.1 | - | `0` | Sens NON CONFIRMÉ. Sa date se met à jour sans changement de valeur |
| 3.2 | `PROP_SCHEDULE_ON` | `0` | Sens NON CONFIRMÉ : vaut 0 alors que des créneaux sont actifs. Écrit par le switch `schedule_enabled`, ignoré par `next_feed` |
| 3.3 | `PROP_SOUND_ON` | `0` | Probable son (0 = coupé) : HYPOTHÈSE, non retestée dans l'app |
| 3.4 | `PROP_PORTION_SIZE` | `5` | HYPOTHÈSE (taille de portion) |
| 3.5 | `PROP_MAX_FEEDINGS` | `5` | Sens NON CONFIRMÉ. Non exposé |
| 3.6 | `PROP_SCHEDULE` | `FF08000301FF0C000301FF12000501` | Planning, voir ci-dessous |
| 4.1 | `PROP_FOOD_LEVEL` | `90`, puis `95` | Poids en grammes, cohérent avec l'app (CONFIRMÉ). Dérive : voir ci-dessous |
| 4.2 | - | `20`, puis `22` | Sens NON CONFIRMÉ. Inchangé par la distribution et par les modifications de planning |
| 4.3 | - | `9` | Sens NON CONFIRMÉ. Inchangé après une distribution : ce n'est donc pas la dernière distribution |
| 4.4 | - | `2` | Sens NON CONFIRMÉ. Idem 4.3 |
| 5.1 | - | absente (`value` null) | NON TROUVÉ |
| 5.2 | - | `3`, puis `1` | Portions de la dernière distribution (CONFIRMÉ), voir ci-dessous |

Clés testées et absentes (`value` null) : 1.1-1.3, 2.4-2.7, 3.7-3.16, 4.5-4.11, 5.1, 5.3-5.8, 6.1-6.3, 7.1, 8.1, 9.1, 10.1.

Les clés 2.1, 2.2, 2.3, 3.1, 3.5, 4.2, 4.3 et 4.4 (sens non confirmé) sont lues à titre de diagnostic uniquement : aucune entité ne les expose.

## 3.6 : planning

Chaîne hexadécimale, **5 octets par créneau** (10 caractères hex). Exemple observé : `FF 08 00 03 01 | FF 0C 00 03 01 | FF 12 00 05 01`, soit 08:00 x3, 12:00 x3, 18:00 x5.

| Octet | Rôle | Statut |
|---|---|---|
| 1 | `FF` : jours | NON CONFIRMÉ. Probablement un masque de jours (FF = tous). Seule valeur observée : jamais modifié. Conservé tel quel (`days_raw`) |
| 2 | heure | HYPOTHÈSE de lecture cohérente avec l'app (heures locales) |
| 3 | minute | idem |
| 4 | portions | **CONFIRMÉ** : seul octet modifié après passage du créneau de 18 h de 5 à 4 portions dans l'app (`...12000501` devient `...12000401`) |
| 5 | activation | **CONFIRMÉ** : `01` actif, `00` désactivé (désactivation du créneau de 18 h : `...12000400`) |

Notes :
- Les heures du planning sont en heure locale de l'appareil (hypothèse, cohérente avec l'heure de la dernière remontée de 5.2).
- Écriture : le format d'écriture est supposé identique à celui de lecture. HYPOTHÈSE, jamais testée. Les écritures de planning sont désactivées par défaut dans l'intégration.
- Nombre maximal de créneaux : inconnu (limite de 10 dans l'intégration par prudence).

## 5.2 : portions de la dernière distribution

**CONFIRMÉ.** Valeur `3` à la lecture de base (créneau de 12 h x3 passé juste avant), puis `1` après une distribution d'1 portion lancée depuis l'app. La date de mise à jour de la clé suit l'événement. Pas de total journalier ni d'historique. L'intégration ne l'expose pas encore en entité (reste dans le diagnostic).

## 4.1 : poids en grammes

La valeur (92, 90, 95 g) est cohérente avec l'app. **Dérive** : la valeur évolue sans lien avec les distributions (90 devient 95 après une distribution d'1 portion), et l'app demande un recalibrage de la balance. Ne pas se fier à ce capteur pour une alerte de niveau bas tant que le recalibrage n'est pas fait.

## 3.2 : sens non confirmé

Vaut 0 pendant toute l'observation, y compris avec des créneaux actifs dans l'app. Il n'est donc pas un indicateur de « planning actif ». Le switch `schedule_enabled` l'expose tel quel, et `next_feed` l'ignore. Une écriture sur 3.2 n'a pas été validée sur l'appareil.
