# Connecteurs externes

## Role

La couche `connectors` sert a brancher des systemes externes sans recabler toute l'application.

Elle isole:

- la configuration par compte
- le contrat des actions exposees au LLM
- le contexte disponible pour aider le LLM
- l'execution concrete des actions
- les formulaires de test visibles dans le portail

## Contrat d'un connecteur

Un connecteur declare:

- `key`
  Identifiant stable du connecteur
- `label`
  Nom affiche dans l'interface
- `description`
  Role du connecteur
- `account_fields`
  Champs de configuration stockes pour le compte utilisateur
- `operations`
  Operations autorisees via `connector.invoke`
- `test_form`
  Formulaire de test rendu sur la fiche d'un lapin

Chaque operation declare:

- `key`
  Nom de l'operation
- `description`
  Intention de haut niveau
- `params_schema`
  Parametres attendus

## Action LLM normalisee

Le LLM ne manipule pas directement Home Assistant, un webhook ou un futur bridge.

Il produit une action unique:

```json
{
  "name": "connector.invoke",
  "connector": "home_assistant",
  "operation": "call_service",
  "params": {
    "domain": "light",
    "service": "turn_on",
    "entity_id": "light.salon"
  }
}
```

ou par exemple:

```json
{
  "name": "connector.invoke",
  "connector": "webhook",
  "operation": "trigger",
  "params": {
    "event": "play_music",
    "payload": {
      "artist": "Leonard Cohen"
    }
  }
}
```

Le backend:

- valide l'action
- verifie que le connecteur est configure
- execute l'operation

## Connecteurs actuels

### Home Assistant

- type: connecteur domotique
- operation: `call_service`
- usage: lumiere, media player, scenes, scripts, switch

### Webhook

- type: connecteur HTTP generique
- operation: `trigger`
- usage: bridge local, automatisation maison, scripts auto-heberges

Le connecteur `webhook` permet de prouver que l'architecture n'est pas uniquement un habillage de Home Assistant. Il offre une sortie HTTP simple pour connecter le portail Nabaztag a un service externe ou a un futur bridge local open source.
