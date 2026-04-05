# Nabaztag macOS Client

Client macOS minimal pour :

- se connecter à son compte `nabaztag.org`
- afficher directement la liste des lapins du compte
- parler à un lapin depuis le bureau
- piloter un lapin directement depuis le bureau
- rattacher un Nabaztag à un lapin via un code temporaire généré sur le site

## Lancer en mode développement

```bash
python3 apps/macos_client/app.py
```

## Construire une app macOS / DMG

Le dossier contient une base `py2app` pour produire une application macOS, puis un `.dmg`.

```bash
cd apps/macos_client
./build_dmg.sh
```

L'app générée se trouve dans `dist/` et le `.dmg` final dans :

```bash
apps/portal/portal_app/static/downloads/nabaztag-macos-client.dmg
```

## Ce que fait cette version

- connexion de l'application au compte via email et mot de passe
- affichage des lapins du compte
- envoi d'un message texte à un lapin
- pilotage direct des oreilles, LEDs, radio et sommeil/réveil
- appairage d'un lapin via un code temporaire saisi dans l'app

## Limites

- packaging macOS prévu pour une construction sur macOS
