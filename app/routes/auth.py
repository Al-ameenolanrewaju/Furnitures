from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, current_user
from ..models import User

bp = Blueprint("auth", __name__)

@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("admin.dashboard") if current_user.role == "ADMIN" else url_for("store.home"))
    if request.method == "POST":
        user = User.query.filter_by(email=request.form.get("email", "").strip().lower(), active=True).first()
        if user and user.check_password(request.form.get("password", "")):
            login_user(user, remember=bool(request.form.get("remember")))
            return redirect(request.args.get("next") or (url_for("admin.dashboard") if user.role == "ADMIN" else url_for("store.home")))
        flash("Email or password is incorrect.", "danger")
    return render_template("auth/login.html")

@bp.get("/logout")
def logout():
    logout_user()
    return redirect(url_for("store.home"))
