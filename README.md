# Mova Pet Feeder

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

Intégration Home Assistant pour le distributeur de croquettes **Mova PF10** (`mova.feeder.q2401`), via le cloud MOVAhome (`cloud_polling`, aucune communication locale ni push trouvée).

## Fonctionnalités

| Entité | Type | Rôle |
|---|---|---|
| `food_level` | Capteur (g) | Poids de croquettes (propriété 4.1). Voir l'avertissement sur le recalibrage |
| `next_feed` | Capteur (horodatage) | Prochaine distribution calculée depuis le planning ; attribut `slots` |
| `online` | Capteur binaire (diagnostic) | Appareil en ligne dans le cloud |
| `schedule_enabled` | Interrupteur | Propriété 3.2, **sens non confirmé** (vaut 0 avec des créneaux actifs) |
| `sound` | Interrupteur (config) | Propriété 3.3 |
| `portion_size` | Nombre (config, 1 à 50) | Propriété 3.4 |
| `feed` | Bouton | Distribue `default_portions` (option, 1 par défaut) |

Action `mova_petfeeder.feed(portions)` : cible le bouton `feed`, distribue 1 à 10 portions. Actions de planning (`set_schedule`, `upsert_schedule_slot`, `remove_schedule_slot`) sur `next_feed`, voir plus bas.

Statut sur l'appareil : lecture vérifiée ; écritures (switches, number, distribution) non validées par l'intégration sur l'appareil. Tableau complet dans [docs/FEATURES.md](docs/FEATURES.md). Non disponible : historique, statistiques, notifications, communication locale.

## Avertissements

- **Recalibrage** : le poids `food_level` dérive sur l'appareil testé et l'application Mova demande un recalibrage. Recalibrez avant de vous fier à la valeur.
- **Écritures de planning désactivées par défaut** : le format d'écriture de la propriété 3.6 n'a pas été validé. Elles sont refusées tant que l'option `enable_schedule_write` n'est pas activée (Options de l'intégration). Une mauvaise écriture pourrait altérer le planning de l'appareil.
- Les jours de chaque créneau ne sont pas décodés : `next_feed` n'est calculé que pour des créneaux quotidiens et vaut inconnu sinon.
- Les heures du planning sont supposées dans le fuseau de Home Assistant.

## Prérequis

- Compte MOVAhome avec un distributeur associé.
- Home Assistant 2024.11.0 ou plus récent.

## Installation

### HACS (recommandé)

1. HACS, Intégrations, menu, **Dépôts personnalisés**.
2. Ajouter `https://github.com/iblur01/ha-mova-petfeeder`, type **Intégration**.
3. Installer **Mova Pet Feeder**, puis redémarrer Home Assistant.

### Manuelle

Copier `custom_components/mova_petfeeder/` dans le dossier `custom_components/` de Home Assistant, puis redémarrer.

## Configuration

1. Paramètres, Appareils et services, Ajouter une intégration, **Mova Pet Feeder**.
2. Saisir l'email et le mot de passe MOVAhome, et la région (`eu`, `us`, `cn`, `ru`, `tw`, `sg`, `in`).

Le mot de passe n'est pas stocké en clair (seul un hash est conservé).

Options : intervalle d'interrogation (60 s par défaut, 30 à 600 s), portions par défaut du bouton, `enable_schedule_write`.

## Notes

- Interrogation du cloud toutes les 60 s par défaut. L'appareil doit être en ligne pour les commandes ; les valeurs lues viennent du cache cloud.
- Diagnostics disponibles, avec identifiants masqués.

## Documentation

- [docs/FEATURES.md](docs/FEATURES.md) : ce qui est vérifié, hypothétique, introuvable
- [docs/ENDPOINTS.md](docs/ENDPOINTS.md) : cartographie des endpoints
- [docs/PROPERTIES.md](docs/PROPERTIES.md) : propriétés et décodage du planning
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) : conception implémentée et écarts
- [docs/TESTING.md](docs/TESTING.md) : tests
