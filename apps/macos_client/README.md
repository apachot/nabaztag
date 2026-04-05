# Nabaztag macOS Client

Client macOS minimal pour:

- appairer un `bridge local`
- lancer ou arrêter la boucle du bridge
- visualiser l'état du bridge
- appairer un compagnon macOS
- appairer l'application macOS au compte
- récupérer la liste des lapins
- parler à un lapin depuis le bureau
- piloter un lapin directement depuis le bureau
- rattacher un Nabaztag à un lapin via un code temporaire généré sur le site

Le client est volontairement léger et réutilise le protocole du bridge local déjà présent dans le portail.

## Lancer en mode développement

```bash
python3 apps/macos_client/app.py
```

## Construire une app macOS

Le dossier contient une base `py2app` pour produire une application macOS.

```bash
cd apps/macos_client
python3 -m pip install -e .
python3 setup.py py2app
```

L'app générée se trouve ensuite dans `dist/`.

## Ce que fait cette première version

- appairage avec `https://nabaztag.org`
- stockage local de la config bridge
- démarrage local de la boucle `run`
- affichage de l'état du bridge
- appairage compagnon via le code mobile du portail
- appairage de l'application au compte via un code temporaire généré sur le portail
- affichage des lapins du compte
- envoi d'un message texte à un lapin
- pilotage direct des oreilles, LEDs, radio et sommeil/réveil
- appairage d'un lapin via un code temporaire saisi dans l'app

## Limites

- pas encore de packaging `.dmg`
- pas encore de login utilisateur dédié dans l'app
