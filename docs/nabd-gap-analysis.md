# Analyse d'écart entre notre couche `nabd` et le protocole Nabaztag historique

Ce document vise à clarifier un point devenu central dans le projet :

- ce que notre intégration actuelle sait faire via le protocole JSONL de `nabd`
- ce que le protocole Nabaztag historique permet plus bas niveau
- ce que le code OpenJabNab confirme réellement
- les écarts qu'il reste à combler si l'on veut aller vers des fonctions plus proches du matériel

Il complète :

- [nabaztag-protocol-research.md](/Users/apachot/Documents/GitHub/nabaztag/docs/nabaztag-protocol-research.md)
- [nabaztag-protocol-matrix.md](/Users/apachot/Documents/GitHub/nabaztag/docs/nabaztag-protocol-matrix.md)
- [openjabnab-crosswalk.md](/Users/apachot/Documents/GitHub/nabaztag/docs/openjabnab-crosswalk.md)

## 1. Ce que notre pile actuelle appelle "protocole"

Dans ce dépôt, la couche matérielle réelle est aujourd’hui abordée via un client TCP JSONL vers `nabd`.

Références :

- [commands.py](/Users/apachot/Documents/GitHub/nabaztag/apps/api/app/protocol/commands.py)
- [client.py](/Users/apachot/Documents/GitHub/nabaztag/apps/api/app/protocol/client.py)
- [protocol-notes.md](/Users/apachot/Documents/GitHub/nabaztag/docs/protocol-notes.md)

Les commandes aujourd’hui construites par notre code sont :

- `{"type":"mode", ...}`
- `{"type":"state"}`
- `{"type":"info", ...}`
- `{"type":"ears", ...}`
- `{"type":"command", ...}`
- `{"type":"recording_start", ...}`
- `{"type":"recording_stop", ...}`

Mais côté client effectif, seules sont réellement gérées :

- `connect`
- `disconnect`
- `sync`
- `info`
- `ears`
- `command`

## 2. Ce que cette couche sait faire aujourd’hui

### Confirmé et effectivement exploité

- synchroniser un état initial via un paquet `state`
- passer le lapin en `idle` ou `interactive`
- bouger les oreilles
- piloter les LEDs de corps en mode idle via `info`
- lancer une séquence audio/chorégraphie via `command`

### Partiellement exploité

- lecture d’état distant général
- affichage des oreilles gauche/droite dans le portail

### Non exploité ou non supporté

- reboot logiciel du lapin
- lecture publique fiable de l’état réel des LEDs
- enregistrement audio distant start/stop avec récupération du fichier
- contrôle natif nez / LED du bas en mode `protocol`

## 3. Ce que le protocole historique permet plus bas niveau

Le croisement avec la documentation historique et OpenJabNab confirme l’existence d’un niveau de protocole plus bas que notre couche JSONL :

- paquets binaires encapsulés par `0x7F ... 0xFF`
- bloc ambient `0x04`
- bloc message `0x0A`
- bloc sleep `0x0B`
- bloc reboot `0x09`
- trames de type `3`, `4`, `9`, `10`, `11` traitées par le bootcode

Référence :

- [openjabnab-crosswalk.md](/Users/apachot/Documents/GitHub/nabaztag/docs/openjabnab-crosswalk.md)

## 4. Ce qu’OpenJabNab confirme au-dessus de la doc

OpenJabNab confirme notamment :

- le reboot `0x09` est bien traité côté bootcode
- le lapin remonte bien des événements XMPP de mouvement d’oreilles
- `record.jsp` peut être retenté côté lapin, ce qui explique des doublons d’upload
- `locate.jsp` fournit bien les paramètres `ping` et `broad`

Mais OpenJabNab confirme aussi une limite :

- l’API publique qu’il expose ne fournit pas proprement les vraies positions d’oreilles
- le code contient même `TODO: send real positions`

Donc :

- la remontée d’oreilles existe au niveau protocolaire
- mais elle n’est pas forcément visible au niveau API applicatif exposé aux intégrateurs

## 5. Écart principal n°1 : reboot

### Côté protocole historique

- le reboot `0x09` existe
- le bootcode le traite explicitement

### Côté notre couche `nabd`

Je n’ai trouvé dans ce dépôt :

- aucune commande JSON `reboot`
- aucune mention documentée de `restart` ou `shutdown`
- aucune branche de traitement côté client pour un reboot

### Conclusion

Le reboot est :

- confirmé au niveau protocolaire historique
- non confirmé au niveau interface JSON `nabd` utilisée par notre stack

Tant que l’on n’a pas la doc ou le code du vrai démon `nabd`, ajouter un reboot dans notre API reviendrait à inventer un paquet non documenté.

## 6. Écart principal n°2 : état réel des oreilles

### Ce que l’on sait

- OpenJabNab reçoit `<ears><left>..</left><right>..</right></ears>` en XMPP
- donc il existe une remontée réelle device -> serveur

### Ce que notre stack fait aujourd’hui

- notre modèle sait stocker `left_ear` et `right_ear`
- le portail les affiche
- mais nous complétons encore souvent l’état par reconstruction depuis les dernières commandes locales

Références :

- [events.py](/Users/apachot/Documents/GitHub/nabaztag/apps/api/app/protocol/events.py)
- [main.py](/Users/apachot/Documents/GitHub/nabaztag/apps/portal/portal_app/main.py)

### Conclusion

L’état oreilles est aujourd’hui :

- potentiellement observable au niveau device
- mais pas encore exploité comme vraie télémétrie fiable dans notre pile

## 7. Écart principal n°3 : état réel des LEDs

Je n’ai pas trouvé dans les sources inspectées :

- d’équivalent propre à `<ears>` pour les LEDs
- d’API publique OpenJabNab exposant un état réel courant des LEDs

Dans notre pile actuelle, l’état LED présenté est donc principalement :

- reconstruit depuis les dernières commandes
- ou repris depuis un état distant déjà agrégé

Conclusion :

- pour les LEDs, nous restons dans un modèle d’état commandé ou estimé

## 8. Écart principal n°4 : enregistrement

Notre documentation locale du protocole dit explicitement :

- pas de primitive documentée de start/stop recording brut avec récupération audio

Référence :

- [protocol-notes.md](/Users/apachot/Documents/GitHub/nabaztag/docs/protocol-notes.md)

Même si notre couche a des builders `recording_start` et `recording_stop`, le gateway les rejette en mode `protocol`.

Conclusion :

- la surface API existe chez nous
- la capacité protocolaire réelle n’est pas démontrée
- il faut continuer à considérer l’enregistrement comme non supporté dans ce mode

## 9. Tableau de synthèse

| Fonction | Protocole historique | OpenJabNab | Notre couche `nabd` actuelle | Statut projet |
|---|---|---|---|---|
| Bouger les oreilles | oui | oui | oui | supporté |
| Jouer de l’audio | oui | oui | oui | supporté |
| LEDs corps idle | oui | oui | oui | supporté partiellement |
| LED nez | oui | oui | non en `protocol` | supporté hors `protocol` |
| LED bas | oui | oui | non en `protocol` | supporté hors `protocol` |
| Sleep / wake | oui | oui | partiellement documenté | piste solide |
| Reboot | oui (`0x09`) | oui | non documenté | écart important |
| État oreilles réel | partiel | reçu côté XMPP | non fiabilisé | écart important |
| État LEDs réel | flou | non trouvé | non fiabilisé | écart important |
| Start/stop recording | flou | non démontré proprement | non supporté | écart important |

## 10. Ce que cela change pour le projet

### Ce qu’on peut dire sans ambiguïté

- notre couche `nabd` actuelle est une couche de contrôle haut niveau, pas une implémentation exhaustive du protocole Nabaztag historique
- OpenJabNab valide l’existence d’un niveau plus bas et plus riche que ce que nous exploitons aujourd’hui
- certaines fonctions attendues intuitivement, comme `reboot`, ne peuvent pas être ajoutées sérieusement sans documentation ou code du démon sous-jacent

### Ce qu’il faut présenter prudemment dans l’interface

- oreilles : état possiblement réel, mais pas encore garanti par notre pile
- LEDs : état estimé ou commandé
- connexion : état sessionnel, pas santé matérielle complète

## 11. Prochaines actions techniques utiles

1. Obtenir et auditer le vrai code source de `nabd`, ou au minimum sa documentation de protocole JSON.
2. Vérifier si le paquet `state` de `nabd` contient déjà plus d’informations que ce que nous fusionnons aujourd’hui.
3. Tester empiriquement, sur un lapin de dev, l’existence d’une commande JSON de reboot non documentée seulement si une source sérieuse l’indique.
4. Séparer dans l’UI :
   - `état confirmé par le device`
   - `état reconstruit par le serveur`

## 12. Conclusion

Le point le plus important est le suivant :

- notre pile actuelle sait déjà beaucoup piloter
- mais elle ne couvre pas encore toute la richesse du protocole Nabaztag historique

Le principal verrou n’est plus l’interface du portail ou de l’API applicative. Le verrou est désormais la connaissance précise de la couche `nabd` elle-même et de ce qu’elle expose réellement au-dessus du protocole historique.
