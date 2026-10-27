# Tests

## Lancer

```bash
python3 -m unittest discover -s tests -v
```

Aucun réseau, aucun Home Assistant requis. État actuel : 41 tests, dont 31 exécutés et 10 sautés (HA non installé).

## Couvert (sans HA)

- `tests/test_models.py` (Python pur) : décodage et encodage de 3.6 (exemple réel `FF08000301FF0C000301FF12000501`), aller-retour, longueur invalide, upsert et remove de créneau, `next_feed` (même jour, minuit, jours inconnus, créneau désactivé, 3.2 ignoré), `parse_devices`, `parse_props` (null), `build_state` (valeurs invalides), `parse_token`, `check_command_result`, builders, `safe_detail` sans jeton, `hash_password`.
- `tests/test_api.py` (`FakeSession`) : formulaire de login et URL de base, login refusé, un seul re-login sur 401, second 401 = `MovaAuthError`, `code != 0` sans re-login, jeton expiré donne un refresh, refresh en échec donne un login, erreurs de connexion, deux appels concurrents = un seul login, logs sans secret, aucune lecture n'atteint `sendCommand`.

Les fixtures (`tests/fixtures/`) sont masquées.

## Sauté sans HA (10 tests, `tests/test_coordinator_ha.py`)

Exécutés uniquement si `homeassistant` est installé : réauth au premier refresh, `ConfigEntryNotReady`, tolérance de 3 échecs, distribution (refus, refresh programmé), pas de refresh après échec, écriture de planning refusée/acceptée selon l'option, diagnostic masqué, suppression des entités obsolètes, migration v1 vers v2.

## Avec Home Assistant 2026.10

Avec `requirements_test_2026_10.txt` (HA 2026.10.4 et `pytest-homeassistant-custom-component`), désactiver le plugin, sinon sa fixture async autouse `configure_event_loop` met les tests unittest synchrones en erreur (`PytestRemovedIn9Warning`) :

```bash
PYTHONPATH=tests:. python -m pytest tests -q -p no:homeassistant
```

Sous HA 2024.11, la commande reste `PYTHONPATH=tests:. python -m pytest tests -q`.

## Non testé

- Client aiohttp réel (réseau, TLS, vrais codes d'erreur du cloud).
- Coordinator HA et plateformes dans un vrai Home Assistant (ces 10 tests n'ont pas été exécutés dans cet environnement).
- Validation sur appareil : écriture 3.2/3.3/3.4, action de distribution par l'intégration, écriture de 3.6, grant `refresh_token`, forme de `set_properties` avec `did`.
- `config_flow` (user, reauth, options) : aucun test.

## Fichiers hérités

`test_api.py` et `scripts/test_poll.py` (racine et `scripts/`) appellent le vrai cloud et utilisent d'anciennes clés : ils ne font pas partie de la suite et ne sont pas lancés par la commande ci-dessus.
