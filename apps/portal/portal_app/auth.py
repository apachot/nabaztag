from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from .extensions import db
from .models import User

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not email or not password:
            flash("Email et mot de passe sont obligatoires.", "error")
        elif password != confirm_password:
            flash("Les mots de passe ne correspondent pas.", "error")
        elif User.query.filter_by(email=email).first() is not None:
            flash("Un compte existe déjà avec cet email.", "error")
        else:
            user = User(email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash("Compte créé.", "success")
            return redirect(url_for("main.dashboard"))

    return render_template("auth/register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()

        if user is None or not user.check_password(password):
            flash("Identifiants invalides.", "error")
        else:
            login_user(user, remember=True)
            flash("Connexion réussie.", "success")
            next_url = request.args.get("next")
            return redirect(next_url or url_for("main.dashboard"))

    return render_template("auth/login.html")


@auth_bp.post("/logout")
@login_required
def logout():
    logout_user()
    flash("Déconnecté.", "success")
    return redirect(url_for("main.index"))

