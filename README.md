# Verda Padel

A separate Flask venue platform with the supplied Verda logo, `#03764A` and white. Public booking and store, staff administration, court/table cashier, quick sales, inventory, debts, reporting and receipts use persistent database records. The preview is **fictional demonstration data**, not an operating venue.

## Open the prepared local preview

- Website: http://127.0.0.1:5000
- Staff sign in: http://127.0.0.1:5000/auth/login
- The unique local demo credentials are in `instance/preview-access.txt`. This ignored file is only for this local preview; do not deploy that account/database.

The source is in `C:\Users\rand\Desktop\verda-padel`. The original `Padel_House-main` reference remains untouched. If the preview has stopped, run from this directory:

```powershell
.\.venv\Scripts\python.exe -m waitress --listen=127.0.0.1:5000 run:app
```

If port 5000 is already in use by this preview, open it instead of starting a second process. To run another instance, use port 5001 and open that port. Do not run multiple versions of the code against the same database during an upgrade.

## Fresh installation (Windows)

Use a new directory and new database for a real venue installation. Python 3.10 or newer is required. Python, Flask, Jinja2, Bootstrap 5, vanilla HTML/CSS/JavaScript, SQLAlchemy, Flask-Login, Flask-WTF, Flask-Migrate/Alembic, Pillow and python-barcode remain the application stack.

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item -LiteralPath .env.example -Destination .env
.\.venv\Scripts\python.exe -m flask --app run setup
.\.venv\Scripts\python.exe -m flask --app run create-admin
.\.venv\Scripts\python.exe -m waitress --listen=127.0.0.1:5000 run:app
```

`create-admin` securely prompts for a username, email and password (12+ characters). No fixed production credentials or reference-client records are seeded. `setup` applies migrations and creates empty configuration; it is safe to repeat. Startup does not call `create_all` or automatically seed users.

For a disposable demonstration installation only:

```powershell
.\.venv\Scripts\python.exe -m flask --app run demo-data
```

For development without Waitress, `python run.py` binds loopback with debug disabled. On Linux/macOS, use `python3 -m venv .venv`, `.venv/bin/python`, and `cp .env.example .env`; the remaining module commands are the same.

## Configure the venue

Sign in and open **Website & settings**. Enter approved contact/location information, opening hours, hourly fallback rate, discount window, rounding/minimum policy, booking window and delivery fee. Configure real courts (their rate overrides the fallback), products/costs/stock, categories, tables and staff permissions. Supply approved venue photography and About/Contact text in both languages. English is the initial default; Arabic is also available.

Only mark venue details confirmed and turn off demo mode after replacing fictional content. Unconfirmed non-demo installations cannot accept public booking/checkout. No online payment gateway is included: cash/card actions **record** a staff collection and do not charge a bank card.

## Production operation

Set `VERDA_ENV=production` and a unique `SECRET_KEY` in a protected environment or `.env`. Generate a secret locally, for example with `python -c "import secrets; print(secrets.token_hex(32))"`, and store it privately. Production refuses to start without a secret and uses secure session cookies. Debug remains disabled.

Use Waitress behind your HTTPS reverse proxy/service manager. Keep its listener on `127.0.0.1`, as shown above; expose HTTPS through the proxy. Run as a dedicated OS account with access only to the project, database and uploads. Do not expose the development server or `instance/` files. Keep `.env` and backups outside public hosting roots. Restart the service after configuration/code updates. Production secure cookies require HTTPS; plain HTTP is appropriate only for development.

SQLite is the tested local engine. `DATABASE_URL` supports the reference application's environment-configured production database. For its MySQL driver, install `requirements-mysql.txt` (system build dependencies may be required). A live MySQL deployment and its migration/locking behavior still require staging validation; no MySQL server was available here. Do not point this migration lineage at the previous client's database.

Mutations serialize their validation and writes using SQLite `BEGIN IMMEDIATE` or a locked transaction row on other engines. This favors correctness for a single venue; benchmark expected multi-cashier traffic before scaling. Browser timers display elapsed time only; the server calculates charges. There are no background sync services or offline transactions.

## Upgrades, verification and recovery

Back up before upgrading. Stop the application, install the reviewed dependency set, run `python -m flask --app run db upgrade`, then `python -m flask --app run db check`, and restart. Migrations belong to this new Verda project. IDs, sale snapshots and audit history are preserved in supported incremental upgrades; do not reset tables to deploy changes.

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m scripts.check_translations
.\.venv\Scripts\python.exe -m flask --app run db check
```

See [operations and recovery](docs/OPERATIONS.md), [admin and cashier guide](docs/USAGE.md), [completion and verification report](docs/COMPLETION.md), [source assessment](docs/SOURCE-ASSESSMENT.md), and [brand decisions](docs/BRAND.md).
