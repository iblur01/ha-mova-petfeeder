# Fonctionnalités

Statut sur l'appareil réel (Mova PF10, compte de test). « Vérifiée » = observée, lecture seule ou action faite dans l'app Mova avec relecture des propriétés. Détails : [ENDPOINTS.md](ENDPOINTS.md), [PROPERTIES.md](PROPERTIES.md).

| Vérifiées sur l'appareil | Hypothétiques | Impossibles ou non trouvées |
|---|---|---|
| Login cloud (`expires_in` 7200 s, `refresh_token` présent) | Grant `refresh_token` (jamais testé chez Mova) | Historique des distributions (NON TROUVÉ) |
| Liste des appareils : modèle, firmware, en ligne | Action de distribution (siid 3, aiid 1) lancée par l'intégration | Statistiques quotidiennes (NON TROUVÉ) |
| Lecture des propriétés (cache cloud, fonctionne hors ligne) | Écriture de 3.2 (mode nuit, inversé) et 3.3 (anti-glouton), selon le mapping du plugin MOVAhome | Notifications (NON TROUVÉ) |
| Planning 3.6 : heure, minute, portions et activation par créneau (relecture après modification dans l'app) | Écriture de 3.4 : seuil couplé au nombre de portions et au poids par portion ; gardé en lecture seule | Erreurs matérielles (bit de recalibrage exposé depuis 2.2) |
| Portions de la dernière distribution (5.2) : 3 puis 1 après 1 portion | Écriture de 3.6 (format supposé identique à la lecture) | Communication locale (NON TROUVÉ, aucune preuve : `cloud_polling`) |
| Poids en grammes (4.1), cohérent avec l'app, mais dérive : recalibrage demandé par l'app | Jours du créneau (octet 1 de 3.6, probablement un masque) | Push / temps réel (aucune preuve) |
| En ligne / hors ligne (`listV2.online`) | Sens de 3.1, 2.1, 2.3, 4.2, 4.3, 4.4 | Total journalier distribué (NON TROUVÉ) |
| | Bornes : 10 portions manuelles, 10 créneaux | |
| | Nécessité de l'en-tête `Dreame-Rlc` | |

## Entités de l'intégration

| Entité | Statut |
|---|---|
| `food_level` (sensor) | lecture VÉRIFIÉE, valeur à recalibrer |
| `next_feed` (sensor) | créneaux VÉRIFIÉS ; jours HYPOTHÈSE (calcul sur 0xFF uniquement) |
| `online` (binary_sensor) | VÉRIFIÉ |
| `night_mode`, `anti_glutton` (switches) | mappings et polarités repris du plugin MOVAhome |
| `anti_glutton_threshold`, `grams_per_portion` | 3.4 / 3.5 lus en grammes ; seuil gardé en lecture seule car recalculé par l'app |
| capteurs de défaut (binary_sensor) | bits 1, 2, 4, 8 et 16 du masque 2.2 : erreur, blocage, manque de croquettes, batterie faible et recalibrage ; inconnus si le masque est absent |
| bouton `feed` + action `feed(portions)` | champ portions dans la même fenêtre de l'action ; commande d'alimentation basée sur l'API du dépôt |
| actions de planning | HYPOTHÈSE, désactivées par défaut (`enable_schedule_write`) |
