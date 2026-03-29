from __future__ import annotations

import json

from flask import Blueprint, flash, redirect, render_template, request, url_for
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
    return f"{_portal_base_url().rstrip('/')}/vl"


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
