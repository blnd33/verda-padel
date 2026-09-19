# Operation and recovery

## Backups

From the project directory, make a new SQLite snapshot:

```powershell
.\.venv\Scripts\python.exe -m flask --app run backup 'C:\VerdaBackups\verda-2026-09-17.db'
```

The command uses SQLite's online backup API and refuses to overwrite an existing file or the live database. For a coordinated database/upload snapshot, stop the application first, run the command, and copy `app/static/uploads` to the same dated backup set. Keep the production `SECRET_KEY`/`.env` separately encrypted with restricted access. Development's `instance/.session-secret` has the equivalent session-secret role. Retain the matching source release and migration revision. Never put backups under `app/static`.

Schedule backups using the deployment operator's normal system scheduler, with retention and off-machine copies appropriate to the venue. No backup scheduler or cloud integration has been installed automatically. Check storage space and restore a sample backup regularly.

## Restore SQLite

1. Stop all Verda application processes and take a safety copy of the current database and uploads.
2. Restore into a **new directory**, using the source version associated with the backup. Copy the backup to the configured SQLite path (`instance/verda.db` for the default URL) and restore the matching `app/static/uploads` directory and secret.
3. Run SQLite `PRAGMA integrity_check` on the restored copy; it must return `ok`. The automated recovery test opens the backup with SQLite and runs this check.
4. Run `python -m flask --app run db current`. If intentionally deploying newer source, apply its reviewed incremental migrations with `db upgrade` after retaining the original backup.
5. Start the restored installation on a temporary loopback port. Sign in, inspect known receipt totals, stock and balances, then switch the production service to the restored installation.

Do not overwrite a database that is open in a running service. Do not mix a live database's `-wal`/`-shm` sidecars with a backup; restoring into a clean directory avoids this. Restoring a database to an earlier point also restores stock, collections and operation keys to that point: reconcile any transactions recorded after the backup before reopening sales.

For MySQL, use its native consistent backup/restore tooling and include the transaction-lock row and migration table. The `backup` command deliberately refuses non-SQLite databases. MySQL recovery was not executed in this environment.

## Errors and audit history

Staff activity records capture actor, action, entity, time, reason and relevant changes; passwords are omitted. Request log messages contain JSON fields for endpoint, method, status and duration, without request bodies, customer details, credentials or private confirmation URL tokens. Standard server error logs go to the service's stderr. The local preview writes ignored `instance/server.log` and `instance/server-error.log`. Monitor failed responses, database availability and backup success; rotate deployment logs and restrict access to them.

Validation errors roll back mutations. Use the page's back action to correct retained browser form values; reload when the error says the operation reference expired. Never retry with a different payment just because printing failed: open the receipt archive and inspect the recorded payment first. Reprinting is read-only. If the browser loses its connection, a fresh page load is needed to confirm what the server recorded; the interface does not claim offline success.

## Accounting definitions

All money is integer IQD, rounded half-up. Timestamps are stored in UTC and displayed in the venue timezone (initially Asia/Baghdad). For overnight hours, early-morning bookings belong to the preceding business day. A sale uses its POS start business day, or website fulfillment business day; a collection/refund uses the day it is recorded.

- Finalized POS bills, including debt invoices, and fulfilled website orders are sales. Website confirmation alone is not a sale or a payment. Booking quoted/confirmed values are reported separately and excluded from sales.
- Cash/card collections are actual recorded payment rows. Debt collections settle receivables and never create new sales. Outstanding debt, active sessions and stopped unpaid bills are current balances independent of report date filters.
- Refund adjustments reverse recognized sales on their own business date. Actual collected money is reversed using its original cash/card methods. Uncollected debt is voided, not refunded as cash.
- Product costs come from the original line snapshot. Explicit goods returns reverse that cost; consumed/unreturned goods retain their cost. A refund before website fulfillment reverses no sales or COGS because neither has been recognized.
- Gross margin = net sales minus historical net product cost. Operating result additionally subtracts operating expenses. Inventory purchases affect cash movement but are excluded from operating expenses to avoid deducting them again alongside COGS.
- Cash movement on this report means **cash and card collections less all recorded expenses**. It is not a bank balance or cash-drawer reconciliation.
- Court-time charges are before whole-bill manual discounts; finalized court bills include products and bill discounts. Product drill-down values are original item values before whole-bill discounts and later refunds.
- Court utilization unions actual session intervals within currently configured opening hours, through the current time. Available hours subtract maintenance. Historical activation dates and opening schedules are not stored, so the denominator is explicitly an estimate, especially after configuration changes. It is not a historical capacity ledger.
- Receipt archive totals exclude cancelled/voided records but can include unpaid charges. Cash/card filters match actual recorded methods, including mixed-method website collections. Paid/unpaid filters represent current payment state. CSV uses the same filtered records and totals as the screen.

## Launch inputs still required

The owner must supply approved contact/address/directions/social links, court names/rates, operating hours, minimum/rounding and cancellation policies, delivery availability/fees, actual product inventory/costs, and venue copy/photos. Arrange a native Arabic copy review and check the actual printer's paper/driver settings. Configure a production host/domain/HTTPS, restricted administrator accounts and backups before accepting real customers. None of these business details were invented.
