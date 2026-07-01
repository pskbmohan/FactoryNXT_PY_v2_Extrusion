from flask import Blueprint, render_template, request, redirect, url_for, flash, session

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        session['username'] = username
        flash(f"Logged in as {username}", "success")
        return redirect(url_for("dashboard.index"))
    return render_template("login.html")
