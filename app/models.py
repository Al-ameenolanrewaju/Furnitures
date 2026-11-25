from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from . import db

def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)

class TimestampMixin:
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

class User(UserMixin, TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(140), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="CUSTOMER")
    active = db.Column(db.Boolean, nullable=False, default=True)
    def set_password(self, value):
        self.password_hash = generate_password_hash(value)
    def check_password(self, value):
        return check_password_hash(self.password_hash, value)

class Category(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    description = db.Column(db.Text)
    image_url = db.Column(db.String(700))
    products = db.relationship("Product", back_populates="category")

class Product(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey("category.id"), index=True)
    name = db.Column(db.String(180), nullable=False, index=True)
    slug = db.Column(db.String(200), unique=True, nullable=False, index=True)
    sku = db.Column(db.String(80), unique=True)
    short_description = db.Column(db.String(300))
    description = db.Column(db.Text)
    price = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    compare_at_price = db.Column(db.Numeric(12, 2))
    material = db.Column(db.String(120))
    colour = db.Column(db.String(120))
    dimensions = db.Column(db.String(180))
    finish = db.Column(db.String(120))
    stock = db.Column(db.Integer, nullable=False, default=0)
    featured = db.Column(db.Boolean, nullable=False, default=False)
    is_new = db.Column(db.Boolean, nullable=False, default=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    image_url = db.Column(db.String(700))
    category = db.relationship("Category", back_populates="products")
    images = db.relationship("ProductImage", back_populates="product", cascade="all, delete-orphan", order_by="ProductImage.position")
    variants = db.relationship("ProductVariant", back_populates="product", cascade="all, delete-orphan")
    reviews = db.relationship("Review", back_populates="product", cascade="all, delete-orphan")

class ProductImage(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False, index=True)
    image_data = db.Column(db.LargeBinary, nullable=False)
    mime_type = db.Column(db.String(50), nullable=False)
    alt_text = db.Column(db.String(180))
    position = db.Column(db.Integer, nullable=False, default=0)
    product = db.relationship("Product", back_populates="images")

class ProductVariant(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False, index=True)
    label = db.Column(db.String(140), nullable=False)
    colour = db.Column(db.String(80))
    material = db.Column(db.String(100))
    finish = db.Column(db.String(100))
    dimensions = db.Column(db.String(160))
    price_delta = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    stock = db.Column(db.Integer, nullable=False, default=0)
    sku = db.Column(db.String(80))
    product = db.relationship("Product", back_populates="variants")

class Order(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(32), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    customer_name = db.Column(db.String(140), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(40), nullable=False)
    address = db.Column(db.Text, nullable=False)
    notes = db.Column(db.Text)
    subtotal = db.Column(db.Numeric(12, 2), nullable=False)
    delivery_fee = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    total = db.Column(db.Numeric(12, 2), nullable=False)
    status = db.Column(db.String(30), nullable=False, default="PENDING")
    items = db.relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"))
    variant_id = db.Column(db.Integer, db.ForeignKey("product_variant.id"))
    product_name = db.Column(db.String(180), nullable=False)
    variant_label = db.Column(db.String(140))
    unit_price = db.Column(db.Numeric(12, 2), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    order = db.relationship("Order", back_populates="items")

class Review(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    customer_name = db.Column(db.String(140), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    body = db.Column(db.Text, nullable=False)
    approved = db.Column(db.Boolean, nullable=False, default=False)
    product = db.relationship("Product", back_populates="reviews")
