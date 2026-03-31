# Matrice structurée du protocole Nabaztag

Ce document extrait de manière opérationnelle les éléments utiles issus de [nabaztag-protocol-research.md](/Users/apachot/Documents/GitHub/nabaztag/docs/nabaztag-protocol-research.md).

Objectif :

- disposer d’une vue exploitable rapidement
- séparer les couches HTTP, XMPP, blocs binaires et commandes applicatives
- indiquer pour chaque élément son sens, son niveau de certitude et son intérêt pour le projet

## 1. Légende

### Niveau de certitude

- `fort` : recoupé par plusieurs sources ou appuyé par une documentation directe
- `moyen` : bien plausible mais partiellement inféré ou incomplet
- `faible` : mentionné une seule fois ou encore ambigu

### Statut projet

- `utilisé` : déjà exploité dans notre pile
- `supportable` : semble intégrable proprement
- `bloquant` : zone encore mal comprise
- `hors périmètre` : documenté mais pas prioritaire actuellement

## 2. Couche HTTP de boot et d’événements

| Élément | Type | Sens | Paramètres connus | Certitude | Statut projet | Sources |
|---|---|---|---|---|---|---|
| `bc.jsp` | HTTP GET | renvoie le bootcode / bytecode exécuté par la VM du lapin | `v`, `m`, `l`, `p`, `h` | fort | utilisé | eSKUeL boot, Cyrille Giquello |
| `locate.jsp` | HTTP GET | renvoie les serveurs `ping`, `broad`, `xmpp_domain` | `sn`, `h`, `v` | fort | utilisé | eSKUeL boot |
| `p4.jsp` | HTTP GET/POST | ping périodique et remontée d’événements | `sn`, `tc`, `st`, `sd`, `v`, `h` | moyen | utilisé partiellement | jNabServer, Tampere |
| `record.jsp` | HTTP POST | upload audio enregistré par le lapin | `sn`, `m` observé selon contextes | fort | utilisé | jNabServer, Tampere |
| `rfid.jsp` | HTTP GET/POST | remontée d’identifiant RFID / Ztamp | `sn`, `t` observé côté implémentations alternatives | fort | utilisé | jNabServer, implémentations communautaires |
| `api.jsp` | HTTP GET | API publique historique pour déclencher des actions sur un lapin | voir section 3 | fort | supportable | PDF API V1/V2 |
| `api_prefs.jsp` | page web | activation des événements externes et récupération du token | n/a | fort | hors périmètre | PDF API V1/V2 |

## 3. API publique historique `api.jsp`

### Paramètres de pilotage

| Paramètre | Sens | Valeurs / format | Certitude | Remarques |
|---|---|---|---|---|
| `sn` | numéro de série du lapin ciblé | chaîne hexadécimale | fort | identifiant du rabbit |
| `token` | jeton de sécurité | chaîne numérique ou alphanumérique selon l’époque | fort | obtenu via `api_prefs.jsp` |
| `key` | clé d’usage API V2 | numérique dans l’exemple doc | moyen | introduit en V2 |
| `idapp` | identifiant de l’application émettrice | numérique | fort | pas toujours utilisé dans les implémentations alternatives |
| `idmessage` | identifiant de message / son | numérique | fort | peut référencer un message de bibliothèque ou un MP3 perso |
| `tts` | texte à synthétiser | texte | fort | couplable avec `voice`, `speed`, `pitch` |
| `nabcast` | identifiant de Nabcast | numérique | fort | héritage Violet |
| `ttl` / `ttlive` | durée de conservation du message | secondes | moyen | la doc mentionne les deux graphies |

### Paramètres oreilles

| Paramètre | Sens | Valeurs | Certitude | Remarques |
|---|---|---|---|---|
| `posleft` | position oreille gauche | `0` à `16` | fort | `0` souvent décrit comme horizontal |
| `posright` | position oreille droite | `0` à `16` | fort | même logique |
| `ears=ok` | active l’envoi / la prise en compte des positions | chaîne `ok` | moyen | cité dans le PDF V2 |

### Paramètres chorégraphie / voix

| Paramètre | Sens | Valeurs | Certitude | Remarques |
|---|---|---|---|---|
| `chor` | chorégraphie textuelle | séquence CSV | fort | syntaxe documentée |
| `chortitle` | titre de la chorégraphie | texte | fort | purement descriptif |
| `voice` | voix TTS | ex. `claire22s`, `julie22k` | fort | doc V2 |
| `speed` | vitesse de lecture | numérique | fort | synthèse vocale |
| `pitch` | hauteur / fréquence | numérique | fort | synthèse vocale |

## 4. Couche XMPP

| Élément | Type | Sens | Certitude | Statut projet | Sources |
|---|---|---|---|---|---|
| `stream:stream` | ouverture XMPP | début de session XMPP | fort | utilisé | eSKUeL |
| `DIGEST-MD5` | SASL | mécanisme d’authentification principal observé | fort | utilisé indirectement | eSKUeL |
| `PLAIN` | SASL | mécanisme aussi annoncé par le serveur | moyen | hors périmètre | eSKUeL |
| resource `boot` | bind XMPP | phase de boot XMPP | fort | utilisé conceptuellement | eSKUeL |
| resource `idle` | bind XMPP | phase d’attente normale | fort | utilisé conceptuellement | eSKUeL |
| `violet:iq:sources` | requête IQ | récupération de paquets d’état / configuration | fort | supportable | eSKUeL |
| `violet: packet` | conteneur | enveloppe XMPP contenant les blocs binaires Base64 | fort | utilisé conceptuellement | eSKUeL |
| `ttl='604800'` | attribut packet | TTL du packet ou de sa validité | moyen | bloquant | eSKUeL |

## 5. Paquets binaires

### Format général

| Élément | Sens | Certitude | Remarques |
|---|---|---|---|
| `7F` | en-tête de bloc | fort | très récurrent |
| `AA` | type de bloc | fort | ex. `03`, `04`, `09`, `0A`, `0B` |
| `BB BB BB` | taille de la donnée | fort | longueur binaire |
| `DATA` | charge utile | fort | contenu spécifique au bloc |
| `FF` | fin de bloc | fort | fin logique |
| `0A` final | fin de paquet complète possible | moyen | cité par jNabServer, pas universellement confirmé |

### Exemples documentés

| Encodage | Décodage | Interprétation | Certitude | Source |
|---|---|---|---|---|
| `fwQAAAx////+BAAFAA7/CAALAAABAP8=` | `7f0400000c7ffffffe040005000eff08000b00000100ff` | état par défaut en fin de boot, oreilles verticales | fort | eSKUeL |
| `fwQAAAh////+BAsFB/8=` | `7f040000087ffffffe040b0507ff` | paquet ambient lié aux oreilles | moyen | eSKUeL |

## 6. Types de blocs

| Type | Nom usuel | Sens | Certitude | Statut projet | Remarques |
|---|---|---|---|---|---|
| `03` | ping interval | modifie l’intervalle de ping | fort | supportable | cité par jNabServer |
| `04` | ambient | état / commande ambient, dont oreilles et nez | fort | supportable | source centrale pour oreilles/blink |
| `09` | reboot | redémarrage du lapin | fort | supportable | très intéressant pour reset soft |
| `0A` | message | porte des commandes applicatives textuelles encodées | fort | utilisé conceptuellement | audio, stream, leds, etc. |
| `0B` | sleep/wake | mise en veille ou réveil | fort | supportable | documenté par eSKUeL |

## 7. Bloc `04` ambient

### Services documentés

| Service | Sens | Valeurs documentées | Certitude | Intérêt projet |
|---|---|---|---|---|
| `00` | disable | n/a | moyen | faible |
| `01` | météo | selon service | moyen | faible |
| `02` | bourse | selon service | moyen | faible |
| `03` | trafic | selon service | moyen | faible |
| `04` | oreille gauche | `0` à `16` | fort | fort |
| `05` | oreille droite | `0` à `16` | fort | fort |
| `06` | notification email | selon service | moyen | faible |
| `07` | qualité de l’air | selon service | moyen | faible |
| `08` | nez / clignotement | `00`, `01`, `02` | fort | moyen |
| `0B` | sleep / wake | état | fort | moyen |
| `0E` | taïchi | `0` à `255` | moyen | faible |

### Nez

| Valeur | Sens | Certitude |
|---|---|---|
| `00` | disable / off | fort |
| `01` | blink | fort |
| `02` | double blink | fort |

## 8. Commandes applicatives portées par le bloc `0A`

| Commande | Sens | Certitude | Intérêt projet | Remarques |
|---|---|---|---|---|
| `CH <url>` | exécute une chorégraphie | fort | fort | utile pour mouvements complexes |
| `CL 0xAABBCCDD` | définit une couleur LED | fort | fort | LED ciblée + RGB |
| `PL 0xX` | choisit une palette | fort | moyen | surtout historique |
| `MU <url>` | lit un MP3 | fort | fort | utilisé pour audio/TTS |
| `MC <url>` | lit un MP3 | fort | moyen | variante de lecture |
| `MW` | wait | fort | moyen | séquencement |
| `ST <url>` | stream | fort | moyen | radio / stream |
| `SP <url>` | stream | fort | moyen | variante |
| `ID` | identifié par jNabServer | moyen | faible | peu documenté dans le détail |

## 9. Chorégraphies textuelles de l’API publique

### Tempo

| Élément | Sens | Valeurs | Certitude |
|---|---|---|---|
| première valeur | tempo | ex. `10` = dixième de seconde | fort |

### Commande `motor`

Format :

`heure,motor,oreille,angle,0,sens`

| Champ | Sens | Valeurs | Certitude |
|---|---|---|---|
| `heure` | moment de l’action | entier | fort |
| `motor` | type de commande | littéral | fort |
| `oreille` | cible | `1` = gauche, `0` = droite | fort |
| `angle` | angle | `0` à `180` | fort |
| 5e argument | inutilisé | `0` | fort |
| `sens` | sens de rotation | `0` ou `1` | fort |

### Commande `led`

Format :

`heure,led,cible,r,g,b`

| Champ | Sens | Valeurs | Certitude |
|---|---|---|---|
| `heure` | moment de l’action | entier | fort |
| `led` | type de commande | littéral | fort |
| `cible` | LED ciblée | `0` bas, `1` gauche, `2` milieu, `3` droite, `4` haut | fort |
| `r,g,b` | couleur | `0` à `255` | fort |

## 10. Capacités device documentées

| Capacité | Documentée | Certitude | Remarques |
|---|---|---|---|
| oreilles motorisées | oui | fort | positions suivies par capteurs optiques selon certaines sources |
| cinq LEDs | oui | fort | haut, gauche, milieu, droite, bas |
| bouton simple clic | oui | fort | événement |
| bouton double clic | oui | fort | événement |
| mouvement manuel des oreilles | oui | fort | événement |
| RFID ISO 14443 B | oui | fort | Ztamp |
| micro | oui | fort | enregistrement après appui long |
| haut-parleur / lecture audio | oui | fort | MP3, stream |

## 11. État réel vs état commandé

| Élément | Peut être commandé | Peut être relu explicitement dans les docs trouvées | Conclusion |
|---|---|---|---|
| oreille gauche | oui | non clairement | on a une commande fiable, pas une télémétrie publique claire |
| oreille droite | oui | non clairement | même situation |
| LEDs | oui | non clairement | la commande est documentée, la lecture d’état ne l’est pas clairement |
| enregistrement audio | oui côté bouton / event | oui via `record.jsp` | upload confirmé |
| RFID | oui côté événement device | oui via `rfid.jsp` | remontée confirmée |

Conclusion pratique :

- la documentation retrouvée décrit très bien comment envoyer des instructions
- elle décrit beaucoup moins bien comment obtenir un état physique réel du lapin
- pour les oreilles et LEDs, on dispose surtout d’un “état commandé” plutôt que d’une lecture matérielle garantie

## 12. Mapping rapide avec notre projet

| Besoin projet | Élément historique le plus pertinent | Action recommandée |
|---|---|---|
| boot du lapin | `bc.jsp`, `locate.jsp` | déjà central, continuer à documenter |
| reset logiciel | bloc `09` reboot, ou stratégie `disconnect/connect` | explorer les deux |
| oreilles | bloc `04`, commande `motor`, `posleft` / `posright` | piloter par instruction, afficher comme état estimé |
| LEDs | `CL`, `led`, ambient, chorégraphies | piloter par instruction, afficher comme état estimé |
| voix / audio | `MU`, `MC`, TTS API | continuer via génération audio serveur |
| scénarios riches | `CH`, chorégraphies | piste forte pour enrichir l’expressivité |
| Ztamp | `rfid.jsp` | déjà exploitable |
| voice pipeline | `record.jsp` | déjà exploitable |

## 13. Priorités de recherche restantes

| Sujet | Importance | Pourquoi |
|---|---|---|
| sémantique exacte de `p4.jsp` | élevée | clé pour distinguer heartbeat et événements |
| fonctionnement réel de `violet:iq:sources` hors boot | élevée | peut aider à mieux synchroniser l’état |
| lecture effective de l’état oreilles / LEDs | élevée | utile pour watchdog et diagnostics |
| bloc `09` dans les implémentations réelles | moyenne | utile pour un reset plus propre |
| rôle précis du `ttl` XMPP | moyenne | optimisation / cache |
| détail du langage Metal | moyenne | utile si on veut aller plus bas niveau |
