# Contribuer a Nabaztag

Merci de vouloir contribuer au projet.

Ce depot a une particularite: il melange du backend web classique, du pilotage d'objet connecte, de la compatibilite avec un ecosysteme historique Nabaztag, et une couche IA moderne pour rendre les lapins plus expressifs. Le meilleur moyen d'etre utile est donc de commencer simple, avec un petit perimetre bien compris, puis d'elargir.

## Esprit du projet

Quelques principes guident les contributions:

- privilegier le reemploi logiciel des Nabaztag existants
- ne pas supposer qu'un refit materiel est necessaire
- garder une interface tangible, sensible et expressive
- preferer des ameliorations concretes et testables
- documenter les limites reelles plutot que masquer les zones floues

Le but n'est pas de transformer le Nabaztag en gadget demonstration IA. Le but est d'en faire un compagnon domestique attachant, fiable et vivant.

## Avant de commencer

Le projet est un monorepo organise principalement autour de:

- `apps/portal`
  Portail Flask pour les comptes, la configuration, les fiches lapins, les interactions et les fonctions IA.

- `apps/api`
  API FastAPI exposee aux autres composants et couche de pilotage des devices.

- `apps/web`
  Interface legacy Next.js conservee comme reference.

Si vous ne savez pas par ou entrer, commencez par lire:

- [README.md](/Users/apachot/Documents/GitHub/nabaztag/README.md)
- [docs/protocol-notes.md](/Users/apachot/Documents/GitHub/nabaztag/docs/protocol-notes.md)

## Setup local

### Prerequis

- Python `3.10+`
- `npm` si vous voulez aussi lancer l'interface web legacy

### Portail Flask

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ./apps/portal
export NABAZTAG_API_BASE_URL=http://localhost:8000
flask --app portal_app:create_app run --debug --port 5000
```

### API FastAPI

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ./apps/api
uvicorn app.main:app --reload --app-dir apps/api
```

### Driver recommande pour commencer

Pour contribuer sans lapin physique, commencez avec le driver `simulated`.

Copiez `apps/api/.env.example` vers `apps/api/.env`, puis definissez:

```bash
NABAZTAG_GATEWAY_DRIVER=simulated
```

Cela permet de travailler sur le portail, les routes, les modeles, les ecrans et une bonne partie de l'orchestration sans dependre d'un device reel.

## Zones de contribution utiles

### 1. Portail Flask

Fichiers utiles:

- [apps/portal/portal_app/main.py](/Users/apachot/Documents/GitHub/nabaztag/apps/portal/portal_app/main.py)
- [apps/portal/portal_app/models.py](/Users/apachot/Documents/GitHub/nabaztag/apps/portal/portal_app/models.py)
- [apps/portal/portal_app/templates/](/Users/apachot/Documents/GitHub/nabaztag/apps/portal/portal_app/templates)

Typiquement:

- ecrans et parcours utilisateur
- configuration des lapins
- orchestration LLM / TTS
- memoire conversationnelle
- interventions aleatoires
- experience utilisateur sur la fiche d'un lapin

### 2. API et gateway

Fichiers utiles:

- [apps/api/app/main.py](/Users/apachot/Documents/GitHub/nabaztag/apps/api/app/main.py)
- [apps/api/app/gateway.py](/Users/apachot/Documents/GitHub/nabaztag/apps/api/app/gateway.py)
- [apps/api/app/protocol/](/Users/apachot/Documents/GitHub/nabaztag/apps/api/app/protocol)

Typiquement:

- primitives de pilotage
- etat des devices
- evenements
- adaptation entre API moderne et protocole Nabaztag

### 3. Protocole Nabaztag

Fichier cle:

- [docs/protocol-notes.md](/Users/apachot/Documents/GitHub/nabaztag/docs/protocol-notes.md)

Si vous aimez les sujets bas niveau, il y a encore beaucoup a faire sur:

- les commandes supportees
- la robustesse reseau
- la comprehension des limites du protocole
- les capacites audio

### 4. IA et expressivite

Le projet n'utilise pas l'IA uniquement pour produire du texte. Les contributions utiles concernent aussi:

- les prompts systeme
- la generation JSON structuree
- la coherence entre voix, oreilles et LEDs
- la personnalite des lapins
- la qualite des interactions et du langage corporel

## Comment contribuer proprement

Quelques regles simples:

- faites des changements cibles, pas des refontes diffuses
- gardez les commits lisibles et intentionnels
- privilegiez des noms de fonctions et de variables explicites
- ajoutez une petite explication si une logique n'est pas evidente
- ne melangez pas dans un meme commit un changement fonctionnel et un nettoyage sans rapport

Quand vous modifiez un comportement:

- decrivez ce qui change
- expliquez la raison
- indiquez comment le verifier

## Tests et verification

Le projet comporte encore une part importante de validation manuelle, notamment des qu'un vrai lapin entre dans la boucle.

Quand c'est possible, verifiez au minimum:

- que le portail demarre
- que l'API demarre
- que le parcours concerne fonctionne avec le driver `simulated`
- que le rendu ne casse pas la fiche lapin

Si votre changement touche a un comportement device reel, dites clairement:

- ce qui a ete teste avec un vrai lapin
- ce qui n'a pas pu l'etre

## Types de contributions particulierement utiles

Les sujets suivants ont une forte valeur:

- ameliorer la robustesse audio
- etendre les primitives supportees par le protocole
- rendre les comportements expressifs plus coherents
- ameliorer la lisibilite et la maintenabilite du portail
- enrichir la documentation
- proposer des scenarios d'usage domestiques credibles

## Proposer une contribution

Vous pouvez contribuer de plusieurs manieres:

- ouvrir une issue
- proposer une idee d'usage
- signaler une limite de protocole
- ouvrir directement une pull request

Si vous ouvrez une PR, essayez d'inclure:

- le probleme traite
- la solution retenue
- les fichiers principaux modifies
- la methode de verification

## Si vous avez un vrai Nabaztag

C'est precieux.

Les retours les plus utiles sont souvent ceux qui viennent du terrain:

- comportement reel des oreilles et des LEDs
- qualite audio
- stabilite apres plusieurs heures
- ecarts entre simulation et device reel
- limites non documentees du protocole

Le projet gagne enormement en qualite quand les hypotheses logicielles sont confrontees a un vrai lapin.
