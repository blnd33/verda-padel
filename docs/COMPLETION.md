# Implementation and verification report

Prepared 17 September 2026. This is a working local demonstration and deployable source project. It has not been published or connected to a real venue's operations.

## Result and source

The separate project is `C:\Users\rand\Desktop\verda-padel`. The outer `C:\Users\rand\Desktop\Padel_House-main` copy was selected after comparing it with the nested duplicate. Relevant domain models and compatible Bootstrap assets were retained; source inspection and differing files are recorded in SOURCE-ASSESSMENT.md. No original installation, database, customer, financial, staff credential, secret or integration setting was modified or imported.

The technology stack remains Python/Flask, Jinja2, HTML/CSS/vanilla JavaScript, Bootstrap 5, SQLAlchemy/Flask-SQLAlchemy, Flask-Login, Flask-WTF, Flask-Migrate/Alembic, Pillow and python-barcode. SQLite is the verified local engine; environment-configured production database support is retained. Waitress supplies a WSGI entry point. No SPA framework, replacement database engine, gateway, printer bridge or external synchronization was introduced.

The presentation layer is new: an editorial public homepage, court/time booking layout, storefront and cart, staff workspace with responsive navigation, touch-friendly cashier and quick-sale pages, and Verda receipts. The original supplied logo retains its artwork/proportions. Colors derive from `#03764A` and white with accessible status treatments. English is LTR; Arabic is RTL. Geometric court/product illustrations are clearly non-photographic; no other venue's photos or invented testimonials are used.

## Completion checklist

| Brief sections | Delivered behavior | Qualification |
| --- | --- | --- |
| 1–7 Identity, stack, scope, source and original design | Separate Verda project; source comparison; preserved stack; supplied logo/palette; completely new templates/CSS; included modules connected to persistent data; excluded routes/integrations omitted | Real business content remains to be supplied |
| 8 Frontend and accessibility | Reusable macros/partials, local Bootstrap assets, shared tokens, reduced-motion and focus styling, labels, mobile navigation and horizontally contained tables | Representative browser review, not a formal accessibility certification |
| 9 Languages, currency, time | English and Arabic dictionaries; RTL/LTR; persistent selection; integer IQD; UTC storage and configurable venue timezone | Native Arabic editorial sign-off remains advisable |
| 10–11 Public website | Home, booking, store/detail/cart/checkout/confirmation, About, Contact, configurable links/hours/copy/hero; private pages noindex/no-store | Venue photos/details and applicable agency branding were not supplied; no invented final information |
| 12–14 Booking and midnight | Shared interval validation for display/submission/staff/edit/approval; pending/confirmed/cancellation conflicts; transactional creation; unguessable references; explicit business/actual dates and discount windows | Current-hour starts are rejected once the hour has begun; next eligible hourly slot is offered |
| 15–16 Store and checkout | Category/search, direct-access visibility checks, quantities/cart/remove/clear, authoritative prices, atomic stock/order creation, delivery fee snapshot, pickup clears address, idempotency | No online payment; requests require venue confirmation |
| 17–18 Staff and dashboard | Secure login/logout, throttling, role/permission enforcement, active/session-version checks, staff creation/edit/password changes, last-super-admin guard, setup CLI, real operational dashboard | Super administrators administer staff; the preview account is local only |
| 19–20 Bookings, courts, tables | Staff reservation workflows, cancellation queue, history/audit, court/table CRUD/archive, occupancy and maintenance intervals | Operational policies need owner approval before launch |
| 21–22 Catalog, inventory, barcodes | Translated product/category CRUD, visibility, explicit stock tracking, stock ledger, low-stock alerts, Code128 labels/download/regeneration and configurable sizes | Keyboard-style scanner entry tested; no physical scanner/printer connected |
| 23–26 POS, pricing, quick sale, debt/payment | Court/table occupancy, booking links, live display timers, frozen stopped billing, product/preparation workflows, single discounts, quick sale, cash/card recording, linked debts and partial/full collections | Card selection records an external collection; it does not charge a card |
| 27 Receipts/archive/exports | Venue/product/price/cost snapshots, actual/billed duration, payment history, private receipts, configurable 58–80 mm layout, read-only reprint, archive filters and BOM UTF-8 CSV with formula protection | CSV is the implemented export; no XLSX button misrepresents a CSV as XLSX |
| 28 Expenses/reports | Expense CRUD/filter/void, sales vs collection/debt separation, refunds and goods returns, historical costs, margin/operating result/cash movement, product/court details, receipt drill-down and CSV | Court utilization uses actual session intervals and a clearly labeled current-schedule capacity estimate |
| 29 Notifications/activity | Scoped persisted notifications, per-user reads, action/actor/time/reason/change audit; structured request log payloads without customer names, bodies, private URL tokens or credentials | Dashboard data refreshes on navigation/reload; no misleading offline/live claims |
| 30 Settings/content | Managed multilingual copy, hero upload, section visibility, business details, prices/hours/delivery/printing/language settings | Missing business inputs remain explicit in setup/demo banners |
| 31–33 Models, defects, safety and operation | Incremental migrations, stable IDs/snapshots, transaction locks, stock/amount checks, CSRF, password hashing, safe redirects/uploads, permission checks, protected customer references, pagination, backup CLI and recovery guide | MySQL staging/performance checks are not yet executed |
| 34–36 Acceptance and handover | Automated business/security/concurrency/recovery suite, browser journeys, responsive/RTL review, redacted environment example, setup and usage/recovery documentation | Remaining external launch inputs are listed below |

## Repaired defects

One authoritative service now owns price/time/discount/availability/stock/settlement/report rules. Court rate precedence is explicit and valid zero settings remain zero. Boundary billing uses seconds before rounding (including 59:59, 60:00 and 60:01). Linked reservations are not double-counted as both booking revenue and POS revenue. Structured debt records distinguish receivables from cash collections. Mutations have operation-level authorization, CSRF, transaction protection and replay keys. Bookings/orders cannot be fetched publicly through sequential IDs. Concurrent last-stock and overlapping-booking attempts are serialized. Repeated cancellation/refund restores stock at most once. Historical records are archived rather than cascade-deleted, and receipts use sale-time snapshots. Shared notification reads are per person.

The fresh project also removes duplicate factories, startup schema creation/default credentials, client-specific seeds and active excluded integrations. The browser pass found and repaired a real CSRF expiry-type error. Final reporting checks corrected website cash/card archive filters and pre-fulfillment refund cost reversal.

## Automated evidence

Run from the project directory:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m scripts.check_translations
.\.venv\Scripts\python.exe -m flask --app run db check
.\.venv\Scripts\python.exe -m compileall -q app tests scripts
```

The suite exercises public/staff routes, locales, valid and missing CSRF, conflicts and concurrent requests, midnight/inactive courts/invalid durations/forged prices, cancellation states, pickup/delivery and stock checks, hourly boundaries, occupancy/frozen bills, discounts, quick sales, debt collection/refunds, permission denial, notification isolation, immutable receipt values/reprint, safe redirects/login throttling, barcode/export/excluded endpoints, expense filtering/void audit, zero-setting saves and 58 mm receipt configuration. It also creates a fresh migrated database, repeats setup, creates/verifies an administrator, upgrades an existing Verda revision with retained IDs, backs up, checks integrity and serves the restored database.

Final results on 17 September 2026: **31 tests passed in 21.34 seconds**, with no warnings; the expanded translation audit covers **575 extracted interface messages, zero missing translations**; Alembic reported **no new upgrade operations detected**; Python compile verification completed without errors. Tests use independent temporary databases with fictional records; they do not reset the preview database.

## Browser evidence

Verified in the local browser with CSRF enabled:

- Public booking request → private pending confirmation → staff approval showing confirmed.
- Store product/cart → pickup checkout → private order confirmation; no online-payment claim.
- Staff sign in → cashier table creation → product addition → Finish play → unchanged stopped timer with another product addition → cash settlement → paid receipt with 2,000 IQD recorded and zero balance.
- Quick-sale keyboard barcode entry twice → quantity two → debt invoice for a named fictional customer with 2,000 IQD outstanding.
- Paid/unpaid archive entries; local receipt rendering; mobile navigation.
- Desktop public layouts, tablet cashier at 820×1180, English homepage and Arabic booking at 390×844. Language selection renders corresponding text and direction. Viewport overrides were reset after review.

This is representative browser verification, not exhaustive testing of every browser/device combination. Receipt layout/reprint logic was checked; no physical printing, actual bank-card transaction, hardware scanner, offline transaction, email or SMS delivery was claimed or performed.

## Before accepting real customers

Supply the actual venue data/policies and replace the clearly fictional catalog. Review translations with a native speaker. Verify the physical receipt/label printer, select the production database/host/domain, configure HTTPS and a protected secret, create real staff accounts and set up/rehearse backups. MySQL, production load and deployment were not tested in this environment. The application is available locally; there is no public deployment URL.

See README.md to run it, USAGE.md for staff workflows, and OPERATIONS.md for metric definitions and recovery.
