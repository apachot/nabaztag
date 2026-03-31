# Recherche documentaire sur le protocole Nabaztag

Ce document consolide des informations techniques retrouvées sur le Web au sujet du protocole Nabaztag, en particulier pour les Nabaztag:tag v2.

Objectif :

- recenser les endpoints et flux réseau historiques
- lister les types de paquets et les instructions connues
- distinguer ce qui est documenté, ce qui est observé, et ce qui reste inféré

Important :

- ce document mélange des sources de qualité variable : documentation d’époque, billets techniques, projets alternatifs, archives communautaires
- certaines informations se recoupent bien entre plusieurs sources, d’autres sont clairement issues de rétro-ingénierie
- quand une information est incertaine, c’est indiqué

## 1. Vue d’ensemble

Le Nabaztag:tag v2 utilise une architecture mixte :

- HTTP au démarrage et pour certains événements
- XMPP pour le contrôle interactif
- fichiers binaires ou paquets encodés pour décrire l’état et les actions du lapin

Le schéma général qui ressort des sources est :

1. le lapin démarre et contacte un serveur HTTP configuré
2. il récupère un bootcode via `bc.jsp`
3. il récupère les serveurs fonctionnels via `locate.jsp`
4. il ouvre ensuite une session XMPP
5. le serveur lui envoie des paquets binaires encodés contenant états et ordres
6. le lapin notifie certains événements au serveur via HTTP, notamment `p4.jsp`, `record.jsp` et `rfid.jsp`

Sources principales :

- https://www.eskuel.net/le-nabaztag-comment-ca-marche--partie-1--le-boot-1484
- https://www.eskuel.net/tag/d%C3%A9veloppement
- https://www.web3.lu/jnabserver-for-nabaztag/
- https://cyrille.giquello.fr/divers/nabaztag
- https://nabaztag.com/doc

## 2. Endpoints HTTP historiques

Les endpoints les plus souvent mentionnés sont :

- `bc.jsp`
- `locate.jsp`
- `p4.jsp`
- `record.jsp`
- `rfid.jsp`
- `api.jsp`
- `api_prefs.jsp`

Cette liste est confirmée par plusieurs sources :

- jNabServer :
  https://www.web3.lu/jnabserver-for-nabaztag/
- étude de l’université de Tampere :
  https://webpages.tuni.fi/utacs_history/cs/reports/dsarja/D-2007-11.pdf
- article communautaire :
  https://cyrille.giquello.fr/divers/nabaztag

### 2.1 `bc.jsp`

Fonction :

- sert le bootcode ou bytecode exécuté par la machine virtuelle du lapin

Exemple de requête observée :

`GET /bc.jsp?v=0.0.0.10&m=00:13:d3:84:53:5a&l=00:00:00:00:00:00&p=00:00:00:00:00:00&h=4 HTTP/1.0`

Paramètres documentés ou observés :

- `v` : version du lapin ou du firmware
- `m` : adresse MAC du lapin
- `l` : souvent présenté comme login, mais usage exact historique incertain selon les sources
- `p` : souvent présenté comme password, usage exact historique incertain selon les sources
- `h` : paramètre non clairement identifié

Points importants :

- le lapin télécharge un programme exécuté par sa VM embarquée
- il y a souvent confusion entre firmware et bytecode
- plusieurs sources insistent sur le fait que c’est ce bytecode, et non forcément le firmware, qui change la logique réseau

Sources :

- https://www.eskuel.net/le-nabaztag-comment-ca-marche--partie-1--le-boot-1484
- https://cyrille.giquello.fr/divers/nabaztag

### 2.2 `locate.jsp`

Fonction :

- renvoie les adresses des serveurs à utiliser ensuite

Exemple de requête observée :

`GET /locate.jsp?sn=0013d384535a&h=4&v=21029 HTTP/1.0`

Exemple de réponse observée :

```text
ping tagtag.nabaztag.objects.violet.net
broad broad.violet.net
xmpp_domain xmpp.nabaztag.com
```

Interprétation récurrente :

- `ping` : serveur HTTP utilisé pour les événements, notamment tags RFID et reconnaissance vocale
- `broad` : serveur HTTP pour chorégraphies, sons et autres ressources
- `xmpp_domain` : serveur XMPP pour le contrôle du lapin

Sources :

- https://www.eskuel.net/le-nabaztag-comment-ca-marche--partie-1--le-boot-1484
- https://www.eskuel.net/tag/d%C3%A9veloppement

### 2.3 `p4.jsp`

Fonction :

- endpoint de ping et de notification d’événements
- utilisé de manière périodique
- semble aussi porter des informations d’événements utilisateur

Exemple de paramètres observés dans jNabServer :

```text
{tc=7fffffff v=65808 st=1 requestfile=/vl/p4.jsp h=4 sd=0 sn=0013d3845819}
```

Ce qu’on peut en dire avec un niveau raisonnable de confiance :

- `sn` : numéro de série
- `tc` : probablement compteur ou paramètre temporel lié au ping
- `st` : état ou type de ping, sens exact non confirmé ici
- `sd` : inconnu
- `v` : version
- `h` : inconnu

Ce que les sources disent de manière convergente :

- le lapin appelle régulièrement le serveur avec un intervalle de ping
- cet intervalle peut être modifié par le serveur via un bloc de type `03`

Sources :

- https://www.web3.lu/jnabserver-for-nabaztag/
- https://webpages.tuni.fi/utacs_history/cs/reports/dsarja/D-2007-11.pdf

### 2.4 `record.jsp`

Fonction :

- upload d’un enregistrement audio réalisé par le lapin

Les sources indiquent :

- le son est enregistré après maintien du bouton pendant environ 2 secondes
- l’audio est encodé en ADPCM ou IMA ADPCM selon les sources

Sources :

- https://www.web3.lu/jnabserver-for-nabaztag/
- https://webpages.tuni.fi/utacs_history/cs/reports/dsarja/D-2007-11.pdf

### 2.5 `rfid.jsp`

Fonction :

- upload ou notification de l’identifiant RFID détecté

Sources :

- https://www.web3.lu/jnabserver-for-nabaztag/
- https://webpages.tuni.fi/utacs_history/cs/reports/dsarja/D-2007-11.pdf

### 2.6 `api.jsp`

Fonction :

- endpoint public historique de l’API Violet/Nabaztag permettant à une application extérieure de déclencher des événements sur un lapin

Cette API est documentée dans les PDF d’époque `Nabaztag API V1` et `Nabaztag API V2`.

URL indiquée :

`http://www.nabaztag.com/vl/FR/api.jsp`

Capacités explicitement citées dans les PDFs :

- modification de la vitesse de lecture
- commande des oreilles
- commande des LEDs
- envoi d’un message en TTS
- envoi d’un message dans un Nabcast
- envoi d’une chorégraphie

Sources :

- capture du PDF API V2 :
  https://storage.googleapis.com/nabaztag/doc/v2/APIV2.pdf
- PDF API V1 :
  https://storage.googleapis.com/nabaztag/doc/v2/DocumentationAPI-revA001.pdf

### 2.7 `api_prefs.jsp`

Fonction :

- page historique d’activation de la réception d’événements extérieurs
- permet d’obtenir le `token` nécessaire à l’appel de `api.jsp`

URL indiquée :

`http://www.nabaztag.com/vl/FR/api_prefs.jsp`

Les docs API V1 et V2 précisent :

- il faut activer la réception d’événements externes
- un `token` est alors affiché
- si on désactive puis réactive, un nouveau token est généré

Sources :

- https://storage.googleapis.com/nabaztag/doc/v2/APIV2.pdf
- https://storage.googleapis.com/nabaztag/doc/v2/DocumentationAPI-revA001.pdf

## 2 bis. Paramètres documentés de l’API publique `api.jsp`

Les documents API V1 et V2 fournissent une liste de paramètres très utile.

### Paramètres documentés

- `sn` : numéro de série du lapin ciblé
- `idmessage` : identifiant du message ou du MP3 à jouer
- `posright` : position de l’oreille droite entre `0` et `16`
- `posleft` : position de l’oreille gauche
- `token` : token de sécurité nécessaire à l’envoi
- `idapp` : identifiant d’application émettrice
- `tts` : texte à lire en synthèse vocale
- `chor` : chorégraphie à envoyer
- `chortitle` : nom associé à la chorégraphie
- `ears=ok` : demande explicite d’envoi de position d’oreilles
- `nabcast` : identifiant du Nabcast
- `ttl` ou `ttlive` : durée de conservation du message côté service, telle qu’elle apparaît dans les docs
- `voice` : choix de la voix TTS
- `speed` : vitesse de lecture
- `pitch` : fréquence de la voix
- `key` : introduit dans l’API V2 comme identifiant permettant d’utiliser l’API

### Exemple documenté

Exemple V2 donné dans le PDF :

```text
http://www.nabaztag.com/vl/FR/api.jsp?key=431561751&sn=00039D4022DE&token=112231049046144&posleft=0&posright=0&idmessage=10333&idapp=10
```

Exemple V1 documenté :

```text
http://www.nabaztag.com/vl/FR/api.jsp?sn=00039D4022DE&token=112231049046144&posleft=0&posright=0&idmessage=10333&idapp=10
```

Points intéressants :

- V2 introduit explicitement un paramètre `key`
- les paramètres de pilotage oreilles et message restent très proches entre V1 et V2
- la logique de token est déjà présente en V1

Sources :

- https://storage.googleapis.com/nabaztag/doc/v2/APIV2.pdf
- https://storage.googleapis.com/nabaztag/doc/v2/DocumentationAPI-revA001.pdf

## 3. Session XMPP

Les sources indiquent qu’après la phase HTTP initiale, le Nabaztag:tag v2 passe par XMPP.

L’article d’eSKUeL détaille une séquence de boot XMPP très utile :

- ouverture d’un `stream:stream`
- annonce des mécanismes SASL `DIGEST-MD5` et `PLAIN`
- choix de `DIGEST-MD5` par le lapin
- challenge / response en Base64
- acceptation côté serveur par retour `<success />`
- rebinding sur la ressource `boot`
- ouverture de session
- requête `violet:iq:sources`
- réception d’un paquet `violet:packet`
- rebinding sur la ressource `idle`
- présence XMPP
- libération de `boot`

Exemples de namespaces vus dans les échanges :

- `jabber:client`
- `http://etherx.jabber.org/streams`
- `urn:ietf:params:xml:ns:xmpp-sasl`
- `urn:ietf:params:xml:ns:xmpp-bind`
- `urn:ietf:params:xml:ns:xmpp-session`
- `violet:iq:sources`
- `violet: packet`

Points notables :

- plusieurs travaux de rétro-ingénierie indiquent qu’un serveur alternatif peut se contenter d’accepter le flux d’authentification sans réellement vérifier le digest
- la phase `boot` puis `idle` semble structurante dans le cycle de vie XMPP du lapin

Source principale :

- https://www.eskuel.net/tag/d%C3%A9veloppement

## 4. Format général des paquets envoyés au lapin

Plusieurs sources convergent vers un format de paquet binaire encapsulé, souvent Base64 dans XMPP.

Un schéma récurrent donné par eSKUeL pour les blocs contrôlant le lapin est :

```text
7F AA BB BB BB DATA FF
```

Avec :

- `7F` : en-tête
- `AA` : type de bloc
- `BB BB BB` : taille des données
- `DATA` : contenu
- `FF` : fin de paquet

Dans jNabServer, les paquets de réponse sont décrits comme :

- début en `7F`
- fin en `FF` puis `0A`
- suite de blocs concaténés

Il faut donc être prudent :

- le format de bloc interne `7F ... FF` est bien documenté
- la présence systématique du `0A` final dépend peut-être du type de message ou du framing implémenté côté serveur alternatif

Sources :

- https://www.eskuel.net/le-nabaztag-comment-ca-marche--partie-3--communiquer-avec-un-lapin-1486
- https://www.web3.lu/jnabserver-for-nabaztag/

## 4 bis. Focus sur `violet:iq:sources` et `violet:packet`

Le meilleur matériau public retrouvé sur les paquets XMPP Nabaztag est l’échange de fin de boot documenté par eSKUeL.

### Requête du lapin

Une fois la session XMPP établie sur la resource `boot`, le lapin envoie :

```xml
<iq from='[email protected]/boot' to='[email protected]/sources' type='get' id='3'>
  <query xmlns="violet:iq:sources">
    <packet xmlns="violet: packet" format="1.0"/>
  </query>
</iq>
```

Cette requête indique plusieurs choses :

- le lapin s’adresse à une ressource logique `sources`
- il attend un ou plusieurs paquets de configuration ou d’état
- le format annoncé est `1.0`

### Réponse du serveur

Exemple documenté :

```xml
<iq from='[email protected]/sources' to='[email protected]/boot' id='3' type='result'>
  <query xmlns='violet:iq:sources'>
    <packet xmlns='violet: packet' format='1.0' ttl='604800'>
      fwQAAAx////+BAAFAA7/CAALAAABAP8=
    </packet>
  </query>
</iq>
```

Éléments notables :

- `ttl='604800'` apparaît dans la réponse
- `604800` correspond à `7` jours
- le contenu utile du paquet est Base64

### Exemple décodé

La source eSKUeL donne la conversion hexadécimale du paquet ci-dessus :

```text
7f0400000c7ffffffe040005000eff08000b00000100ff
```

Interprétation fournie :

- il s’agit du paquet contenant l’état par défaut du lapin en fin de boot
- dans l’exemple commenté, les oreilles sont remises à la verticale

### Deuxième exemple : paquet de mouvement d’oreilles

Exemple Base64 donné :

```text
fwQAAAh////+BAsFB/8=
```

Décodage hexadécimal indiqué :

```text
7f040000087ffffffe040b0507ff
```

Cela renforce l’idée que :

- les paquets `violet:packet` sont simplement des enveloppes Base64 autour des blocs binaires Nabaztag
- le type `04` y joue un rôle central pour les commandes ou états ambient / oreilles

### Ce qu’on peut en déduire

Avec un niveau de confiance raisonnable, `violet:packet` semble être :

- le conteneur XMPP standard des paquets binaires destinés au lapin
- utilisé à la fois pour envoyer un état initial et pour pousser des commandes
- transporté sous forme Base64 dans le corps XML

`violet:iq:sources` semble être :

- une requête de récupération de “sources” ou de configuration active
- utilisée au moins pendant la séquence de boot pour injecter l’état initial

### Ce qui reste flou

Les points suivants ne sont pas clarifiés publiquement dans les sources retrouvées :

- si `sources` ne sert qu’au boot ou aussi à des rafraîchissements ultérieurs
- si plusieurs `packet` peuvent être retournés dans un même `iq`
- si `ttl` pilote un cache côté lapin, côté serveur, ou les deux
- si tous les ordres applicatifs transitent exclusivement par cette structure ou si d’autres enveloppes XMPP existent aussi

### Sources

- https://www.eskuel.net/tag/d%C3%A9veloppement
- https://www.eskuel.net/le-nabaztag-comment-ca-marche--partie-3--communiquer-avec-un-lapin-1486

## 5. Types de blocs documentés

Les sources communautaires et de rétro-ingénierie listent principalement :

- `03` : ping interval block
- `04` : ambient block
- `09` : reboot block
- `0A` : message block
- `0B` : sleep block dans la description eSKUeL des messages serveur

Il y a ici une petite tension entre les sources :

- jNabServer décrit surtout `03`, `04`, `09`, `0A`
- eSKUeL traite explicitement un block `0B` pour sleep/wake

Interprétation raisonnable :

- `0B` est bien utilisé pour sleep/wake dans les paquets qu’il a observés
- jNabServer a probablement documenté seulement les blocs qu’il manipulait le plus souvent

### 5.1 Bloc `03` : ping interval

Fonction :

- change l’intervalle entre deux appels de ping du lapin vers le serveur

Documenté notamment par jNabServer.

### 5.2 Bloc `04` : ambient

Fonction :

- définit un état visuel ou comportemental “ambient”
- utilisé notamment pour oreilles, météo, trafic, nez, etc.

Format documenté par eSKUeL :

```text
7F 04 XX XX XX 7F FF FF FE n*(AA BB) FF
```

où chaque couple `AA BB` correspond à :

- `AA` : identifiant de service
- `BB` : valeur du service

Services listés :

- `00` : disable
- `01` : météo
- `02` : bourse
- `03` : trafic
- `04` : oreille gauche
- `05` : oreille droite
- `06` : notification email
- `07` : qualité de l’air
- `08` : clignotement du nez
- `0B` : sleep / wake
- `0E` : taïchi

Valeurs documentées :

- oreilles : `0` à `16`
- nez :
  - `00` : disable
  - `01` : blink
  - `02` : double blink
- taïchi : `0` à `255`

Cette partie est l’une des plus utiles pour piloter le lapin de manière structurée.

Source :

- https://www.eskuel.net/le-nabaztag-comment-ca-marche--partie-3--communiquer-avec-un-lapin-1486

### 5.3 Bloc `09` : reboot

Fonction :

- redémarre le lapin

Documenté comme :

- type `09`
- sans donnée ou quasi sans donnée utile

Source :

- https://www.eskuel.net/le-nabaztag-comment-ca-marche--partie-3--communiquer-avec-un-lapin-1486

### 5.4 Bloc `0A` : message

Fonction :

- porte une suite de commandes applicatives
- typiquement audio, chorégraphie, couleur, streaming

Particularité :

- le contenu utile n’est pas directement lisible
- il est encodé selon un algorithme décrit par eSKUeL

Algorithme cité :

```text
C[i] = (B[i] - 0x2F) * (1 + 2 * C[i-1])
```

avec :

- `C[-1] = 35`
- `C` : tableau chiffré
- `B` : tableau déchiffré

Exemple déchiffré :

`MU http://192.168.100.2:2222/mp3/surprise/fr/295.mp3`

Source :

- https://www.eskuel.net/le-nabaztag-comment-ca-marche--partie-3--communiquer-avec-un-lapin-1486

### 5.5 Bloc `0B` : sleep / wake

Fonction :

- endormir ou réveiller le lapin

Exemples donnés :

- `7f0b00000101ff` : sleep
- `7f0b00000100ff` : wake

Source :

- https://www.eskuel.net/le-nabaztag-comment-ca-marche--partie-3--communiquer-avec-un-lapin-1486

## 6. Commandes applicatives documentées

Dans les `message blocks`, plusieurs commandes textuelles sont documentées.

### 6.1 Liste observée par eSKUeL

- `CH <url>` : exécute une chorégraphie
- `CL 0xAABBCCDD` : définit la couleur de la LED `AA` avec la couleur RGB `BBCCDD`
- `PL 0xX` : choisit la palette
- `MC <url>` ou `MU <url>` : lit un MP3
- `MW` : attend la fin des commandes précédentes
- `ST <url>` ou `SP <url>` : lance un flux stream

Source :

- https://www.eskuel.net/le-nabaztag-comment-ca-marche--partie-3--communiquer-avec-un-lapin-1486

### 6.2 Liste observée par jNabServer

jNabServer liste huit commandes possibles dans un message block :

- `ID`
- `CL`
- `PL`
- `CH`
- `MU`
- `MC`
- `ST`
- `MW`

Source :

- https://www.web3.lu/jnabserver-for-nabaztag/

### 6.3 Commandes de chorégraphie

Une autre source communautaire documente le format des chorégraphies et les codes d’opération suivants :

- `01` : TEMPO
- `07` : LED
- `08` : EAR
- `0B` : EAR STEP
- `0A` : MIDI
- `0E` : CHOR
- `IFNE` : synchronisation à un son, détails inconnus

Détails donnés :

- commande LED :
  `ts 07 LED-id red green blue 00 00`
- commande EAR :
  `ts 08 right=0|left=1 position forward=0|backward=1`
- commande EAR STEP :
  `ts 0B right=0|left=1 steps`

Source :

- https://www.web3.lu/nabaztag-choreographies/

## 6 bis. Chorégraphies via l’API publique

Les docs API V1 et V2 décrivent aussi une syntaxe “haut niveau” de chorégraphie, distincte du format binaire interne.

Cette syntaxe est une suite de valeurs séparées par des virgules.

### Tempo

- première valeur : tempo exprimé en Hz
- la doc donne `10` comme exemple correspondant à un dixième de seconde

### Commande oreilles

Format documenté :

```text
heure,motor,oreille,angle,0,sens
```

Avec :

- `heure` : moment de l’action
- `motor` : mot-clé de commande
- `oreille` :
  - `1` = gauche
  - `0` = droite
- `angle` : de `0` à `180`
- cinquième argument : inutilisé, mettre `0`
- `sens` :
  - `1` : haut -> derrière -> bas -> devant -> haut
  - `0` : haut -> devant -> bas -> derrière -> haut

Exemple documenté :

```text
0,motor,1,20,0,0
```

### Commande LEDs

Format documenté :

```text
heure,led,cible,r,g,b
```

Avec :

- `cible` :
  - `0` : LED du bas
  - `1` : LED gauche
  - `2` : LED du milieu
  - `3` : LED droite
  - `4` : LED du haut
- `r`, `g`, `b` : valeurs RGB entre `0` et `255`

Exemple documenté :

```text
0,led,2,0,238,0,2,led,1,250,0,0,3,led,2,0,0,0
```

### Combinaison oreilles + LEDs

Exemple documenté :

```text
10,0,motor,1,20,0,0,0,led,2,0,238,0,2,led,1,250,0,0,3,led,2,0,0,0
```

Sources :

- https://storage.googleapis.com/nabaztag/doc/v2/APIV2.pdf
- https://storage.googleapis.com/nabaztag/doc/v2/DocumentationAPI-revA001.pdf

## 6 ter. Voix TTS historiques documentées

Le PDF API V2 documente aussi des voix TTS utilisables via `voice`.

Voix françaises citées :

- `julie22k`
- `claire22s`

Voix anglaises citées :

- `graham22s`
- `lucy22s`
- `heather22k`
- `ryan22k`
- `aaron22s`
- `laura22s`

Valeurs par défaut documentées :

- français : `claire22s`
- anglais : `heather22k`

Source :

- https://storage.googleapis.com/nabaztag/doc/v2/APIV2.pdf

## 7. Capteurs et événements documentés

Les sources décrivent les capacités suivantes côté matériel et VM :

- positionnement de deux oreilles motrices
- cinq LEDs
- bouton simple et double clic
- mouvement des oreilles
- lecture RFID ISO 14443 B
- enregistrement micro
- lecture audio

Le texte de jNabServer cite explicitement :

- single click
- double click
- ear movement
- RFID
- record and encode sound from microphone

Il est aussi indiqué que la position des oreilles est suivie par des capteurs optiques.

Sources :

- https://www.web3.lu/jnabserver-for-nabaztag/
- https://webpages.tuni.fi/utacs_history/cs/reports/dsarja/D-2007-11.pdf

## 8. Bytecode, VM et langage

Une idée importante ressort de plusieurs sources :

- le lapin embarque une machine virtuelle
- il exécute un bytecode téléchargé au démarrage
- le langage associé est appelé `Metal`

Cela explique plusieurs choses :

- le comportement réseau n’est pas entièrement “figé” dans le firmware
- des projets alternatifs ont pu rester compatibles sans modifier matériellement le lapin
- le serveur HTTP de boot est un point central du système

Sources :

- https://nabaztag.com/doc
- https://cyrille.giquello.fr/divers/nabaztag

La page de référence moderne de Nabaztag pointe d’ailleurs vers :

- API v2
- API v1
- langage Metal
- construction de proxy XMPP

Page index :

- https://nabaztag.com/doc

## 9. Bascules HTTP vs XMPP

Une distinction importante est rappelée dans les archives communautaires :

- les premiers modes historiques ont utilisé une logique HTTP
- Violet a ensuite basculé vers une architecture XMPP en mars 2008
- OpenNab et OpenJabNab ne ciblaient donc pas exactement le même mode de fonctionnement

Résumé donné par Cyrille Giquello :

- OpenNab : environnement PHP utilisant la version HTTP
- OpenJabNab : environnement C++ / PHP ciblant la version XMPP

Source :

- https://cyrille.giquello.fr/divers/nabaztag

## 10. Ce qui semble bien établi

Les éléments suivants apparaissent très solides car recoupés par plusieurs sources :

- existence des endpoints `bc.jsp`, `locate.jsp`, `p4.jsp`, `record.jsp`, `rfid.jsp`
- séquence de boot HTTP puis connexion XMPP
- usage de XMPP avec SASL DIGEST-MD5
- usage des resources `boot` puis `idle`
- existence de blocs binaires typés
- présence des commandes `CH`, `CL`, `PL`, `MU/MC`, `ST/SP`, `MW`
- possibilité de piloter les oreilles et les LEDs
- usage d’un bytecode téléchargé et d’une VM embarquée
- existence d’une API publique `api.jsp` avec token, oreilles, TTS et chorégraphies
- syntaxe publique documentée pour les chorégraphies `motor` et `led`
- encapsulation Base64 de blocs binaires dans `violet:packet`
- usage de `violet:iq:sources` pendant la fin de boot pour pousser un état initial

## 11. Ce qui reste flou ou incertain

Les points suivants restent soit mal documentés, soit dépendants des versions :

- sens exact de certains paramètres HTTP comme `h`, `sd`, `tc`
- différence exacte entre tous les sous-modes HTTP et XMPP selon la génération du bytecode
- format complet des réponses de `p4.jsp`
- détail complet de tous les types de blocs existants
- présence exacte de certains blocs dans tous les firmwares ou bytecodes
- rôle réel et systématique du `0A` terminal dans toutes les réponses serveur
- sémantique exacte de `ttl` dans `violet:packet`
- cycle de vie exact de la ressource `sources`

## 12. Conséquences pratiques pour ce projet

Pour un serveur alternatif moderne, cette recherche suggère :

- `bc.jsp` et `locate.jsp` restent les points d’entrée fondamentaux de compatibilité
- le pilotage fin du lapin repose ensuite sur des paquets structurés envoyés via XMPP
- les oreilles et les LEDs peuvent être contrôlées par instructions, mais pas nécessairement relues comme télémétrie matérielle réelle
- `record.jsp` et `rfid.jsp` sont des points critiques pour réinjecter des usages modernes autour de la voix et des Ztamps
- l’approche “augmentation logicielle sans refit matériel” est cohérente avec la logique technique historique du produit

## 13. Sources

### Sources techniques principales

- Nabaztag documentation hub :
  https://nabaztag.com/doc
- eSKUeL, partie 1, boot :
  https://www.eskuel.net/le-nabaztag-comment-ca-marche--partie-1--le-boot-1484
- eSKUeL, partie 2, authentification et fin du boot :
  https://www.eskuel.net/tag/d%C3%A9veloppement
- eSKUeL, partie 3, communication avec le lapin :
  https://www.eskuel.net/le-nabaztag-comment-ca-marche--partie-3--communiquer-avec-un-lapin-1486
- jNabServer overview :
  https://www.web3.lu/jnabserver-for-nabaztag/
- Nabaztag choreographies :
  https://www.web3.lu/nabaztag-choreographies/
- Archive communautaire Cyrille Giquello :
  https://cyrille.giquello.fr/divers/nabaztag
- Rapport Tampere University :
  https://webpages.tuni.fi/utacs_history/cs/reports/dsarja/D-2007-11.pdf

### Sources de contexte

- OpenJabNab home :
  https://dev.openjabnab.fr/
- OpenJabNab setup :
  https://openjabnab.fr/help/config_v2.php
- Docs Nabaztag v1 :
  https://docs.nabaztag.com/nabaztag-getting-started/nabaztag-v1
- Docs Nabaztag v2 :
  https://docs.nabaztag.com/nabaztag-getting-started/nabaztag-v2

## 14. Suite possible

Les prochaines étapes utiles seraient :

- extraire proprement le contenu lisible des PDF API v1/v2 référencés sur `nabaztag.com/doc`
- comparer ces documents avec les implémentations OpenJabNab et notre code local
- documenter précisément les paquets que notre pile envoie aujourd’hui
- bâtir une matrice “instruction connue / supportée / observée / relue”

## 15. Matrice de synthèse

| Élément | Documenté | Observé / confirmé | Remarques |
|---|---|---|---|
| `bc.jsp` | Oui | Oui | Bootcode téléchargé au démarrage |
| `locate.jsp` | Oui | Oui | Renvoie `ping`, `broad`, `xmpp_domain` |
| `p4.jsp` | Oui | Oui | Ping et événements, format exact partiellement flou |
| `record.jsp` | Oui | Oui | Upload audio, généralement après appui long |
| `rfid.jsp` | Oui | Oui | Notification tag RFID |
| `api.jsp` | Oui | Oui | API publique orientée événements |
| `api_prefs.jsp` | Oui | Oui | Active les événements externes et expose le token |
| XMPP `boot` / `idle` | Oui | Oui | Très bien décrit par eSKUeL |
| Bloc `03` ping interval | Oui | Oui | Cité par jNabServer |
| Bloc `04` ambient | Oui | Oui | Cité par eSKUeL |
| Bloc `09` reboot | Oui | Oui | Cité par eSKUeL |
| Bloc `0A` message | Oui | Oui | Porte les commandes applicatives |
| Bloc `0B` sleep/wake | Oui | Oui | Très clairement documenté par eSKUeL |
| Commande `CH` | Oui | Oui | Chorégraphie |
| Commande `CL` | Oui | Oui | Couleur LED |
| Commande `PL` | Oui | Oui | Palette |
| Commande `MU` / `MC` | Oui | Oui | Lecture MP3 |
| Commande `ST` / `SP` | Oui | Oui | Streaming |
| Commande `MW` | Oui | Oui | Attente / synchronisation |
| Lecture position réelle oreilles | Non clairement | Non | On trouve surtout des commandes, pas une télémétrie publique claire |
| Lecture état réel LEDs | Non clairement | Non | Même limite |
