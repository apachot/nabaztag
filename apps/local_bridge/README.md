# Nabaztag Local Bridge

Agent local minimal pour relayer des actions du portail Nabaztag vers des services du reseau domestique sans exposer ce reseau sur Internet.

## Principe

- le bridge s'appaire une fois avec un code temporaire genere dans `Mon compte`
- il garde un jeton local
- il poll ensuite le portail via une connexion sortante
- il execute localement les commandes recues

## Demarrage rapide

Appairage:

```bash
python3 apps/local_bridge/bridge_agent.py pair \
  --portal https://nabaztag.org \
  --pairing-token TON_CODE \
  --name maison
```

Boucle d'execution:

```bash
python3 apps/local_bridge/bridge_agent.py run
```

## Capacites MVP

- `webhook.trigger`
- `mqtt.publish` si `paho-mqtt` est installe localement
