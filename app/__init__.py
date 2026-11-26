import os

from flask import Flask, g, request, session, Response, flash, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf import CSRFProtect
from flask_wtf.csrf import CSRFError
from werkzeug.utils import safe_join
from sqlalchemy.orm import undefer
from sqlalchemy import event


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
        SECRET_KEY=os.getenv("SECRET_KEY"),
        SQLALCHEMY_DATABASE_URI=database_url,
        SQLALCHEMY_ENGINE_OPTIONS={},
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        WTF_CSRF_ENABLED=True,
        WTF_CSRF_TIME_LIMIT=86400,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "true").lower() == "true",
        UPLOAD_FOLDER=os.getenv("UPLOAD_FOLDER", os.path.join(app.instance_path, "uploads")),
        MAX_CONTENT_LENGTH=10 * 1024 * 1024,
    )
    if config_object:
        app.config.from_object(config_object)
    if not app.testing:
        secret_key = app.config.get("SECRET_KEY")
        if not isinstance(secret_key, str) or len(secret_key) < 32:
            raise RuntimeError("Configure a SECRET_KEY with at least 32 characters outside testing.")
        if os.getenv("APP_ENV", "").strip().lower() == "production" and app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite:"):
            raise RuntimeError("Configure DATABASE_URL with a persistent PostgreSQL database for production.")

    db.init_app(app)
    if database_url.startswith(("postgresql://", "postgresql+psycopg://")):
        # Supabase transaction poolers may discard session-level settings.
        # Set the schema for every transaction so pooled connections cannot
        # leak the public schema or another application's search_path.
        with app.app_context():
            engine = db.engine

        @event.listens_for(engine, "begin")
        def set_furniture_search_path(connection):
            connection.exec_driver_sql("SET LOCAL search_path TO furniture")

    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    login_manager.login_view = "auth.login"

    from . import models

    @app.cli.command("init-db")
    def init_db():
        """Initialize the database schema for the Render startup command."""
        db.create_all()
        print("Database tables are ready.")

    @app.cli.command("seed-demo")
    def seed_demo():
        """Create the temporary preview store and a small sample furniture catalogue."""
        from .utils import slugify

        store_name = os.getenv("STORE_NAME", "Furniture Store").strip()
        store_slug = slugify(os.getenv("STORE_SLUG", "") or store_name)
        owner_name = os.getenv("STORE_OWNER_NAME", "Prototype Owner").strip()
        owner_email = os.getenv("STORE_OWNER_EMAIL", "prototype-owner@example.com").strip().lower()
        owner_password = os.getenv("STORE_OWNER_PASSWORD", "")

        business = models.Business.query.filter_by(slug=store_slug).first()
        if business is None:
            business = models.Business(name=store_name, slug=store_slug,
                description="Furniture catalogue preview. Message us to confirm availability and delivery.",
                contact_email=owner_email, status="ACTIVE")
            db.session.add(business)
            db.session.flush()

        # The public demo catalogue must not depend on an admin password being
        # configured in Render. Create an owner only when valid credentials
        # have explicitly been supplied.
        owner = models.User.query.filter_by(email=owner_email).first()
        if owner is not None and owner.business_id != business.id:
            raise RuntimeError("Preview owner email is assigned to another account.")
        if owner is None and owner_password:
            if len(owner_password) < 12:
                raise RuntimeError("STORE_OWNER_PASSWORD must contain at least 12 characters.")
            owner = models.User(business_id=business.id, name=owner_name,
                email=owner_email, role="OWNER", active=True)
            owner.set_password(owner_password)
            db.session.add(owner)

        if not models.StoreSettings.query.filter_by(business_id=business.id).first():
            db.session.add(models.StoreSettings(business_id=business.id,
                hero_title="Furniture that makes a house feel like home",
                tagline="Thoughtfully selected pieces for every room",
                catalogue_title="Explore the collection",
                about_text="Browse our furniture catalogue and message us to confirm availability, pricing and delivery.",
                footer_text="Quality furniture for comfortable living."))

        categories = {}
        for room, name in [("Living Room", "Sofas"), ("Living Room", "Coffee Tables"),
                           ("Bedroom", "Beds"), ("Dining", "Dining Tables")]:
            slug = slugify(f"{room}-{name}")
            category = models.Category.query.filter_by(business_id=business.id, slug=slug).first()
            if category is None:
                category = models.Category(business_id=business.id, name=name, slug=slug, gender=room)
                db.session.add(category)
                db.session.flush()
            categories[name] = category

        samples = [
            ("Modern 3-Seater Sofa", "sofa", "A contemporary three-seater sofa with a comfortable, clean-lined silhouette. Demo listing — confirm availability and final price.", 850000, "Sofas", "https://images.unsplash.com/photo-1555041469-a586c61ea9bc?w=1200"),
            ("Minimalist Coffee Table", "coffee-table", "A versatile coffee table for modern living spaces. Demo listing — confirm availability and final price.", 220000, "Coffee Tables", "https://images.unsplash.com/photo-1499933374294-4584851497cc?w=1200"),
            ("Contemporary Upholstered Bed", "upholstered-bed", "A refined upholstered bed frame for a calm, comfortable bedroom. Demo listing — confirm availability and final price.", 690000, "Beds", "https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?w=1200"),
            ("Solid Wood Dining Table", "wood-dining-table", "A warm, timeless dining table for everyday meals and gatherings. Demo listing — confirm availability and final price.", 540000, "Dining Tables", "https://images.unsplash.com/photo-1600210492486-724fe5c67fb0?w=1200"),
        ]
        for name, slug, description, price, category_name, image_url in samples:
            product = models.Product.query.filter_by(business_id=business.id, slug=slug).first()
            if product is None:
                product = models.Product(business_id=business.id,
                    category_id=categories[category_name].id, name=name, slug=slug,
                    description=description, regular_price=price, gender="Unisex",
                    fashion_type="Ready-to-wear", featured=True, new_arrival=True,
                    is_published=True, sku=f"DEMO-{slug.upper()}")
                db.session.add(product)
                db.session.flush()
                db.session.add(models.ProductImage(business_id=business.id,
                    product_id=product.id, url=image_url,
                    alt_text=f"{name} — illustrative demo image", sort_order=0))

        db.session.commit()
        print(f"Preview store ready: {store_name}; sample listings are illustrative only.")

    @app.cli.command("seed-oade-catalogue")
    def seed_oade_catalogue():
        """Add an idempotent set of 20 illustrative products to Oadé Living only."""
        from .utils import slugify

        business = models.Business.query.filter_by(slug="oade-living", status="ACTIVE").first()
        if business is None:
            raise RuntimeError("Oadé Living was not found or is not active; no products were added.")

        # Product names, category groups, sample NGN prices and illustrative Unsplash photos.
        catalogue = [
            ("Lagos Modular 3-Seater Sofa", "Living Room", "Sofas", 1250000, "A generously proportioned modular sofa with clean lines and comfortable cushions.", "photo-1555041469-a586c61ea9bc"),
            ("Oslo Accent Armchair", "Living Room", "Armchairs", 485000, "A sculptural accent chair designed for reading corners and relaxed seating.", "photo-1567538096630-e0c55bd6374c"),
            ("Aurelia Round Coffee Table", "Living Room", "Coffee Tables", 295000, "A round centre table with a refined profile for contemporary living rooms.", "photo-1499933374294-4584851497cc"),
            ("Linea Media TV Console", "Living Room", "TV Consoles", 420000, "A streamlined media console with practical storage for everyday essentials.", "photo-1600210492486-724fe5c67fb0"),
            ("Noma Oak Side Table", "Living Room", "Side Tables", 165000, "A compact side table for lamps, books and small living-room accessories.", "photo-1493663284031-b7e3aefcae8e"),
            ("Haven Upholstered King Bed", "Bedroom", "Beds", 980000, "A soft upholstered king bed frame with a calm, modern silhouette.", "photo-1505693416388-ac5ce068fe85"),
            ("Alder Sliding Door Wardrobe", "Bedroom", "Wardrobes", 1150000, "A spacious wardrobe concept with a clean exterior and generous storage.", "photo-1616486338812-3dadae4b4ace"),
            ("Milo Bedside Cabinet", "Bedroom", "Bedside Tables", 185000, "A practical bedside cabinet with room for nighttime essentials.", "photo-1631679706909-1844bbd07221"),
            ("Solace Bedroom Dresser", "Bedroom", "Dressers", 395000, "A contemporary dresser designed to bring useful storage to the bedroom.", "photo-1616486338812-3dadae4b4ace"),
            ("Cedar 6-Seater Dining Table", "Dining", "Dining Tables", 790000, "A welcoming dining table with room for family meals and shared occasions.", "photo-1600210492486-724fe5c67fb0"),
            ("Marlow Dining Chair", "Dining", "Dining Chairs", 145000, "A supportive dining chair with a timeless, versatile design.", "photo-1617806118233-18e1de247200"),
            ("Sienna Storage Cabinet", "Dining", "Cabinets", 365000, "A versatile cabinet for tableware, linens and dining-room storage.", "photo-1616486029423-aaa4789e8c9a"),
            ("Forma Executive Office Desk", "Office", "Office Desks", 560000, "A generous work surface for a focused home or professional workspace.", "photo-1497366754035-f200968a6e72"),
            ("Ergo Mesh Office Chair", "Office", "Office Chairs", 325000, "A contemporary office chair with a breathable mesh-inspired design.", "photo-1580480055273-228ff5388ef8"),
            ("Atlas Open Bookcase", "Office", "Bookcases", 285000, "An open bookcase for books, framed photos and carefully chosen objects.", "photo-1507652313519-d4e9174996dd"),
            ("Kora Multi-Purpose Storage Unit", "Office", "Storage", 345000, "A flexible storage unit for keeping work and household essentials organised.", "photo-1595428774223-ef52624120d2"),
            ("Cove 2-Seater Loveseat", "Living Room", "Sofas", 795000, "A compact two-seater sofa suited to apartments and smaller living spaces.", "photo-1550254478-ead40cc54513"),
            ("Amani Nesting Coffee Tables", "Living Room", "Coffee Tables", 255000, "A pair of nesting tables that offer flexible surface space when needed.", "photo-1499933374294-4584851497cc"),
            ("Monarch Queen Bed Frame", "Bedroom", "Beds", 825000, "A simple queen bed frame designed to complement a range of bedroom styles.", "photo-1505693416388-ac5ce068fe85"),
            ("Harper 4-Seater Dining Set", "Dining", "Dining Tables", 920000, "A coordinated dining table and chair set for everyday family dining.", "photo-1600607687939-ce8a6c25118c"),
        ]

        categories = {
            category.name: category
            for category in models.Category.query.filter_by(business_id=business.id).all()
        }
        created = 0
        for name, room, category_name, price, description, photo_id in catalogue:
            slug = slugify(name)
            existing = models.Product.query.filter_by(business_id=business.id, slug=slug).first()
            if existing:
                continue
            category_slug = slugify(f"{room}-{category_name}")
            category = models.Category.query.filter_by(
                business_id=business.id, slug=category_slug
            ).first()
            if category is None:
                category = models.Category(
                    business_id=business.id,
                    name=category_name,
                    slug=category_slug,
                    gender=room,
                )
                db.session.add(category)
                db.session.flush()
            product = models.Product(
                business_id=business.id,
                category_id=category.id,
                name=name,
                slug=slug,
                description=description + " Illustrative catalogue listing; confirm actual specifications, availability and final price before ordering.",
                regular_price=price,
                gender="Unisex",
                fashion_type="Furniture",
                featured=created < 4,
                new_arrival=True,
                is_published=True,
                sku=f"OADE-{slug.upper()[:80]}",
            )
            db.session.add(product)
            db.session.flush()
            db.session.add(models.ProductImage(
                business_id=business.id,
                product_id=product.id,
                url=f"https://images.unsplash.com/{photo_id}?auto=format&fit=crop&w=1200&q=85",
                alt_text=f"{name} — illustrative product image",
                sort_order=0,
            ))
            created += 1

        db.session.commit()
        total = models.Product.query.filter_by(business_id=business.id).count()
        print(f"Oadé Living catalogue seed complete: {created} new products added; {total} products total.")

    @app.cli.command("bootstrap-store")
    def bootstrap_store():
        """Create one independent client store from STORE_* environment variables."""
        from sqlalchemy.exc import IntegrityError
        from .utils import slugify

        store_name = os.getenv("STORE_NAME", "").strip()
        store_slug = slugify(os.getenv("STORE_SLUG", "") or store_name)
        owner_name = os.getenv("STORE_OWNER_NAME", "").strip()
        owner_email = os.getenv("STORE_OWNER_EMAIL", "").strip().lower()
        owner_password = os.getenv("STORE_OWNER_PASSWORD", "")
        contact_email = os.getenv("STORE_CONTACT_EMAIL", "").strip().lower() or owner_email
        whatsapp_number = os.getenv("STORE_WHATSAPP_NUMBER", "").strip() or None

        if not store_name or not store_slug or len(store_slug) > 160 or not owner_name or not owner_email:
            raise RuntimeError(
                "Set STORE_NAME, STORE_OWNER_NAME and STORE_OWNER_EMAIL; "
                "STORE_SLUG is optional and defaults to a slug of STORE_NAME. "
                "The store slug must be no longer than 160 characters."
            )
        if len(owner_name) > 160 or len(owner_email) > 255:
            raise RuntimeError("STORE_OWNER_NAME or STORE_OWNER_EMAIL exceeds the supported length.")

        business = models.Business.query.filter_by(slug=store_slug).first()
        existing_owner = models.User.query.filter_by(email=owner_email).first()
        if existing_owner and (not business or existing_owner.business_id != business.id):
            raise RuntimeError("STORE_OWNER_EMAIL is already assigned to another account.")
        if business and business.status != "ACTIVE":
            raise RuntimeError("The existing store is not active; refusing to change its status.")
        if business:
            another_owner = models.User.query.filter(
                models.User.business_id == business.id,
                models.User.role == "OWNER",
                models.User.email != owner_email,
            ).first()
            if another_owner:
                raise RuntimeError("This store already has a different owner account; refusing to add or replace an owner.")
        if not existing_owner and (not owner_password or len(owner_password) < 12):
            raise RuntimeError("Set STORE_OWNER_PASSWORD to a unique password of at least 12 characters.")

        try:
            if business is None:
                business = models.Business(
                    name=store_name,
                    slug=store_slug,
                    description=os.getenv("STORE_DESCRIPTION", "").strip() or None,
                    contact_email=contact_email,
                    whatsapp_number=whatsapp_number,
                    status="ACTIVE",
                )
                db.session.add(business)
                db.session.flush()

            if existing_owner is None:
                owner = models.User(
                    business_id=business.id,
                    name=owner_name,
                    email=owner_email,
                    role="OWNER",
                    active=True,
                )
                owner.set_password(owner_password)
                db.session.add(owner)

            if not models.StoreSettings.query.filter_by(business_id=business.id).first():
                db.session.add(models.StoreSettings(business_id=business.id))

            if not models.Category.query.filter_by(business_id=business.id).first():
                defaults = {
                    "Living Room": ["Sofas", "Armchairs", "Coffee Tables", "TV Consoles", "Side Tables"],
                    "Bedroom": ["Beds", "Wardrobes", "Bedside Tables", "Dressers"],
                    "Dining": ["Dining Tables", "Dining Chairs", "Cabinets"],
                    "Office": ["Office Desks", "Office Chairs", "Bookcases", "Storage"],
                }
                for gender, names in defaults.items():
                    for category_name in names:
                        category_slug = slugify(f"{gender}-{category_name}")
                        db.session.add(models.Category(
                            business_id=business.id,
                            name=category_name,
                            slug=category_slug,
                            gender=gender,
                        ))
            db.session.commit()
            print(f"Store {store_name} and owner account created successfully.")
        except IntegrityError:
            db.session.rollback()
            raise RuntimeError("Store bootstrap encountered an existing database record; no partial setup was saved.")

    @app.cli.command("bootstrap-sulex")
    def bootstrap_sulex():
        """Create the original Sulex store and owner from private environment variables."""
        from sqlalchemy.exc import IntegrityError

        owner_email = os.getenv("SULEX_OWNER_EMAIL", "").strip().lower()
        owner_password = os.getenv("SULEX_OWNER_PASSWORD", "")
        existing_business = models.Business.query.filter_by(slug="sulex").first()
        existing_owner = models.User.query.filter_by(email=owner_email).first() if owner_email else None

        # Safe on every restart after successful setup; never resets an existing password.
        if existing_business and existing_owner and existing_owner.business_id == existing_business.id:
            print("Sulex bootstrap already completed.")
            return
        if not owner_email or not owner_password:
            raise RuntimeError("Set SULEX_OWNER_EMAIL and SULEX_OWNER_PASSWORD in the service environment.")
        if existing_owner:
            raise RuntimeError("SULEX_OWNER_EMAIL is already assigned to a different account.")
        if existing_business and existing_business.status != "ACTIVE":
            raise RuntimeError("The existing Sulex store is not active; refusing to change its status.")

        try:
            business = existing_business or models.Business(
                name="Sulex",
                slug="sulex",
                description="Sulex clothing store",
                contact_email=owner_email,
                status="ACTIVE",
            )
            if not existing_business:
                db.session.add(business)
                db.session.flush()

            owner = models.User(
                business_id=business.id,
                name="Sulex Owner",
                email=owner_email,
                role="OWNER",
                active=True,
            )
            owner.set_password(owner_password)
            db.session.add(owner)

            if not models.StoreSettings.query.filter_by(business_id=business.id).first():
                db.session.add(models.StoreSettings(business_id=business.id))

            if not models.Category.query.filter_by(business_id=business.id).first():
                defaults = {
                    "Living Room": ["Sofas", "Armchairs", "Coffee Tables", "TV Consoles", "Side Tables"],
                    "Bedroom": ["Beds", "Wardrobes", "Bedside Tables", "Dressers"],
                    "Dining": ["Dining Tables", "Dining Chairs", "Cabinets"],
                    "Office": ["Office Desks", "Office Chairs", "Bookcases", "Storage"],
                }
                for gender, names in defaults.items():
                    for category_name in names:
                        slug = "-".join((gender + "-" + category_name).lower().replace("&", " ").split())
                        db.session.add(models.Category(
                            business_id=business.id,
                            name=category_name,
                            slug=slug,
                            gender=gender,
                        ))
            db.session.commit()
            print("Sulex store and owner account created successfully.")
        except IntegrityError:
            db.session.rollback()
            raise RuntimeError("Sulex bootstrap encountered an existing database record; no partial setup was saved.")

    @login_manager.user_loader
    def load_user(user_id):
        try:
            user_id = int(user_id)
        except (TypeError, ValueError):
            return None
        user = models.User.query.filter_by(id=user_id, active=True).first()
        if not user or not user.active:
            return None
        if user.role == "OWNER" and not models.Business.query.filter_by(
            id=user.business_id,
            status="ACTIVE",
        ).first():
            return None
        if user.role not in {"OWNER", "SUPER_ADMIN"}:
            return None
        return user

    @app.before_request
    def resolve_store():
        """Resolve the one configured shop; a connected custom domain may override it."""
        host = (request.host or "").split(":")[0].rstrip(".").lower()
        domain = models.Domain.query.filter(
            db.func.lower(models.Domain.host) == host
        ).first()

        if domain:
            business = domain.business if domain.status == "CONNECTED" else None
            if business and business.status == "ACTIVE":
                g.business = business
                g.domain_status = "CONNECTED"
            else:
                g.business = None
                g.domain_status = domain.status
            return None

        # This app is configured as a single-business catalogue. Use the
        # first active business automatically; no store slug setting is needed.
        business = models.Business.query.filter_by(
            status="ACTIVE"
        ).order_by(models.Business.id.asc()).first()
        g.business = business
        g.domain_status = "default" if business else "NOT_CONFIGURED"

    from .routes.auth import bp as auth_bp
    from .routes.admin import bp as admin_bp
    from .routes.owner import bp as owner_bp
    from .routes.storefront import bp as storefront_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(owner_bp)
    app.register_blueprint(storefront_bp)

    @app.get("/media/products/<int:image_id>")
    def product_image(image_id):
        image = models.ProductImage.query.options(undefer(models.ProductImage.image_data)).filter_by(id=image_id).first_or_404()
        if not image.image_data or not image.mime_type:
            # Preserve old filesystem-backed catalogue image URLs.
            from flask import abort
            abort(404)
        response = Response(image.image_data, mimetype=image.mime_type)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "public, max-age=86400, immutable"
        return response

    @app.get("/media/businesses/<int:business_id>/logo")
    def business_logo(business_id):
        business = models.Business.query.options(undefer(models.Business.logo_data)).filter_by(id=business_id).first_or_404()
        if not business.logo_data or not business.logo_mime_type:
            from flask import abort
            abort(404)
        response = Response(business.logo_data, mimetype=business.logo_mime_type)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "public, max-age=86400"
        return response

    @app.get("/media/businesses/<int:business_id>/banner")
    def business_banner(business_id):
        business = models.Business.query.options(undefer(models.Business.banner_data)).filter_by(id=business_id).first_or_404()
        if not business.banner_data or not business.banner_mime_type:
            from flask import abort
            abort(404)
        response = Response(business.banner_data, mimetype=business.banner_mime_type)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        return response

    @app.get("/media/<path:filename>")
    def uploaded_media(filename):
        resolved_path = safe_join(app.config["UPLOAD_FOLDER"], filename)
        if not resolved_path:
            from flask import abort
            abort(404)
        resolved_path = os.path.realpath(resolved_path)
        upload_root = os.path.realpath(app.config["UPLOAD_FOLDER"])
        if os.path.commonpath([resolved_path, upload_root]) != upload_root or not os.path.isfile(resolved_path):
            from flask import abort
            abort(404)
        with open(resolved_path, "rb") as media_file:
            data = media_file.read()
        response = Response(data, mimetype="application/octet-stream")
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "public, max-age=86400"
        return response

    @app.get("/health")
    def health():
        db.session.execute(db.text("SELECT 1"))
        return {"status": "ok", "database": "ok"}

    @app.context_processor
    def inject_common():
        business = getattr(g, "business", None)
        store_settings = models.StoreSettings.query.filter_by(business_id=business.id).first() if business else None
        cart_count = 0
        if business:
            cart = session.get("cart", {})
            try:
                variant_ids = [int(key.split(":", 1)[0]) for key in cart]
            except (TypeError, ValueError):
                variant_ids = []
            if variant_ids:
                variants = models.ProductVariant.query.filter(
                    models.ProductVariant.business_id == business.id,
                    models.ProductVariant.id.in_(variant_ids),
                ).all()
                cart_count = sum(int(cart.get(f"{variant.id}:", 0)) for variant in variants)
        return {"tenant": business, "cart_count": cart_count, "settings": store_settings}

    @app.errorhandler(CSRFError)
    def handle_csrf_error(error):
        flash("Your form session expired. Please review the form and submit it again.", "warning")
        return redirect(request.referrer or url_for("auth.login"))

    @app.errorhandler(404)
    def not_found(error):
        return {"error": "Not found"}, 404

    return app
