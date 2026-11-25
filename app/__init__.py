import os
from flask import Flask, g, session, redirect, url_for, flash, request
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, current_user
from flask_wtf import CSRFProtect
from sqlalchemy import select

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()

def create_app(config_object=None):
    app = Flask(__name__)
    database_url = os.getenv("DATABASE_URL", "sqlite:///furniture_store.db").strip()
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
    elif database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    app.config.update(
        SECRET_KEY=os.getenv("SECRET_KEY", "dev-only-change-this-secret-before-deploy"),
        SQLALCHEMY_DATABASE_URI=database_url,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "false").lower() == "true",
        MAX_CONTENT_LENGTH=12 * 1024 * 1024,
        STORE_NAME=os.getenv("STORE_NAME", "Haven & Form"),
        STORE_WHATSAPP=os.getenv("STORE_WHATSAPP", ""),
    )
    if config_object:
        app.config.from_object(config_object)
    if os.getenv("APP_ENV", "").lower() == "production":
        if len(app.config.get("SECRET_KEY", "")) < 32:
            raise RuntimeError("Production requires a SECRET_KEY of at least 32 characters.")
        if app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite:"):
            raise RuntimeError("Production requires a persistent PostgreSQL DATABASE_URL.")
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    csrf.init_app(app)

    from . import models
    from .routes import storefront, auth, admin
    app.register_blueprint(storefront.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(admin.bp)

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return db.session.get(models.User, int(user_id))
        except (TypeError, ValueError):
            return None

    @app.before_request
    def load_shared_context():
        g.store_name = app.config["STORE_NAME"]

    @app.context_processor
    def inject_globals():
        cart = session.get("cart", {})
        return {
            "store_name": app.config["STORE_NAME"],
            "cart_count": sum(max(0, int(item.get("quantity", 0))) for item in cart.values() if isinstance(item, dict)),
            "wishlist_ids": session.get("wishlist", []),
            "current_year": __import__("datetime").datetime.now().year,
        }

    @app.cli.command("init-db")
    def init_db():
        """Create tables for a fresh installation; use migrations for subsequent schema changes."""
        db.create_all()
        email = os.getenv("ADMIN_EMAIL", "").strip().lower()
        password = os.getenv("ADMIN_PASSWORD", "")
        if email and password and not models.User.query.filter_by(email=email).first():
            if len(password) < 12:
                raise RuntimeError("ADMIN_PASSWORD must contain at least 12 characters.")
            user = models.User(name=os.getenv("ADMIN_NAME", "Store Administrator"), email=email, role="ADMIN")
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
        print("Database tables are ready.")

    @app.get("/health")
    def health():
        db.session.execute(db.text("SELECT 1"))
        return {"status": "ok", "database": "ok"}

    @app.errorhandler(404)
    def not_found(error):
        return __import__("flask").render_template("errors/404.html"), 404

    return app
