import os
import pytest
from app import create_app, db
from app.models import Category, Product

@pytest.fixture()
def app(tmp_path):
    class TestConfig:
        TESTING = True
        SECRET_KEY = "test-secret"
        SQLALCHEMY_DATABASE_URI = "sqlite:///" + str(tmp_path / "test.db")
        WTF_CSRF_ENABLED = False
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        category = Category(name="Living room", slug="living-room")
        db.session.add(category)
        db.session.flush()
        db.session.add(Product(name="Sample sofa", slug="sample-sofa", category_id=category.id, price=125000, stock=4, is_active=True))
        db.session.commit()
        yield app
        db.drop_all()

@pytest.fixture()
def client(app):
    return app.test_client()

def test_homepage_loads(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Make room for" in response.data

def test_catalogue_search_and_category_filter(client):
    assert client.get("/shop?q=sofa").status_code == 200
    assert client.get("/shop?category=living-room").status_code == 200

def test_product_detail_loads(client):
    response = client.get("/product/sample-sofa")
    assert response.status_code == 200
    assert b"Sample sofa" in response.data

def test_cart_add_and_checkout_page(client):
    response = client.post("/cart/add", data={"product_id": 1, "quantity": 2}, follow_redirects=True)
    assert response.status_code == 200
    assert client.get("/checkout").status_code == 200

def test_wishlist_persists_in_session(client):
    client.post("/wishlist/toggle", data={"product_id": 1})
    response = client.get("/wishlist")
    assert response.status_code == 200
    assert b"Sample sofa" in response.data
