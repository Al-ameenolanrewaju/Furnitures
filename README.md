# Furniture Storefront

A premium furniture e-commerce storefront built with Flask, using the clothing catalogue repository as its design and interaction reference. The reference repository is not modified.

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export SECRET_KEY='replace-with-a-random-secret-at-least-32-characters'
export DATABASE_URL='sqlite:///furniture_store.db'
export ADMIN_EMAIL='admin@example.com'
export ADMIN_PASSWORD='use-a-unique-password-at-least-12-characters'
flask --app 'app:create_app()' init-db
flask --app 'app:create_app()' run
```

The `init-db` command creates tables on a fresh database and creates the first administrator only when ADMIN_EMAIL and ADMIN_PASSWORD are supplied. For later schema changes use Flask-Migrate revisions and `flask db upgrade`; do not run init-db as a schema migration mechanism on an established database.

## Production

Use PostgreSQL, a strong SECRET_KEY of at least 32 characters, APP_ENV=production and COOKIE_SECURE=true. Configure STORE_NAME and STORE_WHATSAPP. Render build command: `pip install -r requirements.txt`; start command: `gunicorn 'app:create_app()'`. Run the initial `init-db` command once for a new database, then use migrations for future schema changes.

## Included functionality

- Editorial storefront, responsive navigation, room/category browsing and image-led product cards.
- Search and combined category, price, material, colour and stock filters.
- Product pages with image gallery, dimensions, materials, finishes and selectable variants.
- Session-persistent guest cart and saved list, stock-aware quantity controls and checkout.
- Orders and order items stored in the database, stock decrement at checkout and optional WhatsApp handoff.
- Admin dashboard, product and image upload, categories, variants, stock and order status management.
- Product images uploaded by administrators are stored as binary data in PostgreSQL; no Cloudinary or persistent disk is required.
- Run automated tests with `pytest -q`.

## Important

No demo inventory, customer records or payment credentials are preloaded. Configure the store, add real products and connect a payment provider before accepting online payments. The current checkout records the order and optionally hands off to WhatsApp for payment/delivery confirmation.
