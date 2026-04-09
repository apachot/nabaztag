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
- executer des actions explicites demandees en langage naturel

Le LLM n'est donc pas utilise comme un moteur purement verbal. Il est sollicite pour produire une performance structuree et, desormais, pour choisir dans un catalogue d'actions compatibles avec le lapin. Il peut donc non seulement parler, mais aussi declencher des mouvements d'oreilles, des effets lumineux, une mise en veille, un reveil ou une radio connue quand la demande de l'utilisateur s'y prete. Le lapin devient une interface expressive complete.

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
- une application compagnon macOS pour appairer et piloter un lapin
- une API de pilotage des devices
- des endpoints compatibles avec l'ecosysteme Violet/OpenJabNab
- un serveur XMPP minimal pour recevoir les vraies connexions des Nabaztag
- une couche conversationnelle appuyee sur les modeles Mistral
- une synthese vocale moderne via Voxtral TTS
- une bibliotheque embarquee de performances et de choregraphies pre-calculees

Chaque lapin peut disposer:

- de son propre prompt de personnalite
- de son propre modele LLM
- de sa propre voix TTS
- de son propre comportement expressif
- de sa propre fenetre de conversation recente
- de ses propres interventions aleatoires
- de ses propres actions declenchees a la demande via un catalogue normalise

Le but est d'arriver a des lapins qui ne sont pas des copies les uns des autres, mais de vrais personnages.

## Etat actuel

Le projet dispose maintenant d'une chaine utilisable de bout en bout sur du materiel Nabaztag/Nabaztag:tag non modifie:

- le portail `nabaztag.org` gere les comptes, les lapins, le rattachement d'un serial physique et la fiche de pilotage
- le serveur XMPP accepte les connexions device, observe les boutons/oreilles et distribue une file de commandes
- l'application macOS guide la configuration Wi-Fi du lapin, recupere son serial depuis la page de setup, le cree sur le portail et le rattache au compte
- le lapin peut lire des MP3 locaux servis par le portail, des streams radio simples et des reponses TTS
- les oreilles, la LED du nez, la LED du dessous et les 3 LEDs du ventre sont pilotables
- les messages utilisateur generent une reponse vocale et peuvent declencher des actions structurees: oreilles, LEDs, radio, connecteurs, sommeil/reveil
- les interventions aleatoires peuvent etre programmees par lapin avec plage horaire et frequence minimale
- des interventions de naissance et des interventions aleatoires sont pre-calculees pour reduire les couts d'appel LLM/TTS
- 10 choregraphies musicales de 10 secondes sont embarquees: extrait musical CC0, mouvements d'oreilles et animation lumineuse, declenchables au hasard depuis le web ou l'app macOS
- la petite musique systeme Nabaztag de fin d'audio est supprimee pour ces choregraphies, afin que seul le morceau choisi soit entendu
- un DMG macOS local est produit par `apps/macos_client/build_dmg.sh`; le depot contient aussi la mise en scene du DMG avec un raccourci `Applications`

Les choregraphies musicales utilisent des extraits de boucles CC0 publiees sur OpenGameArt par `drakzlin`. Les fichiers generes et leurs credits sont dans `apps/portal/portal_app/static/bundled-choreographies/`.

## Cas d'usage cibles

Le projet ne vise pas seulement a faire "parler" le lapin. L'ambition est de lui donner un vrai role dans la maison, avec plusieurs familles d'usages coherentes.

### 1. Nabaztag comme telecommande incarnee

Le lapin peut servir d'interface vocale et expressive vers d'autres systemes:

- domotique locale: lampes, prises, volets, chauffage
- TV, hifi, ampli, scenes multimedia
- routines domestiques: `bonne nuit`, `on mange`, `mode film`, `reveil`
- services numeriques: agenda, mails, musique, rappels

Dans ce mode, le Nabaztag n'est pas l'appareil final qui fait tout. Il capte l'intention, la traduit en action, puis la restitue avec une voix, des oreilles, des LEDs ou une petite reaction sonore.

### 2. Nabaztag comme terminal audio

Le lapin peut aussi agir comme un petit endpoint sonore reseau:

- lancer une radio
- jouer une ambiance ou un son court
- servir de point de sortie pour des contenus audio simples et compatibles

Il ne faut pas le penser comme un Chromecast, un AirPlay ou une enceinte Bluetooth moderne. Il faut plutot le penser comme un client de flux audio simple, pilote par le portail.

### 3. Nabaztag comme agent ambiant

Le lapin ne fait pas que reagir. Il peut aussi habiter la maison:

- interventions aleatoires
- commentaires contextuels
- notifications de la maison
- conversations entre lapins
- scenarios RFID, heure, presence, routines

Cette couche est celle de la personnalite: un lapin qui n'est pas seulement une interface, mais une presence.

## Architecture cible a moyen terme

Pour les integrations de maison connectee, l'objectif n'est pas de devenir dependant d'un service cloud proprietaire ou d'un abonnement mensuel. La direction privilegiee est une architecture generique, securisee et open source.

Le modele vise est le suivant:

- `Nabaztag` comme interface physique
- un `catalogue d'actions` comme contrat entre le LLM et le systeme
- un `orchestrateur` pour choisir l'action pertinente
- des `connecteurs` vers les services et appareils
- une `restitution expressive` sur le lapin

Autrement dit:

- le lapin capture une intention
- le LLM choisit dans un catalogue d'actions compatibles
- l'action est executee soit localement sur le lapin, soit sur un systeme externe
- le resultat revient sur le lapin sous forme de voix, LEDs, oreilles ou audio

Aujourd'hui, cette couche prend la forme d'une architecture de `connecteurs externes`:

- configuration par compte utilisateur
- catalogue d'operations exposees au LLM
- contexte declaratif pour aider le LLM a choisir une action compatible
- execution centralisee cote portail
- formulaires de test sur la fiche d'un lapin

Le contrat est documente dans [docs/connectors.md](docs/connectors.md).

## Vers un bridge local open source

Pour la maison connectee, la bonne direction n'est pas de donner au serveur `nabaztag.org` un acces entrant direct au reseau domestique de l'utilisateur.

La piste privilegiee est plutot un `bridge local` auto-heberge chez l'utilisateur:

- le bridge voit les appareils du reseau local
- il expose une connexion sortante securisee vers le serveur Nabaztag
- il execute localement les commandes recues
- il peut parler a plusieurs ecosystemes sans enfermer le projet dans un seul

Ce bridge pourrait devenir le point d'integration generique pour:

- Home Assistant
- MQTT
- Jellyfin
- lecteurs audio et media servers
- TV, ampli ou hifi pilotables localement
- scenes et automatisations maison

L'interet est double:

- pas besoin d'ouvrir son reseau local a Internet
- pas de dependance structurelle a une offre cloud tierce

Dans cette vision, Home Assistant reste une integration interessante, mais comme connecteur parmi d'autres, pas comme centre obligatoire du systeme.

Les connecteurs actuellement branches sont:

- `home_assistant`
- `webhook`
- `mqtt`
- `jellyfin`
- `local_bridge`

`webhook` et `mqtt` sont volontairement plus generiques. Ils permettent de relier le lapin a un service HTTP auto-heberge, a un broker MQTT, ou a un futur bridge local sans coupler tout le projet a un seul ecosysteme. `jellyfin` valide de son cote un usage media open source plus concret: demander une musique a la voix, la resoudre via un catalogue local, puis la lire sur le lapin via un proxy audio MP3 du portail. `local_bridge` pose enfin le socle cible: un agent auto-heberge qui se connecte en sortie au portail et execute chez l'utilisateur des actions locales sans exposition entrante du LAN.

## Contribuer

Le projet est encore en construction et il est volontairement ouvert a la contribution. Si vous aimez les interfaces tangibles, les objets connectes atypiques, l'IA embarquee dans des experiences physiques, ou simplement le reemploi creatif d'objets anciens, vous etes au bon endroit.

Pour un guide plus operationnel, voir aussi [CONTRIBUTING.md](CONTRIBUTING.md).

Les contributions utiles ne se limitent pas au code. Le projet a besoin de regards et de competences tres varies:

- backend Python
- protocoles et integration device
- UX du portail
- design d'interaction
- prompts et orchestration LLM
- synthese et traitement audio
- documentation
- tests avec de vrais lapins

L'objectif n'est pas seulement de "faire tourner" le systeme. Il s'agit de construire une plateforme credible pour des compagnons physiques expressifs, sobres et attachants.

## Ce que le systeme sait deja faire

La plateforme couvre aujourd'hui les usages suivants:

- inscription et connexion sur le portail
- inventaire de lapins et fiche detaillee par lapin
- association d'un device physique a un lapin
- provisioning Wi-Fi depuis l'application macOS
- lecture du serial physique sur la page de configuration du lapin
- rattachement automatique par serial lorsque le lapin se connecte au portail
- suivi de presence via les sessions XMPP actives
- controle des oreilles
- controle des LEDs: nez, dessous, ventre gauche/centre/droite
- lecture audio
- lecture radio / stream MP3 simple
- upload et lecture d'un fichier audio depuis le portail
- prompt de personnalite editable pour chaque lapin
- selection du modele Mistral par lapin
- selection de la voix Voxtral par lapin
- generation de performances expressives structurees
- pre-calcul de performances avec MP3 et sidecar JSON
- message vocal de premiere connexion choisi dans une bibliotheque embarquee
- catalogue d'actions compatible LLM pour les oreilles, LEDs, radio, sommeil et reveil
- conversations courtes avec memoire recente
- purge agressive du contexte conversationnel pour stabiliser le systeme
- interventions aleatoires selon une frequence et une plage horaire
- interventions aleatoires avec mouvements d'oreilles et LEDs en plus de la voix
- choregraphies musicales de 10 secondes avec audio, oreilles et LEDs
- declenchement d'une choregraphie au hasard depuis le portail ou l'application macOS
- interface mobile web dediee avec micro, reveil vocal `Ok <nom du lapin>` et conversation continue
- acquittement sonore local et sur le lapin lors du reveil vocal mobile
- application macOS Qt avec connexion, liste des lapins, conversation, programmation des interventions, provisioning Wi-Fi et declenchement de choregraphies
- support de stations radio connues, dont `RFI Monde`
- architecture de connecteurs externes avec action LLM generique `connector.invoke`
- premier connecteur domotique `Home Assistant`
- connecteurs generiques `webhook` et `mqtt` pour valider l'extensibilite
- connecteur media `Jellyfin` pour chercher et lire de la musique auto-hebergee sur le lapin
- bridge local auto-heberge avec appairage, polling sortant et file de commandes
- endpoint d'upload d'enregistrement compatible avec les usages Nabaztag historiques

## Architecture

Le monorepo est organise autour de plusieurs applications:

- `apps/portal`
  Portail Flask pour les comptes, l'inventaire des lapins, la fiche detaillee, la configuration IA, le suivi des conversations et le pilotage des actions.

- `apps/portal/portal_app/xmpp_server.py`
  Serveur XMPP de production pour les connexions des vrais lapins. Il traduit la file de commandes du portail en paquets Nabaztag.

- `apps/api`
  API FastAPI qui expose l'etat des lapins, les commandes, les evenements et la couche de communication avec les devices.

- `apps/macos_client`
  Application Qt pour macOS: appairage utilisateur, provisioning Wi-Fi, rattachement du serial, pilotage, conversation et programmation.

- `apps/local_bridge`
  Agent local experimental qui se connecte au portail en polling sortant et execute des capacites du reseau domestique.

- `apps/web`
  Ancienne interface Next.js conservee comme reference exploratoire.

## Ou contribuer dans le code

Pour eviter l'effet "grand depot opaque", voici les principaux points d'entree:

- `apps/portal/portal_app/main.py`
  Le coeur du portail Flask: routes, logique applicative, actions sur les lapins, conversations, IA et orchestration.

- `apps/portal/portal_app/device_protocol.py`
  L'encodage des paquets audio, oreilles, LEDs et choregraphies envoyes aux lapins par XMPP.

- `apps/portal/portal_app/xmpp_server.py`
  La boucle XMPP: authentification simplifiee, presence, observation des boutons/oreilles et dispatch des commandes.

- `apps/portal/portal_app/templates/`
  Les templates du portail, notamment les fiches lapins et les ecrans de configuration.

- `apps/portal/portal_app/models.py`
  Le modele de donnees du portail.

- `apps/api/app/main.py`
  L'API FastAPI exposee aux autres composants.

- `apps/api/app/gateway.py`
  La couche d'abstraction pour piloter les lapins selon le driver retenu.

- `apps/api/app/protocol/`
  La partie la plus utile si vous voulez travailler sur le protocole Nabaztag ou etendre les primitives supportees.

- `apps/macos_client/qt_client.py`
  Le client macOS moderne.

- `apps/macos_client/provisioning_support.py`
  La logique macOS Wi-Fi/CoreWLAN/CoreLocation et le parseur de la page de configuration du Nabaztag.

- `docs/protocol-notes.md`
  Le bon point de depart pour comprendre l'etat actuel des connaissances sur le protocole.

## Pile IA

Le projet utilise aujourd'hui principalement Mistral:

- modeles de chat Mistral pour la generation des reponses et des performances
- Voxtral TTS pour la synthese vocale
- generation structuree en JSON pour coordonner la parole et un catalogue d'actions du lapin

L'idee n'est pas de demander au modele "dis quelque chose". L'idee est de demander:

- quoi dire
- quelles actions du lapin utiliser
- dans quel ordre les utiliser
- avec quels parametres compatibles
- comment garder une reponse expressive et naturelle

Cette structuration est essentielle pour que le lapin existe comme personnage physique, et pas seulement comme canal audio.

## Lancer le projet en local

Le chemin le plus simple pour contribuer est de faire tourner d'abord le portail et l'API en local avec le driver `simulated`, puis de brancher un vrai lapin ensuite si vous en avez un.

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

## Chantiers ouverts

Voici quelques axes de contribution particulierement utiles:

- ameliorer l'expressivite du lapin: meilleures performances combinees voix + oreilles + LEDs
- stabiliser la conversation: memoire, resume, reprise de contexte
- enrichir les scenarios de vie domestique: interventions aleatoires, routines, reactions contextuelles
- fiabiliser l'audio: capture, lecture, diagnostics, compatibilite materielle
- etendre le protocole: nouvelles primitives, meilleure robustesse, commandes manquantes
- simplifier l'onboarding developpeur: scripts de demarrage, fixtures, jeu de donnees local
- documenter les cas d'usage et les limites connues

Si vous voulez contribuer, le plus simple est d'ouvrir une issue, proposer une piste, ou envoyer directement une pull request.
