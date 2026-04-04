# Nabaztag macOS Client

Client macOS minimal pour:

- appairer un `bridge local`
- lancer ou arrêter la boucle du bridge
- visualiser l'état du bridge

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

## Limites

- pas encore de pilotage graphique des lapins
- pas encore de packaging `.dmg`
- pas encore de login utilisateur dédié dans l'app
