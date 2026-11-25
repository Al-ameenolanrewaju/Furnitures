import re
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from .. import db
from ..models import Product, Category, ProductVariant, ProductImage, Order, OrderItem

bp = Blueprint("admin", __name__, url_prefix="/admin")

def admin_required():
    if not current_user.is_authenticated or current_user.role != "ADMIN":
        abort(403)

@bp.before_request
@login_required
def protect():
    admin_required()

@bp.get("/")
def dashboard():
    return render_template("admin/dashboard.html", product_count=Product.query.count(), order_count=Order.query.count(), pending_count=Order.query.filter_by(status="PENDING").count(), recent_orders=Order.query.order_by(Order.created_at.desc()).limit(8).all())

@bp.route("/products", methods=["GET", "POST"])
def products():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Product name is required.", "warning")
            return redirect(url_for("admin.products"))
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        if Product.query.filter_by(slug=slug).first(): slug += "-" + __import__("secrets").token_hex(2)
        product = Product(name=name, slug=slug, category_id=request.form.get("category_id", type=int) or None, sku=request.form.get("sku") or None, short_description=request.form.get("short_description"), description=request.form.get("description"), price=request.form.get("price", type=float) or 0, compare_at_price=request.form.get("compare_at_price", type=float), material=request.form.get("material"), colour=request.form.get("colour"), dimensions=request.form.get("dimensions"), finish=request.form.get("finish"), stock=request.form.get("stock", type=int) or 0, featured=bool(request.form.get("featured")), is_new=bool(request.form.get("is_new")), image_url=request.form.get("image_url") or None)
        db.session.add(product)
        db.session.flush()
        for upload in request.files.getlist("images"):
            if upload and upload.filename:
                data = upload.read()
                mime = upload.mimetype or ""
                if mime not in {"image/jpeg", "image/png", "image/webp"} or len(data) > 8 * 1024 * 1024:
                    db.session.rollback()
                    flash("Use JPG, PNG or WebP images under 8 MB.", "warning")
                    return redirect(url_for("admin.products"))
                db.session.add(ProductImage(product_id=product.id, image_data=data, mime_type=mime, alt_text=product.name))
        db.session.commit()
        flash("Furniture product created.", "success")
        return redirect(url_for("admin.products"))
    return render_template("admin/products.html", products=Product.query.order_by(Product.created_at.desc()).all(), categories=Category.query.order_by(Category.name).all())

@bp.post("/products/<int:product_id>/toggle")
def toggle_product(product_id):
    product = Product.query.get_or_404(product_id)
    product.is_active = not product.is_active
    db.session.commit()
    return redirect(url_for("admin.products"))

@bp.post("/products/<int:product_id>/delete")
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    if OrderItem.query.filter_by(product_id=product.id).first():
        product.is_active = False
        flash("Product is in an order history, so it was archived instead of deleted.", "info")
    else:
        db.session.delete(product)
        flash("Product deleted.", "success")
    db.session.commit()
    return redirect(url_for("admin.products"))

@bp.route("/categories", methods=["GET", "POST"])
def categories():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        if name and not Category.query.filter_by(slug=slug).first():
            db.session.add(Category(name=name, slug=slug, description=request.form.get("description")))
            db.session.commit()
            flash("Category created.", "success")
        return redirect(url_for("admin.categories"))
    return render_template("admin/categories.html", categories=Category.query.order_by(Category.name).all())

@bp.post("/categories/<int:category_id>/delete")
def delete_category(category_id):
    category = Category.query.get_or_404(category_id)
    if category.products:
        flash("Move or archive the category's products before deleting it.", "warning")
    else:
        db.session.delete(category)
        db.session.commit()
    return redirect(url_for("admin.categories"))

@bp.get("/orders")
def orders():
    return render_template("admin/orders.html", orders=Order.query.order_by(Order.created_at.desc()).all())

@bp.post("/orders/<int:order_id>/status")
def order_status(order_id):
    order = Order.query.get_or_404(order_id)
    status = request.form.get("status", "")
    if status in {"PENDING", "CONFIRMED", "PROCESSING", "SHIPPED", "DELIVERED", "CANCELLED"}:
        order.status = status
        db.session.commit()
    return redirect(url_for("admin.orders"))

@bp.route("/products/<int:product_id>/variants", methods=["GET", "POST"])
def variants(product_id):
    product = Product.query.get_or_404(product_id)
    if request.method == "POST":
        variant = ProductVariant(product_id=product.id, label=request.form.get("label", "").strip(), colour=request.form.get("colour"), material=request.form.get("material"), finish=request.form.get("finish"), dimensions=request.form.get("dimensions"), price_delta=request.form.get("price_delta", type=float) or 0, stock=request.form.get("stock", type=int) or 0, sku=request.form.get("sku"))
        if not variant.label:
            flash("Variant name is required.", "warning")
        else:
            db.session.add(variant); db.session.commit(); flash("Variant added.", "success")
        return redirect(url_for("admin.variants", product_id=product.id))
    return render_template("admin/variants.html", product=product)
