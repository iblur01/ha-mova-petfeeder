# Architecture implémentée

Ce document décrit le code réel de `custom_components/mova_petfeeder/`. Les statuts sur l'appareil sont CONFIRMÉ / HYPOTHÈSE / NON TROUVÉ (voir [PROPERTIES.md](PROPERTIES.md)). `iot_class` = `cloud_polling` : aucune preuve de push ni de communication locale.

## Couches

Dépendances vers le bas uniquement.

| Couche | Fichiers | Rôle |
|---|---|---|
| Transport | `api.py` | `MovaClient` (aiohttp, `session.post()` injectable) : login, refresh, `list_devices`, `get_props`, `set_properties`, `action` |
| Parsing | `models.py`, `const.py` | Python pur, sans import HA : dataclasses, exceptions, `parse_*`, `decode/encode_schedule`, `next_feed`, `build_*`, `check_command_result`, `safe_detail` |
| Orchestration | `coordinator.py` | `MovaCoordinator(DataUpdateCoordinator[dict[did, FeederState]])` : polling, tolérance aux pannes, commandes, refresh différé |
| HA | `__init__`, `config_flow`, `entity`, plateformes, `services.py`, `diagnostics` | Entités, options, réauth, actions |

## Flux

- **Login** : `POST` formulaire (`data=dict`, donc `+` et `&` de l'email encodés). Le mot de passe envoyé est le hash tiré de `entry.data` (le mot de passe en clair n'est pas stocké). Refus HTTP 400/401/403 ou absence d'`access_token` : `MovaAuthError`. Réseau, timeout (15 s), 5xx, JSON invalide : `MovaConnectionError`.
- **Refresh** : `_ensure_token` sous `asyncio.Lock`. Jeton renouvelé 300 s avant expiration (`expires_in` = 7200 s observé). Grant `refresh_token` : HYPOTHÈSE ; tout échec bascule sur un login complet.
- **Requête** : HTTP 401 donne un login forcé et une seule nouvelle tentative ; second 401 : `MovaAuthError`. `code != 0` : `MovaApiError`, sans nouveau login.
- **Polling** : 1 appel `listV2` (en ligne, firmware) + 1 appel `props` par distributeur (`ENTITY_KEYS` + `DIAG_KEYS` dans une seule requête). Intervalle 60 s par défaut, option 30 à 600 s. Résultat : `dict[did, FeederState]`. Un distributeur ajouté après le démarrage est signalé en log et n'apparaît qu'au rechargement.
- **Commande** (`_async_command`) : refus si distributeur inconnu, hors ligne, ou déjà en cours (`asyncio.Lock` par distributeur, pas de double distribution). Puis appel client. Après succès : refresh différé de 10 s (le précédent est remplacé). Aucun refresh si échec. Switches et number : mise à jour optimiste.

## Stratégie d'erreurs

| Exception | Premier refresh | Polling | Commande |
|---|---|---|---|
| `MovaAuthError` | `ConfigEntryAuthFailed` (réauth) | idem | `HomeAssistantError` + `async_start_reauth` |
| `MovaConnectionError` / `MovaApiError` | `UpdateFailed` (`ConfigEntryNotReady`) | 1 et 2 échecs consécutifs : données conservées + warning ; 3e : `UpdateFailed` | `HomeAssistantError` |
| `MovaCommandError` | - | - | `HomeAssistantError` |
| Valeur de propriété invalide | champ à `None` (log debug) | idem | - |
| Entrée invalide, écriture de planning désactivée | - | - | `ServiceValidationError` |
| Exception inattendue | `UpdateFailed` + log | idem | propagée |

Les logs ne contiennent jamais le corps d'une requête ou d'une réponse (`safe_detail` : code et 100 premiers caractères de `msg`).

## UX de distribution

- Entité `button` `feed` : appuie = distribue `default_portions` (option, 1 par défaut).
- Action d'entité `mova_petfeeder.feed(portions)` sur ce bouton (1 à 10, borne HYPOTHÈSE). Rejetés : number séparé, number qui distribue au `set_value`.
- Bornes de portions manuelles et du planning (10) : choisies par prudence, non vérifiées sur l'appareil.

## Planning

- Lecture : capteur `next_feed` (timestamp) avec attribut `slots` (`time`, `portions`, `enabled`, `days_raw`).
- Écriture : actions d'entité `set_schedule`, `upsert_schedule_slot`, `remove_schedule_slot` (sur `next_feed`). Elles réécrivent 3.6 d'un bloc.
- Protégé par l'option `enable_schedule_write`, **désactivée par défaut** (`ServiceValidationError` sinon). Format d'écriture : HYPOTHÈSE.

## Entités finales (6 + action)

| Plateforme | `translation_key` | Source | Catégorie | Statut de la source |
|---|---|---|---|---|
| sensor | `food_level` | 4.1 (g) | - | CONFIRMÉ mais dérive |
| sensor | `next_feed` | 3.6 | - | créneaux CONFIRMÉS, jours NON CONFIRMÉS |
| binary_sensor | `online` | `listV2.online` | diagnostic | CONFIRMÉ |
| switch | `schedule_enabled` | 3.2 | - | sens NON CONFIRMÉ |
| switch | `sound` | 3.3 | config | HYPOTHÈSE |
| number | `portion_size` | 3.4 (1 à 50) | config | HYPOTHÈSE |
| button | `feed` | action 3/1 | - | HYPOTHÈSE (jamais lancée par l'intégration sur l'appareil) |

Firmware et modèle : `DeviceInfo` (`sw_version`, `model`). Pas d'entité « dernière distribution » : 5.2 est confirmée mais non exposée à ce stade.

## Migration

- Entrée de config v1 vers v2 (`async_migrate_entry`, sans réseau) : `password` remplacé par `password_hash`, `unique_id` = email en minuscules.
- `unique_id` d'entités conservés : `{mac sans ':' en minuscules}_{suffixe}` (`did` si pas de MAC). `schedule_sensor` devient `next_feed`. `portion_size_sensor` et `manual_portions` sont supprimés du registre au démarrage. Nouveau : `online`.
- Identifiant de device : `(domain, mac)`, inchangé.

## Écarts par rapport au document de conception

1. **Exceptions dans `models.py`** (et non `api.py`) ; `api.py` les ré-exporte via `__all__`. Les parseurs de `models.py` peuvent ainsi les lever sans importer le client.
2. **`check_command_result` côté client** : appelée dans `MovaClient._send`, non dans le coordinator. Les erreurs de commande sortent déjà typées (`MovaCommandError`).
3. **Actions enregistrées dans les plateformes** : `feed` dans `button.py`, actions de planning enregistrées depuis `sensor.py` (via `services.py`), et non au niveau du domaine dans `__init__.py`.
4. **Minimum HA 2024.11.0** (`hacs.json`) : relevé par rapport au 2024.6.0 de l'ancien README (usage de `runtime_data`, `type MovaConfigEntry`).
5. **`did` envoyé dans chaque élément de `params` de `set_properties`** : non vérifié chez Mova (HYPOTHÈSE). Une écriture réelle pourrait demander une autre forme.
6. **`next_feed` ignore 3.2** : sa signature est `next_feed(slots, now)` (le document de conception prévoyait `schedule_enabled`). Raison : 3.2 vaut 0 avec des créneaux actifs.
7. Hors document de conception : le `sw_version`/modèle dans `DeviceInfo`, l'option `scan_interval` 30 à 600 s, le diagnostic masqué.

## Sécurité

- `diagnostics.py` masque mot de passe/hash, jetons, `did`, MAC, `bindDomain`, etc.
- Constantes d'application (sel, Basic, tenant) dans `const.py`. L'en-tête `Dreame-Rlc` est en dur : **à vérifier avant publication HACS**.
- `.env` et `*.credentials.json` sont dans `.gitignore`.
