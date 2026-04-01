# Application mobile Nabaztag

MVP Expo pour :

- scanner un QR code d'appairage généré par le portail
- récupérer les lapins du compte
- afficher leur statut
- envoyer du texte au pipeline conversationnel d'un lapin

## Démarrage

```bash
npm install
npm run dev:mobile
```

## Limites actuelles

- le wake phrase `OK Nabaztag` n'est pas encore branché
- la reconnaissance vocale locale téléphone reste à intégrer
- le token mobile est gardé en mémoire dans le MVP, pas encore persisté
