# Furniture Storefront

A Flask-based furniture catalogue and store-management website. Customers can browse furniture, filter collections, save favourites, add items to a cart, and send an order enquiry through WhatsApp. Store owners manage products, categories, product images, variants, inventory, orders, branding, homepage content and store settings from the owner dashboard.

## Stack

- Python and Flask
- Flask-SQLAlchemy and Flask-Migrate
- PostgreSQL in production; SQLite for local development and tests
- Product images and logos stored as binary data in PostgreSQL
- Gunicorn on Render

## Local development

```bash
python -m venv .venv
# Activate the virtual environment for your shell
pip install -r requirements.txt
cp .env.example .env
```

Set a local `SECRET_KEY` (at least 32 characters), use `DATABASE_URL=sqlite:///furniture_store.db`, and set `COOKIE_SECURE=false` for local HTTP. Then run:

```bash
flask --app 'app:create_app()' db upgrade
flask --app 'app:create_app()' bootstrap-store
flask --app 'app:create_app()' run
```

The bootstrap command requires `STORE_NAME`, `STORE_OWNER_NAME`, `STORE_OWNER_EMAIL`, and a unique `STORE_OWNER_PASSWORD` of at least 12 characters. Optional values are `STORE_SLUG`, `STORE_DESCRIPTION`, `STORE_CONTACT_EMAIL`, and `STORE_WHATSAPP_NUMBER`. It creates the store, owner, settings, and starter furniture categories. It is safe to rerun after successful setup and does not reset an existing owner's password.

## Render deployment

Create a Render Web Service from this repository:

- Branch: `main`
- Runtime: Python
- Build command: `pip install -r requirements.txt`
- Start command: `flask --app 'app:create_app()' db upgrade && gunicorn 'app:create_app()'`
- Add a persistent PostgreSQL database and use its **internal** connection URL for `DATABASE_URL`.

Required environment variables:

| Variable | Value |
|---|---|
| `APP_ENV` | `production` |
| `SECRET_KEY` | Unique random secret of at least 32 characters |
| `DATABASE_URL` | PostgreSQL connection URL |
| `COOKIE_SECURE` | `true` |

Provision the store once after the database is available by running `flask --app 'app:create_app()' bootstrap-store` in the Render Shell with the required `STORE_*` environment variables set. Do not use the legacy `bootstrap-sulex` command for this furniture installation. The application exposes `GET /health` for health checks.

## Images and persistence

New product images and store logos are validated and stored in PostgreSQL, so they survive application redeploys without Cloudinary or a persistent image disk. Legacy images served from `/media/<filename>` still depend on their original file storage and should be re-uploaded through the dashboard if they need to be retained.

## Storefront functionality

- Furniture homepage and collection/category browsing
- Product details, variants and availability
- Cart and wishlist drawers
- WhatsApp order enquiry
- Responsive storefront navigation
- Owner dashboard for catalogue, categories, images, variants, inventory, orders and store content
- Platform administration for business and domain management

## Tests

```bash
python -m pytest -q
```

Run the test suite before deploying changes to production.
