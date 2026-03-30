# Nabaztag

## Redonner une vie sensible a un objet culte

Le Nabaztag est un objet a part dans l'histoire du numerique. Ce lapin connecte, apparu au milieu des annees 2000, n'etait pas seulement un gadget: c'etait une tentative tres en avance de rendre l'informatique domestique plus sensible, plus douce, plus incarnee. Il ne se contentait pas d'afficher une information. Il bougeait les oreilles, changeait de couleur, faisait entendre une voix, occupait physiquement l'espace et installait une relation.

Ce projet part d'une conviction simple: le Nabaztag n'est pas un vestige nostalgique, c'est un excellent support pour explorer une nouvelle generation d'interfaces tangibles, expressives et sobres.

L'objectif n'est pas de transformer le lapin en simple enceinte connectee ou en chatbot de plus. L'objectif est de lui redonner une presence. Une personnalite. Une capacite d'interaction qui ne passe pas uniquement par les ecrans, mais par la voix, les lumieres, les oreilles, le rythme, l'humour, l'attention et la surprise.

## Une intelligence emotionnelle pour le lapin

Le coeur de ce depot est la reconstruction d'une plateforme Nabaztag moderne capable de doter chaque lapin d'une forme d'intelligence emotionnelle.

Concretement, cela signifie que le lapin ne repond pas seulement avec du texte. Il peut:

- parler avec une voix de synthese moderne
- adopter une personnalite propre a chaque lapin
- bouger ses oreilles pour signifier une intention, une hesitation, une joie ou une curiosite
- utiliser ses LEDs comme langage corporel
- improviser de petites interventions expressives
- tenir une conversation courte avec memoire recente

Le LLM n'est donc pas utilise comme un moteur purement verbal. Il est sollicite pour produire une performance structuree: un texte a dire, un mouvement d'oreille gauche, un mouvement d'oreille droite, un etat des LEDs. Le lapin devient une interface expressive complete.

Nous cherchons a retrouver ce qui faisait la singularite du Nabaztag a l'epoque, tout en l'amenant beaucoup plus loin:

- une presence domestique legere
- une relation affective plutot qu'utilitaire
- un objet qui divertit, surprend, reagit et accompagne
- une technologie qui prend une forme sensible

## Un projet Green IT par nature

Ce projet a aussi une dimension Green IT tres forte.

Plutot que de produire un nouvel objet materiel, l'idee est de reemployer un parc existant de Nabaztag. Ces lapins, encore desireux de parler, d'ecouter et de bouger, peuvent retrouver une utilite contemporaine grace a une pile logicielle moderne.

Le principe est important: cette renaissance passe d'abord par le logiciel. Le projet ne repose pas sur un refit materiel, une refonte electronique ou l'ajout de nouveaux modules. L'ambition est de redonner des capacites a des Nabaztag existants, dans leur forme d'origine, sans transformation hardware necessaire.

Cette approche a plusieurs vertus:

- prolonger la duree de vie d'objets electroniques deja fabriques
- reduire le besoin de rachat de nouveaux assistants domestiques
- redonner de la valeur a un materiel patrimonial et affectif
- montrer qu'une innovation IA n'a pas besoin de s'appuyer sur du hardware neuf

Le projet s'inscrit donc dans une logique de reconditionnement logiciel. Il ne s'agit pas seulement de "faire marcher de vieux lapins". Il s'agit de demontrer qu'un objet ancien peut redevenir pertinent, desirable et creatif si on lui fournit une couche logicielle adaptee.

Le Green IT, ici, n'est pas un slogan. C'est une strategie de conception:

- reutiliser plutot que remplacer
- enrichir l'existant plutot qu'ajouter des objets
- tirer parti d'interfaces physiques deja la
- faire de l'IA un outil de reanimation d'objets plutot qu'un pretexte a la surconsommation

## Vision du projet

Le depot reconstruit une chaine complete de controle et d'orchestration pour Nabaztag:

- un portail web pour gerer ses lapins
- une API de pilotage des devices
- des endpoints compatibles avec l'ecosysteme Violet/OpenJabNab
- une couche conversationnelle appuyee sur les modeles Mistral
- une synthese vocale moderne via Voxtral TTS

Chaque lapin peut disposer:

- de son propre prompt de personnalite
- de son propre modele LLM
- de sa propre voix TTS
- de son propre comportement expressif
- de sa propre fenetre de conversation recente
- de ses propres interventions aleatoires

Le but est d'arriver a des lapins qui ne sont pas des copies les uns des autres, mais de vrais personnages.

## Ce que le systeme sait deja faire

La plateforme couvre aujourd'hui les usages suivants:

- inscription et connexion sur le portail
- inventaire de lapins et fiche detaillee par lapin
- association d'un device physique a un lapin
- affichage de l'etat distant
- controle des oreilles
- controle des LEDs
- lecture audio
- prompt de personnalite editable pour chaque lapin
- selection du modele Mistral par lapin
- selection de la voix Voxtral par lapin
- generation de performances expressives structurees
- conversations courtes avec memoire recente
- purge agressive du contexte conversationnel pour stabiliser le systeme
- interventions aleatoires selon une frequence et une plage horaire
- endpoint d'upload d'enregistrement compatible avec les usages Nabaztag historiques

## Architecture

Le monorepo est organise autour de trois applications principales:

- `apps/portal`
  Portail Flask pour les comptes, l'inventaire des lapins, la fiche detaillee, la configuration IA, le suivi des conversations et le pilotage des actions.

- `apps/api`
  API FastAPI qui expose l'etat des lapins, les commandes, les evenements et la couche de communication avec les devices.

- `apps/web`
  Ancienne interface Next.js conservee comme reference exploratoire.

## Pile IA

Le projet utilise aujourd'hui principalement Mistral:

- modeles de chat Mistral pour la generation des reponses et des performances
- Voxtral TTS pour la synthese vocale
- generation structuree en JSON pour coordonner la parole, les oreilles et les LEDs

L'idee n'est pas de demander au modele "dis quelque chose". L'idee est de demander:

- quoi dire
- comment le dire
- quelle attitude corporelle adopter
- quels signaux lumineux utiliser

Cette structuration est essentielle pour que le lapin existe comme personnage physique, et pas seulement comme canal audio.

## Lancer le projet en local

### Portail Flask

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ./apps/portal
export NABAZTAG_API_BASE_URL=http://localhost:8000
flask --app portal_app:create_app run --debug --port 5000
```

Le portail est alors disponible sur `http://localhost:5000`.

### API FastAPI

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ./apps/api
uvicorn app.main:app --reload --app-dir apps/api
```

### Interface legacy

```bash
npm install
npm run dev:web
```

## Drivers de gateway

L'API peut fonctionner avec deux drivers:

- `simulated`
- `protocol`

Copier `apps/api/.env.example` vers `apps/api/.env`, puis definir par exemple:

```bash
NABAZTAG_GATEWAY_DRIVER=simulated
```

Quand `protocol` est active, l'API s'appuie sur l'adaptateur de protocole Nabaztag pour les operations supportees.

La couche protocolaire est principalement repartie dans:

- `apps/api/app/protocol/client.py`
- `apps/api/app/protocol/commands.py`
- `apps/api/app/protocol/events.py`

Les observations et limites du protocole sont documentees dans `docs/protocol-notes.md`.

## Smoke test protocole

1. Copier `apps/api/.env.example` vers `apps/api/.env`
2. Definir:

```bash
NABAZTAG_GATEWAY_DRIVER=protocol
NABAZTAG_GATEWAY_HOST=<ip-ou-host-de-nabd>
NABAZTAG_GATEWAY_PORT=10543
```

`NABAZTAG_GATEWAY_HOST` et `NABAZTAG_GATEWAY_PORT` servent de cible par defaut. Le portail peut ensuite enregistrer une cible dediee par lapin.

3. Demarrer l'API:

```bash
uvicorn app.main:app --reload --app-dir apps/api
```

4. Lancer le test HTTP:

```bash
bash scripts/smoke-test-protocol.sh
```

Le smoke test couvre actuellement:

- creation d'un lapin
- connexion
- synchronisation
- oreilles
- audio
- un premier controle de LED

## Production

Les points d'entree publics en production sont:

- `https://nabaztag.org/` pour le portail Flask
- `https://nabaztag.org/api/` pour l'API FastAPI
- `https://nabaztag.org/vl` pour la racine HTTP compatible Violet
- `https://nabaztag.org/vl/locate.jsp` pour la reponse initiale de localisation
- `5222/TCP` sur `nabaztag.org` pour l'ecoute XMPP

Les anciennes routes sous `https://dev.emotia.com/nabaztag/` redirigent vers `https://nabaztag.org/`.

## Services systemd

Les unites systemd de production versionnees dans le depot sont:

- `deploy/systemd/nabaztag-portal.service`
- `deploy/systemd/nabaztag-xmpp.service`

Pour les installer sur un serveur Debian:

```bash
sudo cp deploy/systemd/nabaztag-portal.service /etc/systemd/system/
sudo cp deploy/systemd/nabaztag-xmpp.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now nabaztag-portal.service
sudo systemctl enable --now nabaztag-xmpp.service
```

## Pourquoi ce depot compte

Ce projet ne consiste pas simplement a remettre en ligne un vieux service pour lapins connectes.

Il affirme aussi une idee tres concrete: on peut rendre un objet ancien de nouveau contemporain sans lui imposer de refit materiel. Ici, l'innovation vient d'une surcouche logicielle, de l'orchestration, de l'IA et de la qualite de l'interaction, pas du remplacement de l'objet lui-meme.

Il cherche a montrer qu'il est possible de:

- reparer une relation entre humain et objet numerique
- redonner de la valeur a un hardware ancien
- concevoir des experiences IA moins intrusives, plus poetiques et plus tangibles
- faire du reemploi un moteur d'innovation

Le Nabaztag a toujours ete un objet en avance sur son temps. Ce depot veut lui donner un second souffle, sans trahir ce qui faisait sa singularite: une interface physique, expressive, malicieuse et attachante.
