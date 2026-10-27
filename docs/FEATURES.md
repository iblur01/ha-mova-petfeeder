# Fonctionnalités

Statut sur l'appareil réel (Mova PF10, compte de test). « Vérifiée » = observée, lecture seule ou action faite dans l'app Mova avec relecture des propriétés. Détails : [ENDPOINTS.md](ENDPOINTS.md), [PROPERTIES.md](PROPERTIES.md).

| Vérifiées sur l'appareil | Hypothétiques | Impossibles ou non trouvées |
|---|---|---|
| Login cloud (`expires_in` 7200 s, `refresh_token` présent) | Grant `refresh_token` (jamais testé chez Mova) | Historique des distributions (NON TROUVÉ) |
| Liste des appareils : modèle, firmware, en ligne | Action de distribution (siid 3, aiid 1) lancée par l'intégration | Statistiques quotidiennes (NON TROUVÉ) |
| Lecture des propriétés (cache cloud, fonctionne hors ligne) | Écriture de 3.2 (switch `schedule_enabled`) | Notifications (NON TROUVÉ) |
| Planning 3.6 : heure, minute, portions et activation par créneau (relecture après modification dans l'app) | Écriture de 3.3 (son) et 3.4 (taille de portion) | Erreurs matérielles (NON TROUVÉ) |
| Portions de la dernière distribution (5.2) : 3 puis 1 après 1 portion | Écriture de 3.6 (format supposé identique à la lecture) | Communication locale (NON TROUVÉ, aucune preuve : `cloud_polling`) |
| Poids en grammes (4.1), cohérent avec l'app, mais dérive : recalibrage demandé par l'app | Jours du créneau (octet 1 de 3.6, probablement un masque) | Push / temps réel (aucune preuve) |
| En ligne / hors ligne (`listV2.online`) | Sens de 3.2 (vaut 0 avec créneaux actifs), 3.1, 3.3, 3.4, 3.5, 2.1, 2.2, 2.3, 4.2, 4.3, 4.4 | Total journalier distribué (NON TROUVÉ) |
| | Bornes : 10 portions manuelles, 10 créneaux | |
| | Nécessité de l'en-tête `Dreame-Rlc` | |

## Entités de l'intégration

| Entité | Statut |
|---|---|
| `food_level` (sensor) | lecture VÉRIFIÉE, valeur à recalibrer |
| `next_feed` (sensor) | créneaux VÉRIFIÉS ; jours HYPOTHÈSE (calcul sur 0xFF uniquement) |
| `online` (binary_sensor) | VÉRIFIÉ |
| `schedule_enabled` (switch) | lecture VÉRIFIÉE, sens NON CONFIRMÉ |
| `sound`, `portion_size` | lecture VÉRIFIÉE (valeurs), sens et écriture HYPOTHÈSE |
| bouton `feed` + action `feed(portions)` | HYPOTHÈSE (jamais lancée sur l'appareil par l'intégration) |
| actions de planning | HYPOTHÈSE, désactivées par défaut (`enable_schedule_write`) |
