# Croisement entre la matrice protocolaire et le code OpenJabNab

Ce document croise :

- la documentation et la rétro-ingénierie synthétisées dans [nabaztag-protocol-matrix.md](/Users/apachot/Documents/GitHub/nabaztag/docs/nabaztag-protocol-matrix.md)
- le code source OpenJabNab inspecté localement dans `/tmp/OpenJabNab-src`
- notre propre pile actuelle

Objectif :

- distinguer ce qui est seulement documenté de ce qui est réellement implémenté dans OpenJabNab
- identifier les éléments déjà convergents avec notre stack
- lister les trous encore à combler

## 1. Résumé exécutif

Le code OpenJabNab confirme plusieurs points importants de la matrice protocolaire :

- les paquets binaires `0x04`, `0x0A`, `0x0B` sont réellement implémentés côté serveur
- l’encapsulation binaire `7F + blocs + FF` est bien celle utilisée
- l’algorithme d’obfuscation des `message packets` est bien présent
- le bootcode `main.mtl` appelle réellement `locate.jsp`, `record.jsp` et `rfid.jsp`
- le bootcode traite explicitement les trames de type `3`, `4`, `9`, `10`, `11`
- `violet:iq:sources` est bien demandé côté lapin dans le code de boot

En revanche, ce croisement confirme aussi une limite importante :

- OpenJabNab semble surtout maintenir et pousser un état commandé
- je n’ai pas trouvé de mécanisme clair exposant une télémétrie publique de position réelle des oreilles ou d’état réel des LEDs

## 2. Fichiers OpenJabNab inspectés

### Bibliothèque serveur

- `/tmp/OpenJabNab-src/server/lib/packet.h`
- `/tmp/OpenJabNab-src/server/lib/packet.cpp`
- `/tmp/OpenJabNab-src/server/lib/ambientpacket.h`
- `/tmp/OpenJabNab-src/server/lib/ambientpacket.cpp`
- `/tmp/OpenJabNab-src/server/lib/messagepacket.h`
- `/tmp/OpenJabNab-src/server/lib/messagepacket.cpp`
- `/tmp/OpenJabNab-src/server/lib/sleeppacket.h`
- `/tmp/OpenJabNab-src/server/lib/sleeppacket.cpp`
- `/tmp/OpenJabNab-src/server/lib/bunny.cpp`

### Bootcode / VM

- `/tmp/OpenJabNab-src/bootcode/sources/main.mtl`

## 3. Encapsulation des paquets

### Ce que disait la matrice

- les paquets sont structurés autour de `7F`, d’un type, d’une longueur, de données, puis `FF`
- les types principaux identifiés étaient `04`, `0A`, `0B`

### Ce que confirme OpenJabNab

Dans `packet.h`, OpenJabNab définit explicitement :

- `Packet_Ambient = 0x04`
- `Packet_Message = 0x0A`
- `Packet_Sleep = 0x0B`

Dans `packet.cpp` :

- `Packet::Parse(...)` vérifie que le buffer commence par `0x7F` et finit par `0xFF`
- chaque bloc est lu selon :
  - type sur 1 octet
  - longueur sur 3 octets
  - charge utile sur `len`

Cela confirme fortement notre matrice sur ce point.

### Conséquence projet

- notre compréhension de l’enveloppe binaire est correcte
- on peut s’appuyer sur OpenJabNab comme implémentation de référence pour sérialiser ou parser les blocs principaux

## 4. Bloc ambient `0x04`

### Ce que disait la matrice

- le bloc `04` porte des services ambient, notamment oreilles et nez

### Ce que confirme OpenJabNab

Dans `ambientpacket.h`, OpenJabNab déclare explicitement :

- `MoveLeftEar`
- `MoveRightEar`
- `Service_Nose`
- `Service_BottomLed`
- `Service_TaiChi`

La table de services est :

- `Disable_Service = 0`
- `Service_Weather = 1`
- `Service_StockMarket = 2`
- `Service_Periph = 3`
- `MoveLeftEar = 4`
- `MoveRightEar = 5`
- `Service_EMail = 6`
- `Service_AirQuality = 7`
- `Service_Nose = 8`
- `Service_BottomLed = 9`
- `Service_TaiChi = 0x0e`

Dans `ambientpacket.cpp` :

- la charge utile commence par `7FFFFFFE`
- puis s’ajoutent des couples `(service, valeur)`
- `SetEarsPosition(left, right)` remplit directement les services `4` et `5`

### Ce que cela apporte par rapport à la matrice

Deux confirmations utiles :

1. `Service_BottomLed = 9` est explicitement présent dans OpenJabNab
   alors que certaines sources communautaires parlaient surtout du nez et des oreilles

2. le format `7F FF FF FE` comme en-tête interne du payload ambient est effectivement implémenté

### Conséquence projet

- pour les oreilles, OpenJabNab confirme bien que le bon transport de base est le bloc ambient
- le `bottom led` mérite d’être mieux documenté dans notre pile, car il existe clairement dans OpenJabNab

## 5. Bloc message `0x0A`

### Ce que disait la matrice

- le bloc `0A` porte des commandes applicatives textuelles obfusquées
- les commandes historiques incluent `CH`, `CL`, `PL`, `MU`, `MC`, `ST`, `SP`, `MW`

### Ce que confirme OpenJabNab

Dans `messagepacket.cpp`, OpenJabNab implémente exactement l’algorithme d’obfuscation / désobfuscation :

- `currentChar` initialisé à `35`
- parcours du buffer à partir de l’octet `1`
- formule :
  `currentChar = ((code - 47) * (1 + 2 * currentChar)) % 256`

Cela correspond très bien à la formule documentée dans la recherche.

### Ce que confirme le bootcode

Dans `bootcode/sources/main.mtl`, on retrouve explicitement l’exécution des commandes :

- `ST`
- `SP`
- `MW`
- `CH`
- `PL`
- `CL`

Ainsi, le croisement doc + code est très bon sur cette partie.

### Conséquence projet

- notre note sur l’algorithme n’est plus seulement documentaire, elle est confirmée par une implémentation effective
- si on veut un jour parser proprement des `message packets` côté projet, OpenJabNab fournit une base robuste

## 6. Bloc sleep `0x0B`

### Ce que disait la matrice

- `0B` semblait piloter sleep / wake

### Ce que confirme OpenJabNab

Dans `sleeppacket.h/.cpp` :

- `State { Wake_Up = 0, Sleep }`
- la payload a une taille de 1 octet
- `0` = réveil
- `1` = sommeil

Le bootcode `main.mtl` traite aussi explicitement le code `11` de changement de mode :

- `mode == 0` : `endSleep`
- `mode == 1` : `startSleep`

Il faut donc distinguer :

- le paquet serveur `0x0B`
- la logique interne de changement de mode dans certaines trames de bootcode

### Conséquence projet

- la partie sleep/wake est bien réelle et clairement codée
- elle est un bon candidat pour une commande fiable dans notre stack

## 7. Bloc reboot `0x09`

### Ce que disait la matrice

- `09` correspond à un reboot

### Ce que confirme OpenJabNab

Dans `bootcode/sources/main.mtl`, la fonction `evalTrame` traite :

- `code == 9`
- action : `reboot 0x0407FE58 0x13fb6754`

Donc le reboot n’est pas juste théorique, il est bien prévu dans le bootcode.

### Conséquence projet

- très bonne piste pour un reset plus propre que `disconnect/connect`
- il reste à voir si notre couche protocolaire actuelle sait émettre proprement ce type de trame

## 8. `violet:iq:sources` et `violet:packet`

### Ce que disait la matrice

- `violet:iq:sources` est utilisé au boot
- `violet:packet` est le conteneur Base64 des paquets binaires

### Ce que confirme OpenJabNab

Dans `bootcode/sources/main.mtl`, on voit explicitement :

- une requête de sources vers la ressource `sources`
- avec le namespace `violet:iq:sources`
- et le packet :
  `<packet xmlns="violet:packet" format="1.0"/>`

On voit aussi :

- `_isResourceValid` considère `sources` comme une ressource toujours valable
- `evalTrame` est appelée après récupération des données utiles

### Conséquence projet

- la lecture documentaire du rôle de `sources` est confirmée côté code
- en revanche, le code seul ne suffit pas encore à dire si `sources` sert uniquement au boot ou aussi à d’autres rafraîchissements

## 9. Endpoints HTTP confirmés par le bootcode

### Ce que disait la matrice

- `locate.jsp`, `record.jsp`, `rfid.jsp` étaient centraux

### Ce que confirme OpenJabNab

Dans `main.mtl`, on trouve explicitement :

- `configurl = ... "/locate.jsp?..."`
- `recordurl mode = ... "/vl/record.jsp?...&m=..."`
- `rfidurl tag = ... "/vl/rfid.jsp?...&t=..."`

On voit aussi le comportement associé :

- upload audio en `POST`
- remontée RFID en `GET`
- retries sur l’upload d’enregistrement

### Cas particulier de `p4.jsp`

Dans le code OpenJabNab inspecté, je n’ai pas retrouvé d’endpoint nommé explicitement `p4.jsp`.

En revanche, le bootcode montre clairement le mécanisme fonctionnel associé :

- `locate.jsp` fournit `ping` et `broad`
- le lapin récupère ensuite des trames via HTTP et XMPP
- ces trames sont passées à `evalTrame`
- `processIncomingTrame` gère leur exécution et leur éventuelle mise en file avec `ttl`

Autrement dit :

- la logique "serveur qui pousse ou expose des trames de contrôle" est bien présente
- mais le nom `p4.jsp` ne ressort pas comme primitive explicite dans OpenJabNab

### Conséquence projet

- dans notre matrice, `p4.jsp` doit être considéré comme historiquement documenté
- mais non confirmé tel quel par le code OpenJabNab inspecté
- ce que le code confirme vraiment, c’est le couple `ping` / `broad` + `evalTrame`

### Détail utile

L’upload record côté OpenJabNab :

- s’arrête si le bouton est relâché ou si `8000 ms` sont dépassées
- rejoue un son de fin d’enregistrement
- tente jusqu’à `3` retries en cas de timeout réseau

### Conséquence projet

- notre compréhension fonctionnelle de `record.jsp` et `rfid.jsp` est alignée avec OpenJabNab
- le retry côté device est important : il peut expliquer certains doublons d’upload observés chez nous

## 10. Ce qu’OpenJabNab confirme sur les doublons d’enregistrement

Dans `main.mtl`, le flux d’upload de l’enregistrement :

- garde un `recordretry=3`
- relance la requête HTTP si le timeout réseau est atteint

Cela veut dire qu’un même audio peut être renvoyé plusieurs fois en cas de timeout ou d’ambiguïté réseau.

### Conséquence projet

Cela confirme directement la pertinence du garde-fou que nous avons ajouté :

- déduplication par empreinte audio sur une fenêtre courte

Ce n’est donc pas juste une hypothèse applicative : le bootcode OpenJabNab montre bien un comportement de retry côté lapin.

## 11. Ce qu’OpenJabNab remonte réellement depuis le lapin

### Oreilles

Dans `xmpphandler.cpp`, OpenJabNab parse explicitement :

- `<ears xmlns="violet:nabaztag:ears"><left>...</left><right>...</right></ears>`

puis appelle :

- `bunny->OnEarsMove(left, right)`

Cela prouve un point important :

- le lapin remonte bien au serveur des positions d’oreilles via XMPP
- OpenJabNab sait les recevoir et les dispatcher aux plugins

Cette remontée est donc plus qu’un simple "état commandé localement par le serveur".

### Limite de l’API publique

Dans `bunny.cpp`, le chemin API Violet `?ears=...` fait :

- `answer->AddEarPosition(0, 0); // TODO: send real positions`

Donc :

- OpenJabNab reçoit bien des mouvements d’oreilles
- mais l’API publique exposée au-dessus ne renvoie pas proprement ces positions réelles
- elle renvoie même actuellement une valeur factice

### LEDs

Je n’ai pas trouvé dans les fichiers inspectés :

- d’équivalent XMPP simple pour une remontée publique de l’état courant des LEDs
- d’API publique claire qui exposerait cet état réel

### Conséquence projet

- pour les oreilles, il existe une télémétrie montante réelle côté protocole XMPP
- mais elle n’est pas proprement exposée par l’API publique OpenJabNab
- pour les LEDs, je n’ai pas trouvé de remontée d’état réel comparable

## 12. État réel vs état commandé

### Ce que disait la matrice

- la doc permet surtout de piloter les oreilles et LEDs
- elle ne démontre pas clairement une lecture télémétrique d’état réel

### Ce que confirme OpenJabNab

Je n’ai pas trouvé dans les fichiers inspectés :

- d’API publique claire renvoyant la position réelle courante des oreilles
- d’endpoint public documenté renvoyant l’état courant des LEDs

En revanche, OpenJabNab :

- construit des paquets de commande
- maintient des structures internes de service
- reçoit aussi des événements XMPP de mouvement d’oreilles

Conclusion :

- OpenJabNab confirme un modèle de contrôle
- il confirme aussi une remontée réelle des oreilles vers le serveur
- mais pas une télémétrie fine, publique et proprement exposée pour oreilles + LEDs

## 13. Tableau de croisement

| Élément | Matrice documentaire | OpenJabNab | Conclusion |
|---|---|---|---|
| `bc.jsp` | documenté | présent dans configs et bootcode | confirmé |
| `locate.jsp` | documenté | URL construite dans `main.mtl` | confirmé |
| `p4.jsp` | documenté | pas retrouvé tel quel, remplacé de fait par `ping` / `broad` + trames | non confirmé tel quel |
| `record.jsp` | documenté | URL et logique d’upload confirmées | confirmé |
| `rfid.jsp` | documenté | URL et logique de remontée confirmées | confirmé |
| `api.jsp` | documenté | pas le cœur d’OpenJabNab inspecté ici | non croisé complètement |
| `violet:iq:sources` | documenté | explicitement présent | confirmé |
| `violet:packet` | documenté | explicitement présent | confirmé |
| bloc `0x04` | documenté | classe `AmbientPacket` | confirmé |
| bloc `0x0A` | documenté | classe `MessagePacket` | confirmé |
| bloc `0x0B` | documenté | classe `SleepPacket` | confirmé |
| bloc `0x09` reboot | documenté | traité dans `main.mtl` | confirmé |
| oreilles par instruction | documenté | `SetEarsPosition`, services `4` et `5` | confirmé |
| oreilles par remontée device | flou | `<ears>...</ears>` reçu en XMPP | confirmé |
| nez blink | documenté | `Service_Nose` | confirmé |
| bottom LED | partiellement documenté | `Service_BottomLed` | confirmé par code |
| lecture état réel oreilles via API publique | flou | `TODO: send real positions` | non confirmé |
| lecture état réel LEDs | flou | pas trouvé clairement | non confirmé |
| doublons upload audio | plausible | retries explicites | confirmé |

## 14. Faisabilité dans notre stack actuelle

### 14.1 État des oreilles

Dans notre pile actuelle :

- l’API locale sait stocker `left_ear` et `right_ear`
- le portail sait aussi afficher ces champs
- mais le chemin `state_event_from_packet(...)` ne fusionne aujourd’hui aucun delta détaillé provenant du paquet `state`

Conséquence :

- même si `nabd` ou une couche voisine pouvait fournir un état riche, notre code actuel ne l’exploite pas encore comme une télémétrie fine
- côté portail, on complète encore l’état par reconstruction à partir des dernières commandes

### 14.2 Reboot protocolaire `0x09`

Dans notre pile actuelle :

- le client protocole parle uniquement en JSON ligne à ligne au démon `nabd`
- les commandes supportées sont `connect`, `disconnect`, `sync`, `info`, `ears`, `command`
- aucune commande `reboot` n’existe aujourd’hui dans `apps/api/app/protocol/commands.py`
- aucune branche `reboot` n’est gérée dans `apps/api/app/protocol/client.py`

Conséquence :

- nous ne savons pas aujourd’hui émettre un reboot bas niveau type `0x09`
- pour y parvenir, il faudrait soit :
- ajouter un support natif dans `nabd` si ce démon expose une commande JSON équivalente
- soit descendre d’un niveau et parler un protocole plus bas que l’interface JSON actuelle

### 14.3 Ce qu’on peut considérer comme solide

- le parsing et la sérialisation des paquets `0x04`, `0x0A`, `0x0B`
- le fait que `record.jsp` puisse être réessayé automatiquement côté lapin
- le rôle de `violet:iq:sources` dans le bootstrap fonctionnel
- la pertinence d’un reboot natif type `0x09` comme prochaine piste de recherche

### 14.4 Ce qu’il faut continuer à traiter comme état estimé

- la position courante des oreilles
- l’état courant des LEDs

Tant qu’on n’a pas identifié une remontée fiable de télémétrie, ces valeurs doivent rester présentées comme :

- dernier état commandé
- ou état reconstruit

### 14.5 Prochain chantier technique le plus intéressant

À partir de ce croisement, la suite la plus utile serait probablement :

1. inspecter plus finement le traitement de `p4.jsp` dans OpenJabNab
2. chercher si des trames montantes contiennent réellement un delta d’état oreilles / LEDs, au-delà du message XMPP `<ears>`
3. vérifier si `nabd` expose un reboot JSON équivalent, avant d’envisager un client de plus bas niveau
