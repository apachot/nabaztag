# Reconnaissance matérielle du Nabaztag:tag v2

Ce document rassemble ce que l’on sait aujourd’hui de l’architecture matérielle du `Nabaztag:tag v2`, dans la perspective d’un éventuel travail plus bas niveau sur le device :

- adaptation du bootcode
- compréhension de la chaîne de démarrage
- possibilité future d’un firmware enrichi
- identification des limites matérielles réelles

Le principe de ce document est volontairement strict :

- séparer les faits confirmés
- distinguer les indices techniques
- isoler les hypothèses

## 1. Ce qui est confirmé

### 1.1 Capacités matérielles générales

Les sources publiques et communautaires confirment que le Nabaztag:tag v2 dispose au minimum de :

- Wi‑Fi `2.4 GHz`
- lecteur RFID `13.56 MHz`
- microphone
- haut-parleur
- bouton
- oreilles motorisées avec détection de position
- cinq LEDs

Sources :

- [nabaztag.com](https://nabaztag.com/)
- [docs.nabaztag.com](https://docs.nabaztag.com/nabaztag-getting-started/nabaztag-v2)
- [web3.lu](https://www.web3.lu/tag/nabaztag/)

### 1.2 Existence d’un code embarqué exécutable

Le comportement du lapin repose sur un bootcode téléchargé puis exécuté côté device. Ce code :

- pilote les oreilles
- pilote les LEDs
- lit de l’audio
- enregistre du son
- remonte des événements
- traite les trames reçues du serveur

Sources :

- [web3.lu](https://www.web3.lu/tag/nabaztag/)
- code OpenJabNab inspecté dans `/tmp/OpenJabNab-src/bootcode/sources/main.mtl`

### 1.3 Présence d’une couche flash / firmware

Les sources du bootcode OpenJabNab montrent l’existence de primitives de flash :

- `read_uc_flash`
- `write_uc_flash`
- `flash_uc`
- opcode `flashFirmware`

Cela confirme qu’il existe bien, en dessous du simple bootcode applicatif, une couche de firmware ou au moins une image persistante réinscriptible.

Références locales :

- `/tmp/OpenJabNab-src/bootcode/compiler/mtl_linux/vlog.c`
- `/tmp/OpenJabNab-src/bootcode/compiler/mtl_linux/vinterp.c`
- `/tmp/OpenJabNab-src/bootcode/compiler/mtl_linux/vbc.h`
- `/tmp/OpenJabNab-src/bootcode/compiler/mtl_linux/vbc_str.h`

### 1.4 Indice fort d’une architecture ARM

Les sources OpenJabNab contiennent :

- `#include "inarm.h"`

Cela ne suffit pas à identifier le SoC exact, mais c’est un indice fort en faveur d’une cible ARM.

Référence locale :

- `/tmp/OpenJabNab-src/bootcode/compiler/mtl_linux/vlog.c`

### 1.5 Indice fort d’une puce Wi‑Fi Ralink RT2501

Les sources du bootcode font explicitement référence à :

- `rt2501usb.h`
- `rt2501_state`
- `rt2501_send`
- `rt2501_scan`
- `rt2501_auth`

Cela indique fortement que le sous-système Wi‑Fi s’appuie sur une puce de la famille `Ralink RT2501`.

Références locales :

- `/tmp/OpenJabNab-src/bootcode/compiler/mtl_linux/vnet.c`
- `/tmp/OpenJabNab-src/bootcode/compiler/mtl_linux/vlog.c`

## 2. Ce que les dossiers FCC apportent

Le dossier FCC du modèle `TYR-TAGTAG` met à disposition :

- `Block Diagram`
- `Schematics`
- `Internal Photos`
- `Operational Description`
- `Test Report`

Source :

- [FCC ID TYR-TAGTAG](https://fccid.io/TYR-TAGTAG)

Ce point est important, parce qu’il veut dire que l’identification du CPU, de la mémoire, des interfaces et de l’étage audio ne repose pas uniquement sur la rétro-ingénierie logicielle. On a aussi une base documentaire matérielle exploitable.

Ce que le dossier FCC confirme déjà explicitement :

- `2.412-2.462 GHz` pour le Wi‑Fi
- `13.553-13.557 MHz` pour la partie RFID

Source :

- [FCC ID TYR-TAGTAG](https://fccid.io/TYR-TAGTAG)

## 3. Ce que l’on peut raisonnablement inférer

### 3.1 Le Nabaztag n’est pas un microcontrôleur minimaliste

Le cumul de ces fonctions :

- Wi‑Fi
- MP3
- enregistrement audio
- RFID
- moteur d’oreilles
- exécution d’un bytecode applicatif

suggère un système embarqué relativement riche pour l’époque, plus proche d’une petite plate-forme embarquée spécialisée que d’un microcontrôleur extrêmement contraint.

Cette inférence est cohérente avec :

- la présence d’un interpréteur de bytecode
- les opérations de flash
- la pile réseau
- le décodage MP3

### 3.2 Il y a probablement plusieurs couches logicielles

Au minimum, on peut distinguer :

- une couche bas niveau persistante
- un bootcode ou runtime téléchargé
- une logique applicative exécutée côté lapin

Cela veut dire que “faire un nouveau firmware” peut désigner plusieurs choses très différentes :

- modifier le bootcode uniquement
- reconstruire une image plus basse
- remplacer complètement la logique embarquée

## 4. Ce que nous ne savons pas encore proprement

À ce stade, je n’ai pas trouvé de preuve solide, documentée et recoupée sur :

- la référence exacte du CPU / SoC principal
- la quantité exacte de RAM
- la quantité exacte de flash
- la carte mémoire complète
- le chargeur de boot exact
- la chaîne de démarrage détaillée
- les interfaces exactes entre CPU, audio, moteurs et RFID
- la procédure sûre de reflash complet

Autrement dit :

- nous avons des indices sérieux
- mais pas encore une caractérisation suffisante pour lancer sans risque un vrai chantier de firmware complet

## 5. Ce que cela implique pour un éventuel nouveau firmware

### 5.1 Ce qui devient crédible

Si l’architecture matérielle est suffisamment ouverte et comprise, un firmware enrichi pourrait théoriquement :

- exposer un vrai reboot logiciel
- remonter un état réel des oreilles
- remonter un état réel plus précis des LEDs
- mieux contrôler l’audio et les buffers
- ajouter une détection de silence locale
- ajouter un wake word local
- améliorer la robustesse des uploads audio

### 5.2 Ce qui reste bloquant aujourd’hui

Avant d’aller vers un firmware complet, il faut encore établir :

- le CPU exact
- la chaîne de build
- le format exact des images firmware
- la procédure de flash / recovery
- le niveau de brick risk

## 6. Ce qu’on peut déjà faire sans recompiler un firmware complet

Même sans firmware bas niveau, on a déjà de quoi agir sur un niveau utile :

- analyser le bootcode et ses capacités
- comprendre les primitives disponibles
- documenter les paquets et les états
- identifier quelles fonctions manquent seulement parce qu’elles ne sont pas exposées dans notre stack

En pratique, avant de toucher au firmware complet, le meilleur ratio valeur/risque reste probablement :

- audit plus fin du bootcode
- audit plus fin du démon `nabd`
- extraction des informations matérielles depuis les pièces FCC

## 7. Prochaines étapes réalistes

### 7.1 Priorité 1

Exploiter les documents FCC pour identifier :

- le CPU principal
- la RAM
- la flash
- le codec audio ou l’étage audio
- les liaisons RFID / Wi‑Fi / moteurs

### 7.2 Priorité 2

Comparer ces informations avec :

- les sources OpenJabNab
- les éventuels firmwares publiés
- les pages de mise à jour communautaires

### 7.3 Priorité 3

Déterminer si le premier chantier utile est :

- un nouveau bootcode
- une extension de `nabd`
- ou un vrai firmware complet

## 8. Conclusion

Oui, nous avons déjà des informations utiles sur l’architecture :

- indice fort `ARM`
- indice fort `Ralink RT2501`
- présence certaine d’une couche flashable
- disponibilité de schémas et photos internes via le FCC

Mais non, nous n’avons pas encore une connaissance assez précise du hardware pour lancer proprement un “nouveau firmware” sans phase préalable de reconnaissance matérielle plus méthodique.
