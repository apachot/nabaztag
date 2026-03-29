#!/usr/bin/env bash

set -euo pipefail

API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"
RABBIT_NAME="${RABBIT_NAME:-Lapin test}"
RABBIT_SLUG="${RABBIT_SLUG:-lapin-test}"

echo "Creating rabbit on ${API_BASE_URL}"

CREATE_RESPONSE="$(curl -fsS -X POST "${API_BASE_URL}/api/rabbits" \
  -H 'Content-Type: application/json' \
  -d "{\"name\":\"${RABBIT_NAME}\",\"slug\":\"${RABBIT_SLUG}\"}")"

RABBIT_ID="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])' <<< "${CREATE_RESPONSE}")"

echo "Rabbit id: ${RABBIT_ID}"

echo "Connect"
curl -fsS -X POST "${API_BASE_URL}/api/rabbits/${RABBIT_ID}/connect" \
  -H 'Content-Type: application/json' \
  -d '{"mode":"device"}'
echo

echo "Sync"
curl -fsS -X POST "${API_BASE_URL}/api/rabbits/${RABBIT_ID}/sync" \
  -H 'Content-Type: application/json' \
  -d '{}'
echo

echo "Move ears"
curl -fsS -X POST "${API_BASE_URL}/api/rabbits/${RABBIT_ID}/commands/ears" \
  -H 'Content-Type: application/json' \
  -d '{"left":4,"right":12}'
echo

echo "Play audio"
curl -fsS -X POST "${API_BASE_URL}/api/rabbits/${RABBIT_ID}/commands/audio" \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://example.com/demo.mp3"}'
echo

echo "Set center LED"
curl -fsS -X POST "${API_BASE_URL}/api/rabbits/${RABBIT_ID}/commands/led" \
  -H 'Content-Type: application/json' \
  -d '{"target":"center","color":"#ff6a3d"}'
echo

echo "Events"
curl -fsS "${API_BASE_URL}/api/rabbits/${RABBIT_ID}/events"
echo
