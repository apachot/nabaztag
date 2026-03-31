# Cas d'usage intéressants à partir de la documentation collectée

Ce document synthétise les cas d'usage rendus plausibles par :

- la documentation historique du protocole
- le croisement avec OpenJabNab
- l'analyse d'écart avec notre couche `nabd`
- la reconnaissance matérielle déjà réalisée

Objectif :

- distinguer les usages activables immédiatement
- séparer ceux qui demandent un travail protocolaire ou firmware
- guider l'évolution de la fiche d'un lapin et de la roadmap produit

## 1. Usages activables immédiatement

| Cas d'usage | Valeur produit | Primitives actuelles | Statut |
|---|---|---|---|
| Scenes expressives courtes | rendre le lapin plus incarné qu'un simple haut-parleur | voix + oreilles + LEDs | testable |
| Improvisation domestique | divertissement spontané | Mistral + voix + oreilles + LEDs | testable |
| Radio / stream ambiant | compagnon sonore de maison | lecture audio distante | testable |
| Scenario Ztamp | interaction tangible objet -> performance | RFID + génération + expressivité | testable |
| Presence lumineuse / humeur | signalisation douce sans écran | LEDs et nez | déjà partiellement là |

## 2. Usages très intéressants mais partiellement bloqués

| Cas d'usage | Intérêt | Blocage principal | Niveau |
|---|---|---|---|
| Veille / réveil natif | rythmer la vie domestique du lapin | commande sleep/wake non branchée dans notre stack | moyen |
| Reboot logiciel propre | fiabilité et maintenance | reboot `0x09` non exposé par notre couche actuelle | moyen |
| Etat réel des oreilles | debug, UX fiable, watchdog | télémétrie non fiabilisée côté pile actuelle | moyen |
| Etat réel des LEDs | observabilité | pas de remontée claire trouvée | moyen |
| Session interactive persistante | conversation plus fluide | couche `nabd` encore trop haut niveau / éphémère | moyen |

## 3. Usages qui poussent vers un travail device / firmware

| Cas d'usage | Valeur | Dépendance | Niveau |
|---|---|---|---|
| Stop recording au silence | conversation naturelle | logique locale de capture audio | élevé |
| Wake word local | interaction mains libres | device audio + algo local | élevé |
| Watchdog matériel / audio | robustesse | introspection device plus fine | élevé |
| API embarquée de santé | diagnostic | firmware / daemon plus riche | élevé |
| Gestion avancée des buffers audio | qualité et stabilité | pile audio device | élevé |

## 4. Cas d'usage les plus prometteurs pour le projet

### 4.1 Court terme

1. scenes expressives pretes a l'emploi
2. improvisation multimodale
3. radio / ambiance domestique
4. scenarios Ztamp

### 4.2 Moyen terme

1. veille / reveil natif
2. reboot logiciel propre
3. etat reel oreilles / LEDs
4. watchdog prudent

### 4.3 Long terme

1. wake word local
2. conversation vraiment mains libres
3. firmware ou couche device enrichie

## 5. Interfaces de test ajoutees sur la fiche d'un lapin

La fiche du lapin peut servir de laboratoire produit. Les interfaces les plus utiles sont :

- lancement de scenes expressives
- improvisation domestique
- test de flux audio / radio
- scenario Ztamp manuel

Ces interfaces ne remplacent pas les usages finaux, mais elles permettent de valider rapidement la desirabilite et les limites techniques.

## 6. Principe de priorisation

La meilleure logique pour le projet reste :

- exploiter d'abord tout ce que l'architecture client-serveur permet sans toucher au lapin
- documenter clairement les ecarts quand une fonction demande un niveau de controle plus bas
- ne basculer vers le firmware que lorsque les verrous restants sont clairement cote device
