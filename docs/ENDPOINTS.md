# Endpoints Mova (cloud MOVAhome)

Hôte : serveur régional `iot.mova-tech.com`, port 13267 (préfixe `eu.`, `us.`... selon la région ; `cn` sans préfixe). Seuls les chemins sont donnés ci-dessous. Toutes les valeurs sensibles sont masquées par `***`.

Niveaux de confiance : **VÉRIFIÉ** (requête réelle observée, lecture seule), **HYPOTHÈSE** (code repris de l'intégration Dreame ou de l'ancien code, jamais observé chez Mova), **NON TROUVÉ**.

Seuls E1, E2 et E3 ont été appelés lors des sessions de reconnaissance (compte de test, région `eu`, requêtes espacées). E4 n'a jamais été appelé par la reconnaissance.

## E1. Login : `POST /dreame-auth/oauth/token`

- Rôle : obtenir un jeton d'accès.
- Corps (formulaire urlencoded) : `platform`, `scope`, `grant_type=password`, `username=***`, `password=md5(mot de passe + sel)=***`, `type=account`. En-têtes : `Authorization: Basic ***`, `Tenant-Id`, `Dreame-Rlc=***`, `User-Agent` iOS.
- Réponse : HTTP 200, pas de champ `code` applicatif. Clés : `access_token` str, `refresh_token` str, `token_type` str, `expires_in` int (7200 s observé, soit 2 h), `scope` str, `tenant_id` str, `country` str, `region` str, `uid` str, `jti` str, `client_id` str, `role_*`, `lang`, `t` int, `u` int, `is_new_register` bool, `user_token` bool.
- Erreurs : le client traite HTTP 400/401/403 ou l'absence de `access_token` comme `MovaAuthError`. Aucune erreur observée en réel. Le format exact d'une erreur de mot de passe n'a pas été observé.
- Confiance : VÉRIFIÉ (succès). Erreurs : HYPOTHÈSE.

### Variante refresh : même chemin, `grant_type=refresh_token`
- Corps : `platform`, `scope`, `grant_type=refresh_token`, `refresh_token=***`.
- Confiance : HYPOTHÈSE (repris de Dreame, jamais testé chez Mova). Si le refresh échoue, le client fait un login complet.

## E2. Liste des appareils : `POST /dreame-user-iot/iotuserbind/device/listV2`

- Rôle : appareils du compte, état en ligne, firmware.
- Paramètres : aucun corps. En-tête `Dreame-Auth: ***` (pas de préfixe `Bearer`), `Dreame-Rlc`.
- Réponse : HTTP 200, `code` 0, `success` true, `msg`. `data.page.records[]` avec notamment : `did` str, `model` str (`mova.feeder.q2401`), `ver` str (firmware), `customName` str, `mac` str, `online` bool, `latestStatus` int, `bindDomain` str, `property` str (contient la MAC en clair), `battery` int, `updateTime` str, `deviceInfo` objet, `featureCode` int.
- Erreurs : `code != 0` donne `MovaApiError(code)`. Aucune erreur observée.
- Confiance : VÉRIFIÉ.
- Notes : `bindDomain` (`<n>.mt.<region>.iot...:<port>`) fournit le préfixe de l'URL `sendCommand`. `updateTime` est une date de liaison, pas un historique. Aucun champ d'erreur matérielle ni de dernière distribution.

## E3. Lecture des propriétés : `POST /dreame-user-iot/iotstatus/props`

- Rôle : lire des propriétés MiOT depuis le cache cloud (fonctionne appareil hors ligne, valeur + date de dernière remontée).
- Corps JSON : `{"did": "***", "keys": "3.2,3.3,..."}` (clés `siid.piid` séparées par des virgules).
- Réponse : HTTP 200, `code` 0, `success` true. `data` : liste de `{key: str, value: str | null, updateDate: int (ms epoch)}`. Toutes les valeurs sont des chaînes. Une clé inexistante renvoie `value` null, sans erreur.
- Erreurs : `code != 0` donne `MovaApiError`.
- Confiance : VÉRIFIÉ. La sémantique des clés est décrite dans [PROPERTIES.md](PROPERTIES.md).
- Limite : une seule valeur par clé, aucun historique.

## E4. Commandes : `POST /dreame-iot-com-<n>/device/sendCommand`

- `<n>` = premier segment de `bindDomain` (ex. `20000`).
- Corps : `{did, id, data: {did, id, method, params, from}}`.
- Méthodes :
  - `set_properties`, `params = [{did, siid, piid, value}]` ;
  - `action`, `params = {did, siid:3, aiid:1, in:[{piid:1, value:<portions>}]}`.
- Réponse attendue : `code` 0 et `data.result` (liste pour `set_properties`, dict pour `action`) avec `code` 0 par élément. Un `code` non nul donne `MovaCommandError`.
- Confiance :
  - **Action de distribution et écritures 3.2/3.3/3.4 : HYPOTHÈSE** (code hérité du dépôt de référence, jamais rejoué par la reconnaissance actuelle).
  - **Écriture de 3.6 : HYPOTHÈSE** (format d'écriture = format de lecture, jamais testé).
  - `did` est envoyé dans chaque élément de `params` de `set_properties` : non vérifié chez Mova.
- Les modifications observées (distribution, créneau modifié, créneau désactivé) ont été faites **depuis l'application Mova**, pas par cette intégration.

## Fonctionnalités demandées

| # | Fonctionnalité | Statut | Source / détail |
|---|---|---|---|
| 1 | Historique des distributions | NON TROUVÉ | Aucun endpoint. `5.2` donne seulement les portions de la dernière distribution (CONFIRMÉ), pas un historique |
| 2 | Statistiques quotidiennes | NON TROUVÉ | Aucun endpoint. `4.2` (22, 20 observés) : sens non confirmé |
| 3 | Quantités distribuées | HYPOTHÈSE partielle | `5.2` = portions de la dernière distribution (CONFIRMÉ) ; pas de total ni de poids distribué |
| 4 | État en ligne / hors ligne | VÉRIFIÉ | `online` de E2 (aussi 2.1, sens non confirmé) |
| 5 | État matériel | HYPOTHÈSE | 2.2, 2.3, 3.1 : sens non confirmé |
| 6 | Erreurs matérielles | NON TROUVÉ | Aucun champ identifié |
| 7 | Version firmware | VÉRIFIÉ | `ver` de E2 |
| 8 | Planning (créneaux) | VÉRIFIÉ en lecture | 3.6 : heure, minute, portions, activation CONFIRMÉS ; jours NON CONFIRMÉS ; 3.2 (planning global ?) NON CONFIRMÉ |
| 9 | Niveau de croquettes | VÉRIFIÉ avec réserve | 4.1 en grammes, cohérent avec l'app, mais dérive (l'app demande un recalibrage) |
| 10 | Taille de portion / son | VÉRIFIÉ en lecture | 3.4 et 3.3 lus ; écriture HYPOTHÈSE |
| 11 | Notifications | NON TROUVÉ | Aucun endpoint dans le code de référence ni observé |
| 12 | Communication locale | NON TROUVÉ | Aucune trace ; tout passe par le cloud |

Recherches faites dans le code des deux dépôts de référence (sans réseau) : aucun endpoint d'historique, statistiques, notifications, OTA, MQTT ou local.
