# Wood Factory End-to-End Testing

This document is the execution gate before UX polish and production readiness.
None of these commands run automatically during installation or migration.

## Mandatory environment rule

Do **not** run the automated tests or generate acceptance data on the live customer site.
Use a dedicated staging/test site restored from a recent backup, for example:

```text
almadina-test.horizontechco.com
```

In the commands below:

```text
<LIVE_SITE>    = almadina.horizontechco.com
<TEST_SITE>    = the isolated staging/test site
<COMPANY>      = the ERPNext Company used by the factory
```

## What the acceptance suite verifies

The suite validates:

1. a normal order waiting for cutting;
2. a delayed order blocked at edge banding with an active alert;
3. a damaged piece replaced from an exact matching remnant;
4. a wrong-dimension piece replaced from a new factory-funded board;
5. recovery of reusable board remainder into factory remnants;
6. a completed order ready for delivery;
7. a historically delivered order with timeline and costing records;
8. separation of customer-billable and factory-funded costs;
9. installation of all factory roles;
10. Sales Order, Factory Order, Cutting Order, layouts, and physical pieces for every scenario;
11. idempotency when demo generation is repeated.

Implementation:

```text
wood_factory/e2e.py
wood_factory/tests/test_e2e_factory_flow.py
```

## Safety controls in code

`run_factory_acceptance` refuses to create records unless:

```text
confirm_demo = 1
```

Stock generation additionally requires:

```text
confirm_stock = 1
```

The generated records use a company-specific `WF-DEMO-...` prefix and the marker:

```text
[WOOD_FACTORY_DEMO]
```

The generator does not delete production records, but it must still be used only on the isolated test site.

## 1. Back up the live site

```bash
bench --site <LIVE_SITE> backup --with-files
```

Record the database, public-files, and private-files backup paths before continuing.

## 2. Prepare the isolated test site

Create a separate Frappe site or restore the backup into an existing staging site. Do not point the live domain to it.

After restore, confirm:

- the site database is separate from the live database;
- Redis queues and scheduler operations cannot alter live records;
- outgoing email is disabled or redirected;
- payment, SMS, and external webhooks are disabled;
- the test site has its own host name or is reachable only internally.

The exact site creation and restore commands depend on the current Docker layout and will be executed during the server session.

## 3. Update the application branch

Run inside the Wood Factory app directory used by the test bench:

```bash
cd /home/frappe/frappe-bench/apps/wood_factory
git status
git fetch origin
git switch agent/factory-order-architecture
git pull --ff-only origin agent/factory-order-architecture
```

The working tree must be clean.

## 4. Migrate the test site and build assets

```bash
cd /home/frappe/frappe-bench
bench --site <TEST_SITE> migrate
bench build --app wood_factory
bench --site <TEST_SITE> clear-cache
bench --site <TEST_SITE> clear-website-cache
```

Confirm that the test site opens before running data tests.

## 5. Run focused test modules

```bash
bench --site <TEST_SITE> run-tests \
  --app wood_factory \
  --module wood_factory.tests.test_arabic_translations

bench --site <TEST_SITE> run-tests \
  --app wood_factory \
  --module wood_factory.tests.test_security

bench --site <TEST_SITE> run-tests \
  --app wood_factory \
  --module wood_factory.wood_factory.cutting.test_maxrects
```

## 6. Run the rollback-based E2E tests

```bash
bench --site <TEST_SITE> run-tests \
  --app wood_factory \
  --module wood_factory.tests.test_e2e_factory_flow
```

The test module uses database savepoints and checks:

- the full acceptance suite;
- repeated generation does not duplicate data;
- validation does not change scenario states.

## 7. Create inspectable acceptance data without stock

This step creates persistent demo records on the **test site only**:

```bash
bench --site <TEST_SITE> execute \
  wood_factory.e2e.run_factory_acceptance \
  --kwargs '{"company":"<COMPANY>","include_users":0,"include_stock":0,"confirm_demo":1}'
```

Required result:

```text
passed: true
critical_failed: 0
ready_for_runtime_testing: true
```

Read-only recheck:

```bash
bench --site <TEST_SITE> execute \
  wood_factory.e2e.validate_factory_acceptance \
  --kwargs '{"company":"<COMPANY>"}'
```

## 8. Manual bilingual checks

Log in once with an Arabic test user and once with an English test user. Verify:

- Factory Control Center;
- Factory Worker;
- Factory Scan;
- Factory Reports;
- Factory Order and Cutting Order forms;
- Piece Exception and Board Remnant forms;
- measurements, money, document IDs, and QR/barcodes remain readable in RTL;
- no important action or status remains untranslated.

## 9. Manual operational checks

### Normal order

- the whole order appears in the cutting queue;
- the assigned workstation is active;
- start, block, resume, and complete update the order and timeline;
- normal pieces move with the whole order.

### Replacement from remnant

- the remnant item exactly matches the replacement piece board item;
- the remnant is reserved for that replacement piece;
- no new Cutting Order is created;
- the customer is not billed.

### Replacement from a new board

- Cutting Order type is `Internal Replacement`;
- `Customer Billable` is disabled;
- factory-funded material cost is recorded separately;
- reusable remainder returns to Board Remnant inventory;
- the replacement remains linked to the original customer order.

### Delivery

- unresolved exceptions prevent Ready for Delivery;
- completed production can be marked Ready for Delivery;
- Confirm Delivered creates an auditable timeline event.

## 10. Stock and accounting acceptance

Only after all non-stock checks pass, review the test company's warehouses, accounts, cost centers, valuation, and stock-freeze date.

Then run on the test site:

```bash
bench --site <TEST_SITE> execute \
  wood_factory.e2e.run_factory_acceptance \
  --kwargs '{"company":"<COMPANY>","include_users":0,"include_stock":1,"confirm_demo":1,"confirm_stock":1}'
```

Verify:

- the demo Material Receipt is submitted once;
- board and edge-band quantities exist in demo warehouses;
- approving a customer Cutting Order creates a Material Issue;
- material quantities decrease correctly;
- company, cost center, expense account, and project are correct;
- internal replacement cost is not customer billable;
- eligible cancellation reverses the Factory Cost Ledger entry;
- cancellation is blocked after a related remnant has been consumed or scrapped.

## 11. Full application suite

```bash
bench --site <TEST_SITE> run-tests --app wood_factory
```

Save the complete output for the production-readiness review.

## 12. Live deployment gate

Only after the staging tests pass:

1. take a fresh live backup;
2. deploy the tested commit to the live bench;
3. run migration and asset build on the live site;
4. do **not** generate demo data on the live site;
5. perform only a smoke test using one controlled real order;
6. keep the rollback backup available until the smoke test is approved.

## Exit criteria

The End-to-End stage is complete only when:

- staging migration succeeds;
- assets build successfully;
- Arabic, security, MaxRects, and E2E modules pass;
- runtime acceptance reports zero critical failures;
- stock and accounting checks pass;
- Arabic and English manual checks pass;
- no data is duplicated or corrupted;
- discovered defects are fixed and all affected tests rerun;
- the final tested commit is recorded before live deployment.
