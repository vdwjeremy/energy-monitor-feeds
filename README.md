# Energy Monitor Feeds

Démons Python destinés à Linux et au Raspberry Pi 3. Ils récupèrent des mesures depuis des services web ou des capteurs locaux et les publient via MQTT pour OpenEnergyMonitor / EmonCMS. Le premier collecteur interroge Open-Meteo pour obtenir la température actuelle à Opio, France.

Voir [ARCHITECTURE.md](ARCHITECTURE.md) pour les composants prévus, le contrat MQTT et les choix de déploiement.

## Collecteurs

Chaque source est prise en charge par un collecteur indépendant. Le collecteur lit et valide les mesures, puis le module commun les publie au broker MQTT. EmonCMS reçoit ces messages comme des **Inputs**; un processus configuré dans l'interface EmonCMS les enregistre ensuite dans un ou plusieurs **Feeds**.

### Météo `weather_opio`

Open-Meteo fournit la température actuelle à Opio (`43.66862, 6.98212`, fuseau `Europe/Paris`); aucune clé API n'est nécessaire. Le collector est compatible avec Python 3.9 et plus.

Dans `[collectors.weather_api]` de `config/config.toml`, les valeurs par défaut définissent le nœud et la clé publiés :

```text
Topic:   emon/weather_opio/temperature_c
Payload: 18.5
```

Lancer le collector :

```bash
energy-feed weather_api --config config/config.toml
```

Le premier cycle part immédiatement, puis la collecte est répétée toutes les 300 secondes par défaut. Arrêter avec `Ctrl+C`.

### Refoss EM06 `refoss_em06`

Le collector utilise `refoss_ha` pour découvrir l'appareil et lire ses mesures sur le réseau local. Cette bibliothèque ne fournit pas d'accès au cloud Refoss : le compteur doit être joignable depuis la machine qui exécute le collector. Le paquet `refoss-ha` nécessite Python 3.11 ou plus récent.

Configurer `[collectors.refoss_em06]` dans `config/config.toml`. Si plusieurs EM06 sont présents, indiquer l'UUID (`device_uuid`) pour sélectionner le bon appareil. Pour chaque canal disponible, le collector publie séparément la puissance (W), la tension (V), le courant (A), le facteur de puissance et l'énergie mensuelle importée/exportée (Wh). Exemples :

```text
emon/refoss_em06/channel_1_power_w                       1.25
emon/refoss_em06/channel_1_voltage_v                     230.0
emon/refoss_em06/channel_1_current_a                     5.4
emon/refoss_em06/channel_1_power_factor                  0.97
emon/refoss_em06/channel_1_energy_monthly_wh             1234.0
emon/refoss_em06/channel_1_energy_returned_monthly_wh    0.0
```

Lancer le collector :

```bash
energy-feed refoss_em06 --config config/config.toml
```

### Températures DS18B20 `ds18b20`

Le collector lit tous les fichiers `temperature` des répertoires `28-*` sous `/sys/bus/w1/devices`. Le noyau expose la valeur en millièmes de degré Celsius; elle est convertie en °C. Chaque capteur est publié dans un topic dédié, identifié par son adresse 1-Wire :

```text
emon/ds18b20/28-000000000001_temperature_c    21.562
emon/ds18b20/28-000000000002_temperature_c    19.75
```

La section `[collectors.ds18b20]` de `config/config.toml` permet de régler le répertoire, le nœud MQTT et l'intervalle de lecture. Les valeurs par défaut sont `/sys/bus/w1/devices`, `ds18b20` et 30 secondes. Lancer le collector avec :

```bash
energy-feed ds18b20 --config config/config.toml
```

Observer tous les capteurs avec `mosquitto_sub` :

```bash
mosquitto_sub -h <hote_du_broker> -p 1883 -v -t 'emon/ds18b20/#'
```

Sur Raspberry Pi OS, activer l'interface 1-Wire avec `sudo raspi-config` (Interface Options > 1-Wire), ou ajouter `dtoverlay=w1-gpio` au fichier de configuration du démarrage (`/boot/firmware/config.txt` sur les versions récentes, parfois `/boot/config.txt`), puis redémarrer. Câbler le DS18B20 sur le GPIO configuré (GPIO 4 par défaut) avec une résistance pull-up de 4,7 kΩ entre DATA et 3,3 V. Vérifier que les capteurs apparaissent avec `ls /sys/bus/w1/devices/28-*`. Le service systemd `energy-feed@ds18b20` peut ensuite être activé comme les deux autres collectors.

### Configuration et topics MQTT

Les collectors utilisent le préfixe `basetopic` (par défaut `emon`) et le même format EmonCMS `emon/<node>/<key>`. Leurs nœuds par défaut sont `weather_opio`, `refoss_em06` et `ds18b20`. Les topics Refoss incluent le canal, ceux du DS18B20 l'adresse 1-Wire. Chaque payload est numérique. Configurer l'hôte et le port du broker dans `[mqtt]`; les identifiants sont fournis par variables d'environnement, jamais inscrits dans le TOML.

## Installation locale

Prérequis : Python 3.9 ou plus récent, `pip` et un broker MQTT accessible. Depuis la racine du dépôt :

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
cp config/config.example.toml config/config.toml
```

Modifier `config/config.toml` pour renseigner l'hôte et le port du broker ainsi que les options des collectors à utiliser. Pour un broker avec authentification, définir `username_env = "MQTT_USERNAME"` et `password_env = "MQTT_PASSWORD"` dans la section `[mqtt]`, puis exporter ces variables avant le lancement. Ne pas inscrire leurs valeurs dans le fichier TOML ni dans Git. Pour démarrer les deux collectors localement, ouvrir un terminal par collector et lancer les deux commandes de leurs sections respectives.

Les erreurs de collecte ou de publication sont journalisées; la boucle continue au cycle suivant. Arrêter avec `Ctrl+C`.

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

## Déploiement sur Raspberry Pi

Les commandes suivantes installent le dépôt depuis GitHub dans `/opt/energy-monitor-feeds`. Remplacer `<URL_DU_DEPOT>` par l'URL Git du dépôt. Pour faire fonctionner Refoss, utiliser Python 3.11 ou plus récent; la météo et le DS18B20 acceptent Python 3.9+.

```bash
sudo apt update
sudo apt install -y git python3 python3-venv
sudo adduser --system --group --no-create-home energy-feed
sudo git clone <URL_DU_DEPOT> /opt/energy-monitor-feeds
sudo python3 -m venv /opt/energy-monitor-feeds/.venv
sudo /opt/energy-monitor-feeds/.venv/bin/pip install /opt/energy-monitor-feeds
sudo install -d -o root -g energy-feed -m 0750 /etc/energy-monitor-feeds
sudo install -o root -g energy-feed -m 0640 \
  /opt/energy-monitor-feeds/config/config.example.toml \
  /etc/energy-monitor-feeds/config.toml
```

Modifier `/etc/energy-monitor-feeds/config.toml` pour le broker et les collectors à utiliser : `weather_api`, `refoss_em06` et/ou `ds18b20`. Utiliser `sudoedit /etc/energy-monitor-feeds/config.toml`. Si le broker exige une authentification, définir les noms des variables dans `[mqtt]`, puis créer et protéger le fichier d'environnement :

```bash
sudo install -o root -g energy-feed -m 0640 /dev/null \
  /etc/energy-monitor-feeds/energy-feed.env
sudoedit /etc/energy-monitor-feeds/energy-feed.env
```

Y placer les définitions `MQTT_USERNAME=...` et `MQTT_PASSWORD=...` si elles sont configurées; ne pas les ajouter à Git. Installer le service systemd fourni par le dépôt :

```bash
sudo install -o root -g root -m 0644 \
  /opt/energy-monitor-feeds/deploy/systemd/energy-feed@.service \
  /etc/systemd/system/energy-feed@.service
sudo systemctl daemon-reload
```

Activer chaque collector souhaité; leurs services peuvent fonctionner en parallèle :

```bash
sudo systemctl enable --now energy-feed@weather_api
sudo systemctl enable --now energy-feed@refoss_em06
sudo systemctl enable --now energy-feed@ds18b20
sudo journalctl -u energy-feed@weather_api -f
```

Avant leur démarrage, activer 1-Wire pour le DS18B20 et vérifier que le compteur Refoss est accessible localement; renseigner son `device_uuid` si plusieurs EM06 sont présents. Les services redémarrent après une sortie en erreur et journalisent dans `journald`; ils tournent sous le compte `energy-feed`. Pour consulter un journal, remplacer le nom dans `sudo journalctl -u energy-feed@ds18b20 -f`.

## Mise à jour sur Raspberry Pi

La configuration et les secrets restent dans `/etc/energy-monitor-feeds`; la mise à jour du dépôt ne les remplace pas. Depuis le Raspberry Pi, récupérer la nouvelle version, réinstaller le paquet pour prendre en compte le code et les dépendances, puis actualiser l'unité systemd :

```bash
sudo git -C /opt/energy-monitor-feeds pull --ff-only
sudo /opt/energy-monitor-feeds/.venv/bin/pip install /opt/energy-monitor-feeds
sudo install -o root -g root -m 0644 \
  /opt/energy-monitor-feeds/deploy/systemd/energy-feed@.service \
  /etc/systemd/system/energy-feed@.service
sudo systemctl daemon-reload
sudo systemctl try-restart energy-feed@weather_api energy-feed@refoss_em06 energy-feed@ds18b20
```

`try-restart` redémarre uniquement les collectors déjà actifs. Retirer de la commande les unités que l'on ne souhaite pas mettre à jour/redémarrer. Vérifier ensuite leur état avec `systemctl status energy-feed@ds18b20` (ou remplacer par un autre nom de collector), et consulter les journaux avec `journalctl -u <unite> -f`. L'option `--ff-only` évite de fusionner automatiquement des modifications locales; en cas de refus, examiner les changements du dépôt avant de poursuivre.

## Ajouter un collecteur

Un collecteur doit rester limité à une source et à la conversion de ses données en mesures numériques documentées. Il doit définir des timeouts, traiter les erreurs transitoires sans arrêter définitivement le processus et laisser la connexion MQTT ainsi que les logs au module commun. Ajouter des tests unitaires pour les conversions et les payloads, sans dépendre du réseau ou du matériel réel. `local_sensors.py` est un squelette en attente du choix de matériel; `weather_api`, `refoss_em06` et `ds18b20` sont exécutables.

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