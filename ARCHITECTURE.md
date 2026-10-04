# Architecture proposée

## Objectif

Ce dépôt héberge des démons Python qui collectent des mesures depuis des API web et des capteurs locaux, puis les publient sur le broker MQTT consommé par OpenEnergyMonitor (EmonCMS). La cible est un Raspberry Pi 3 sous Linux : les processus doivent rester légers, redémarrer proprement après une panne et fonctionner sans privilèges élevés.

Le premier collecteur implémenté interroge Open-Meteo pour la température actuelle à Opio, France. Les autres collecteurs pourront être ajoutés sans modifier le cycle MQTT commun.

## Décisions structurantes

- Un collecteur correspond à une source cohérente (par exemple une API météo ou un ensemble de capteurs sur le même bus).
- Chaque collecteur s'exécute dans son propre processus et son propre service `systemd`. Une source en panne ne bloque donc pas les autres.
- La configuration, la validation des mesures, les logs et la publication MQTT sont partagés dans un petit module commun.
- Les dépendances réseau sont limitées et explicites. Les lectures ont des délais d'expiration, et le client MQTT sait se reconnecter.
- Les identifiants et secrets sont fournis à l'exécution, jamais enregistrés dans Git.

## Arborescence cible

```text
energy-monitor-feeds/
├── .gitignore
├── ARCHITECTURE.md
├── README.md
├── pyproject.toml
├── config/
│   └── config.example.toml
├── deploy/
│   └── systemd/
│       └── energy-feed@.service
├── src/
│   ├── cli.py
│   ├── config.py
│   ├── logging_config.py
│   ├── models.py
│   ├── mqtt.py
│   └── collectors/
│       ├── __init__.py
│       ├── weather_api.py
│       └── local_sensors.py (squelette)
└── tests/
    ├── test_config.py
    ├── test_mqtt_payload.py
    └── test_weather_api.py
```

Les collecteurs implémentent une interface simple : lire une ou plusieurs mesures, les valider, puis les remettre au module de publication. Le module commun ne connaît pas les détails des API ou des pilotes de capteurs.

Le collecteur `weather_api` demande `current=temperature_2m` à l'API Open-Meteo pour Opio (`43.66862, 6.98212`, `Europe/Paris`), sans clé API. Il publie la mesure sous le nœud `weather_opio` et l'entrée `temperature_c`. `local_sensors.py` est un squelette; aucun capteur ni pilote local n'est encore configuré.

## Flux de données

```text
API web / capteur local
          │
          ▼
   Collecteur dédié
          │  timeout, validation, unités normalisées
          ▼
   Client MQTT commun
          │  QoS configurable, reconnexion
          ▼
      Broker MQTT
          │  abonnement / entrée MQTT EmonCMS
          ▼
    Input puis feed EmonCMS
```

Les démons publient des valeurs, mais ne créent pas directement les feeds EmonCMS. Dans EmonCMS, une entrée MQTT doit recevoir le topic, puis son traitement doit enregistrer les valeurs dans un feed.

## Contrat MQTT

Utiliser le format MQTT standard d'EmonCMS `emon/<node>/<key>`, avec un topic par mesure. Le nœud identifie le capteur et la clé identifie le canal et la mesure :

```text
Topic:   emon/refoss_em06/channel_{channel_idx}_power
Exemple: emon/refoss_em06/channel_1_power
Payload: 420
```

EmonCMS utilise `emon` comme `basetopic` par défaut. Il interprète l'exemple comme le nœud `refoss_em06` et l'entrée `channel_1_power`. Pour une API web, choisir un nom de nœud stable pour la source ou la ressource (par exemple `openweather_home`) et une clé descriptive (par exemple `temperature_c`). Publier une valeur numérique par message et documenter les unités.

Le service `emoncms_mqtt` s'abonne à `emon/#` et crée/met à jour les Inputs à partir de ces topics. Dans EmonCMS, ajouter ensuite un processus d'enregistrement vers un feed pour chaque Input à conserver. Utiliser des noms stables en minuscules, sans espaces, et éviter de mélanger des unités dans une même mesure.

La politique QoS doit être configurable. QoS 0 minimise le trafic; QoS 1 améliore la livraison mais autorise les doublons. Pour des mesures périodiques, le choix doit tenir compte du traitement EmonCMS et de la tolérance aux doublons. Ne pas retenir les messages (retain) par défaut, sauf besoin explicite d'exposer la dernière valeur connue.

## Configuration et secrets

- Une configuration TOML non secrète décrit le broker, les préfixes/topics des sources, les intervalles de collecte et les options propres aux sources.
- Les secrets sont injectés via l'environnement du service (`EnvironmentFile` protégé) ou un mécanisme de secrets du système. Ne pas committer de fichier réel de secrets.
- Le service tourne sous un compte Linux dédié sans shell interactif. N'ajouter l'accès à un groupe matériel (par exemple GPIO) que si le capteur l'exige.
- Le broker doit utiliser une authentification et, hors réseau local de confiance, TLS. Les identifiants ne doivent pas apparaître dans les logs.

## Résilience et exploitation

- Appliquer un timeout à chaque appel HTTP et à chaque lecture de capteur; une erreur ne doit pas bloquer indéfiniment le collecteur.
- Journaliser vers `stdout`/`stderr` avec le module `logging`, pour centralisation par `journald`. Inclure le nom du collecteur et le résultat, jamais les secrets.
- Utiliser `systemd` avec `Restart=on-failure`, une temporisation de redémarrage et un utilisateur dédié.
- Continuer les cycles après une erreur transitoire, avec délai progressif en cas de panne persistante. Une mesure invalide est rejetée et signalée, pas publiée comme zéro.
- La première version peut garder les mesures en mémoire seulement. Une file persistante SQLite ne se justifie que si la perte des mesures pendant une indisponibilité MQTT n'est pas acceptable.
- Synchroniser l'horloge du Raspberry Pi via NTP. Publier des valeurs numériques avec unités convenues; vérifier le comportement temporel souhaité dans EmonCMS avant d'ajouter un timestamp dans le payload.

## Dépendances et compatibilité

Viser Python 3.9 ou plus récent pour couvrir les versions courantes de Raspberry Pi OS. Préférer la bibliothèque standard. Un client MQTT tel que `paho-mqtt` et un client HTTP tel que `requests` suffisent pour les premiers collecteurs; ajouter un pilote seulement pour le matériel réellement utilisé. Garder les dépendances verrouillées ou bornées dans `pyproject.toml` et tester l'installation sur l'architecture ARM du Pi 3.

Les tests unitaires doivent couvrir au minimum le chargement de configuration, la validation et la sérialisation des payloads sans exiger de broker ni de capteur. Les tests d'intégration peuvent utiliser un broker de test séparé.