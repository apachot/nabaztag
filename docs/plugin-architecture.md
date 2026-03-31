# Architecture plugin pour le portail Nabaztag

L'objectif est de faire évoluer le projet vers une plate-forme extensible :

- le noyau gère le lapin, les commandes device, la conversation et l'expressivité
- les fonctionnalités externes deviennent des plugins activables
- l'on évite d'accumuler toutes les intégrations dans `main.py`

## 1. Principe

Le noyau du projet doit rester responsable de :

- l'identité du lapin
- le lien avec le device physique
- la synthèse vocale
- les oreilles, LEDs et audio
- les événements internes
- les tâches planifiées
- la persistance centrale

Les plugins apportent ensuite :

- une capacité métier
- une configuration
- des actions
- éventuellement des panneaux d'interface
- éventuellement des réactions à des événements

## 2. Premier socle implémenté

Le projet dispose désormais :

- d'un registre de plugins Python
- d'un état d'activation par lapin
- d'une interface d'activation / désactivation sur la fiche d'un lapin

Références :

- [plugins.py](/Users/apachot/Documents/GitHub/nabaztag/apps/portal/portal_app/plugins.py)
- [models.py](/Users/apachot/Documents/GitHub/nabaztag/apps/portal/portal_app/models.py)

## 3. Modèle de données

Le registre décrit les plugins disponibles dans le code :

- `plugin_id`
- `label`
- `description`
- `category`
- `default_enabled`
- `experimental`

La base stocke ensuite, par lapin :

- `plugin_id`
- `enabled`
- `settings`

Cela permet :

- des plugins installés globalement
- activés ou non par lapin
- avec possibilité future de configuration spécifique

## 4. Premier plugin pilote

Le premier plugin réel est :

- `use_cases`

Il encapsule le `Laboratoire d'usages` :

- scènes expressives
- improvisation
- radio / stream
- scénario Ztamp

Ce choix est volontaire :

- c'est déjà une capacité cohérente
- elle n'est pas fondamentale au noyau
- elle sert de plugin pilote avant Spotify ou d'autres connecteurs

## 5. Plugins candidats

Plugins naturels pour la suite :

- `spotify`
- `calendar`
- `mail`
- `weather`
- `radio`
- `ovos_bridge`
- `home_assistant_bridge`

## 6. Étapes suivantes

### Étape 1

Sortir progressivement les écrans et actions du `Laboratoire d'usages` dans un module plugin dédié, plutôt qu'un simple registre déclaratif.

### Étape 2

Définir une interface plugin plus riche, par exemple :

- `is_available(user, rabbit)`
- `get_panels(rabbit)`
- `handle_action(...)`
- `handle_event(...)`

### Étape 3

Introduire une configuration plugin :

- globale utilisateur
- spécifique au lapin

### Étape 4

Brancher les événements internes du lapin sur les plugins :

- `rabbit.recording.uploaded`
- `rabbit.rfid.detected`
- `rabbit.button`
- `rabbit.auto_performance.generated`

## 7. Intérêt stratégique

Cette architecture permet :

- d'ajouter Spotify sans polluer le noyau
- de tester des intégrations plus facilement
- d'activer/désactiver les capacités selon le lapin
- d'avoir des lapins spécialisés

Exemples :

- un lapin `musique` avec `spotify`
- un lapin `famille` avec `calendar`
- un lapin `objets tangibles` avec `ztamp`

## 8. Conclusion

La direction est maintenant claire :

- le noyau du projet doit rester petit et stable
- les intégrations externes doivent devenir des plugins
- `use_cases` est le premier pas concret vers cette architecture
