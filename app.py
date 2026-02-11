import os
import secrets
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user, login_required,
    logout_user, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash


def create_app():
    app = Flask(__name__, instance_relative_config=True)

    # Create instance folder (Flask recommended)
    os.makedirs(app.instance_path, exist_ok=True)

    # ---------- SECRET KEY (Unique per project/machine, persisted) ----------
    # Used for session/cookie signing (NOT for password hashing)
    secret_file = os.path.join(app.instance_path, "secret_key.txt")
    if os.path.exists(secret_file):
        with open(secret_file, "r", encoding="utf-8") as f:
            app.config["SECRET_KEY"] = f.read().strip()
    else:
        sk = secrets.token_urlsafe(48)
        with open(secret_file, "w", encoding="utf-8") as f:
            f.write(sk)
        app.config["SECRET_KEY"] = sk

    # ---------- DB ----------
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///auth.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    return app


app = create_app()
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.login_message_category = "warning"
login_manager.init_app(app)


# ------------------ MODEL ------------------
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)

    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(180), unique=True, nullable=False, index=True)

    # store salted hash here (NOT plaintext)
    password_hash = db.Column(db.String(255), nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password: str):
        # strong salted hashing; every user will get different salt automatically
        self.password_hash = generate_password_hash(password, method="scrypt")

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# ------------------ ROUTES ------------------
@app.route("/")
def home():
    return redirect(url_for("dashboard" if current_user.is_authenticated else "login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        errors = []
        if len(full_name) < 2:
            errors.append("Full name must be at least 2 characters.")
        if "@" not in email or "." not in email:
            errors.append("Please enter a valid email address.")
        if len(password) < 6:
            errors.append("Password must be at least 6 characters.")
        if password != confirm:
            errors.append("Passwords do not match.")
        if User.query.filter_by(email=email).first():
            errors.append("Email already registered. Please log in.")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("register.html", full_name=full_name, email=email)

        user = User(full_name=full_name, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash("Account created successfully. Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        remember = True if request.form.get("remember") == "on" else False

        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            flash("Invalid email or password.", "danger")
            return render_template("login.html", email=email)

        login_user(user, remember=remember)
        flash(f"Welcome back, {user.full_name.split()[0]} 👋", "success")
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out successfully.", "info")
    return redirect(url_for("login"))


# ------------------ INIT DB ------------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
