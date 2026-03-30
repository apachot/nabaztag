from __future__ import annotations

import json
import secrets
import subprocess
import time
from mimetypes import guess_type
from pathlib import Path

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
    RabbitDeviceCommand,
    RabbitEventLog,
    RabbitRecording,
    utc_now,
)

main_bp = Blueprint("main", __name__)

LIVE_EVENT_TYPES = {
    "rabbit.button",
    "rabbit.recording.uploaded",
    "rabbit.rfid.detected",
    "rabbit.ears.moved",
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


def _latest_ztamps_for_rabbit(rabbit_id: int, *, limit: int = 20) -> list[dict]:
    events = (
        RabbitEventLog.query.filter_by(rabbit_id=rabbit_id, event_type="rabbit.rfid.detected")
        .order_by(RabbitEventLog.created_at.desc())
        .all()
    )
    seen_tags: set[str] = set()
    ztamps: list[dict] = []
    for event in events:
        serialized = _serialize_event_log(event)
        payload = serialized.get("payload") or {}
        tag = payload.get("tag")
        if not tag or tag in seen_tags:
            continue
        seen_tags.add(tag)
        ztamps.append(
            {
                "tag": tag,
                "created_at": serialized.get("created_at"),
                "serial": payload.get("serial"),
            }
        )
        if len(ztamps) >= limit:
            break
    return ztamps


def _synthesize_tts_asset(*, rabbit_slug: str, text: str) -> tuple[Path, str]:
    normalized_text = " ".join(text.split())
    if not normalized_text:
        raise ValueError("empty text")

    token = secrets.token_hex(6)
    wav_name = f"{rabbit_slug}-tts-{token}.wav"
    wav_path = _audio_assets_dir() / wav_name

    try:
        espeak_result = subprocess.run(
            [
                "espeak",
                "-v",
                "fr",
                "-s",
                "155",
                "-w",
                str(wav_path),
                normalized_text,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("espeak is not available on the server") from exc

    if espeak_result.returncode != 0 or not wav_path.exists():
        raise RuntimeError((espeak_result.stderr or espeak_result.stdout or "espeak failed").strip())

    mp3_path = wav_path.with_suffix(".mp3")
    try:
        ffmpeg_result = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(wav_path),
                "-codec:a",
                "libmp3lame",
                "-q:a",
                "4",
                str(mp3_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return wav_path, wav_name

    if ffmpeg_result.returncode == 0 and mp3_path.exists():
        try:
            wav_path.unlink()
        except OSError:
            current_app.logger.warning("unable to delete wav tts asset after mp3 conversion: %s", wav_path)
        return mp3_path, mp3_path.name

    current_app.logger.warning(
        "ffmpeg tts conversion failed for %s: %s",
        wav_path,
        (ffmpeg_result.stderr or ffmpeg_result.stdout)[-1000:],
    )
    return wav_path, wav_name


def _maybe_transcode_recording_to_mp3(source_path: Path) -> Path:
    target_path = source_path.with_suffix(".mp3")
    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(source_path),
                "-af",
                "highpass=f=280,"
                "lowpass=f=2600,"
                "afftdn=nf=-40,"
                "anlmdn=s=0.0003,"
                "acompressor=threshold=-20dB:ratio=3:attack=5:release=50,"
                "dynaudnorm=f=150:g=11",
                "-codec:a",
                "libmp3lame",
                "-q:a",
                "4",
                str(target_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        current_app.logger.info("ffmpeg not available, keeping raw recording %s", source_path)
        return source_path

    if result.returncode != 0 or not target_path.exists():
        current_app.logger.warning(
            "ffmpeg conversion failed for %s: %s",
            source_path,
            (result.stderr or result.stdout)[-1000:],
        )
        return source_path

    try:
        source_path.unlink()
    except OSError:
        current_app.logger.warning("unable to delete raw recording after mp3 conversion: %s", source_path)
    return target_path


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
    raw_filename = f"record_{serial_number}_{int(time.time())}.wav"
    raw_filepath = _recordings_dir() / raw_filename
    raw_filepath.write_bytes(payload)
    stored_path = _maybe_transcode_recording_to_mp3(raw_filepath)
    filename = stored_path.name
    transcript = _transcribe_recording_asset(stored_path)
    rabbit = _rabbit_for_serial(serial_number)
    if rabbit is not None:
        db.session.add(
            RabbitRecording(
                rabbit_id=rabbit.id,
                serial=serial_number,
                filename=filename,
                source_path=str(stored_path),
                mode=request.args.get("m"),
            )
        )
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


@main_bp.get("/rabbits/<int:rabbit_id>")
@login_required
def rabbit_detail(rabbit_id: int):
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
        queued_commands=queued_commands,
        ztamps=ztamps,
        led_color_presets=LED_COLOR_PRESETS,
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
    events = (
        RabbitEventLog.query.filter_by(rabbit_id=rabbit.id)
        .filter(RabbitEventLog.event_type.in_(LIVE_EVENT_TYPES))
        .order_by(RabbitEventLog.created_at.desc())
        .limit(100)
        .all()
    )
    return render_template("rabbits/alerts.html", rabbit=rabbit, events=events)


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
    payload = []
    for event in events:
        try:
            parsed_payload = json.loads(event.payload) if event.payload else None
        except json.JSONDecodeError:
            parsed_payload = {"raw": event.payload}
        payload.append(
            {
                "id": event.id,
                "event_type": event.event_type,
                "source": event.source,
                "created_at": event.created_at.isoformat() if event.created_at else None,
                "payload": parsed_payload,
            }
        )
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

    if action not in {"connect", "disconnect", "sync"}:
        flash("Action invalide.", "error")
        return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))

    payload = {"mode": "device"} if action == "connect" else {}
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
        flash("Positions d'oreilles invalides.", "error")
        return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))
    _enqueue_device_command(
        rabbit,
        command_type="ears",
        payload={"left": int(left), "right": int(right)},
    )
    flash("Commande oreilles mise en file.", "success")
    return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))


@main_bp.post("/rabbits/<int:rabbit_id>/device/led")
@login_required
def rabbit_device_led(rabbit_id: int):
    rabbit = Rabbit.query.filter_by(id=rabbit_id, owner_id=current_user.id).first_or_404()
    target = request.form.get("target", "").strip().lower()
    color_preset = request.form.get("color_preset", "").strip().lower()
    color = LED_COLOR_PRESETS.get(color_preset)
    if target not in {"nose", "left", "center", "right", "bottom"} or color is None:
        flash("Commande LED invalide.", "error")
        return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))
    _enqueue_device_command(
        rabbit,
        command_type="led",
        payload={"target": target, "color": color, "preset": color_preset},
    )
    flash("Commande LED mise en file.", "success")
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


@main_bp.post("/rabbits/<int:rabbit_id>/device/audio/upload")
@login_required
def rabbit_device_audio_upload(rabbit_id: int):
    rabbit = Rabbit.query.filter_by(id=rabbit_id, owner_id=current_user.id).first_or_404()
    uploaded = request.files.get("audio_file")
    if uploaded is None or not uploaded.filename:
        flash("Fichier audio obligatoire.", "error")
        return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))

    original_name = secure_filename(uploaded.filename)
    if not original_name:
        flash("Nom de fichier invalide.", "error")
        return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))

    extension = Path(original_name).suffix.lower()
    if extension not in {".mp3", ".wav", ".ogg"}:
        flash("Formats acceptés: MP3, WAV, OGG.", "error")
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
    flash("Audio téléversé et lecture mise en file.", "success")
    return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))


@main_bp.post("/rabbits/<int:rabbit_id>/device/say")
@login_required
def rabbit_device_say(rabbit_id: int):
    rabbit = Rabbit.query.filter_by(id=rabbit_id, owner_id=current_user.id).first_or_404()
    message = request.form.get("message", "").strip()
    if not message:
        flash("Message obligatoire.", "error")
        return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))
    if len(message) > 500:
        flash("Message trop long. Limite: 500 caractères.", "error")
        return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))

    try:
        asset_path, asset_name = _synthesize_tts_asset(rabbit_slug=rabbit.slug, text=message)
    except (ValueError, RuntimeError) as exc:
        flash(f"Synthèse vocale impossible: {exc}", "error")
        return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))

    asset_url = f"broadcast/ojn_local/audio/{asset_name}"
    _enqueue_device_command(
        rabbit,
        command_type="audio",
        payload={
            "url": asset_url,
            "source": "tts",
            "filename": asset_path.name,
            "text": message,
        },
    )
    flash("Message synthétisé et lecture mise en file.", "success")
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
