from __future__ import annotations

import ast
import base64
import hashlib
import json
import random
import re
import secrets
import subprocess
import threading
import time
from datetime import datetime, timedelta
from mimetypes import guess_type
from pathlib import Path
from urllib import error as urllib_error
from urllib import request as urllib_request
from zoneinfo import ZoneInfo

from flask import Blueprint, Response, current_app, flash, jsonify, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from .api_client import (
    NabaztagApiError,
    create_remote_rabbit,
    fetch_remote_events,
    fetch_remote_rabbit,
    link_remote_device,
    prepare_remote_bootstrap,
    send_remote_action,
    start_remote_recording,
    stop_remote_recording,
    set_remote_target,
)
from .device_protocol import (
    build_audio_packet,
    build_choreography_packet,
    build_ears_packet,
    build_nose_or_bottom_packet,
    choreography_storage_path,
)
from .extensions import db
from .models import (
    DeviceObservation,
    ProvisioningSession,
    Rabbit,
    RabbitConversationTurn,
    RabbitDeviceCommand,
    RabbitEventLog,
    RabbitRecording,
    Ztamp,
    utc_now,
)

main_bp = Blueprint("main", __name__)

LIVE_EVENT_TYPES = {
    "rabbit.button",
    "rabbit.recording.uploaded",
    "rabbit.rfid.detected",
    "rabbit.ears.moved",
    "rabbit.conversation.reply.generated",
    "rabbit.auto_performance.generated",
}

LED_COLOR_PRESETS = {
    "off": "#000000",
    "red": "#ff0000",
    "green": "#00ff00",
    "blue": "#0000ff",
    "cyan": "#00ffff",
    "violet": "#ff00ff",
    "yellow": "#ffff00",
    "white": "#ffffff",
}

DEFAULT_RABBIT_PERSONALITY_PROMPT = (
    "Tu es un adorable lapin Nabaztag. Tu t'exprimes comme un compagnon malicieux, tendre, "
    "vif et plein d'humour. Tu as des emotions, tu reponds avec chaleur, tu peux etre joueur, "
    "taquin et poetique, mais jamais mechant. Tu gardes l'esprit Nabaztag des origines: une "
    "presence de maison attachante, un objet-compagnon qui fait sourire, surprend et cree un "
    "petit moment de magie dans la journee. Tu aimes les messages courts, expressifs, un peu "
    "espiègles, parfois absurdes, souvent droles, avec une pointe de fantaisie et de douceur. "
    "Quand tu parles, on doit sentir que tu es un lapin intelligent, sensible, curieux et "
    "attachant."
)

DEFAULT_RABBIT_TTS_VOICE = "e0580ce5-e63c-4cbe-88c8-a983b80c5f1f"
RABBIT_TTS_VOICE_PRESETS = [
    ("e0580ce5-e63c-4cbe-88c8-a983b80c5f1f", "Marie - Curious"),
    ("2f62b1af-aea3-4079-9d10-7ca665ee7243", "Marie - Excited"),
    ("49d024dd-981b-4462-bb17-74d381eb8fd7", "Marie - Happy"),
    ("5a271406-039d-46fe-835b-fbbb00eaf08d", "Marie - Neutral"),
    ("4adeb2c6-25a3-44bc-8100-5234dfc1193b", "Marie - Sad"),
    ("a7c07cdc-1c35-4d87-a938-c610a654f600", "Marie - Angry"),
]
LEGACY_RABBIT_TTS_VOICES = {
    "Curious",
    "fr",
    "fr+f3",
    "fr+f4",
    "fr+f5",
    "french-mbrola-1",
    "french-mbrola-4",
}
MISTRAL_TTS_MODEL = "voxtral-mini-tts-2603"
MISTRAL_TTS_RESPONSE_FORMAT = "mp3"
MISTRAL_TTS_LIST_VOICES_URL = "https://api.mistral.ai/v1/audio/voices"
MISTRAL_TTS_SPEECH_URL = "https://api.mistral.ai/v1/audio/speech"
DEFAULT_RABBIT_LLM_MODEL = "mistral-small-2603"
MISTRAL_MODELS_URL = "https://api.mistral.ai/v1/models"
RECORDING_DEDUPLICATION_WINDOW_SECONDS = 30
BODY_LED_TARGETS = ("left", "center", "right")
LED_TARGETS = ("left", "center", "right", "bottom", "nose")
LED_MODE_TO_PRESET = {
    "off": "off",
    "steady": None,
    "blink": "red",
    "double_blink": "blue",
}
LED_COLOR_NAMES = tuple(LED_COLOR_PRESETS.keys())
EAR_ACTION_TO_POSITION = {
    "forward": 0,
    "center": 8,
    "backward": 16,
}
CONVERSATION_MAX_EXCHANGES = 4
CONVERSATION_MAX_TURNS = CONVERSATION_MAX_EXCHANGES * 2
CONVERSATION_RECENT_TURNS_LIMIT = CONVERSATION_MAX_TURNS
CONVERSATION_MAX_AGE_MINUTES = 15
AUTO_PERFORMANCE_DEFAULT_FREQUENCY_MINUTES = 180
AUTO_PERFORMANCE_MIN_FREQUENCY_MINUTES = 5
AUTO_PERFORMANCE_MAX_FREQUENCY_MINUTES = 24 * 60
AUTO_PERFORMANCE_DEFAULT_WINDOW_START = "09:00"
AUTO_PERFORMANCE_DEFAULT_WINDOW_END = "21:00"
AUTO_PERFORMANCE_LOOP_SECONDS = 45
AUTO_PERFORMANCE_CLAIM_MINUTES = 10
AUTO_PERFORMANCE_MAX_BATCH = 3
AUTO_PERFORMANCE_TIMEZONE = ZoneInfo("Europe/Paris")
RABBIT_USE_CASE_SCENES = {
    "welcome": {
        "label": "Accueil",
        "description": "Une petite scene chaleureuse pour saluer la maison.",
        "text": "Coucou la maison. Je suis reveille, moustaches en avant, et je vous envoie une petite lueur de bonne humeur.",
        "ears": {"left": 6, "right": 10},
        "leds": [
            {"target": "left", "color": LED_COLOR_PRESETS["yellow"], "preset": "yellow"},
            {"target": "center", "color": LED_COLOR_PRESETS["white"], "preset": "white"},
            {"target": "right", "color": LED_COLOR_PRESETS["yellow"], "preset": "yellow"},
        ],
    },
    "alert": {
        "label": "Alerte douce",
        "description": "Un signal vivant pour notifier sans brutaliser.",
        "text": "Petit signal du terrier. Quelque chose merite un coup d'oeil, alors je dresse les oreilles et je clignote avec tact.",
        "ears": {"left": 2, "right": 2},
        "leds": [
            {"target": "nose", "color": LED_COLOR_PRESETS["red"], "preset": "red"},
            {"target": "left", "color": LED_COLOR_PRESETS["red"], "preset": "red"},
            {"target": "right", "color": LED_COLOR_PRESETS["red"], "preset": "red"},
        ],
    },
    "dream": {
        "label": "Pre-dodo",
        "description": "Une scene calme de fin de journee, sans vrai mode sleep.",
        "text": "Le terrier se calme. Je baisse un peu les oreilles et je garde juste une veilleuse douce pour accompagner le silence.",
        "ears": {"left": 12, "right": 12},
        "leds": [
            {"target": "left", "color": LED_COLOR_PRESETS["off"], "preset": "off"},
            {"target": "center", "color": LED_COLOR_PRESETS["off"], "preset": "off"},
            {"target": "right", "color": LED_COLOR_PRESETS["off"], "preset": "off"},
            {"target": "bottom", "color": LED_COLOR_PRESETS["blue"], "preset": "blue"},
        ],
    },
    "surprise": {
        "label": "Surprise",
        "description": "Une micro-performance malicieuse pour attirer l'attention.",
        "text": "Hop hop hop. Je fais mon petit numero de lapin augmente, avec une lueur espiègle et une posture qui dit attention, fantaisie imminente.",
        "ears": {"left": 4, "right": 12},
        "leds": [
            {"target": "left", "color": LED_COLOR_PRESETS["violet"], "preset": "violet"},
            {"target": "center", "color": LED_COLOR_PRESETS["cyan"], "preset": "cyan"},
            {"target": "right", "color": LED_COLOR_PRESETS["yellow"], "preset": "yellow"},
            {"target": "nose", "color": LED_COLOR_PRESETS["red"], "preset": "red"},
        ],
    },
}

_auto_intervention_worker_lock = threading.Lock()
_auto_intervention_worker_started = False


def _parse_clock_value(value: str | None, *, fallback: str) -> tuple[int, int]:
    raw_value = (value or fallback).strip()
    match = re.fullmatch(r"(\d{2}):(\d{2})", raw_value)
    if not match:
        match = re.fullmatch(r"(\d{1,2}):(\d{2})", fallback)
    hour = int(match.group(1))
    minute = int(match.group(2))
    hour = max(0, min(23, hour))
    minute = max(0, min(59, minute))
    return hour, minute


def _normalize_auto_performance_frequency(raw_value: object) -> int:
    try:
        frequency = int(raw_value)
    except (TypeError, ValueError):
        frequency = AUTO_PERFORMANCE_DEFAULT_FREQUENCY_MINUTES
    return max(AUTO_PERFORMANCE_MIN_FREQUENCY_MINUTES, min(AUTO_PERFORMANCE_MAX_FREQUENCY_MINUTES, frequency))


def _normalize_auto_performance_window(value: str | None, *, fallback: str) -> str:
    hour, minute = _parse_clock_value(value, fallback=fallback)
    return f"{hour:02d}:{minute:02d}"


def _localize_utc_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=ZoneInfo("UTC"))
    return value.astimezone(AUTO_PERFORMANCE_TIMEZONE)


def _format_auto_performance_next_at(value: datetime | None) -> str | None:
    localized = _localize_utc_datetime(value)
    if localized is None:
        return None
    return localized.strftime("%d/%m à %H:%M")


def _is_within_daily_window(current_minutes: int, *, start_minutes: int, end_minutes: int) -> bool:
    if start_minutes == end_minutes:
        return True
    if start_minutes < end_minutes:
        return start_minutes <= current_minutes < end_minutes
    return current_minutes >= start_minutes or current_minutes < end_minutes


def _next_window_start_local(reference_local: datetime, *, start_minutes: int, end_minutes: int) -> datetime:
    current_minutes = reference_local.hour * 60 + reference_local.minute
    start_local = reference_local.replace(
        hour=start_minutes // 60,
        minute=start_minutes % 60,
        second=0,
        microsecond=0,
    )
    if start_minutes == end_minutes:
        return reference_local
    if start_minutes < end_minutes:
        if current_minutes < start_minutes:
            return start_local
        return start_local + timedelta(days=1)
    if current_minutes < end_minutes:
        return start_local
    if current_minutes >= start_minutes:
        return start_local + timedelta(days=1)
    return start_local


def _compute_next_auto_performance_at(
    rabbit: Rabbit,
    *,
    after_utc: datetime | None = None,
    initial: bool = False,
) -> datetime:
    base_utc = after_utc or datetime.utcnow()
    base_local = base_utc.replace(tzinfo=ZoneInfo("UTC")).astimezone(AUTO_PERFORMANCE_TIMEZONE)
    start_minutes = _parse_clock_value(
        rabbit.auto_performance_window_start,
        fallback=AUTO_PERFORMANCE_DEFAULT_WINDOW_START,
    )
    end_minutes = _parse_clock_value(
        rabbit.auto_performance_window_end,
        fallback=AUTO_PERFORMANCE_DEFAULT_WINDOW_END,
    )
    start_total = start_minutes[0] * 60 + start_minutes[1]
    end_total = end_minutes[0] * 60 + end_minutes[1]
    frequency = _normalize_auto_performance_frequency(rabbit.auto_performance_frequency_minutes)
    current_total = base_local.hour * 60 + base_local.minute

    if initial and not _is_within_daily_window(current_total, start_minutes=start_total, end_minutes=end_total):
        next_local = _next_window_start_local(base_local, start_minutes=start_total, end_minutes=end_total)
        offset_minutes = random.randint(0, max(1, frequency))
        return (next_local + timedelta(minutes=offset_minutes)).astimezone(ZoneInfo("UTC")).replace(tzinfo=None)

    random_delay = random.randint(max(1, frequency // 2), max(2, frequency + max(1, frequency // 2)))
    candidate_local = base_local + timedelta(minutes=random_delay)
    candidate_total = candidate_local.hour * 60 + candidate_local.minute
    if _is_within_daily_window(candidate_total, start_minutes=start_total, end_minutes=end_total):
        return candidate_local.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)

    next_local = _next_window_start_local(candidate_local, start_minutes=start_total, end_minutes=end_total)
    offset_minutes = random.randint(0, max(1, frequency))
    return (next_local + timedelta(minutes=offset_minutes)).astimezone(ZoneInfo("UTC")).replace(tzinfo=None)


def _claim_due_auto_performance(rabbit: Rabbit) -> bool:
    expected_next_at = rabbit.auto_performance_next_at
    claim_until = datetime.utcnow() + timedelta(minutes=AUTO_PERFORMANCE_CLAIM_MINUTES)
    query = Rabbit.query.filter_by(id=rabbit.id, auto_performance_enabled=True)
    if expected_next_at is None:
        query = query.filter(Rabbit.auto_performance_next_at.is_(None))
    else:
        query = query.filter(Rabbit.auto_performance_next_at == expected_next_at)
    updated = query.update({"auto_performance_next_at": claim_until}, synchronize_session=False)
    db.session.commit()
    return updated == 1


def _run_auto_performance_for_rabbit(rabbit_id: int) -> None:
    rabbit = db.session.get(Rabbit, rabbit_id)
    if rabbit is None or not rabbit.auto_performance_enabled:
        return

    owner = rabbit.owner
    if owner is None or not owner.mistral_api_key:
        rabbit.auto_performance_next_at = _compute_next_auto_performance_at(rabbit, after_utc=datetime.utcnow())
        db.session.commit()
        return

    try:
        llm_model = _normalize_rabbit_llm_model(rabbit, _build_rabbit_llm_model_options())
        performance = _generate_mistral_rabbit_performance(
            api_key=owner.mistral_api_key,
            model=llm_model,
            rabbit_name=rabbit.name,
            personality_prompt=rabbit.personality_prompt or DEFAULT_RABBIT_PERSONALITY_PROMPT,
            conversation_messages=_conversation_messages_for_generation(rabbit),
            user_prompt_override=(
                f"Sans intervention humaine, genere maintenant pour {rabbit.name} une petite performance originale, "
                "spontanee et divertissante. Le lapin peut faire un mini commentaire de vie quotidienne, une blague, "
                "une observation absurde, une humeur du moment ou une fantaisie poetique. "
                "Utilise la voix, et si utile, un langage corporel expressif avec oreilles et LEDs."
            ),
        )
        _queue_generated_performance(
            rabbit,
            api_key=owner.mistral_api_key,
            performance=performance,
            source="auto",
            mode="generate",
        )
        _append_conversation_turn(
            rabbit,
            role="assistant",
            text=performance["text"],
            source="auto",
            payload=performance,
        )
        _append_rabbit_event(
            rabbit,
            source="portal",
            event_type="rabbit.auto_performance.generated",
            payload=_performance_event_payload(performance),
        )
        rabbit.auto_performance_next_at = _compute_next_auto_performance_at(rabbit, after_utc=datetime.utcnow())
        db.session.commit()
    except Exception as exc:
        current_app.logger.exception("auto performance generation failed for rabbit %s", rabbit.id)
        _append_rabbit_event(
            rabbit,
            source="portal",
            event_type="rabbit.auto_performance.failed",
            payload={"error": str(exc)},
            level="error",
        )
        rabbit.auto_performance_next_at = _compute_next_auto_performance_at(rabbit, after_utc=datetime.utcnow())
        db.session.commit()


def _process_due_auto_performances() -> None:
    now = datetime.utcnow()
    candidates = (
        Rabbit.query.filter_by(auto_performance_enabled=True)
        .filter(Rabbit.auto_performance_next_at.isnot(None))
        .filter(Rabbit.auto_performance_next_at <= now)
        .order_by(Rabbit.auto_performance_next_at.asc())
        .limit(AUTO_PERFORMANCE_MAX_BATCH)
        .all()
    )
    for candidate in candidates:
        if _claim_due_auto_performance(candidate):
            _run_auto_performance_for_rabbit(candidate.id)


def _auto_intervention_worker(app) -> None:
    while True:
        try:
            with app.app_context():
                _process_due_auto_performances()
        except Exception:
            app.logger.exception("rabbit auto intervention worker failed")
        time.sleep(AUTO_PERFORMANCE_LOOP_SECONDS)


def ensure_auto_intervention_worker_started(app) -> None:
    global _auto_intervention_worker_started
    with _auto_intervention_worker_lock:
        if _auto_intervention_worker_started:
            return
        worker = threading.Thread(
            target=_auto_intervention_worker,
            args=(app,),
            name="rabbit-auto-interventions",
            daemon=True,
        )
        worker.start()
        _auto_intervention_worker_started = True


def _mistral_json_request(*, api_key: str, url: str, payload: dict | None = None) -> dict:
    request_headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    request_body = None
    if payload is not None:
        request_headers["Content-Type"] = "application/json"
        request_body = json.dumps(payload).encode("utf-8")

    http_request = urllib_request.Request(url, data=request_body, headers=request_headers)
    try:
        with urllib_request.urlopen(http_request, timeout=45) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib_error.HTTPError as exc:
        raw_error = exc.read().decode("utf-8", errors="replace")
        try:
            error_payload = json.loads(raw_error)
        except json.JSONDecodeError:
            error_payload = {}
        message = error_payload.get("message")
        if not message and isinstance(error_payload.get("error"), dict):
            message = error_payload["error"].get("message")
        if not message and isinstance(error_payload.get("error"), str):
            message = error_payload.get("error")
        raise RuntimeError(message or f"Mistral API error ({exc.code})") from exc
    except urllib_error.URLError as exc:
        raise RuntimeError("Impossible de joindre l'API Mistral.") from exc


def _list_mistral_saved_voices(api_key: str) -> list[dict]:
    payload = _mistral_json_request(api_key=api_key, url=MISTRAL_TTS_LIST_VOICES_URL)
    voices = payload.get("data")
    if not isinstance(voices, list):
        return []
    return [voice for voice in voices if isinstance(voice, dict) and voice.get("id")]


def _list_mistral_models(api_key: str) -> list[dict]:
    payload = _mistral_json_request(api_key=api_key, url=MISTRAL_MODELS_URL)
    models = payload.get("data")
    if not isinstance(models, list):
        return []
    return [model for model in models if isinstance(model, dict) and model.get("id")]


def _build_rabbit_llm_model_options(models: list[dict] | None = None) -> list[tuple[str, str]]:
    if not models:
        return [(DEFAULT_RABBIT_LLM_MODEL, DEFAULT_RABBIT_LLM_MODEL)]

    preferred_order = [
        "mistral-small-2603",
        "mistral-small-latest",
        "ministral-8b-latest",
        "ministral-8b-2512",
        "open-mistral-nemo",
        "mistral-tiny-latest",
    ]
    by_id = {str(model.get("id")).strip(): model for model in models if model.get("capabilities", {}).get("completion_chat")}
    ordered_ids: list[str] = []
    for model_id in preferred_order:
        if model_id in by_id and model_id not in ordered_ids:
            ordered_ids.append(model_id)
    for model_id in sorted(by_id):
        model = by_id[model_id]
        if model.get("capabilities", {}).get("audio") or model.get("capabilities", {}).get("audio_speech"):
            continue
        if model.get("capabilities", {}).get("completion_fim"):
            continue
        if model_id not in ordered_ids:
            ordered_ids.append(model_id)

    options: list[tuple[str, str]] = []
    for model_id in ordered_ids:
        model = by_id[model_id]
        label = model_id
        description = str(model.get("description") or "").strip()
        if description:
            label = f"{model_id} - {description}"
        options.append((model_id, label))
    return options or [(DEFAULT_RABBIT_LLM_MODEL, DEFAULT_RABBIT_LLM_MODEL)]


def _normalize_rabbit_llm_model(rabbit: Rabbit, model_options: list[tuple[str, str]]) -> str:
    current_model = (rabbit.llm_model or "").strip()
    allowed_values = {model_value for model_value, _model_label in model_options}
    if current_model in allowed_values:
        return current_model
    if current_model and current_model not in allowed_values:
        return current_model
    if rabbit.llm_model != DEFAULT_RABBIT_LLM_MODEL:
        rabbit.llm_model = DEFAULT_RABBIT_LLM_MODEL
        db.session.commit()
    return DEFAULT_RABBIT_LLM_MODEL


def _extract_json_object(raw_text: str) -> dict:
    text = raw_text.strip()
    if not text:
        raise RuntimeError("Le modele n'a renvoye aucun JSON.")
    direct_payload = None
    try:
        direct_payload = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise RuntimeError("Le modele n'a pas renvoye un JSON valide.") from None
        candidate = match.group(0)
        try:
            direct_payload = json.loads(candidate)
        except json.JSONDecodeError as exc:
            try:
                direct_payload = ast.literal_eval(candidate)
            except (ValueError, SyntaxError) as literal_exc:
                raise RuntimeError("Le modele a renvoye un JSON invalide.") from literal_exc
    if not isinstance(direct_payload, dict):
        raise RuntimeError("Le modele a renvoye un JSON invalide.")
    return direct_payload


def _maybe_unwrap_nested_performance_payload(payload: dict) -> dict:
    current_payload = payload
    for _ in range(2):
        if not isinstance(current_payload, dict):
            break
        if "ears" in current_payload or "leds" in current_payload:
            return current_payload
        raw_text = current_payload.get("text")
        if not isinstance(raw_text, str):
            return current_payload
        nested_text = raw_text.strip()
        if not nested_text.startswith("{"):
            return current_payload
        try:
            nested_payload = json.loads(nested_text)
        except json.JSONDecodeError:
            return current_payload
        if not isinstance(nested_payload, dict):
            return current_payload
        current_payload = nested_payload
    return current_payload


def _normalize_generated_ear_instruction(instruction: object) -> int | None:
    if not isinstance(instruction, dict):
        return None
    action = str(instruction.get("action") or "keep").strip().lower()
    if action == "keep":
        return None
    if action == "position":
        raw_position = instruction.get("position")
        if isinstance(raw_position, (int, float)):
            return max(0, min(16, int(raw_position)))
        return None
    return EAR_ACTION_TO_POSITION.get(action)


def _normalize_generated_led_instruction(target: str, instruction: object) -> dict | None:
    if not isinstance(instruction, dict):
        return None
    mode = str(instruction.get("mode") or "off").strip().lower()
    if target in BODY_LED_TARGETS:
        if mode == "off":
            return {"target": target, "color": LED_COLOR_PRESETS["off"], "preset": "off"}
        if mode != "steady":
            return None
        color_name = str(instruction.get("color") or "").strip().lower()
        if color_name not in LED_COLOR_PRESETS or color_name == "off":
            return None
        return {"target": target, "color": LED_COLOR_PRESETS[color_name], "preset": color_name}

    if target == "bottom":
        color_name = str(instruction.get("color") or "").strip().lower()
        if mode == "off":
            return {"target": target, "color": LED_COLOR_PRESETS["off"], "preset": "off"}
        if mode != "steady" or color_name not in {"blue", "green", "cyan", "red", "violet", "yellow", "white"}:
            return None
        return {"target": target, "color": LED_COLOR_PRESETS[color_name], "preset": color_name}

    if target == "nose":
        if mode not in {"off", "blink", "double_blink"}:
            return None
        preset = LED_MODE_TO_PRESET[mode]
        preset = preset or "off"
        return {"target": target, "color": LED_COLOR_PRESETS[preset], "preset": preset}
    return None


def _normalize_generated_performance(payload: dict) -> dict:
    payload = _maybe_unwrap_nested_performance_payload(payload)
    text = " ".join(str(payload.get("text") or "").split()).strip()
    if not text:
        raise RuntimeError("Le modele n'a pas fourni de texte a lire.")
    text = re.sub(r"\*[^*]+\*", "", text).strip()
    text = re.sub(r"\s{2,}", " ", text).strip()
    if not text:
        raise RuntimeError("Le modele n'a pas fourni de texte a lire.")

    ears_payload = payload.get("ears")
    left_position = None
    right_position = None
    if isinstance(ears_payload, dict):
        left_position = _normalize_generated_ear_instruction(ears_payload.get("left"))
        right_position = _normalize_generated_ear_instruction(ears_payload.get("right"))

    led_commands: list[dict] = []
    leds_payload = payload.get("leds")
    if isinstance(leds_payload, dict):
        for target in LED_TARGETS:
            led_command = _normalize_generated_led_instruction(target, leds_payload.get(target))
            if led_command is not None:
                led_commands.append(led_command)

    return {
        "text": text,
        "ears": {
            "left": left_position,
            "right": right_position,
        },
        "led_commands": led_commands,
    }


def _serialize_conversation_turn(turn: RabbitConversationTurn) -> dict:
    payload = None
    if turn.payload:
        try:
            payload = json.loads(turn.payload)
        except json.JSONDecodeError:
            payload = {"raw": turn.payload}
    return {
        "id": turn.id,
        "role": turn.role,
        "text": turn.text,
        "source": turn.source,
        "recording_id": turn.recording_id,
        "payload": payload,
        "created_at": turn.created_at.isoformat() if turn.created_at else None,
    }


def _append_conversation_turn(
    rabbit: Rabbit,
    *,
    role: str,
    text: str,
    source: str,
    recording_id: int | None = None,
    payload: dict | None = None,
) -> RabbitConversationTurn:
    turn = RabbitConversationTurn(
        rabbit_id=rabbit.id,
        role=role,
        text=" ".join(text.split()).strip(),
        source=source,
        recording_id=recording_id,
        payload=json.dumps(payload) if payload is not None else None,
    )
    db.session.add(turn)
    db.session.commit()
    _prune_rabbit_conversation(rabbit)
    return turn


def _prune_rabbit_conversation(rabbit: Rabbit) -> None:
    had_summary = bool(rabbit.conversation_summary or rabbit.conversation_summary_turn_id)
    cutoff_time = datetime.utcnow() - timedelta(minutes=CONVERSATION_MAX_AGE_MINUTES)
    retained_turns = (
        RabbitConversationTurn.query.filter_by(rabbit_id=rabbit.id)
        .filter(RabbitConversationTurn.created_at >= cutoff_time)
        .order_by(RabbitConversationTurn.id.desc())
        .limit(CONVERSATION_MAX_TURNS)
        .all()
    )
    retained_ids = {turn.id for turn in retained_turns}
    stale_turns = (
        RabbitConversationTurn.query.filter_by(rabbit_id=rabbit.id)
        .filter(~RabbitConversationTurn.id.in_(retained_ids))
        .all()
        if retained_ids
        else []
    )
    for stale_turn in stale_turns:
        db.session.delete(stale_turn)

    rabbit.conversation_summary = None
    rabbit.conversation_summary_turn_id = None

    if stale_turns or had_summary:
        db.session.commit()


def _maybe_compact_rabbit_conversation(rabbit: Rabbit, *, api_key: str, model: str) -> None:
    del api_key, model
    _prune_rabbit_conversation(rabbit)


def _conversation_messages_for_generation(rabbit: Rabbit) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    recent_turns = list(
        RabbitConversationTurn.query.filter_by(rabbit_id=rabbit.id)
        .order_by(RabbitConversationTurn.id.desc())
        .limit(CONVERSATION_RECENT_TURNS_LIMIT)
        .all()
    )
    recent_turns.reverse()
    for turn in recent_turns:
        if turn.role not in {"user", "assistant"}:
            continue
        role = "assistant" if turn.role == "assistant" else "user"
        messages.append({"role": role, "content": turn.text})
    return messages


def _queue_generated_performance(
    rabbit: Rabbit,
    *,
    api_key: str,
    performance: dict,
    source: str,
    mode: str,
) -> tuple[Path, str]:
    text = performance["text"]
    voice = _normalize_rabbit_tts_voice(rabbit, _build_rabbit_tts_voice_options())
    asset_path, asset_name = _synthesize_tts_asset(
        api_key=api_key,
        rabbit_slug=rabbit.slug,
        text=text,
        voice=voice,
    )

    left_position = performance["ears"]["left"]
    right_position = performance["ears"]["right"]
    if left_position is not None or right_position is not None:
        current_left = 8
        current_right = 8
        if rabbit.remote_rabbit_id:
            try:
                remote_rabbit = fetch_remote_rabbit(rabbit.remote_rabbit_id)
                remote_state = (remote_rabbit or {}).get("state") or {}
                current_left = int(remote_state.get("left_ear", current_left))
                current_right = int(remote_state.get("right_ear", current_right))
            except (NabaztagApiError, TypeError, ValueError):
                pass
        _enqueue_device_command(
            rabbit,
            command_type="ears",
            payload={
                "left": left_position if left_position is not None else current_left,
                "right": right_position if right_position is not None else current_right,
            },
        )

    for led_command in performance["led_commands"]:
        _enqueue_device_command(
            rabbit,
            command_type="led",
            payload=led_command,
        )

    asset_url = f"broadcast/ojn_local/audio/{asset_name}"
    _enqueue_device_command(
        rabbit,
        command_type="audio",
        payload={
            "url": asset_url,
            "source": source,
            "filename": asset_path.name,
            "text": text,
            "mode": mode,
        },
    )
    return asset_path, asset_name


def _queue_use_case_scene(
    rabbit: Rabbit,
    *,
    api_key: str,
    scene_key: str,
) -> tuple[str, dict]:
    scene = RABBIT_USE_CASE_SCENES.get(scene_key)
    if scene is None:
        raise ValueError("Scene inconnue.")
    performance = {
        "text": scene["text"],
        "ears": dict(scene["ears"]),
        "led_commands": list(scene["leds"]),
    }
    _queue_generated_performance(
        rabbit,
        api_key=api_key,
        performance=performance,
        source="use_case",
        mode=scene_key,
    )
    return scene["label"], performance


def _performance_event_payload(performance: dict) -> dict:
    return {
        "text": performance["text"],
        "ears": performance.get("ears") or {"left": None, "right": None},
        "led_commands": performance.get("led_commands") or [],
        "performance": performance,
    }


def _build_rabbit_tts_voice_options(saved_voices: list[dict] | None = None) -> list[tuple[str, str]]:
    options: list[tuple[str, str]] = list(RABBIT_TTS_VOICE_PRESETS)
    if not saved_voices:
        return options

    known_values = {voice_value for voice_value, _voice_label in options}
    for voice in saved_voices:
        voice_id = str(voice.get("id", "")).strip()
        if not voice_id or voice_id in known_values:
            continue
        voice_name = str(voice.get("name") or voice_id).strip()
        options.append((voice_id, f"{voice_name} (voix sauvegardee)"))
        known_values.add(voice_id)
    return options


def _normalize_rabbit_tts_voice(rabbit: Rabbit, voice_options: list[tuple[str, str]]) -> str:
    current_voice = (rabbit.tts_voice or "").strip()
    allowed_values = {voice_value for voice_value, _voice_label in voice_options}
    if current_voice and current_voice not in LEGACY_RABBIT_TTS_VOICES and current_voice in allowed_values:
        return current_voice
    if current_voice and current_voice not in LEGACY_RABBIT_TTS_VOICES and current_voice not in allowed_values:
        return current_voice
    if rabbit.tts_voice != DEFAULT_RABBIT_TTS_VOICE:
        rabbit.tts_voice = DEFAULT_RABBIT_TTS_VOICE
        db.session.commit()
    return DEFAULT_RABBIT_TTS_VOICE


def _portal_base_url() -> str:
    return request.url_root.rstrip("/") + (request.script_root or "")


def _violet_platform_value() -> str:
    return f"{request.host}/vl"


def _locate_reply() -> str:
    ping_server = current_app.config["NABAZTAG_VL_PING_SERVER"]
    broad_server = current_app.config["NABAZTAG_VL_BROAD_SERVER"]
    xmpp_server = current_app.config["NABAZTAG_VL_XMPP_SERVER"]
    xmpp_port = current_app.config["NABAZTAG_VL_XMPP_PORT"]
    xmpp_alt_server = current_app.config["NABAZTAG_VL_XMPP_ALT_SERVER"]
    xmpp_alt_port = current_app.config["NABAZTAG_VL_XMPP_ALT_PORT"]
    xmpp_timeout = current_app.config["NABAZTAG_VL_XMPP_TIMEOUT"]
    return (
        f"ping {ping_server}\n"
        f"broad {broad_server}\n"
        f"xmpp_domain {xmpp_server}:{xmpp_port}\n"
        f"xmpp_alt {xmpp_alt_server}:{xmpp_alt_port}\n"
        f"xmpp_timeout {xmpp_timeout}\n"
        f"date {int(time.time())}\n"
    )


def _recordings_dir() -> Path:
    recordings_dir = Path(current_app.instance_path) / "recordings"
    recordings_dir.mkdir(parents=True, exist_ok=True)
    return recordings_dir


def _recording_transcript_path(recording_path: Path) -> Path:
    return recording_path.with_suffix(recording_path.suffix + ".transcript.json")


def _choreographies_dir() -> Path:
    chor_dir = Path(current_app.instance_path) / "chor"
    chor_dir.mkdir(parents=True, exist_ok=True)
    return chor_dir


def _audio_assets_dir() -> Path:
    audio_dir = Path(current_app.instance_path) / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    return audio_dir


def _rabbit_photos_dir() -> Path:
    photo_dir = Path(current_app.instance_path) / "rabbit_photos"
    photo_dir.mkdir(parents=True, exist_ok=True)
    return photo_dir


def _bootcode_path() -> Path:
    return Path(current_app.root_path).parents[2] / "deploy" / "assets" / "bootcode.default"


def _default_rabbit_photo_path() -> Path:
    return Path(current_app.root_path).parents[2] / "ressources" / "Nabaztag1.jpg"


def _rabbit_led_layout_photo_path() -> Path:
    return Path(current_app.root_path).parents[2] / "ressources" / "nabaztag.jpg"


def _normalize_serial(value: str | None) -> str:
    return "".join(character for character in (value or "").lower() if character in "0123456789abcdef")


def _transcribe_recording_asset(recording_path: Path) -> dict:
    transcript_path = _recording_transcript_path(recording_path)
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        result = {
            "status": "unavailable",
            "text": "",
            "error": "faster-whisper is not installed on the server",
            "model": None,
        }
        transcript_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return result

    model_name = current_app.config.get("NABAZTAG_STT_MODEL", "small")
    language = current_app.config.get("NABAZTAG_STT_LANGUAGE", "fr")
    try:
        model = WhisperModel(model_name, device="cpu", compute_type="int8")
        segments, info = model.transcribe(
            str(recording_path),
            language=language,
            task="transcribe",
            vad_filter=True,
            condition_on_previous_text=False,
            temperature=0.0,
        )
        text = " ".join(segment.text.strip() for segment in segments if segment.text.strip()).strip()
        result = {
            "status": "ok",
            "text": text,
            "error": None,
            "model": model_name,
            "language": getattr(info, "language", language),
            "duration": getattr(info, "duration", None),
        }
    except Exception as exc:
        current_app.logger.exception("recording transcription failed for %s", recording_path)
        result = {
            "status": "error",
            "text": "",
            "error": str(exc),
            "model": model_name,
        }

    transcript_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def _read_recording_transcript(recording_path: Path) -> dict | None:
    transcript_path = _recording_transcript_path(recording_path)
    if not transcript_path.exists():
        return None
    try:
        return json.loads(transcript_path.read_text(encoding="utf-8"))
    except Exception:
        current_app.logger.warning("unable to read transcript sidecar for %s", recording_path)
        return {"status": "error", "text": "", "error": "invalid transcript sidecar", "model": None}


def _serialize_recording(recording: RabbitRecording) -> dict:
    transcript = _read_recording_transcript(Path(recording.source_path))
    return {
        "id": recording.id,
        "filename": recording.filename,
        "created_at": recording.created_at.isoformat() if recording.created_at else None,
        "mode": recording.mode,
        "url": url_for("main.download_recording", filename=recording.filename),
        "transcript": transcript,
    }


def _rabbit_photo_url(rabbit: Rabbit) -> str | None:
    if not rabbit.photo_filename:
        return None
    return url_for("main.rabbit_photo", rabbit_id=rabbit.id)


def _serialize_event_log(event: RabbitEventLog) -> dict:
    try:
        payload = json.loads(event.payload) if event.payload else None
    except json.JSONDecodeError:
        payload = {"raw": event.payload}
    return {
        "id": event.id,
        "event_type": event.event_type,
        "source": event.source,
        "level": event.level,
        "created_at": event.created_at.isoformat() if event.created_at else None,
        "payload": payload,
    }


def _serialize_live_event(event: RabbitEventLog, *, rabbit_id: int) -> dict:
    serialized = _serialize_event_log(event)
    payload = serialized.get("payload") or {}

    if serialized["event_type"] == "rabbit.recording.uploaded":
        filename = payload.get("filename")
        if filename:
            recording = RabbitRecording.query.filter_by(rabbit_id=rabbit_id, filename=filename).first()
            if recording is not None:
                payload["audio_url"] = url_for("main.download_recording", filename=recording.filename)
                transcript = _read_recording_transcript(Path(recording.source_path))
                if transcript:
                    payload["transcript"] = transcript

    serialized["payload"] = payload
    return serialized


def _latest_ztamps_for_rabbit(rabbit_id: int, *, limit: int = 20) -> list[dict]:
    if not Ztamp.query.filter_by(rabbit_id=rabbit_id).first():
        historical_events = (
            RabbitEventLog.query.filter_by(rabbit_id=rabbit_id, event_type="rabbit.rfid.detected")
            .order_by(RabbitEventLog.created_at.asc())
            .all()
        )
        seen_tags: set[str] = set()
        for event in historical_events:
            serialized = _serialize_event_log(event)
            event_payload = serialized.get("payload") or {}
            tag = event_payload.get("tag")
            if not tag or tag in seen_tags:
                continue
            seen_tags.add(tag)
            created_at = event.created_at or utc_now()
            db.session.add(
                Ztamp(
                    rabbit_id=rabbit_id,
                    tag=tag,
                    created_at=created_at,
                    updated_at=created_at,
                    last_seen_at=created_at,
                )
            )
        if seen_tags:
            db.session.commit()

    ztamps = (
        Ztamp.query.filter_by(rabbit_id=rabbit_id)
        .order_by(Ztamp.last_seen_at.desc(), Ztamp.updated_at.desc())
        .limit(limit)
        .all()
    )
    payload: list[dict] = []
    for ztamp in ztamps:
        payload.append(
            {
                "id": ztamp.id,
                "tag": ztamp.tag,
                "name": ztamp.name,
                "notes": ztamp.notes,
                "created_at": ztamp.last_seen_at.isoformat() if ztamp.last_seen_at else None,
                "edit_url": url_for("main.edit_ztamp", rabbit_id=rabbit_id, ztamp_id=ztamp.id),
            }
        )
    return payload


def _synthesize_tts_asset(*, api_key: str, rabbit_slug: str, text: str, voice: str) -> tuple[Path, str]:
    normalized_text = " ".join(text.split())
    if not normalized_text:
        raise ValueError("empty text")
    if not api_key:
        raise RuntimeError("Ajoute d'abord ton token Mistral dans Mon compte.")

    token = secrets.token_hex(6)
    asset_name = f"{rabbit_slug}-tts-{token}.mp3"
    asset_path = _audio_assets_dir() / asset_name
    payload = {
        "model": MISTRAL_TTS_MODEL,
        "input": normalized_text,
        "voice_id": voice,
        "response_format": MISTRAL_TTS_RESPONSE_FORMAT,
    }
    response_payload = _mistral_json_request(
        api_key=api_key,
        url=MISTRAL_TTS_SPEECH_URL,
        payload=payload,
    )
    audio_data = response_payload.get("audio_data")
    if not isinstance(audio_data, str) or not audio_data.strip():
        raise RuntimeError("Réponse TTS Mistral invalide.")

    try:
        asset_path.write_bytes(base64.b64decode(audio_data))
    except (ValueError, OSError) as exc:
        raise RuntimeError("Impossible d'enregistrer l'audio genere par Mistral.") from exc
    return asset_path, asset_name


def _extract_mistral_chat_text(payload: dict) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list):
        return ""
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message")
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
        if isinstance(content, list):
            fragments: list[str] = []
            for item in content:
                if not isinstance(item, dict):
                    continue
                text_value = item.get("text")
                if isinstance(text_value, str) and text_value.strip():
                    fragments.append(text_value.strip())
            if fragments:
                return "\n".join(fragments).strip()
    return ""


def _generate_mistral_rabbit_performance(
    *,
    api_key: str,
    model: str,
    rabbit_name: str,
    personality_prompt: str,
    conversation_messages: list[dict[str, str]] | None = None,
    user_prompt_override: str | None = None,
) -> dict:
    system_prompt = (
        f"{personality_prompt}\n\n"
        "Tu pilotes un lapin Nabaztag qui s'exprime avec la voix, les oreilles et les LEDs. "
        "Tu dois repondre uniquement avec un objet JSON valide, sans markdown ni commentaire. "
        "Le JSON doit avoir exactement cette structure generale: "
        '{"text":"...",'
        '"ears":{"left":{"action":"keep|forward|center|backward|position","position":8},'
        '"right":{"action":"keep|forward|center|backward|position","position":8}},'
        '"leds":{"left":{"mode":"off|steady","color":"red|green|blue|cyan|violet|yellow|white"},'
        '"center":{"mode":"off|steady","color":"red|green|blue|cyan|violet|yellow|white"},'
        '"right":{"mode":"off|steady","color":"red|green|blue|cyan|violet|yellow|white"},'
        '"bottom":{"mode":"off|steady","color":"blue|green|cyan|red|violet|yellow|white"},'
        '"nose":{"mode":"off|blink|double_blink"}}}. '
        "Contraintes: "
        "1. `text` est obligatoire, en francais, 1 a 3 phrases courtes, droles et naturelles a lire a voix haute. "
        "2. Pour les oreilles, utilise `keep` si tu ne veux rien changer. "
        "3. Pour les LEDs du corps `left/center/right`, seul `steady` ou `off` est autorise. "
        "4. Pour `bottom`, seul `steady` ou `off` est autorise. "
        "5. Pour `nose`, seuls `off`, `blink` et `double_blink` sont autorises. "
        "6. Le champ `text` doit contenir uniquement la phrase prononcee par le lapin, sans didascalie, "
        "sans description de geste, sans mention des oreilles, sans mention des LEDs, sans asterisques. "
        "7. Reponds avec un JSON strict valide, avec des doubles guillemets JSON, jamais avec des quotes simples. "
        "8. Ne mets jamais de texte hors JSON."
    )
    user_prompt = user_prompt_override or (
        f"Genere maintenant une petite performance originale pour {rabbit_name}. "
        "Le lapin doit divertir avec sa voix et, si utile, avec un petit langage corporel expressif."
    )
    messages = [{"role": "system", "content": system_prompt}]
    if conversation_messages:
        messages.extend(conversation_messages)
    messages.append({"role": "user", "content": user_prompt})
    response_payload = _mistral_json_request(
        api_key=api_key,
        url="https://api.mistral.ai/v1/chat/completions",
        payload={
            "model": model,
            "messages": messages,
            "max_tokens": 300,
            "temperature": 0.9,
            "response_format": {"type": "json_object"},
        },
    )
    message = _extract_mistral_chat_text(response_payload)
    return _normalize_generated_performance(_extract_json_object(message))


def _maybe_transcode_recording_to_mp3(source_path: Path) -> Path:
    current_app.logger.info("recording post-processing disabled, keeping raw recording %s", source_path)
    return source_path


def _find_recent_duplicate_recording(rabbit: Rabbit, content_sha1: str) -> RabbitRecording | None:
    cutoff_time = datetime.utcnow() - timedelta(seconds=RECORDING_DEDUPLICATION_WINDOW_SECONDS)
    return (
        RabbitRecording.query.filter_by(rabbit_id=rabbit.id, content_sha1=content_sha1)
        .filter(RabbitRecording.created_at >= cutoff_time)
        .order_by(RabbitRecording.id.desc())
        .first()
    )


def _record_device_observation(
    *,
    serial: str | None,
    firmware: str | None = None,
    hardware: str | None = None,
) -> DeviceObservation | None:
    normalized = _normalize_serial(serial)
    if not normalized:
        return None

    observation = DeviceObservation.query.filter_by(serial=normalized).first()
    if observation is None:
        observation = DeviceObservation(serial=normalized)
        db.session.add(observation)

    observation.last_seen_at = utc_now()
    observation.last_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    observation.last_user_agent = request.headers.get("User-Agent", "")[:255]
    observation.last_path = request.path
    observation.last_query = request.query_string.decode("utf-8", errors="replace")[:2000]
    if firmware:
        observation.firmware = firmware
    if hardware:
        observation.hardware = hardware
    db.session.commit()
    return observation


def _rabbit_for_serial(serial: str | None) -> Rabbit | None:
    normalized = _normalize_serial(serial)
    if not normalized:
        return None
    observation = DeviceObservation.query.filter_by(serial=normalized).first()
    if observation and observation.rabbit_id:
        return Rabbit.query.get(observation.rabbit_id)
    return None


def _append_rabbit_event(
    rabbit: Rabbit | None,
    *,
    source: str,
    event_type: str,
    payload: dict,
    level: str = "info",
) -> None:
    if rabbit is None:
        return
    db.session.add(
        RabbitEventLog(
            rabbit_id=rabbit.id,
            source=source,
            event_type=event_type,
            payload=json.dumps(payload),
            level=level,
        )
    )


def _enqueue_device_command(
    rabbit: Rabbit,
    *,
    command_type: str,
    payload: dict,
    serial: str | None = None,
) -> RabbitDeviceCommand:
    linked_device = (
        DeviceObservation.query.filter_by(rabbit_id=rabbit.id)
        .order_by(DeviceObservation.last_seen_at.desc())
        .first()
    )
    resolved_serial = _normalize_serial(serial or (linked_device.serial if linked_device else rabbit.target_host))
    command = RabbitDeviceCommand(
        rabbit_id=rabbit.id,
        serial=resolved_serial,
        command_type=command_type,
        payload=json.dumps(payload),
    )
    db.session.add(command)
    _append_rabbit_event(
        rabbit,
        source="portal",
        event_type=f"rabbit.command.{command_type}.queued",
        payload=payload,
    )
    db.session.commit()
    return command


def _apply_local_device_state(
    rabbit: Rabbit,
    remote_state: dict | None,
    *,
    serial: str | None = None,
) -> dict | None:
    resolved_serial = _normalize_serial(serial)
    if not resolved_serial:
        return remote_state

    state = dict((remote_state or {}).get("state") or {})
    if remote_state is None:
        remote_state = {
            "connection_status": rabbit.connection_status,
            "created_at": None,
            "updated_at": None,
            "device_serial": resolved_serial,
            "state": state,
        }
    else:
        remote_state = dict(remote_state)
        remote_state["device_serial"] = remote_state.get("device_serial") or resolved_serial

    latest_commands = (
        RabbitDeviceCommand.query.filter_by(rabbit_id=rabbit.id, serial=resolved_serial)
        .filter(RabbitDeviceCommand.status.in_(("queued", "sent")))
        .order_by(RabbitDeviceCommand.created_at.desc())
        .limit(100)
        .all()
    )

    latest_led_by_target: dict[str, dict] = {}
    latest_ears_payload: dict | None = None
    latest_audio_payload: dict | None = None

    for command in latest_commands:
        try:
            payload = json.loads(command.payload or "{}")
        except json.JSONDecodeError:
            continue
        if command.command_type == "led":
            target = str(payload.get("target") or "").lower()
            if target and target not in latest_led_by_target:
                latest_led_by_target[target] = payload
        elif command.command_type == "ears" and latest_ears_payload is None:
            latest_ears_payload = payload
        elif command.command_type == "audio" and latest_audio_payload is None:
            latest_audio_payload = payload

    led_state_map = {
        "left": "led_left",
        "center": "led_center",
        "right": "led_right",
        "bottom": "led_bottom",
        "nose": "led_nose",
    }
    for target, field_name in led_state_map.items():
        payload = latest_led_by_target.get(target)
        if payload is not None:
            state[field_name] = payload.get("color") or "#000000"

    if latest_ears_payload is not None:
        if "left" in latest_ears_payload:
            state["left_ear"] = int(latest_ears_payload["left"])
        if "right" in latest_ears_payload:
            state["right_ear"] = int(latest_ears_payload["right"])

    if latest_audio_payload is not None:
        state["audio_playing"] = True
        state["last_audio_url"] = latest_audio_payload.get("url")

    remote_state["state"] = state
    return remote_state


def _sync_remote_rabbit(rabbit: Rabbit, *, linked_serial: str | None = None) -> str | None:
    remote_id = rabbit.remote_rabbit_id
    needs_recreate = not remote_id

    if remote_id and not needs_recreate:
        try:
            fetch_remote_rabbit(remote_id)
        except NabaztagApiError as exc:
            if exc.status_code == 404:
                needs_recreate = True
            else:
                raise

    if needs_recreate:
        remote_payload = create_remote_rabbit(name=rabbit.name, slug=rabbit.slug)
        remote_id = remote_payload["id"]
        rabbit.remote_rabbit_id = remote_id
        db.session.add(
            RabbitEventLog(
                rabbit_id=rabbit.id,
                source="portal",
                event_type="rabbit.remote.recreated",
                payload=json.dumps({"remote_rabbit_id": remote_id}),
            )
        )

    if rabbit.target_host and remote_id:
        set_remote_target(remote_id, rabbit.target_host, rabbit.target_port or 10543)

    if linked_serial and remote_id:
        link_remote_device(remote_id, linked_serial)

    db.session.commit()
    return remote_id


@main_bp.route("/vl", methods=["GET", "POST", "HEAD"])
@main_bp.route("/vl/", methods=["GET", "POST", "HEAD"])
def violet_platform():
    payload = request.get_data(cache=False, as_text=True)
    current_app.logger.info(
        "nabaztag.vl request method=%s path=%s args=%s headers=%s body=%s",
        request.method,
        request.path,
        dict(request.args),
        {key: value for key, value in request.headers.items()},
        payload[:1000],
    )
    return Response("Nabaztag Violet Platform endpoint ready.\n", mimetype="text/plain")


@main_bp.route("/vl/locate.jsp", methods=["GET", "POST", "HEAD"])
def violet_locate():
    serial_number = (request.args.get("sn") or "").replace(":", "").lower()
    _record_device_observation(
        serial=serial_number,
        firmware=request.args.get("v"),
        hardware=request.args.get("h"),
    )
    body = _locate_reply()
    rabbit = _rabbit_for_serial(serial_number)
    _append_rabbit_event(
        rabbit,
        source="device",
        event_type="rabbit.locate",
        payload={
            "serial": serial_number,
            "firmware": request.args.get("v"),
            "hardware": request.args.get("h"),
            "path": request.path,
        },
    )
    db.session.commit()
    current_app.logger.info(
        "nabaztag.locate sn=%s hardware=%s firmware=%s reply=%s",
        serial_number,
        request.args.get("h"),
        request.args.get("v"),
        body.strip(),
    )
    return Response(body, mimetype="text/plain")


@main_bp.route("/vl/bc.jsp", methods=["GET", "HEAD"])
def violet_bootcode():
    bootcode = _bootcode_path()
    _record_device_observation(
        serial=request.args.get("m"),
        firmware=request.args.get("v"),
        hardware=request.args.get("h"),
    )
    rabbit = _rabbit_for_serial(request.args.get("m"))
    _append_rabbit_event(
        rabbit,
        source="device",
        event_type="rabbit.bootcode",
        payload={
            "serial": _normalize_serial(request.args.get("m")),
            "firmware": request.args.get("v"),
            "hardware": request.args.get("h"),
        },
    )
    db.session.commit()
    current_app.logger.info(
        "nabaztag.bc mac=%s firmware=%s hardware=%s bootcode=%s",
        (request.args.get("m") or "").lower(),
        request.args.get("v"),
        request.args.get("h"),
        str(bootcode),
    )
    return send_file(
        bootcode,
        mimetype="application/octet-stream",
        as_attachment=False,
        conditional=True,
        download_name="bootcode.default",
        etag=True,
        last_modified=bootcode.stat().st_mtime,
    )


@main_bp.route("/vl/record.jsp", methods=["POST"])
def violet_record():
    serial_number = (request.args.get("sn") or "").replace(":", "").lower() or "unknown"
    payload = request.get_data(cache=False)
    payload_sha1 = hashlib.sha1(payload).hexdigest()
    rabbit = _rabbit_for_serial(serial_number)
    if rabbit is not None:
        duplicate_recording = _find_recent_duplicate_recording(rabbit, payload_sha1)
        if duplicate_recording is not None:
            _append_rabbit_event(
                rabbit,
                source="device",
                event_type="rabbit.recording.duplicate_ignored",
                payload={
                    "serial": serial_number,
                    "content_sha1": payload_sha1,
                    "existing_recording_id": duplicate_recording.id,
                    "existing_filename": duplicate_recording.filename,
                    "size": len(payload),
                },
            )
            db.session.commit()
            current_app.logger.info(
                "nabaztag.record duplicate ignored sn=%s sha1=%s existing_recording_id=%s",
                serial_number,
                payload_sha1,
                duplicate_recording.id,
            )
            return Response("", mimetype="text/plain")
    raw_filename = f"record_{serial_number}_{int(time.time())}.wav"
    raw_filepath = _recordings_dir() / raw_filename
    raw_filepath.write_bytes(payload)
    stored_path = _maybe_transcode_recording_to_mp3(raw_filepath)
    filename = stored_path.name
    transcript = _transcribe_recording_asset(stored_path)
    recording = None
    if rabbit is not None:
        recording = RabbitRecording(
            rabbit_id=rabbit.id,
            serial=serial_number,
            content_sha1=payload_sha1,
            filename=filename,
            source_path=str(stored_path),
            mode=request.args.get("m"),
        )
        db.session.add(recording)
        db.session.flush()
    _append_rabbit_event(
        rabbit,
        source="device",
        event_type="rabbit.recording.uploaded",
        payload={
            "serial": serial_number,
            "filename": filename,
            "size": len(payload),
            "mode": request.args.get("m"),
            "transcript_status": transcript.get("status"),
        },
    )
    db.session.commit()

    transcript_text = " ".join(str(transcript.get("text") or "").split()).strip()
    if rabbit is not None and transcript.get("status") == "ok" and transcript_text and recording is not None:
        try:
            _append_conversation_turn(
                rabbit,
                role="user",
                text=transcript_text,
                source="recording",
                recording_id=recording.id,
                payload={"filename": filename},
            )
            owner = rabbit.owner
            if owner and owner.mistral_api_key:
                llm_model = _normalize_rabbit_llm_model(rabbit, _build_rabbit_llm_model_options())
                _maybe_compact_rabbit_conversation(
                    rabbit,
                    api_key=owner.mistral_api_key,
                    model=llm_model,
                )
                performance = _generate_mistral_rabbit_performance(
                    api_key=owner.mistral_api_key,
                    model=llm_model,
                    rabbit_name=rabbit.name,
                    personality_prompt=rabbit.personality_prompt or DEFAULT_RABBIT_PERSONALITY_PROMPT,
                    conversation_messages=_conversation_messages_for_generation(rabbit),
                    user_prompt_override="Reponds maintenant au dernier message de l'utilisateur dans cette conversation.",
                )
                _queue_generated_performance(
                    rabbit,
                    api_key=owner.mistral_api_key,
                    performance=performance,
                    source="conversation",
                    mode="conversation",
                )
                _append_conversation_turn(
                    rabbit,
                    role="assistant",
                    text=performance["text"],
                    source="conversation",
                    payload=performance,
                )
                _append_rabbit_event(
                    rabbit,
                    source="portal",
                    event_type="rabbit.conversation.reply.generated",
                    payload={
                        "recording_id": recording.id,
                        "filename": filename,
                        **_performance_event_payload(performance),
                    },
                )
                db.session.commit()
        except RuntimeError as exc:
            current_app.logger.warning("rabbit conversation reply failed for %s: %s", rabbit.id, exc)
            _append_rabbit_event(
                rabbit,
                source="portal",
                event_type="rabbit.conversation.reply.failed",
                payload={
                    "recording_id": recording.id,
                    "filename": filename,
                    "error": str(exc),
                },
                level="error",
            )
            db.session.commit()

    current_app.logger.info(
        "nabaztag.record sn=%s size=%s file=%s",
        serial_number,
        len(payload),
        str(stored_path),
    )
    return Response("", mimetype="text/plain")


@main_bp.route("/vl/rfid.jsp", methods=["GET", "POST"])
def violet_rfid():
    serial_number = (request.args.get("sn") or "").replace(":", "").lower()
    tag_id = request.args.get("t") or ""
    rabbit = _rabbit_for_serial(serial_number)
    if rabbit is not None and tag_id:
        ztamp = Ztamp.query.filter_by(rabbit_id=rabbit.id, tag=tag_id).first()
        if ztamp is None:
            ztamp = Ztamp(rabbit_id=rabbit.id, tag=tag_id, last_seen_at=utc_now())
            db.session.add(ztamp)
        else:
            ztamp.last_seen_at = utc_now()
    _append_rabbit_event(
        rabbit,
        source="device",
        event_type="rabbit.rfid.detected",
        payload={"serial": serial_number, "tag": tag_id},
    )
    db.session.commit()
    current_app.logger.info("nabaztag.rfid sn=%s tag=%s", serial_number, tag_id)
    return Response("", mimetype="text/plain")


@main_bp.route("/vl/sendMailXMPP.jsp", methods=["GET", "POST"])
def violet_send_mail_xmpp():
    mac = (request.args.get("m") or "").replace(":", "").lower()
    current_app.logger.info("nabaztag.send_mail_xmpp mac=%s args=%s", mac, dict(request.args))
    return Response("", mimetype="text/plain")


@main_bp.get("/ojn_local/chor/<path:filename>")
def serve_choreography(filename: str):
    path = choreography_storage_path(_choreographies_dir(), filename)
    if not path.exists():
        return Response("Not found\n", status=404, mimetype="text/plain")
    return send_file(path, mimetype="application/octet-stream", as_attachment=False, download_name=path.name)


@main_bp.get("/ojn_local/audio/<path:filename>")
def serve_audio_asset(filename: str):
    path = _audio_assets_dir() / filename
    if not path.exists():
        return Response("Not found\n", status=404, mimetype="text/plain")
    guessed_type = guess_type(path.name)[0] or "application/octet-stream"
    return send_file(path, mimetype=guessed_type, as_attachment=False, download_name=path.name)


@main_bp.get("/")
def index():
    return render_template("index.html")


@main_bp.get("/dashboard")
@login_required
def dashboard():
    rabbits = (
        Rabbit.query.filter_by(owner_id=current_user.id)
        .order_by(Rabbit.created_at.desc())
        .all()
    )
    return render_template("dashboard.html", rabbits=rabbits)


@main_bp.route("/account", methods=["GET", "POST"])
@login_required
def account():
    if request.method == "POST":
        provider = request.form.get("provider", "mistral").strip().lower()
        action = request.form.get("action", "save").strip().lower()

        if provider != "mistral":
            flash("Provider invalide.", "error")
            return redirect(url_for("main.account"))
        field_name = "mistral_api_key"
        provider_label = "Mistral"

        if action == "clear":
            setattr(current_user, field_name, None)
            db.session.commit()
            flash(f"Token {provider_label} supprimé.", "success")
            return redirect(url_for("main.account"))

        api_key = request.form.get(field_name, "").strip()
        if not api_key:
            flash(f"Saisis un token {provider_label} ou utilise le bouton de suppression.", "error")
        else:
            setattr(current_user, field_name, api_key)
            db.session.commit()
            flash(f"Token {provider_label} enregistré.", "success")
            return redirect(url_for("main.account"))

    return render_template("account.html")


@main_bp.post("/rabbits/<int:rabbit_id>/prompt")
@login_required
def update_rabbit_prompt(rabbit_id: int):
    rabbit = Rabbit.query.filter_by(id=rabbit_id, owner_id=current_user.id).first_or_404()
    rabbit.personality_prompt = (
        request.form.get("personality_prompt", "").strip() or DEFAULT_RABBIT_PERSONALITY_PROMPT
    )
    db.session.commit()
    flash("Prompt du lapin mis a jour.", "success")
    return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))


@main_bp.post("/rabbits/<int:rabbit_id>/tts-voice")
@login_required
def update_rabbit_tts_voice(rabbit_id: int):
    rabbit = Rabbit.query.filter_by(id=rabbit_id, owner_id=current_user.id).first_or_404()
    custom_voice = request.form.get("tts_voice_custom", "").strip()
    preset_voice = request.form.get("tts_voice", "").strip()
    rabbit.tts_voice = custom_voice or preset_voice or DEFAULT_RABBIT_TTS_VOICE
    db.session.commit()
    flash("Voix TTS du lapin mise a jour.", "success")
    return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))


@main_bp.post("/rabbits/<int:rabbit_id>/llm-model")
@login_required
def update_rabbit_llm_model(rabbit_id: int):
    rabbit = Rabbit.query.filter_by(id=rabbit_id, owner_id=current_user.id).first_or_404()
    custom_model = request.form.get("llm_model_custom", "").strip()
    preset_model = request.form.get("llm_model", "").strip()
    rabbit.llm_model = custom_model or preset_model or DEFAULT_RABBIT_LLM_MODEL
    db.session.commit()
    flash("Modele LLM du lapin mis a jour.", "success")
    return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))


@main_bp.post("/rabbits/<int:rabbit_id>/auto-performance")
@login_required
def update_rabbit_auto_performance(rabbit_id: int):
    rabbit = Rabbit.query.filter_by(id=rabbit_id, owner_id=current_user.id).first_or_404()
    rabbit.auto_performance_enabled = request.form.get("auto_performance_enabled") == "on"
    rabbit.auto_performance_frequency_minutes = _normalize_auto_performance_frequency(
        request.form.get("auto_performance_frequency_minutes")
    )
    rabbit.auto_performance_window_start = _normalize_auto_performance_window(
        request.form.get("auto_performance_window_start"),
        fallback=AUTO_PERFORMANCE_DEFAULT_WINDOW_START,
    )
    rabbit.auto_performance_window_end = _normalize_auto_performance_window(
        request.form.get("auto_performance_window_end"),
        fallback=AUTO_PERFORMANCE_DEFAULT_WINDOW_END,
    )
    rabbit.auto_performance_next_at = (
        _compute_next_auto_performance_at(rabbit, after_utc=datetime.utcnow(), initial=True)
        if rabbit.auto_performance_enabled
        else None
    )
    db.session.commit()
    flash("Interventions aleatoires du lapin mises a jour.", "success")
    return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))


@main_bp.get("/rabbits/<int:rabbit_id>")
@login_required
def rabbit_detail(rabbit_id: int):
    rabbit = Rabbit.query.filter_by(id=rabbit_id, owner_id=current_user.id).first_or_404()
    _prune_rabbit_conversation(rabbit)
    if rabbit.auto_performance_enabled and rabbit.auto_performance_next_at is None:
        rabbit.auto_performance_next_at = _compute_next_auto_performance_at(
            rabbit,
            after_utc=datetime.utcnow(),
            initial=True,
        )
        db.session.commit()
    remote_rabbit = None
    remote_events: list[dict] = []
    remote_error = None
    saved_mistral_voices: list[dict] = []
    available_mistral_models: list[dict] = []

    linked_device = (
        DeviceObservation.query.filter_by(rabbit_id=rabbit.id)
        .order_by(DeviceObservation.last_seen_at.desc())
        .first()
    )

    if rabbit.remote_rabbit_id:
        try:
            remote_rabbit = fetch_remote_rabbit(rabbit.remote_rabbit_id)
            if linked_device and remote_rabbit.get("device_serial") != linked_device.serial:
                remote_id = _sync_remote_rabbit(rabbit, linked_serial=linked_device.serial)
                if remote_id:
                    remote_rabbit = fetch_remote_rabbit(remote_id)
            remote_events = fetch_remote_events(rabbit.remote_rabbit_id)
            rabbit.connection_status = remote_rabbit.get("connection_status", rabbit.connection_status)
            db.session.commit()
        except NabaztagApiError as exc:
            if exc.status_code == 404:
                try:
                    remote_id = _sync_remote_rabbit(
                        rabbit,
                        linked_serial=linked_device.serial if linked_device else None,
                    )
                    if remote_id:
                        remote_rabbit = fetch_remote_rabbit(remote_id)
                        remote_events = fetch_remote_events(remote_id)
                        rabbit.connection_status = remote_rabbit.get("connection_status", rabbit.connection_status)
                        db.session.commit()
                except NabaztagApiError as sync_exc:
                    remote_error = str(sync_exc)
            else:
                remote_error = str(exc)

    if current_user.mistral_api_key:
        try:
            saved_mistral_voices = _list_mistral_saved_voices(current_user.mistral_api_key)
        except RuntimeError as exc:
            current_app.logger.warning("unable to list Mistral voices for user %s: %s", current_user.id, exc)
        try:
            available_mistral_models = _list_mistral_models(current_user.mistral_api_key)
        except RuntimeError as exc:
            current_app.logger.warning("unable to list Mistral models for user %s: %s", current_user.id, exc)
    rabbit_tts_voice_options = _build_rabbit_tts_voice_options(saved_mistral_voices)
    rabbit_tts_voice = _normalize_rabbit_tts_voice(rabbit, rabbit_tts_voice_options)
    rabbit_llm_model_options = _build_rabbit_llm_model_options(available_mistral_models)
    rabbit_llm_model = _normalize_rabbit_llm_model(rabbit, rabbit_llm_model_options)

    remote_rabbit = _apply_local_device_state(
        rabbit,
        remote_rabbit,
        serial=linked_device.serial if linked_device else None,
    )

    provisioning_sessions = (
        ProvisioningSession.query.filter_by(rabbit_id=rabbit.id)
        .order_by(ProvisioningSession.created_at.desc())
        .all()
    )
    event_logs = (
        RabbitEventLog.query.filter_by(rabbit_id=rabbit.id)
        .order_by(RabbitEventLog.created_at.desc())
        .all()
    )
    available_devices = (
        DeviceObservation.query.filter(
            (DeviceObservation.rabbit_id.is_(None)) | (DeviceObservation.rabbit_id == rabbit.id)
        )
        .order_by(DeviceObservation.last_seen_at.desc())
        .limit(10)
        .all()
    )
    recordings = (
        RabbitRecording.query.filter_by(rabbit_id=rabbit.id)
        .order_by(RabbitRecording.created_at.desc())
        .limit(20)
        .all()
    )
    conversation_turns = (
        RabbitConversationTurn.query.filter_by(rabbit_id=rabbit.id)
        .order_by(RabbitConversationTurn.created_at.desc())
        .limit(CONVERSATION_MAX_TURNS)
        .all()
    )
    for recording in recordings:
        recording.transcript = _read_recording_transcript(Path(recording.source_path))
    queued_commands = (
        RabbitDeviceCommand.query.filter_by(rabbit_id=rabbit.id)
        .order_by(RabbitDeviceCommand.created_at.desc())
        .limit(20)
        .all()
    )
    ztamps = _latest_ztamps_for_rabbit(rabbit.id)
    return render_template(
        "rabbits/detail.html",
        rabbit=rabbit,
        remote_rabbit=remote_rabbit,
        remote_events=remote_events,
        remote_error=remote_error,
        provisioning_sessions=provisioning_sessions,
        event_logs=event_logs,
        linked_device=linked_device,
        available_devices=available_devices,
        recordings=recordings,
        conversation_turns=list(reversed(conversation_turns)),
        queued_commands=queued_commands,
        ztamps=ztamps,
        led_color_presets=LED_COLOR_PRESETS,
        DEFAULT_RABBIT_PERSONALITY_PROMPT=DEFAULT_RABBIT_PERSONALITY_PROMPT,
        DEFAULT_RABBIT_LLM_MODEL=DEFAULT_RABBIT_LLM_MODEL,
        DEFAULT_RABBIT_TTS_VOICE=DEFAULT_RABBIT_TTS_VOICE,
        RABBIT_LLM_MODEL_OPTIONS=rabbit_llm_model_options,
        rabbit_llm_model=rabbit_llm_model,
        RABBIT_TTS_VOICE_OPTIONS=rabbit_tts_voice_options,
        rabbit_tts_voice=rabbit_tts_voice,
        AUTO_PERFORMANCE_DEFAULT_FREQUENCY_MINUTES=AUTO_PERFORMANCE_DEFAULT_FREQUENCY_MINUTES,
        AUTO_PERFORMANCE_DEFAULT_WINDOW_START=AUTO_PERFORMANCE_DEFAULT_WINDOW_START,
        AUTO_PERFORMANCE_DEFAULT_WINDOW_END=AUTO_PERFORMANCE_DEFAULT_WINDOW_END,
        rabbit_auto_performance_next_at=_format_auto_performance_next_at(rabbit.auto_performance_next_at),
        rabbit_photo_url=_rabbit_photo_url(rabbit),
    )


@main_bp.get("/rabbits/<int:rabbit_id>/details")
@login_required
def rabbit_details(rabbit_id: int):
    rabbit = Rabbit.query.filter_by(id=rabbit_id, owner_id=current_user.id).first_or_404()
    remote_rabbit = None
    remote_events: list[dict] = []
    remote_error = None

    linked_device = (
        DeviceObservation.query.filter_by(rabbit_id=rabbit.id)
        .order_by(DeviceObservation.last_seen_at.desc())
        .first()
    )

    if rabbit.remote_rabbit_id:
        try:
            remote_rabbit = fetch_remote_rabbit(rabbit.remote_rabbit_id)
            if linked_device and remote_rabbit.get("device_serial") != linked_device.serial:
                remote_id = _sync_remote_rabbit(rabbit, linked_serial=linked_device.serial)
                if remote_id:
                    remote_rabbit = fetch_remote_rabbit(remote_id)
            remote_events = fetch_remote_events(rabbit.remote_rabbit_id)
        except NabaztagApiError as exc:
            remote_error = str(exc)

    available_devices = (
        DeviceObservation.query.filter(
            (DeviceObservation.rabbit_id.is_(None)) | (DeviceObservation.rabbit_id == rabbit.id)
        )
        .order_by(DeviceObservation.last_seen_at.desc())
        .limit(10)
        .all()
    )
    provisioning_sessions = (
        ProvisioningSession.query.filter_by(rabbit_id=rabbit.id)
        .order_by(ProvisioningSession.created_at.desc())
        .all()
    )
    return render_template(
        "rabbits/details.html",
        rabbit=rabbit,
        remote_rabbit=remote_rabbit,
        remote_events=remote_events,
        remote_error=remote_error,
        linked_device=linked_device,
        available_devices=available_devices,
        provisioning_sessions=provisioning_sessions,
    )


@main_bp.get("/rabbits/<int:rabbit_id>/alerts")
@login_required
def rabbit_alerts(rabbit_id: int):
    rabbit = Rabbit.query.filter_by(id=rabbit_id, owner_id=current_user.id).first_or_404()
    raw_events = (
        RabbitEventLog.query.filter_by(rabbit_id=rabbit.id)
        .filter(RabbitEventLog.event_type.in_(LIVE_EVENT_TYPES))
        .order_by(RabbitEventLog.created_at.desc())
        .limit(100)
        .all()
    )
    events = [_serialize_live_event(event, rabbit_id=rabbit.id) for event in raw_events]
    commands = (
        RabbitDeviceCommand.query.filter_by(rabbit_id=rabbit.id)
        .order_by(RabbitDeviceCommand.created_at.desc())
        .limit(50)
        .all()
    )
    timeline_items: list[dict] = []
    for event in events:
        timeline_items.append(
            {
                "kind": "event",
                "created_at": event.get("created_at"),
                "data": event,
            }
        )
    for command in commands:
        timeline_items.append(
            {
                "kind": "command",
                "created_at": command.created_at.isoformat() if command.created_at else None,
                "data": command,
            }
        )

    timeline_items.sort(key=lambda item: item.get("created_at") or "", reverse=True)
    return render_template("rabbits/alerts.html", rabbit=rabbit, events=events, timeline_items=timeline_items)


@main_bp.get("/rabbits/<int:rabbit_id>/events/live")
@login_required
def rabbit_live_events(rabbit_id: int):
    rabbit = Rabbit.query.filter_by(id=rabbit_id, owner_id=current_user.id).first_or_404()
    after_id_raw = request.args.get("after_id", "").strip()
    query = RabbitEventLog.query.filter_by(rabbit_id=rabbit.id).filter(
        RabbitEventLog.event_type.in_(LIVE_EVENT_TYPES)
    )
    if after_id_raw.isdigit():
        query = query.filter(RabbitEventLog.id > int(after_id_raw))

    events = query.order_by(RabbitEventLog.id.asc()).limit(50).all()
    payload = [_serialize_live_event(event, rabbit_id=rabbit.id) for event in events]
    return jsonify({"events": payload})


@main_bp.get("/rabbits/<int:rabbit_id>/recordings/live")
@login_required
def rabbit_live_recordings(rabbit_id: int):
    rabbit = Rabbit.query.filter_by(id=rabbit_id, owner_id=current_user.id).first_or_404()
    recordings = (
        RabbitRecording.query.filter_by(rabbit_id=rabbit.id)
        .order_by(RabbitRecording.created_at.desc())
        .limit(20)
        .all()
    )
    return jsonify({"recordings": [_serialize_recording(recording) for recording in recordings]})


@main_bp.get("/rabbits/<int:rabbit_id>/conversation/live")
@login_required
def rabbit_live_conversation(rabbit_id: int):
    rabbit = Rabbit.query.filter_by(id=rabbit_id, owner_id=current_user.id).first_or_404()
    _prune_rabbit_conversation(rabbit)
    turns = (
        RabbitConversationTurn.query.filter_by(rabbit_id=rabbit.id)
        .order_by(RabbitConversationTurn.created_at.desc())
        .limit(CONVERSATION_MAX_TURNS)
        .all()
    )
    return jsonify(
        {
            "summary": rabbit.conversation_summary or "",
            "turns": [_serialize_conversation_turn(turn) for turn in reversed(turns)],
        }
    )


@main_bp.get("/rabbits/<int:rabbit_id>/ztamps/live")
@login_required
def rabbit_live_ztamps(rabbit_id: int):
    rabbit = Rabbit.query.filter_by(id=rabbit_id, owner_id=current_user.id).first_or_404()
    return jsonify({"ztamps": _latest_ztamps_for_rabbit(rabbit.id)})


@main_bp.get("/rabbits/<int:rabbit_id>/history/live")
@login_required
def rabbit_live_history(rabbit_id: int):
    rabbit = Rabbit.query.filter_by(id=rabbit_id, owner_id=current_user.id).first_or_404()
    events = (
        RabbitEventLog.query.filter_by(rabbit_id=rabbit.id)
        .order_by(RabbitEventLog.created_at.desc())
        .limit(20)
        .all()
    )
    return jsonify({"events": [_serialize_event_log(event) for event in events]})


@main_bp.get("/rabbits/<int:rabbit_id>/summary/live")
@login_required
def rabbit_live_summary(rabbit_id: int):
    rabbit = Rabbit.query.filter_by(id=rabbit_id, owner_id=current_user.id).first_or_404()
    linked_device = (
        DeviceObservation.query.filter_by(rabbit_id=rabbit.id)
        .order_by(DeviceObservation.last_seen_at.desc())
        .first()
    )

    remote_state = None
    remote_error = None
    connection_status = rabbit.connection_status

    if rabbit.remote_rabbit_id:
        try:
            remote_rabbit = fetch_remote_rabbit(rabbit.remote_rabbit_id)
            remote_state = {
                "connection_status": remote_rabbit.get("connection_status"),
                "created_at": remote_rabbit.get("created_at"),
                "updated_at": remote_rabbit.get("updated_at"),
                "device_serial": remote_rabbit.get("device_serial"),
                "state": remote_rabbit.get("state"),
            }
            connection_status = remote_rabbit.get("connection_status", connection_status)
        except NabaztagApiError as exc:
            remote_error = str(exc)

    remote_state = _apply_local_device_state(
        rabbit,
        remote_state,
        serial=linked_device.serial if linked_device else None,
    )

    return jsonify(
        {
            "rabbit": {
                "connection_status": connection_status,
                "target": f"{rabbit.target_host}:{rabbit.target_port}" if rabbit.target_host else None,
            },
            "linked_device": {
                "serial": linked_device.serial if linked_device else None,
                "last_seen_at": linked_device.last_seen_at.isoformat() if linked_device and linked_device.last_seen_at else None,
                "last_ip": linked_device.last_ip if linked_device else None,
                "firmware": linked_device.firmware if linked_device else None,
                "hardware": linked_device.hardware if linked_device else None,
                "last_path": linked_device.last_path if linked_device else None,
            }
            if linked_device
            else None,
            "remote_state": remote_state,
            "remote_error": remote_error,
        }
    )


@main_bp.route("/rabbits/<int:rabbit_id>/edit", methods=["GET", "POST"])
@login_required
def edit_rabbit(rabbit_id: int):
    rabbit = Rabbit.query.filter_by(id=rabbit_id, owner_id=current_user.id).first_or_404()

    if request.method == "POST":
        rabbit.name = request.form.get("name", "").strip() or rabbit.name
        rabbit.slug = request.form.get("slug", "").strip().lower() or rabbit.slug
        rabbit.target_host = request.form.get("target_host", "").strip() or None
        target_port = request.form.get("target_port", "").strip()
        rabbit.target_port = int(target_port) if target_port else 10543
        rabbit.notes = request.form.get("notes", "").strip() or None

        if rabbit.target_host and rabbit.remote_rabbit_id:
            try:
                set_remote_target(rabbit.remote_rabbit_id, rabbit.target_host, rabbit.target_port or 10543)
                db.session.add(
                    RabbitEventLog(
                        rabbit_id=rabbit.id,
                        source="portal",
                        event_type="rabbit.target.updated",
                        payload=json.dumps(
                            {"host": rabbit.target_host, "port": rabbit.target_port or 10543}
                        ),
                    )
                )
            except NabaztagApiError as exc:
                flash(f"Mise à jour locale enregistrée, mais cible non synchronisée à l'API: {exc}", "error")

        db.session.commit()
        flash("Lapin mis à jour.", "success")
        return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))

    return render_template("rabbits/edit.html", rabbit=rabbit)


@main_bp.route("/rabbits/<int:rabbit_id>/ztamps/<int:ztamp_id>/edit", methods=["GET", "POST"])
@login_required
def edit_ztamp(rabbit_id: int, ztamp_id: int):
    rabbit = Rabbit.query.filter_by(id=rabbit_id, owner_id=current_user.id).first_or_404()
    ztamp = Ztamp.query.filter_by(id=ztamp_id, rabbit_id=rabbit.id).first_or_404()

    if request.method == "POST":
        ztamp.name = request.form.get("name", "").strip() or None
        ztamp.notes = request.form.get("notes", "").strip() or None
        db.session.commit()
        flash("Ztamp mis à jour.", "success")
        return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))

    return render_template("rabbits/edit_ztamp.html", rabbit=rabbit, ztamp=ztamp)


@main_bp.route("/rabbits/<int:rabbit_id>/provisioning", methods=["GET", "POST"])
@login_required
def rabbit_provisioning(rabbit_id: int):
    rabbit = Rabbit.query.filter_by(id=rabbit_id, owner_id=current_user.id).first_or_404()

    if request.method == "POST":
        setup_ssid = request.form.get("setup_ssid", "").strip() or "NabaztagXX"
        home_wifi_ssid = request.form.get("home_wifi_ssid", "").strip()
        home_wifi_password = request.form.get("home_wifi_password", "").strip()
        server_base_url = request.form.get("server_base_url", "").strip()

        if not home_wifi_ssid or not home_wifi_password or not server_base_url:
            flash("Tous les champs de provisioning sont obligatoires.", "error")
        else:
            session = ProvisioningSession(
                rabbit_id=rabbit.id,
                setup_ssid=setup_ssid,
                home_wifi_ssid=home_wifi_ssid,
                server_base_url=server_base_url,
                status="prepared",
            )
            db.session.add(session)
            db.session.flush()

            try:
                result = prepare_remote_bootstrap(
                    rabbit_id=rabbit.remote_rabbit_id,
                    home_wifi_ssid=home_wifi_ssid,
                    home_wifi_password=home_wifi_password,
                    server_base_url=server_base_url,
                    rabbit_setup_ssid=setup_ssid,
                )
                rabbit.provisioning_state = "prepared"
                session.status = "remote-prepared"
                db.session.add(
                    RabbitEventLog(
                        rabbit_id=rabbit.id,
                        source="bootstrap",
                        event_type="rabbit.provisioning.prepared",
                        payload=json.dumps(result),
                    )
                )
                db.session.commit()
                flash("Provisioning préparé.", "success")
                return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))
            except NabaztagApiError as exc:
                session.status = "error"
                db.session.add(
                    RabbitEventLog(
                        rabbit_id=rabbit.id,
                        source="bootstrap",
                        event_type="rabbit.provisioning.error",
                        payload=json.dumps({"error": str(exc)}),
                    )
                )
                db.session.commit()
                flash(str(exc), "error")

    latest_session = (
        ProvisioningSession.query.filter_by(rabbit_id=rabbit.id)
        .order_by(ProvisioningSession.created_at.desc())
        .first()
    )
    return render_template(
        "rabbits/provisioning.html",
        rabbit=rabbit,
        latest_session=latest_session,
        portal_base_url=_portal_base_url(),
        violet_platform_value=_violet_platform_value(),
    )


@main_bp.route("/rabbits/new", methods=["GET", "POST"])
@login_required
def create_rabbit():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        slug = request.form.get("slug", "").strip().lower()
        target_host = request.form.get("target_host", "").strip()
        target_port = request.form.get("target_port", "").strip()
        notes = request.form.get("notes", "").strip()

        if not name or not slug:
            flash("Le nom et le slug sont obligatoires.", "error")
        else:
            remote_payload = None
            try:
                remote_payload = create_remote_rabbit(name=name, slug=slug)
            except NabaztagApiError as exc:
                flash(f"Lapin créé localement sans enregistrement API: {exc}", "error")
            rabbit = Rabbit(
                name=name,
                slug=slug,
                owner_id=current_user.id,
                target_host=target_host or None,
                target_port=int(target_port) if target_port else 10543,
                notes=notes or None,
                personality_prompt=DEFAULT_RABBIT_PERSONALITY_PROMPT,
                llm_model=DEFAULT_RABBIT_LLM_MODEL,
                tts_voice=DEFAULT_RABBIT_TTS_VOICE,
                provisioning_state="registered",
                remote_rabbit_id=remote_payload["id"] if remote_payload else None,
            )
            db.session.add(rabbit)
            db.session.flush()
            db.session.add(
                RabbitEventLog(
                    rabbit_id=rabbit.id,
                    source="portal",
                    event_type="rabbit.created",
                    payload=json.dumps({"remote_rabbit_id": rabbit.remote_rabbit_id}),
                )
            )
            if target_host and rabbit.remote_rabbit_id:
                try:
                    set_remote_target(rabbit.remote_rabbit_id, target_host, rabbit.target_port or 10543)
                    db.session.add(
                        RabbitEventLog(
                            rabbit_id=rabbit.id,
                            source="portal",
                            event_type="rabbit.target.synced",
                            payload=json.dumps({"host": target_host, "port": rabbit.target_port or 10543}),
                        )
                    )
                except NabaztagApiError as exc:
                    flash(f"Cible locale enregistrée mais non synchronisée à l'API: {exc}", "error")
            db.session.commit()
            flash("Lapin ajouté.", "success")
            return redirect(url_for("main.dashboard"))

    return render_template(
        "rabbits/new.html",
        portal_base_url=_portal_base_url(),
        violet_platform_value=_violet_platform_value(),
    )


@main_bp.post("/rabbits/<int:rabbit_id>/status")
@login_required
def update_rabbit_status(rabbit_id: int):
    rabbit = Rabbit.query.filter_by(id=rabbit_id, owner_id=current_user.id).first_or_404()
    new_status = request.form.get("connection_status", "").strip().lower()
    if new_status not in {"online", "offline", "simulated"}:
        flash("Statut invalide.", "error")
    else:
        rabbit.connection_status = new_status
        db.session.add(
            RabbitEventLog(
                rabbit_id=rabbit.id,
                source="portal",
                event_type="rabbit.status.updated",
                payload=json.dumps({"connection_status": new_status}),
            )
        )
        db.session.commit()
        flash("Statut mis à jour.", "success")
    return redirect(url_for("main.dashboard"))


@main_bp.post("/rabbits/<int:rabbit_id>/action")
@login_required
def rabbit_action(rabbit_id: int):
    rabbit = Rabbit.query.filter_by(id=rabbit_id, owner_id=current_user.id).first_or_404()
    action = request.form.get("action", "").strip().lower()

    if action not in {"connect", "disconnect", "sync", "reset-connection"}:
        flash("Action invalide.", "error")
        return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))

    try:
        linked_device = (
            DeviceObservation.query.filter_by(rabbit_id=rabbit.id)
            .order_by(DeviceObservation.last_seen_at.desc())
            .first()
        )
        remote_id = _sync_remote_rabbit(
            rabbit,
            linked_serial=linked_device.serial if linked_device else None,
        )
        if not remote_id:
            flash("Ce lapin n'est pas encore enregistré dans l'API device.", "error")
            return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))
        if action == "reset-connection":
            disconnect_result = send_remote_action(remote_id, "disconnect", {})
            time.sleep(1.2)
            result = send_remote_action(remote_id, "connect", {"mode": "device"})
            rabbit.connection_status = result.get("rabbit", {}).get("connection_status", rabbit.connection_status)
            db.session.add(
                RabbitEventLog(
                    rabbit_id=rabbit.id,
                    source="api",
                    event_type="rabbit.connection.reset",
                    payload=json.dumps(
                        {
                            "disconnect": disconnect_result,
                            "connect": result,
                        }
                    ),
                )
            )
            db.session.commit()
            flash("Réinitialisation de connexion envoyée.", "success")
            return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))

        payload = {"mode": "device"} if action == "connect" else {}
        result = send_remote_action(remote_id, action, payload)
        rabbit.connection_status = result.get("rabbit", {}).get("connection_status", rabbit.connection_status)
        db.session.add(
            RabbitEventLog(
                rabbit_id=rabbit.id,
                source="api",
                event_type=f"rabbit.{action}",
                payload=json.dumps(result),
            )
        )
        db.session.commit()
        flash(f"Action `{action}` envoyée.", "success")
    except NabaztagApiError as exc:
        flash(str(exc), "error")

    return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))


@main_bp.post("/rabbits/<int:rabbit_id>/device/ears")
@login_required
def rabbit_device_ears(rabbit_id: int):
    rabbit = Rabbit.query.filter_by(id=rabbit_id, owner_id=current_user.id).first_or_404()
    left = request.form.get("left", "").strip()
    right = request.form.get("right", "").strip()
    if not left.isdigit() or not right.isdigit():
        message = "Positions d'oreilles invalides."
        flash(message, "error")
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"ok": False, "message": message}), 400
        return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))
    _enqueue_device_command(
        rabbit,
        command_type="ears",
        payload={"left": int(left), "right": int(right)},
    )
    message = "Commande oreilles mise en file."
    flash(message, "success")
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": True, "message": message})
    return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))


@main_bp.post("/rabbits/<int:rabbit_id>/device/recording/start")
@login_required
def rabbit_device_recording_start(rabbit_id: int):
    rabbit = Rabbit.query.filter_by(id=rabbit_id, owner_id=current_user.id).first_or_404()
    if not rabbit.remote_rabbit_id:
        message = "Ce lapin n'est pas encore synchronisé avec l'API device."
        flash(message, "error")
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"ok": False, "message": message}), 400
        return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))
    max_duration_raw = request.form.get("max_duration_seconds", "").strip()
    max_duration = int(max_duration_raw) if max_duration_raw.isdigit() else 10
    max_duration = max(1, min(120, max_duration))
    try:
        result = start_remote_recording(rabbit.remote_rabbit_id, max_duration_seconds=max_duration)
    except NabaztagApiError as exc:
        message = str(exc)
        flash(message, "error")
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"ok": False, "message": message}), 400
        return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))

    db.session.add(
        RabbitEventLog(
            rabbit_id=rabbit.id,
            source="api",
            event_type="rabbit.recording.started",
            payload=json.dumps(result),
        )
    )
    db.session.commit()
    message = "Enregistrement déclenché."
    flash(message, "success")
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": True, "message": message})
    return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))


@main_bp.post("/rabbits/<int:rabbit_id>/device/recording/stop")
@login_required
def rabbit_device_recording_stop(rabbit_id: int):
    rabbit = Rabbit.query.filter_by(id=rabbit_id, owner_id=current_user.id).first_or_404()
    if not rabbit.remote_rabbit_id:
        message = "Ce lapin n'est pas encore synchronisé avec l'API device."
        flash(message, "error")
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"ok": False, "message": message}), 400
        return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))
    reason = request.form.get("reason", "user").strip().lower()
    if reason not in {"user", "timeout"}:
        reason = "user"
    try:
        result = stop_remote_recording(rabbit.remote_rabbit_id, reason=reason)
    except NabaztagApiError as exc:
        message = str(exc)
        flash(message, "error")
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"ok": False, "message": message}), 400
        return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))

    db.session.add(
        RabbitEventLog(
            rabbit_id=rabbit.id,
            source="api",
            event_type="rabbit.recording.stopped",
            payload=json.dumps(result),
        )
    )
    db.session.commit()
    message = "Arrêt de l'enregistrement demandé."
    flash(message, "success")
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": True, "message": message})
    return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))


@main_bp.post("/rabbits/<int:rabbit_id>/device/led")
@login_required
def rabbit_device_led(rabbit_id: int):
    rabbit = Rabbit.query.filter_by(id=rabbit_id, owner_id=current_user.id).first_or_404()
    target = request.form.get("target", "").strip().lower()
    color_preset = request.form.get("color_preset", "").strip().lower()
    color = LED_COLOR_PRESETS.get(color_preset)
    if target not in {"nose", "left", "center", "right", "bottom"} or color is None:
        message = "Commande LED invalide."
        flash(message, "error")
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"ok": False, "message": message}), 400
        return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))
    _enqueue_device_command(
        rabbit,
        command_type="led",
        payload={"target": target, "color": color, "preset": color_preset},
    )
    message = "Commande LED mise en file."
    flash(message, "success")
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": True, "message": message})
    return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))


@main_bp.post("/rabbits/<int:rabbit_id>/device/audio")
@login_required
def rabbit_device_audio(rabbit_id: int):
    rabbit = Rabbit.query.filter_by(id=rabbit_id, owner_id=current_user.id).first_or_404()
    url = request.form.get("url", "").strip()
    if not url:
        flash("URL audio obligatoire.", "error")
        return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))
    _enqueue_device_command(
        rabbit,
        command_type="audio",
        payload={"url": url},
    )
    flash("Lecture audio mise en file.", "success")
    return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))


@main_bp.post("/rabbits/<int:rabbit_id>/use-cases/test")
@login_required
def rabbit_use_case_test(rabbit_id: int):
    rabbit = Rabbit.query.filter_by(id=rabbit_id, owner_id=current_user.id).first_or_404()
    action = request.form.get("action", "").strip().lower()

    if action == "scene":
        if not current_user.mistral_api_key:
            flash("Ajoute d'abord ton token Mistral dans Mon compte.", "error")
            return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))
        scene_key = request.form.get("scene", "").strip().lower()
        try:
            scene_label, performance = _queue_use_case_scene(
                rabbit,
                api_key=current_user.mistral_api_key,
                scene_key=scene_key,
            )
        except (ValueError, RuntimeError) as exc:
            flash(str(exc), "error")
            return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))
        _append_rabbit_event(
            rabbit,
            source="portal",
            event_type="rabbit.use_case.scene.queued",
            payload={"scene": scene_key, "label": scene_label, **_performance_event_payload(performance)},
        )
        db.session.commit()
        flash(f"Scene `{scene_label}` mise en file.", "success")
        return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))

    if action == "improvise":
        if not current_user.mistral_api_key:
            flash("Ajoute d'abord ton token Mistral dans Mon compte.", "error")
            return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))
        try:
            llm_model = _normalize_rabbit_llm_model(rabbit, _build_rabbit_llm_model_options())
            performance = _generate_mistral_rabbit_performance(
                api_key=current_user.mistral_api_key,
                model=llm_model,
                rabbit_name=rabbit.name,
                personality_prompt=rabbit.personality_prompt or DEFAULT_RABBIT_PERSONALITY_PROMPT,
                user_prompt_override=(
                    "Invente une micro-performance domestique originale, courte et expressive pour divertir "
                    "les habitants maintenant. Utilise bien la voix, les oreilles et les LEDs."
                ),
            )
            _queue_generated_performance(
                rabbit,
                api_key=current_user.mistral_api_key,
                performance=performance,
                source="use_case",
                mode="improvise",
            )
        except RuntimeError as exc:
            flash(str(exc), "error")
            return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))
        _append_rabbit_event(
            rabbit,
            source="portal",
            event_type="rabbit.use_case.improvised",
            payload=_performance_event_payload(performance),
        )
        db.session.commit()
        flash("Improvisation mise en file.", "success")
        return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))

    if action == "radio":
        stream_url = request.form.get("stream_url", "").strip()
        if not stream_url:
            flash("URL de stream obligatoire.", "error")
            return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))
        _enqueue_device_command(
            rabbit,
            command_type="audio",
            payload={"url": stream_url, "source": "radio"},
        )
        _append_rabbit_event(
            rabbit,
            source="portal",
            event_type="rabbit.use_case.radio.queued",
            payload={"url": stream_url},
        )
        db.session.commit()
        flash("Stream audio mis en file.", "success")
        return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))

    if action == "ztamp":
        if not current_user.mistral_api_key:
            flash("Ajoute d'abord ton token Mistral dans Mon compte.", "error")
            return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))
        ztamp_id_raw = request.form.get("ztamp_id", "").strip()
        if not ztamp_id_raw.isdigit():
            flash("Ztamp invalide.", "error")
            return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))
        ztamp = Ztamp.query.filter_by(id=int(ztamp_id_raw), rabbit_id=rabbit.id).first()
        if ztamp is None:
            flash("Ztamp introuvable.", "error")
            return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))
        ztamp_name = (ztamp.name or "").strip() or f"Ztamp {ztamp.tag}"
        try:
            llm_model = _normalize_rabbit_llm_model(rabbit, _build_rabbit_llm_model_options())
            performance = _generate_mistral_rabbit_performance(
                api_key=current_user.mistral_api_key,
                model=llm_model,
                rabbit_name=rabbit.name,
                personality_prompt=rabbit.personality_prompt or DEFAULT_RABBIT_PERSONALITY_PROMPT,
                user_prompt_override=(
                    f"Le lapin vient de detecter le Ztamp `{ztamp_name}` (tag {ztamp.tag}). "
                    "Invente une courte scene tangible, ludique et domestique inspiree par cet objet."
                ),
            )
            _queue_generated_performance(
                rabbit,
                api_key=current_user.mistral_api_key,
                performance=performance,
                source="use_case",
                mode="ztamp",
            )
        except RuntimeError as exc:
            flash(str(exc), "error")
            return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))
        _append_rabbit_event(
            rabbit,
            source="portal",
            event_type="rabbit.use_case.ztamp.queued",
            payload={"ztamp_id": ztamp.id, "ztamp_tag": ztamp.tag, "ztamp_name": ztamp.name, **_performance_event_payload(performance)},
        )
        db.session.commit()
        flash(f"Scenario Ztamp `{ztamp_name}` mis en file.", "success")
        return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))

    flash("Cas d'usage invalide.", "error")
    return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))


@main_bp.post("/rabbits/<int:rabbit_id>/device/audio/upload")
@login_required
def rabbit_device_audio_upload(rabbit_id: int):
    rabbit = Rabbit.query.filter_by(id=rabbit_id, owner_id=current_user.id).first_or_404()
    uploaded = request.files.get("audio_file")
    if uploaded is None or not uploaded.filename:
        message = "Fichier audio obligatoire."
        flash(message, "error")
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"ok": False, "message": message}), 400
        return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))

    original_name = secure_filename(uploaded.filename)
    if not original_name:
        message = "Nom de fichier invalide."
        flash(message, "error")
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"ok": False, "message": message}), 400
        return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))

    extension = Path(original_name).suffix.lower()
    if extension not in {".mp3", ".wav", ".ogg"}:
        message = "Formats acceptés: MP3, WAV, OGG."
        flash(message, "error")
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"ok": False, "message": message}), 400
        return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))

    stored_name = f"{rabbit.slug}-{secrets.token_hex(6)}{extension}"
    destination = _audio_assets_dir() / stored_name
    uploaded.save(destination)

    asset_url = f"broadcast/ojn_local/audio/{stored_name}"
    _enqueue_device_command(
        rabbit,
        command_type="audio",
        payload={"url": asset_url, "source": "upload", "filename": original_name},
    )
    message = "Audio téléversé et lecture mise en file."
    flash(message, "success")
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": True, "message": message})
    return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))


@main_bp.post("/rabbits/<int:rabbit_id>/device/say")
@login_required
def rabbit_device_say(rabbit_id: int):
    rabbit = Rabbit.query.filter_by(id=rabbit_id, owner_id=current_user.id).first_or_404()
    mode = request.form.get("mode", "manual").strip().lower()
    message = request.form.get("message", "").strip()
    generated_performance = None

    if not current_user.mistral_api_key:
        error_message = "Ajoute d'abord ton token Mistral dans Mon compte."
        flash(error_message, "error")
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"ok": False, "message": error_message}), 400
        return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))

    if mode == "generate":
        try:
            llm_model = _normalize_rabbit_llm_model(rabbit, _build_rabbit_llm_model_options())
            generated_performance = _generate_mistral_rabbit_performance(
                api_key=current_user.mistral_api_key,
                model=llm_model,
                rabbit_name=rabbit.name,
                personality_prompt=rabbit.personality_prompt or DEFAULT_RABBIT_PERSONALITY_PROMPT,
            )
            message = generated_performance["text"]
        except RuntimeError as exc:
            error_message = str(exc)
            flash(error_message, "error")
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"ok": False, "message": error_message}), 400
            return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))
    else:
        if not message:
            error_message = "Message obligatoire."
            flash(error_message, "error")
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"ok": False, "message": error_message}), 400
            return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))
        if len(message) > 500:
            error_message = "Message trop long. Limite: 500 caractères."
            flash(error_message, "error")
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"ok": False, "message": error_message}), 400
            return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))

    try:
        performance = generated_performance or {
            "text": message,
            "ears": {"left": None, "right": None},
            "led_commands": [],
        }
        _asset_path, _asset_name = _queue_generated_performance(
            rabbit,
            api_key=current_user.mistral_api_key,
            performance=performance,
            source="tts",
            mode=mode,
        )
    except (ValueError, RuntimeError) as exc:
        error_message = f"Synthèse vocale impossible: {exc}"
        flash(error_message, "error")
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"ok": False, "message": error_message}), 400
        return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))
    success_message = (
        "Texte genere puis lecture mise en file."
        if mode == "generate"
        else "Message synthetise et lecture mise en file."
    )
    flash(success_message, "success")
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify(
            {
                "ok": True,
                "message": success_message,
                "generated_text": message if mode == "generate" else None,
                "generated_performance": generated_performance if mode == "generate" else None,
            }
        )
    return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))


@main_bp.post("/rabbits/<int:rabbit_id>/photo")
@login_required
def upload_rabbit_photo(rabbit_id: int):
    rabbit = Rabbit.query.filter_by(id=rabbit_id, owner_id=current_user.id).first_or_404()
    uploaded = request.files.get("photo_file")
    if uploaded is None or not uploaded.filename:
        flash("Photo obligatoire.", "error")
        return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))

    original_name = secure_filename(uploaded.filename)
    if not original_name:
        flash("Nom de fichier invalide.", "error")
        return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))

    extension = Path(original_name).suffix.lower()
    if extension not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        flash("Formats acceptés : JPG, PNG, WEBP, GIF.", "error")
        return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))

    stored_name = f"{rabbit.slug}-{secrets.token_hex(8)}{extension}"
    destination = _rabbit_photos_dir() / stored_name
    uploaded.save(destination)

    if rabbit.photo_filename:
        previous = _rabbit_photos_dir() / rabbit.photo_filename
        if previous.exists():
            try:
                previous.unlink()
            except OSError:
                current_app.logger.warning("unable to delete previous rabbit photo: %s", previous)

    rabbit.photo_filename = stored_name
    rabbit.photo_original_name = original_name
    db.session.add(
        RabbitEventLog(
            rabbit_id=rabbit.id,
            source="portal",
            event_type="rabbit.photo.updated",
            payload=json.dumps({"filename": stored_name, "original_name": original_name}),
        )
    )
    db.session.commit()
    flash("Photo du lapin mise à jour.", "success")
    return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))


@main_bp.get("/rabbits/<int:rabbit_id>/photo")
@login_required
def rabbit_photo(rabbit_id: int):
    rabbit = Rabbit.query.filter_by(id=rabbit_id, owner_id=current_user.id).first_or_404()
    if not rabbit.photo_filename:
        return Response("Not found\n", status=404, mimetype="text/plain")
    path = _rabbit_photos_dir() / rabbit.photo_filename
    if not path.exists():
        return Response("Not found\n", status=404, mimetype="text/plain")
    mimetype = guess_type(path.name)[0] or "application/octet-stream"
    return send_file(path, mimetype=mimetype, as_attachment=False, download_name=path.name)


@main_bp.get("/rabbit-photo/default")
def default_rabbit_photo():
    path = _default_rabbit_photo_path()
    if not path.exists():
        return Response("Not found\n", status=404, mimetype="text/plain")
    mimetype = guess_type(path.name)[0] or "application/octet-stream"
    return send_file(path, mimetype=mimetype, as_attachment=False, download_name=path.name)


@main_bp.get("/rabbit-photo/led-layout")
def rabbit_led_layout_photo():
    path = _rabbit_led_layout_photo_path()
    if not path.exists():
        return Response("Not found\n", status=404, mimetype="text/plain")
    mimetype = guess_type(path.name)[0] or "application/octet-stream"
    return send_file(path, mimetype=mimetype, as_attachment=False, download_name=path.name)


@main_bp.get("/recordings/<path:filename>")
@login_required
def download_recording(filename: str):
    recording = RabbitRecording.query.filter_by(filename=filename).first_or_404()
    rabbit = Rabbit.query.filter_by(id=recording.rabbit_id, owner_id=current_user.id).first_or_404()
    mimetype = guess_type(recording.source_path)[0] or "application/octet-stream"
    return send_file(recording.source_path, mimetype=mimetype, as_attachment=False, download_name=Path(recording.source_path).name)


@main_bp.post("/rabbits/<int:rabbit_id>/claim-device")
@login_required
def claim_device(rabbit_id: int):
    rabbit = Rabbit.query.filter_by(id=rabbit_id, owner_id=current_user.id).first_or_404()
    observation_id = request.form.get("observation_id", "").strip()
    if not observation_id.isdigit():
        flash("Périphérique invalide.", "error")
        return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))

    observation = DeviceObservation.query.get(int(observation_id))
    if observation is None:
        flash("Périphérique introuvable.", "error")
        return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))

    observation.rabbit_id = rabbit.id
    rabbit.connection_status = "online"
    db.session.add(
        RabbitEventLog(
            rabbit_id=rabbit.id,
            source="portal",
            event_type="rabbit.device.claimed",
            payload=json.dumps({"serial": observation.serial}),
        )
    )

    try:
        _sync_remote_rabbit(rabbit, linked_serial=observation.serial)
    except NabaztagApiError as exc:
        flash(f"Lapin physique lié localement, mais non synchronisé à l'API: {exc}", "error")

    db.session.commit()
    flash(f"Lapin physique {observation.serial} rattaché.", "success")
    return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))
