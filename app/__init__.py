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


    @app.cli.command("seed-demo")
    def seed_demo():
        """Add a small, repeatable set of sample furniture for previewing the storefront."""
        from decimal import Decimal
        demo_categories = [
            ("Living room", "living-room", "https://images.unsplash.com/photo-1600210492486-724fe5c67fb0?w=900&q=85"),
            ("Bedroom", "bedroom", "https://images.unsplash.com/photo-1616486338812-3dadae4b4ace?w=900&q=85"),
            ("Dining", "dining", "https://images.unsplash.com/photo-1600566753086-00f18fb6b3ea?w=900&q=85"),
            ("Office", "office", "https://images.unsplash.com/photo-1497366754035-f200968a6e72?w=900&q=85"),
        ]
        categories = {}
        for name, slug, image in demo_categories:
            category = models.Category.query.filter_by(slug=slug).first()
            if not category:
                category = models.Category(name=name, slug=slug, image_url=image)
                db.session.add(category)
            categories[slug] = category
        db.session.flush()
        demo_products = [
            ("Lennox Modular Sofa", "lennox-modular-sofa", "living-room", 1850000, "Bouclé", "Oatmeal", "https://images.unsplash.com/photo-1555041469-a586c61ea9bc?w=1000&q=88", True),
            ("Arlo Accent Chair", "arlo-accent-chair", "living-room", 685000, "Solid ash & linen", "Natural", "https://images.unsplash.com/photo-1567538096630-e0c55bd6374c?w=1000&q=88", True),
            ("Marlow Coffee Table", "marlow-coffee-table", "living-room", 420000, "Solid oak", "Warm oak", "https://images.unsplash.com/photo-1499933374294-4584851497cc?w=1000&q=88", False),
            ("Sora Platform Bed", "sora-platform-bed", "bedroom", 1250000, "Solid wood", "Walnut", "https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?w=1000&q=88", True),
            ("Noma Bedside Table", "noma-bedside-table", "bedroom", 285000, "Oak veneer", "Natural oak", "https://images.unsplash.com/photo-1499933374294-4584851497cc?w=1000&q=88", False),
            ("Forma Dining Table", "forma-dining-table", "dining", 980000, "Solid oak", "Honey oak", "https://images.unsplash.com/photo-1600566753190-17f0baa2a6c3?w=1000&q=88", True),
            ("Aster Dining Chair", "aster-dining-chair", "dining", 195000, "Ash wood & fabric", "Sand", "https://images.unsplash.com/photo-1503602642458-232111445657?w=1000&q=88", False),
            ("Rowan Writing Desk", "rowan-writing-desk", "office", 560000, "Oak & steel", "Natural", "https://images.unsplash.com/photo-1497366811353-6870744d04b2?w=1000&q=88", False),
        ]
        added = 0
        for name, slug, category_slug, price, material, colour, image, featured in demo_products:
            if models.Product.query.filter_by(slug=slug).first():
                continue
            db.session.add(models.Product(
                name=name, slug=slug, category=categories[category_slug],
                sku="DEMO-" + slug.upper().replace("-", "")[:12],
                short_description="A considered piece for a more beautiful everyday.",
                description="Preview sample product. Replace this description and imagery with your own product details before launch.",
                price=Decimal(price), brand="Haven & Form", material=material,
                colour=colour, dimensions="Made to order", finish="Natural",
                stock=8, featured=featured, is_new=not featured, is_active=True,
                image_url=image,
            ))
            added += 1
        db.session.commit()
        print(f"Demo catalogue ready. Added {added} products; existing products were left unchanged.")

    @app.get("/health")
    def health():
        db.session.execute(db.text("SELECT 1"))
        return {"status": "ok", "database": "ok"}

    @app.errorhandler(404)
    def not_found(error):
        return __import__("flask").render_template("errors/404.html"), 404

    return app
