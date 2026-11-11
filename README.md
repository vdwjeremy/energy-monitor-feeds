# Energy Monitor Feeds

Démons Python destinés à Linux et au Raspberry Pi 3. Ils récupèrent des mesures depuis des services web ou des capteurs locaux et les envoient à OpenEnergyMonitor / EmonCMS via MQTT ou son API HTTP. Le premier collecteur interroge Open-Meteo pour obtenir la température actuelle à Opio, France.

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

### Consommation Linky horaire `enedis_conso`

Le collector appelle la route `courbe_de_charge_consommation` de [Conso API](https://conso.boris.sh/documentation), puis insère chaque point directement dans un feed EmonCMS via `feed/insert.json`. Les données Enedis arrivent une fois par jour et peuvent avoir un à deux jours de retard; une collecte quotidienne est donc recommandée. Par défaut, il récupère les trois derniers jours pour inclure les données livrées en retard. Configurez `lookback_days` entre 1 et 30 si nécessaire.

Activez **« Enregistrement de la consommation horaire »** et **« Collecte de ma consommation horaire »** dans votre espace Enedis, puis obtenez un token personnel via Conso API. Dans `config/config.toml`, décommentez et renseignez `[collectors.enedis_conso]` dans `config/config.example.toml`, en particulier l'URL de votre instance EmonCMS et l'ID du feed existant. Placez les deux clés d'écriture dans `/etc/energy-monitor-feeds/energy-feed.env`, sans les inscrire dans le TOML :

```text
CONSO_API_TOKEN=votre_token_personnel
EMONCMS_WRITE_API_KEY=votre_cle_api_ecriture
```

Le point de livraison (`point_id`) comporte 14 chiffres. `feed_id` est l'identifiant du feed temporel EmonCMS à alimenter. La clé `emoncms_api_key_env` indique le nom de la variable d'environnement contenant une API key **Read & Write**. Le collector normalise les valeurs en Wh et envoie chaque point avec son horodatage source (converti en secondes Unix) à `feed/insert.json` :

```text
GET https://emoncms.example/feed/insert.json
id=123&time=1794092400&value=120.0
```

Lancer manuellement le collector avec :

```bash
CONSO_API_TOKEN=votre_token_personnel EMONCMS_WRITE_API_KEY=votre_cle_api_ecriture energy-feed enedis_conso --config config/config.toml
```

Pour un essai local, fournir les deux clés dans l'environnement du processus. En production, l'unité systemd charge le fichier `energy-feed.env` protégé automatiquement. Le collector Enedis écrit directement dans EmonCMS et n'utilise pas le broker MQTT. Activer ensuite le service avec `sudo sh /opt/energy-monitor-feeds/deploy/install.sh enedis_conso`.

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

### Débitmètre YF-B10 `yf_b10`

Le collector compte les fronts actifs du signal du YF-B10 pendant une fenêtre d'échantillonnage. Il calcule la fréquence $F$ en Hz puis le débit $Q$ en L/min avec $Q=(F+4)/8$, d'après la caractéristique $F=(8\times Q-4)\pm5\%$. La fenêtre est configurable et vaut 10 secondes par défaut. Deux topics distincts sont publiés :

```text
emon/yf_b10/frequency_hz    4.4
emon/yf_b10/flow_l_min      1.05
```

Configurer `[collectors.yf_b10]` dans `config/config.toml`. `gpio_pin` est le numéro BCM du GPIO (16 par défaut, broche physique 36); le nœud MQTT vaut `yf_b10` par défaut. Lancer le collector avec :

```bash
energy-feed yf_b10 --config config/config.toml
```

Installer `gpiozero` avec le paquet du projet. Pour que le service systemd puisse accéder au GPIO, ajouter son compte au groupe `gpio`, puis redémarrer le service :

```bash
sudo usermod -aG gpio energy-feed
sudo systemctl restart energy-feed@yf_b10
```

Respecter le brochage et la tension d'alimentation du modèle exact du débitmètre. Ne jamais appliquer 5 V au GPIO Raspberry Pi : son entrée n'est pas tolérante au 5 V. Le signal doit être limité à 3,3 V; utiliser une adaptation de niveau si la sortie n'est pas une sortie collecteur ouvert tirée vers 3,3 V. Relier les masses du capteur et du Raspberry Pi.

### Configuration et topics MQTT

Les collectors qui publient en MQTT utilisent le préfixe `basetopic` (par défaut `emon`) et des payloads numériques. Enedis écrit directement les points horodatés dans le feed EmonCMS configuré via l'API HTTP. Les identifiants MQTT, le token Conso API et la clé API EmonCMS sont fournis par variables d'environnement, jamais inscrits dans le TOML.

## Installation locale

Prérequis : Python 3.9 ou plus récent et `pip`. Un broker MQTT accessible est nécessaire aux collectors MQTT; Enedis nécessite l'accès HTTP à EmonCMS. Refoss demande Python 3.11 ou plus récent. Depuis la racine du dépôt :

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
cp config/config.example.toml config/config.toml
```

Renseigner le broker et les options souhaitées dans `config/config.toml`. Pour un broker authentifié, définir les noms `username_env` et `password_env` dans `[mqtt]`, puis exporter les variables correspondantes avant le lancement. Garder leurs valeurs hors du TOML et de Git.

Chaque collector tourne dans son propre processus. Exemple :

```bash
energy-feed weather_api --config config/config.toml
```

Remplacer `weather_api` par `refoss_em06`, `ds18b20`, `yf_b10` ou `enedis_conso` pour lancer un autre collector, dans un autre terminal si nécessaire. Pour Enedis, exporter les variables définies par `token_env` et `emoncms_api_key_env`; renseigner aussi `emoncms_url` et `feed_id`. Pour les tests, installer plutôt `python -m pip install -e '.[dev]'`. Les erreurs de collecte ou d'écriture sont journalisées; la boucle continue au cycle suivant. Arrêter avec `Ctrl+C`.

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

Prérequis : Raspberry Pi OS, Python 3.9 ou plus récent (3.11+ pour Refoss), accès au broker pour les collectors MQTT ou à EmonCMS pour Enedis, et un dépôt cloné dans `/opt/energy-monitor-feeds`. Installer les outils nécessaires et cloner le dépôt :

```bash
sudo apt update
sudo apt install -y git python3 python3-venv
sudo git clone <URL_DU_DEPOT> /opt/energy-monitor-feeds
```

L'installateur crée le compte de service, l'environnement virtuel, la configuration initiale et l'unité systemd. Sans argument, il ne démarre aucun collector :

```bash
sudo sh /opt/energy-monitor-feeds/deploy/install.sh
```

Modifier `/etc/energy-monitor-feeds/config.toml` avec `sudoedit` pour renseigner le broker et les sections des collectors. Si le broker utilise des identifiants, définir leurs noms de variables dans `[mqtt]`, puis ajouter leurs valeurs à `/etc/energy-monitor-feeds/energy-feed.env` avec `sudoedit`. Ce fichier est protégé et n'est jamais remplacé lors d'une réinstallation.

Après avoir configuré et vérifié le matériel, relancer l'installateur avec les seuls collectors à activer. Exemple :

```bash
sudo sh /opt/energy-monitor-feeds/deploy/install.sh weather_api ds18b20 refoss_em06 yf_b10 enedis_conso
sudo journalctl -u energy-feed@weather_api -f
```

Les noms acceptés sont `weather_api`, `refoss_em06`, `ds18b20`, `yf_b10` et `enedis_conso`; seuls les services nommés sont activés et démarrés. Avant cela, activer 1-Wire pour le DS18B20, vérifier l'accès réseau au Refoss, ajouter `energy-feed` au groupe `gpio` pour le YF-B10, ou configurer le PRM, le feed et les deux clés d'environnement pour Enedis. Les services tournent sous le compte `energy-feed`, redémarrent après une erreur et journalisent dans `journald`.

## Mise à jour sur Raspberry Pi

La configuration et les secrets restent dans `/etc/energy-monitor-feeds`; la mise à jour du dépôt ne les remplace pas. Depuis le Raspberry Pi, récupérer la nouvelle version, réinstaller le paquet pour prendre en compte le code et les dépendances, puis actualiser l'unité systemd :

```bash
sudo git -C /opt/energy-monitor-feeds pull --ff-only
sudo sh /opt/energy-monitor-feeds/deploy/install.sh weather_api ds18b20 refoss_em06 yf_b10 enedis_conso
sudo systemctl try-restart energy-feed@weather_api energy-feed@refoss_em06 energy-feed@ds18b20 energy-feed@yf_b10 energy-feed@enedis_conso
```

`try-restart` redémarre uniquement les collectors déjà actifs. Retirer de la commande les unités que l'on ne souhaite pas mettre à jour/redémarrer. Vérifier ensuite leur état avec `systemctl status energy-feed@yf_b10` (ou remplacer par un autre nom de collector), et consulter les journaux avec `journalctl -u <unite> -f`. L'option `--ff-only` évite de fusionner automatiquement des modifications locales; en cas de refus, examiner les changements du dépôt avant de poursuivre.

## Ajouter un collecteur

Un collecteur doit rester limité à une source et à la conversion de ses données en mesures numériques documentées. Il doit définir des timeouts, traiter les erreurs transitoires sans arrêter définitivement le processus et laisser la connexion MQTT ainsi que les logs au module commun. Ajouter des tests unitaires pour les conversions et les payloads, sans dépendre du réseau ou du matériel réel. `local_sensors.py` est un squelette en attente du choix de matériel; `weather_api`, `refoss_em06`, `ds18b20`, `yf_b10` et `enedis_conso` sont exécutables.

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