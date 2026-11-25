# Furniture Storefront

A premium furniture e-commerce storefront built with Flask, following the visual system and interaction patterns of the clothing catalogue reference.

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export SECRET_KEY='replace-with-a-random-secret-at-least-32-characters'
export DATABASE_URL='sqlite:///furniture_store.db'
flask --app 'app:create_app()' db upgrade
flask --app 'app:create_app()' run
```

Set `ADMIN_EMAIL` and `ADMIN_PASSWORD` before first run to create the initial administrator. In production use PostgreSQL, a strong `SECRET_KEY`, HTTPS and `COOKIE_SECURE=true`.

## Design reference

The storefront uses the same Flask/Jinja architecture, editorial product presentation, responsive navigation, image-led product cards, drawer-based cart and wishlist interactions, and lightweight page navigation approach as the clothing website reference. The reference repository is not modified.

## Notes

- Product images are stored in the database as binary data; no Cloudinary or persistent disk is required.
- Product catalogue, variants, inventory, orders, customers, reviews and admin management are database-backed.
- Checkout creates an order record and can hand off order details to WhatsApp. Configure `STORE_WHATSAPP` to enable that handoff.
- Run tests with `pytest -q`.
