# Energy Monitor Feeds

Démons Python destinés à Linux et au Raspberry Pi 3. Ils récupèrent des mesures depuis des services web ou des capteurs locaux et les publient via MQTT pour OpenEnergyMonitor / EmonCMS. Le premier collecteur interroge Open-Meteo pour obtenir la température actuelle à Opio, France.

Voir [ARCHITECTURE.md](ARCHITECTURE.md) pour les composants prévus, le contrat MQTT et les choix de déploiement.

## Fonctionnement

Chaque source est prise en charge par un collecteur indépendant. Le collecteur lit et valide les mesures, puis le module commun les publie au broker MQTT. EmonCMS reçoit ces messages comme des **Inputs**; un processus configuré dans l'interface EmonCMS les enregistre ensuite dans un ou plusieurs **Feeds**.

Le collecteur météo utilise le format MQTT standard d'EmonCMS `emon/<node>/<key>` :

```text
Topic:   emon/weather_opio/temperature_c
Payload: 18.5
```

Le nœud `weather_opio` identifie la source météo et l'entrée `temperature_c` porte la valeur en degrés Celsius. Le préfixe `emon` est le `basetopic` MQTT standard d'EmonCMS. Les coordonnées utilisées sont `43.66862, 6.98212`, fuseau `Europe/Paris`; l'API ne nécessite pas de clé.

## Installation locale

Prérequis : Python 3.9 ou plus récent, `pip` et un broker MQTT accessible. Depuis la racine du dépôt :

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
cp config/config.example.toml config/config.toml
```

Modifier `config/config.toml` pour renseigner l'hôte et le port du broker. Pour un broker avec authentification, définir `username_env = "MQTT_USERNAME"` et `password_env = "MQTT_PASSWORD"` dans la section `[mqtt]`, puis exporter ces variables avant le lancement. Ne pas inscrire leurs valeurs dans le fichier TOML ni dans Git.

Lancer le collecteur :

```bash
energy-feed weather_api --config config/config.toml
```

Le premier cycle part immédiatement, puis la collecte est répétée toutes les 300 secondes par défaut. Les erreurs de collecte ou de publication sont journalisées; la boucle continue au cycle suivant. Arrêter avec `Ctrl+C`.

## Tester la réception MQTT

Pour tester le broker indépendamment du collecteur, installer `mosquitto-clients` sur Debian/Raspberry Pi OS si nécessaire, puis publier une valeur :

```bash
mosquitto_pub -h 127.0.0.1 -p 1883 \
  -t 'emon/weather_opio/temperature_c' \
  -m '18.5' \
  -q 0
```

Remplacer l'hôte et le port par ceux du broker MQTT utilisé par EmonCMS. Cette commande suppose un broker local sans authentification; ne pas mettre de vrais secrets directement dans la ligne de commande. Vérifier ensuite que l'entrée `weather_opio / temperature_c` apparaît dans **Inputs**. Ajouter un processus d'enregistrement vers un feed, puis contrôler la valeur dans **Feeds**.

Si rien n'arrive, vérifier l'accessibilité réseau du broker, ses identifiants et que le service `emoncms_mqtt` est actif. La connexion au broker seule ne crée pas automatiquement un feed.

## Installation sur Raspberry Pi

Déployer le dépôt dans `/opt/energy-monitor-feeds`, puis installer le paquet et son environnement :

```bash
sudo adduser --system --group --no-create-home energy-feed
sudo python3 -m venv /opt/energy-monitor-feeds/.venv
sudo /opt/energy-monitor-feeds/.venv/bin/pip install /opt/energy-monitor-feeds
sudo install -d -o root -g energy-feed -m 0750 /etc/energy-monitor-feeds
sudo install -o root -g energy-feed -m 0640 \
  /opt/energy-monitor-feeds/config/config.example.toml \
  /etc/energy-monitor-feeds/config.toml
```

Modifier `/etc/energy-monitor-feeds/config.toml` pour le broker de production. Pour l'authentification, définir les noms de variables d'environnement dans la section `[mqtt]`, créer `/etc/energy-monitor-feeds/energy-feed.env` avec `MQTT_USERNAME` et `MQTT_PASSWORD`, puis le protéger (`root:energy-feed`, mode `0640`). Installer et activer l'unité :

```bash
sudo install -o root -g root -m 0644 \
  /opt/energy-monitor-feeds/deploy/systemd/energy-feed@.service \
  /etc/systemd/system/energy-feed@.service
sudo systemctl daemon-reload
sudo systemctl enable --now energy-feed@weather_api
sudo journalctl -u energy-feed@weather_api -f
```

Le service redémarre après une sortie en erreur et journalise dans `journald`. L'unité est configurée pour fonctionner sous le compte système `energy-feed`.

## Ajouter un collecteur

Un collecteur doit rester limité à une source et à la conversion de ses données en mesures numériques documentées. Il doit définir des timeouts, traiter les erreurs transitoires sans arrêter définitivement le processus et laisser la connexion MQTT ainsi que les logs au module commun. Ajouter des tests unitaires pour les conversions et les payloads, sans dépendre du réseau ou du matériel réel. `local_sensors.py` est un squelette en attente du choix de matériel; seul `weather_api` est actuellement exécutable.

## Sécurité

- Ne jamais committer les mots de passe MQTT, tokens ou clés d'API.
- Utiliser un compte système dédié et des permissions minimales.
- Préférer TLS lorsque le broker est accessible hors du réseau local de confiance.
- Ne pas journaliser les valeurs de secrets ni les en-têtes d'authentification.

## Tests

```bash
pytest
```

Les tests utilisent une réponse Open-Meteo simulée et ne nécessitent ni broker MQTT ni accès Internet.