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

### Configuration et topics MQTT

Les deux collectors utilisent le préfixe `basetopic` (par défaut `emon`) et le même format EmonCMS `emon/<node>/<key>`. Leurs nœuds par défaut sont `weather_opio` et `refoss_em06`. Les topics Refoss contiennent également le numéro du canal et l'unité de la mesure. Chaque payload est numérique. Configurer l'hôte et le port du broker dans `[mqtt]`; les identifiants sont fournis par variables d'environnement, jamais inscrits dans le TOML.

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

Les commandes suivantes installent le dépôt depuis GitHub dans `/opt/energy-monitor-feeds`. Remplacer `<URL_DU_DEPOT>` par l'URL Git du dépôt. Pour faire fonctionner les deux collectors, utiliser Python 3.11 ou plus récent; la météo seule accepte Python 3.9+.

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

Modifier `/etc/energy-monitor-feeds/config.toml` pour le broker et les collectors à utiliser : `weather_api` et/ou `refoss_em06`. Utiliser `sudoedit /etc/energy-monitor-feeds/config.toml`. Si le broker exige une authentification, définir les noms des variables dans `[mqtt]`, puis créer et protéger le fichier d'environnement :

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

Activer chaque collector souhaité; les deux services peuvent fonctionner en parallèle :

```bash
sudo systemctl enable --now energy-feed@weather_api
sudo systemctl enable --now energy-feed@refoss_em06
sudo journalctl -u energy-feed@weather_api -f
```

Pour consulter les logs EM06, remplacer `weather_api` par `refoss_em06` dans la commande `journalctl`. Avant son démarrage, vérifier que le compteur est accessible sur le réseau local et renseigner `device_uuid` si plusieurs EM06 sont présents. Le service redémarre après une sortie en erreur et journalise dans `journald`; il tourne sous le compte `energy-feed`.

## Mise à jour sur Raspberry Pi

La configuration et les secrets restent dans `/etc/energy-monitor-feeds`; la mise à jour du dépôt ne les remplace pas. Depuis le Raspberry Pi, récupérer la nouvelle version, réinstaller le paquet pour prendre en compte le code et les dépendances, puis actualiser l'unité systemd :

```bash
sudo git -C /opt/energy-monitor-feeds pull --ff-only
sudo /opt/energy-monitor-feeds/.venv/bin/pip install /opt/energy-monitor-feeds
sudo install -o root -g root -m 0644 \
  /opt/energy-monitor-feeds/deploy/systemd/energy-feed@.service \
  /etc/systemd/system/energy-feed@.service
sudo systemctl daemon-reload
sudo systemctl try-restart energy-feed@weather_api energy-feed@refoss_em06
```

`try-restart` redémarre uniquement les collectors déjà actifs. Retirer de la commande les unités que l'on ne souhaite pas mettre à jour/redémarrer. Vérifier ensuite leur état avec `systemctl status energy-feed@weather_api` ou `systemctl status energy-feed@refoss_em06`, et consulter les journaux avec `journalctl -u <unite> -f`. L'option `--ff-only` évite de fusionner automatiquement des modifications locales; en cas de refus, examiner les changements du dépôt avant de poursuivre.

## Ajouter un collecteur

Un collecteur doit rester limité à une source et à la conversion de ses données en mesures numériques documentées. Il doit définir des timeouts, traiter les erreurs transitoires sans arrêter définitivement le processus et laisser la connexion MQTT ainsi que les logs au module commun. Ajouter des tests unitaires pour les conversions et les payloads, sans dépendre du réseau ou du matériel réel. `local_sensors.py` est un squelette en attente du choix de matériel; `weather_api` et `refoss_em06` sont exécutables.

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