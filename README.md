# Energy Monitor Feeds

Démons Python destinés à Linux et au Raspberry Pi 3. Ils récupèrent des mesures depuis des services web ou des capteurs locaux et les publient via MQTT pour OpenEnergyMonitor / EmonCMS.

> Le dépôt est actuellement vide : ce document décrit le fonctionnement prévu et fournit un test MQTT manuel. Les commandes d'installation et de lancement des démons seront à compléter lorsque le paquet Python et les unités `systemd` auront été ajoutés.

Voir [ARCHITECTURE.md](ARCHITECTURE.md) pour les composants prévus, le contrat MQTT et les choix de déploiement.

## Fonctionnement

Chaque source est prise en charge par un collecteur indépendant. Le collecteur lit et valide les mesures, puis le module commun les publie au broker MQTT. EmonCMS reçoit ces messages comme des **Inputs**; un processus configuré dans l'interface EmonCMS les enregistre ensuite dans un ou plusieurs **Feeds**.

Chaque mesure utilise le format MQTT standard d'EmonCMS `emon/<node>/<key>`. Le nœud est le nom du capteur; la clé décrit le canal et la mesure :

```text
Topic:   emon/refoss_em06/channel_{channel_idx}_power
Exemple: emon/refoss_em06/channel_1_power
Payload: 420
```

Le payload contient une valeur numérique unique. EmonCMS interprète cet exemple comme le nœud `refoss_em06` et l'entrée `channel_1_power`. Pour une autre source, choisir un nom de nœud stable correspondant au capteur ou à la ressource, puis une clé descriptive telle que `temperature_c`. Le préfixe `emon` est le `basetopic` MQTT standard d'EmonCMS.

## Tester la réception MQTT

Avant de développer un collecteur, on peut vérifier le broker et EmonCMS avec `mosquitto_pub` (installer le paquet `mosquitto-clients` sur Debian/Raspberry Pi OS si nécessaire) :

```bash
mosquitto_pub -h 127.0.0.1 -p 1883 \
  -t 'emon/refoss_em06/channel_1_power' \
  -m '420' \
  -q 0
```

Remplacer l'hôte et le port par ceux du broker MQTT utilisé par EmonCMS. Cette commande suppose un broker local sans authentification; ne pas mettre de vrais secrets directement dans la ligne de commande. Vérifier ensuite que l'entrée `refoss_em06 / channel_1_power` apparaît dans **Inputs**. Ajouter ou vérifier son processus d'enregistrement vers un feed, puis contrôler la valeur dans **Feeds**.

Si rien n'arrive, vérifier l'accessibilité réseau du broker, ses identifiants et le motif d'abonnement configuré dans EmonCMS. La connexion au broker seule ne crée pas automatiquement un feed.

## Utilisation prévue des démons

Une fois l'implémentation ajoutée, le parcours opérationnel sera :

1. Installer le paquet et ses dépendances dans un environnement virtuel Python sur le Raspberry Pi.
2. Copier `config/config.example.toml` vers un fichier local non committé et renseigner le broker, les topics des sources et les paramètres du collecteur.
3. Fournir les identifiants MQTT et les clés d'API via un fichier d'environnement protégé, lisible uniquement par le compte de service.
4. Lancer un collecteur en premier plan pour vérifier ses logs et les messages reçus dans EmonCMS.
5. Installer et activer son unité `systemd` afin qu'il démarre au boot et redémarre après une erreur.

Les noms de commande, options de configuration et unités `systemd` seront documentés ici lorsqu'ils seront implémentés; ils ne sont pas encore disponibles dans ce dépôt.

## Ajouter un collecteur

Un collecteur doit rester limité à une source et à la conversion de ses données en mesures numériques documentées. Il doit définir des timeouts, traiter les erreurs transitoires sans arrêter définitivement le processus et laisser la connexion MQTT ainsi que les logs au module commun. Ajouter des tests unitaires pour les conversions et les payloads, sans dépendre du matériel réel.

## Sécurité

- Ne jamais committer les mots de passe MQTT, tokens ou clés d'API.
- Utiliser un compte système dédié et des permissions minimales.
- Préférer TLS lorsque le broker est accessible hors du réseau local de confiance.
- Ne pas journaliser les valeurs de secrets ni les en-têtes d'authentification.