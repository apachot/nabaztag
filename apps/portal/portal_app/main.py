from __future__ import annotations

import json
import time
from pathlib import Path

from flask import Blueprint, Response, current_app, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from .api_client import (
    NabaztagApiError,
    create_remote_rabbit,
    fetch_remote_events,
    fetch_remote_rabbit,
    prepare_remote_bootstrap,
    send_remote_action,
    set_remote_target,
)
from .extensions import db
from .models import ProvisioningSession, Rabbit, RabbitEventLog

main_bp = Blueprint("main", __name__)


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


def _bootcode_path() -> Path:
    return Path(current_app.root_path).parents[2] / "deploy" / "assets" / "bootcode.default"


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
    body = _locate_reply()
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
    filename = f"record_{serial_number}_{int(time.time())}.wav"
    filepath = _recordings_dir() / filename
    filepath.write_bytes(payload)
    current_app.logger.info(
        "nabaztag.record sn=%s size=%s file=%s",
        serial_number,
        len(payload),
        str(filepath),
    )
    return Response("", mimetype="text/plain")


@main_bp.route("/vl/rfid.jsp", methods=["GET", "POST"])
def violet_rfid():
    serial_number = (request.args.get("sn") or "").replace(":", "").lower()
    tag_id = request.args.get("t") or ""
    current_app.logger.info("nabaztag.rfid sn=%s tag=%s", serial_number, tag_id)
    return Response("", mimetype="text/plain")


@main_bp.route("/vl/sendMailXMPP.jsp", methods=["GET", "POST"])
def violet_send_mail_xmpp():
    mac = (request.args.get("m") or "").replace(":", "").lower()
    current_app.logger.info("nabaztag.send_mail_xmpp mac=%s args=%s", mac, dict(request.args))
    return Response("", mimetype="text/plain")


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

    if rabbit.remote_rabbit_id:
        try:
            remote_rabbit = fetch_remote_rabbit(rabbit.remote_rabbit_id)
            remote_events = fetch_remote_events(rabbit.remote_rabbit_id)
            rabbit.connection_status = remote_rabbit.get("connection_status", rabbit.connection_status)
            db.session.commit()
        except NabaztagApiError as exc:
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
    return render_template(
        "rabbits/detail.html",
        rabbit=rabbit,
        remote_rabbit=remote_rabbit,
        remote_events=remote_events,
        remote_error=remote_error,
        provisioning_sessions=provisioning_sessions,
        event_logs=event_logs,
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
    if not rabbit.remote_rabbit_id:
        flash("Ce lapin n'est pas encore enregistré dans l'API device.", "error")
        return redirect(url_for("main.rabbit_detail", rabbit_id=rabbit.id))

    payload = {"mode": "device"} if action == "connect" else {}
    try:
        result = send_remote_action(rabbit.remote_rabbit_id, action, payload)
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
