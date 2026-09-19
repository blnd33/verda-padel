# Verda source assessment

Reference: `C:/Users/rand/Desktop/Padel_House-main` (outer copy). Read-only inspection; no source databases, credentials, environment files, uploads or venue imagery imported.

The nested copy differs in six shared application files: translations.py, routes/main.py, static/css/admin.css, templates/base.html, templates/admin/base_admin.html and templates/admin/bookings.html. Its main routes add PWA, service worker and offline functionality explicitly excluded by the brief. The outer copy is the canonical model reference. Responsive improvements in the nested admin layouts inform the requirements; neither presentation layer is reused.

The original SQLAlchemy models, Flask-Login role structure, multilingual product/category fields and local SQLite/environment DATABASE_URL approach are retained. Shared transactional services replace conflicting calculations and unsafe mutations. Frontend templates and navigation are original.

Verified through static inspection:

- Active factory creates tables and seeds a fixed administrator, client contacts, prices and courts at startup.
- A second factory exists in routes/__init__.py; run.py hardcodes debug=True.
- Source migrations lack a complete baseline and include dropping notifications in migrations labelled as additions. They cannot safely initialize Verda.
- Public main/contact.html is missing.
- Public confirmation uses sequential identifiers; authentication accepts an unchecked next redirect.
- POS routes generally require login without operation-specific permissions.
- POS session timestamps use OS local time; booking display dates depend on mutable settings and `or` defaults that replace zero.
- Stadium/financial relationships contain destructive delete cascades.
- Active route imports include excluded coaching, Tapane and Google Sheets.

Verda uses a fresh, frozen baseline migration for the retained source model structure, followed by incremental Verda migrations. This is a new database lineage, not an upgrade path for the previous client's installation. No previous-client migration is executed against their database.

The original source was not executed: its startup has data-changing and external-integration side effects. These observations are static findings, not claims of reproduced runtime failures.
