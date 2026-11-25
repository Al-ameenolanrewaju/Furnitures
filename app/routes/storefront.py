import re, secrets
from decimal import Decimal
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app, abort
from sqlalchemy import or_
from .. import db
from ..models import Product, Category, ProductVariant, Order, OrderItem, Review

bp = Blueprint("store", __name__)

def money(value):
    return f"₦{Decimal(value or 0):,.0f}"

def product_image(product):
    return product.image_url or (url_for("store.product_image", image_id=product.images[0].id) if product.images else "https://images.unsplash.com/photo-1555041469-a586c61ea9bc?w=900&q=85")

@bp.app_template_filter("naira")
def naira(value):
    return money(value)

@bp.get("/")
def home():
    featured = Product.query.filter_by(is_active=True, featured=True).order_by(Product.updated_at.desc()).limit(8).all()
    new_arrivals = Product.query.filter_by(is_active=True, is_new=True).order_by(Product.created_at.desc()).limit(8).all()
    categories = Category.query.order_by(Category.name).all()
    return render_template("storefront/home.html", featured=featured, new_arrivals=new_arrivals, categories=categories)

@bp.get("/shop")
def catalogue():
    query = Product.query.filter_by(is_active=True)
    term = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    material = request.args.get("material", "").strip()
    colour = request.args.get("colour", "").strip()
    availability = request.args.get("availability", "").strip()
    min_price = request.args.get("min_price", "").strip()
    max_price = request.args.get("max_price", "").strip()
    if term:
        like = f"%{term}%"
        query = query.filter(or_(Product.name.ilike(like), Product.description.ilike(like), Product.material.ilike(like), Product.colour.ilike(like)))
    if category:
        query = query.join(Category).filter(Category.slug == category)
    if material: query = query.filter(Product.material.ilike(f"%{material}%"))
    if colour: query = query.filter(Product.colour.ilike(f"%{colour}%"))
    if availability == "in-stock": query = query.filter(Product.stock > 0)
    if min_price:
        try: query = query.filter(Product.price >= Decimal(min_price))
        except Exception: pass
    if max_price:
        try: query = query.filter(Product.price <= Decimal(max_price))
        except Exception: pass
    products = query.order_by(Product.featured.desc(), Product.created_at.desc()).all()
    categories = Category.query.order_by(Category.name).all()
    materials = [r[0] for r in db.session.query(Product.material).filter(Product.material.isnot(None), Product.is_active.is_(True)).distinct().all()]
    colours = [r[0] for r in db.session.query(Product.colour).filter(Product.colour.isnot(None), Product.is_active.is_(True)).distinct().all()]
    return render_template("storefront/catalogue.html", products=products, categories=categories, materials=materials, colours=colours)

@bp.get("/category/<slug>")
def category(slug):
    item = Category.query.filter_by(slug=slug).first_or_404()
    products = Product.query.filter_by(category_id=item.id, is_active=True).order_by(Product.created_at.desc()).all()
    return render_template("storefront/catalogue.html", products=products, categories=Category.query.all(), active_category=item, materials=[], colours=[])

@bp.get("/product/<slug>")
def product_detail(slug):
    product = Product.query.filter_by(slug=slug, is_active=True).first_or_404()
    related = Product.query.filter(Product.category_id == product.category_id, Product.id != product.id, Product.is_active.is_(True)).limit(4).all()
    reviews = Review.query.filter_by(product_id=product.id, approved=True).order_by(Review.created_at.desc()).all()
    return render_template("storefront/product.html", product=product, related=related, reviews=reviews)

@bp.get("/media/<int:image_id>")
def product_image(image_id):
    from flask import Response
    from ..models import ProductImage
    image = ProductImage.query.get_or_404(image_id)
    response = Response(image.image_data, mimetype=image.mime_type)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "public, max-age=86400"
    return response

@bp.get("/cart")
def cart():
    return render_template("storefront/cart.html", cart=session.get("cart", {}))

@bp.post("/cart/add")
def cart_add():
    product_id = request.form.get("product_id", type=int)
    variant_id = request.form.get("variant_id", type=int)
    quantity = max(1, min(20, request.form.get("quantity", type=int) or 1))
    product = Product.query.filter_by(id=product_id, is_active=True).first_or_404()
    variant = ProductVariant.query.filter_by(id=variant_id, product_id=product.id).first() if variant_id else None
    if variant_id and not variant:
        abort(400)
    stock = variant.stock if variant else product.stock
    if stock < quantity:
        flash("The selected item does not have enough stock.", "warning")
        return redirect(request.referrer or url_for("store.product_detail", slug=product.slug))
    cart = session.get("cart", {})
    key = f"{product.id}:{variant.id if variant else 0}"
    existing = cart.get(key, {})
    cart[key] = {"product_id": product.id, "variant_id": variant.id if variant else None, "quantity": min(stock, int(existing.get("quantity", 0)) + quantity)}
    session["cart"] = cart
    session.modified = True
    flash("Added to your bag.", "success")
    return redirect(request.referrer or url_for("store.cart"))

@bp.post("/cart/update")
def cart_update():
    cart = session.get("cart", {})
    key = request.form.get("key", "")
    quantity = request.form.get("quantity", type=int) or 0
    if key in cart:
        if quantity <= 0: cart.pop(key, None)
        else: cart[key]["quantity"] = min(20, max(1, quantity))
    session["cart"] = cart
    return redirect(url_for("store.cart"))

@bp.get("/wishlist")
def wishlist():
    ids = [int(x) for x in session.get("wishlist", []) if str(x).isdigit()]
    products = Product.query.filter(Product.id.in_(ids), Product.is_active.is_(True)).all() if ids else []
    return render_template("storefront/wishlist.html", products=products)

@bp.post("/wishlist/toggle")
def wishlist_toggle():
    product_id = request.form.get("product_id", type=int)
    product = Product.query.filter_by(id=product_id, is_active=True).first_or_404()
    ids = [str(x) for x in session.get("wishlist", [])]
    if str(product.id) in ids: ids.remove(str(product.id))
    else: ids.append(str(product.id))
    session["wishlist"] = ids
    return redirect(request.referrer or url_for("store.wishlist"))

@bp.route("/checkout", methods=["GET", "POST"])
def checkout():
    cart = session.get("cart", {})
    lines, subtotal = [], Decimal("0")
    for key, entry in cart.items():
        product = db.session.get(Product, entry.get("product_id"))
        if not product or not product.is_active: continue
        variant = db.session.get(ProductVariant, entry.get("variant_id")) if entry.get("variant_id") else None
        price = Decimal(product.price) + (Decimal(variant.price_delta) if variant else Decimal("0"))
        qty = max(1, int(entry.get("quantity", 1)))
        lines.append((product, variant, qty, price))
        subtotal += price * qty
    if request.method == "POST":
        if not lines:
            flash("Your bag is empty.", "warning")
            return redirect(url_for("store.cart"))
        name, email, phone, address = [request.form.get(k, "").strip() for k in ("name", "email", "phone", "address")]
        if not all((name, email, phone, address)):
            flash("Please complete your contact and delivery details.", "warning")
            return redirect(url_for("store.checkout"))
        for product, variant, qty, price in lines:
            stock = variant.stock if variant else product.stock
            if stock < qty:
                flash(f"Not enough stock for {product.name}. Please update your bag.", "warning")
                return redirect(url_for("store.cart"))
        order = Order(order_number="HF-" + secrets.token_hex(4).upper(), customer_name=name, email=email, phone=phone, address=address, notes=request.form.get("notes", "").strip(), subtotal=subtotal, total=subtotal)
        db.session.add(order)
        db.session.flush()
        for product, variant, qty, price in lines:
            db.session.add(OrderItem(order_id=order.id, product_id=product.id, variant_id=variant.id if variant else None, product_name=product.name, variant_label=variant.label if variant else None, unit_price=price, quantity=qty))
            if variant: variant.stock -= qty
            else: product.stock -= qty
        db.session.commit()
        session["cart"] = {}
        message = f"Hello {current_app.config['STORE_NAME']}, I placed order {order.order_number}. Total: {money(order.total)}. Please confirm delivery and payment."
        phone_digits = re.sub(r"\D", "", current_app.config.get("STORE_WHATSAPP", ""))
        wa_url = f"https://wa.me/{phone_digits}?text={__import__('urllib.parse').parse.quote(message)}" if phone_digits else None
        return render_template("storefront/order_success.html", order=order, wa_url=wa_url)
    return render_template("storefront/checkout.html", lines=lines, subtotal=subtotal)

@bp.get("/search")
def search():
    return redirect(url_for("store.catalogue", q=request.args.get("q", "")))
