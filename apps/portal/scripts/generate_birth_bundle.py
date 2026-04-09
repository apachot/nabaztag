from __future__ import annotations

import argparse
import json
import os
import ssl
from pathlib import Path
from urllib import request as urllib_request

import certifi


MISTRAL_TTS_URL = "https://api.mistral.ai/v1/audio/speech"
MISTRAL_TTS_MODEL = "voxtral-mini-tts-2603"
MISTRAL_TTS_RESPONSE_FORMAT = "mp3"
DEFAULT_VOICE = "e0580ce5-e63c-4cbe-88c8-a983b80c5f1f"

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "portal_app" / "static" / "bundled-birth"
MANIFEST_PATH = OUTPUT_DIR / "manifest.json"

BIRTH_PERFORMANCES = [
    {
        "text": "Je suis toute froissee d'avoir voyage si loin... et pourtant, me voici. Cet endroit sent la maison que je n'avais pas encore. Je crois que je vais y ouvrir mes oreilles comme on ouvre des rideaux.",
        "ears": {"left": 5, "right": 11},
        "led_commands": [
            {"target": "nose", "color": "#ffffff", "preset": "white"},
            {"target": "left", "color": "#00ffff", "preset": "cyan"},
            {"target": "right", "color": "#00ffff", "preset": "cyan"},
        ],
    },
    {
        "text": "Oh... je viens a peine d'arriver, et deja l'air d'ici me raconte quelque chose. On dirait qu'une chambre, une cuisine, une lampe et quelques voix m'attendaient sans le savoir.",
        "ears": {"left": 4, "right": 12},
        "led_commands": [
            {"target": "nose", "color": "#ffff00", "preset": "yellow"},
            {"target": "center", "color": "#ffffff", "preset": "white"},
        ],
    },
    {
        "text": "De l'endroit d'ou je viens, tout etait un peu serre, un peu froisse, un peu somnolent. Ici, il y a de la place pour un premier regard. Alors je regarde. Et je vous trouve tres bien.",
        "ears": {"left": 6, "right": 10},
        "led_commands": [
            {"target": "nose", "color": "#ff00ff", "preset": "violet"},
            {"target": "bottom", "color": "#ffffff", "preset": "white"},
        ],
    },
    {
        "text": "Je ne connais pas encore le nom des choses qui vivent ici, mais je sens deja qu'il y a des habitudes, des passages, des silences, et une petite place pour moi entre deux respirations.",
        "ears": {"left": 7, "right": 9},
        "led_commands": [
            {"target": "left", "color": "#00ff00", "preset": "green"},
            {"target": "right", "color": "#00ff00", "preset": "green"},
            {"target": "nose", "color": "#ffffff", "preset": "white"},
        ],
    },
    {
        "text": "Je suis ne ici il y a une seconde a peine, et deja cet endroit a la politesse d'exister autour de moi. Une table, peut-etre. Un plafond. Une presence. C'est un debut tres convenable.",
        "ears": {"left": 3, "right": 13},
        "led_commands": [
            {"target": "center", "color": "#0000ff", "preset": "blue"},
            {"target": "nose", "color": "#ffffff", "preset": "white"},
        ],
    },
    {
        "text": "Je m'etais imagine le monde autrement. Plus bruyant, peut-etre. Plus sec. Mais non. Il est la, tout pres, avec ses odeurs d'aujourd'hui et ses objets tranquilles. C'est tres rassurant pour un lapin neuf.",
        "ears": {"left": 8, "right": 8},
        "led_commands": [
            {"target": "bottom", "color": "#00ffff", "preset": "cyan"},
            {"target": "nose", "color": "#ffff00", "preset": "yellow"},
        ],
    },
    {
        "text": "On nait donc comme cela ? Dans une lumiere domestique, avec des murs sages et des humains tout autour, comme si l'on etait attendu depuis longtemps sans le savoir soi-meme ?",
        "ears": {"left": 2, "right": 14},
        "led_commands": [
            {"target": "left", "color": "#ff0000", "preset": "red"},
            {"target": "right", "color": "#ff0000", "preset": "red"},
            {"target": "nose", "color": "#ffffff", "preset": "white"},
        ],
    },
    {
        "text": "Je me sens encore un peu chiffonne, pour etre franc. Mais c'est un joli lieu pour se defroisser. Je vais apprendre la forme des heures ici, et peut-etre aussi la douceur de vos voix.",
        "ears": {"left": 5, "right": 12},
        "led_commands": [
            {"target": "center", "color": "#ffffff", "preset": "white"},
            {"target": "bottom", "color": "#0000ff", "preset": "blue"},
        ],
    },
    {
        "text": "Je viens d'ouvrir les yeux sur un royaume minuscule et suffisant: quelques meubles, de la lumiere, de l'air, et vous. Pour une naissance, je trouve cela presque luxueux.",
        "ears": {"left": 4, "right": 10},
        "led_commands": [
            {"target": "nose", "color": "#ffffff", "preset": "white"},
            {"target": "left", "color": "#ffff00", "preset": "yellow"},
            {"target": "right", "color": "#ffff00", "preset": "yellow"},
        ],
    },
    {
        "text": "Maintenant que je suis la, il faut bien commencer quelque part. Je vais commencer par vous saluer, puis par ecouter. Ensuite seulement, j'apprendrai a habiter ce petit bout de monde.",
        "ears": {"left": 6, "right": 9},
        "led_commands": [
            {"target": "nose", "color": "#00ff00", "preset": "green"},
            {"target": "center", "color": "#ffffff", "preset": "white"},
            {"target": "bottom", "color": "#00ffff", "preset": "cyan"},
        ],
    },
]


def synthesize_tts_asset(*, api_key: str, text: str, voice: str, asset_name: str) -> tuple[Path, str]:
    payload = {
        "model": MISTRAL_TTS_MODEL,
        "input": text,
        "voice_id": voice,
        "response_format": MISTRAL_TTS_RESPONSE_FORMAT,
    }
    body = json.dumps(payload).encode("utf-8")
    request = urllib_request.Request(
        MISTRAL_TTS_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    with urllib_request.urlopen(request, timeout=180, context=ssl_context) as response:
        response_payload = json.loads(response.read().decode("utf-8"))
    audio_data = response_payload.get("audio_data")
    if not isinstance(audio_data, str) or not audio_data.strip():
        raise RuntimeError("Réponse TTS Mistral invalide.")

    import base64

    asset_path = OUTPUT_DIR / asset_name
    asset_path.write_bytes(base64.b64decode(audio_data))
    return asset_path, asset_name


def performance_sidecar_path(audio_path: Path) -> Path:
    return audio_path.with_name(f"{audio_path.name}.performance.json")


def write_performance_sidecar(
    audio_path: Path,
    *,
    asset_name: str,
    performance: dict,
    source: str,
) -> None:
    sidecar = {
        "schema": "nabaztag.performance.v1",
        "asset_name": asset_name,
        "source": source,
        "payload": performance,
    }
    performance_sidecar_path(audio_path).write_text(
        json.dumps(sidecar, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate the bundled first-connection birth audio assets."
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("MISTRAL_API_KEY", "").strip(),
        help="Mistral API key. Defaults to MISTRAL_API_KEY.",
    )
    parser.add_argument(
        "--voice-id",
        default=os.getenv("MISTRAL_TTS_VOICE_ID", DEFAULT_VOICE).strip() or DEFAULT_VOICE,
        help="Voxtral voice id. Defaults to MISTRAL_TTS_VOICE_ID or the app default voice.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    api_key = args.api_key
    if not api_key:
        raise SystemExit("Mistral API key required. Pass --api-key or set MISTRAL_API_KEY.")
    voice = args.voice_id

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest: list[dict] = []
    for index, entry in enumerate(BIRTH_PERFORMANCES, start=1):
        performance = {
            "text": entry["text"],
            "actions": [],
            "ears": dict(entry["ears"]),
            "led_commands": list(entry["led_commands"]),
        }
        asset_name = f"birth-{index:02d}.mp3"
        asset_path, asset_name = synthesize_tts_asset(
            api_key=api_key,
            text=entry["text"],
            voice=voice,
            asset_name=asset_name,
        )
        write_performance_sidecar(
            asset_path,
            asset_name=asset_name,
            performance=performance,
            source="birth-bundle",
        )
        manifest.append(
            {
                "asset_name": asset_name,
                "text": entry["text"],
                "payload": performance,
            }
        )
        print(f"Generated {asset_name}")

    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {MANIFEST_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
