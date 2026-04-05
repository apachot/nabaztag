# Nabaztag macOS Client

Client macOS minimal pour :

- se connecter à son compte `nabaztag.org`
- afficher directement la liste des lapins du compte
- aider à mettre en service un lapin localement sur `192.168.0.1`
- parler à un lapin depuis le bureau
- piloter un lapin directement depuis le bureau

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

### Signature et notarization Apple

Par défaut, `build_dmg.sh` produit un `.dmg` non signé. macOS affichera alors l’avertissement Gatekeeper habituel.

Pour produire un `.dmg` proprement distribuable :

```bash
export APPLE_DEVELOPER_IDENTITY="Developer ID Application: ..."
export APPLE_NOTARY_PROFILE="notarytool-profile"
cd apps/macos_client
./build_dmg.sh
```

Alternative sans profil `notarytool` préenregistré :

```bash
export APPLE_DEVELOPER_IDENTITY="Developer ID Application: ..."
export APPLE_ID="..."
export APPLE_TEAM_ID="..."
export APPLE_APP_PASSWORD="...."
cd apps/macos_client
./build_dmg.sh
```

Le script :

- signe l’application `.app`
- construit le `.dmg`
- signe le `.dmg`
- soumet le `.dmg` à Apple via `notarytool`
- applique le `staple` si la notarization réussit

## Ce que fait cette version

- connexion de l'application au compte via email et mot de passe
- affichage des lapins du compte
- détection du Wi-Fi du Mac pour préparer la mise en service d'un lapin
- test du configurateur local du lapin sur `192.168.0.1`
- tentative de configuration locale du Wi-Fi + `Violet Platform`
- envoi d'un message texte à un lapin
- pilotage direct des oreilles, LEDs, radio et sommeil/réveil

## Limites

- packaging macOS prévu pour une construction sur macOS
- la configuration automatique du lapin repose sur une détection best effort des formulaires locaux
