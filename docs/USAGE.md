# Admin and cashier guide

## Administrator

1. Sign in at `/auth/login`. Start with **Website & settings**, then create courts, tables, categories and products. Court rates override the global rate; a zero price is valid. Disabling a court/category/product prevents new use while preserving past records.
2. **Staff & permissions** is restricted to super administrators. Create each person's account, choose `admin` and assign only their needed permissions. A cashier commonly needs POS and receipts; add debts if they may sell on account or collect balances. Discounts and cancellations are separate permissions. The final active super administrator cannot be deactivated or demoted. Changing an account invalidates its earlier sessions.
3. Enter initial stock when creating a tracked product. Later changes belong in **Inventory**, with signed quantity and reason. Untracked products have no quantity limit. Low-stock events create internal notifications. Archive products instead of deleting sale history.
4. **Barcode labels** supports product/category selection, optional prices, 38×25/50×30/60×40 mm labels, previews and browser printing. Barcode regeneration requires a reason; old printed labels will need replacement.
5. **Bookings** shows pending requests and searchable history. Inspect a request before approval; approval rechecks availability. Staff can create/edit eligible bookings, reject/cancel with a reason, and mark completed. Cancellation requests have a separate queue; rejecting one restores its prior status. Approval does not record payment.
6. **Court maintenance** reserves blocked intervals and prevents new bookings. Existing conflicting reservations or active sessions must be resolved first.
7. **Website orders** move from pending → confirmed → processing → collected (pickup) or delivered. Record actual cash/card collections separately; partial collections are allowed up to the remaining balance. Pickup clears delivery details. Cancellation restores stock once when allowed. Use the explicit refund action for paid/fulfilled orders; select goods returned only when they were physically returned.
8. **Expenses** records positive IQD amounts with category, date and cash/card method. Edits and archival require reasons. Reports distinguish operating expenses from inventory purchases.
9. **Reports** uses date presets or a custom range, with sales, collections, debts, costs, product details, utilization and underlying records. **Receipt archive** adds type, method and customer/reference filters. CSV downloads preserve those filters. See OPERATIONS.md for exact metric definitions.
10. Notifications are permission-scoped and read independently by each user. Activity history records staff actions and reasons. Managed copy accepts plain text; HTML is escaped.

## Cashier

1. Open **Cashier**. Select an available court and enter customer details; select a currently eligible confirmed booking to link its reserved time and avoid charging it twice. For a table, choose **Open table**; tables do not accrue time charges. An occupied court/table cannot have a second active session.
2. Add products with the touch catalog, category/search controls or a keyboard-style barcode scanner. Product prices and stock are checked on the server. Adjust quantities before preparation; prepared goods require the explicit return workflow. Progress preparation through pending, preparing, ready and delivered as appropriate.
3. **Finish play** freezes time billing and releases the location. The unpaid bill remains available for product additions and settlement. Bill rounding/minimum rules are snapshotted when the session starts. The live timer itself does not set prices.
4. With permission, apply a fixed IQD or percentage discount and provide a reason. Automatic time discounts and a manual bill discount are each applied once.
5. Choose cash/card only after receiving the corresponding payment, then **Finalize bill**. This records the payment; it does not operate a bank terminal. Choose debt only with permission and a customer name. A debt invoice creates a linked receivable instead of a cash collection.
6. The resulting receipt includes item/rate/venue snapshots. Use **Print / reprint** as often as needed; it never creates a new payment. Set browser scale to 100%, disable browser headers/footers, and select paper matching the configured receipt width. Verify the physical printer before live use.
7. **Quick sale** sells products without a court/table. Scan repeatedly to increase quantity, or enter quantities directly. The server verifies the complete basket when submitted. Debt and discount rules are the same as session sales.
8. **Debts** supports manual receivables and automatically linked sales. Record a partial or full cash/card collection. Overpayment is rejected. Collections appear in reports as payments against existing debt, not new revenue.
9. Open unused bills may be voided by permitted staff with a reason. Prepared goods require settlement followed by an explicit refund/return. Finalized receipts remain in history even after a refund.

## Customers and languages

Customers choose an active court, business date and duration, load available slots, enter contact details and receive a private pending-approval reference. After-midnight slots show their actual calendar date. The confirmation link also supports requesting cancellation. Keep private confirmation URLs private.

The store supports category/search, product details, quantities, cart changes, pickup and enabled delivery. Orders are requests with payment handled by staff; no online payment or third-party notification is sent. The language selector persists English or Arabic across navigation; Arabic uses RTL.
