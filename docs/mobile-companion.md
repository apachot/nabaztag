# Companion mobile Nabaztag

## Objectif

Permettre à un iPhone ou un Android de servir d'interface vocale moderne pour les lapins :

- appairage par QR code
- liste des lapins et de leur statut
- capture voix sur téléphone
- envoi du texte reconnu au lapin
- réponse du lapin via le pipeline existant

## Architecture

### Portail

- `POST /mobile-api/v1/pairing/claim`
- `GET /mobile-api/v1/rabbits`
- `GET /mobile-api/v1/rabbits/<id>`
- `POST /mobile-api/v1/rabbits/<id>/conversation`

### Appairage

1. Le portail génère un QR code temporaire dans `Mon compte`
2. L'application le scanne
3. Le portail échange ce code contre un token API mobile
4. L'application utilise ensuite ce token en `Bearer`

### Flux conversationnel

1. Le téléphone reconnait la parole localement
2. Il envoie le texte au portail
3. Le portail injecte ce texte dans l'historique conversationnel du lapin
4. Le modèle Mistral génère une réponse expressive
5. Le lapin parle, bouge les oreilles et pilote ses LEDs

## Étapes suivantes

- brancher une vraie reconnaissance vocale locale sur téléphone
- ajouter un wake phrase `OK Nabaztag`
- persister le token mobile dans le secure storage du téléphone
- afficher aussi les alertes et l'historique de conversation
