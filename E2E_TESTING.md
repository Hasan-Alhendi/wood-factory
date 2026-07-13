# Wood Factory End-to-End Testing

This document is the execution gate before UX polish and production readiness.
None of the commands below are run automatically by installation or migration.

## What the automated acceptance suite verifies

The suite creates or repairs only records marked as Wood Factory demo data and validates:

1. a normal order waiting for cutting;
2. a delayed order blocked at edge banding with an active alert;
3. a damaged piece replaced from an exact matching remnant;
4. a wrong-dimension piece replaced from a new factory-funded board;
5. recovery of the reusable new-board remainder into factory remnants;
6. a completed order ready for delivery;
7. a historically delivered order with timeline and costing records;
8. customer-billable and factory-funded costs remain separated;
9. all factory roles exist;
10. every scenario contains Sales Order, Factory Order, Cutting Order, board layouts, and physical pieces;
11. generating the dataset twice does not duplicate orders, exceptions, remnants, or alerts.

The primary implementation is:

```text
wood_factory/e2e.py
wood_factory/tests/test_e2e_factory_flow.py
```

## Safety rules

- Take a database and files backup before migration.
- Test on `almadina.horizontechco.com` before any other customer site.
- Do not merge the branch into `main` before migration and tests pass.
- Start with `include_stock=0`; this validates factory operations without posting a stock receipt.
- Use `include_stock=1` only after confirming warehouses, stock accounts, valuation, and stock-freeze dates.
- Demo records use a company-specific `WF-DEMO-...` prefix and `[WOOD_FACTORY_DEMO]` marker.
- The generator does not delete production records.

## 1. Back up the site

Run from the bench container or bench host:

```bash
bench --site almadina.horizontechco.com backup --with-files
```

Record the generated database, public-files, and private-files backup paths before continuing.

## 2. Verify the branch before updating

```bash
cd /home/frappe/frappe-bench/apps/wood_factory
git status
git branch --show-current
git fetch origin
git switch agent/factory-order-architecture
git pull --ff-only origin agent/factory-order-architecture
```

The working tree must be clean before migration.

## 3. Migrate and build assets

```bash
cd /home/frappe/frappe-bench
bench --site almadina.horizontechco.com migrate
bench build --app wood_factory
bench --site almadina.horizontechco.com clear-cache
bench --site almadina.horizontechco.com clear-website-cache
```

After migration, confirm that the site opens before running data tests.

## 4. Run focused static and policy tests

```bash
bench --site almadina.horizontechco.com run-tests \
  --app wood_factory \
  --module wood_factory.tests.test_arabic_translations

bench --site almadina.horizontechco.com run-tests \
  --app wood_factory \
  --module wood_factory.tests.test_security

bench --site almadina.horizontechco.com run-tests \
  --app wood_factory \
  --module wood_factory.wood_factory.cutting.test_maxrects
```

## 5. Run end-to-end tests inside the test runner

```bash
bench --site almadina.horizontechco.com run-tests \
  --app wood_factory \
  --module wood_factory.tests.test_e2e_factory_flow
```

The test uses savepoints and rolls its records back after each test method.

## 6. Run runtime acceptance without stock posting

This creates persistent demo scenarios so they can be inspected in the user interface:

```bash
bench --site almadina.horizontechco.com execute \
  wood_factory.e2e.run_factory_acceptance \
  --kwargs '{"company":"<ERPNext Company>","include_users":0,"include_stock":0}'
```

The output must contain:

```text
passed: true
critical_failed: 0
ready_for_runtime_testing: true
```

A read-only recheck can be run at any time:

```bash
bench --site almadina.horizontechco.com execute \
  wood_factory.e2e.validate_factory_acceptance \
  --kwargs '{"company":"<ERPNext Company>"}'
```

## 7. Manual bilingual checks

Log in once with an Arabic user and once with an English user. Verify:

- Factory Control Center;
- Factory Worker;
- Factory Scan;
- Factory Reports;
- Factory Order and Cutting Order forms;
- Piece Exception and Board Remnant forms;
- measurements, money, document IDs, and QR/barcodes remain readable in RTL;
- no important action or status remains untranslated.

## 8. Manual operational checks

Use the generated scenarios to confirm:

### Normal order

- the whole order appears in the cutting queue;
- the assigned workstation is active;
- starting, blocking, resuming, and completing a stage updates the order and timeline;
- all normal pieces move with the whole order.

### Replacement from remnant

- the remnant item exactly matches the replacement piece board item;
- the remnant is reserved for the replacement piece;
- no new Cutting Order is created;
- the customer is not billed for the replacement.

### Replacement from a new board

- the Cutting Order type is `Internal Replacement`;
- `Customer Billable` is disabled;
- factory-funded material cost is recorded separately;
- usable remainder is returned to Board Remnant inventory;
- the replacement remains linked to the original customer order.

### Delivery

- unresolved exceptions prevent Ready for Delivery;
- completed production can be marked Ready for Delivery;
- Confirm Delivered creates an auditable timeline event.

## 9. Stock and accounting acceptance

Only after the previous steps pass, run with optional demo opening stock:

```bash
bench --site almadina.horizontechco.com execute \
  wood_factory.e2e.run_factory_acceptance \
  --kwargs '{"company":"<ERPNext Company>","include_users":0,"include_stock":1}'
```

Then verify:

- the demo Material Receipt is submitted once;
- stock quantities exist in demo board and edge-band warehouses;
- approving a customer Cutting Order creates a Material Issue;
- board and edge-band quantities decrease;
- Stock Entry company, cost center, expense account, and project are correct;
- internal replacement cost is not customer billable;
- cancelling an eligible Stock Entry reverses the Factory Cost Ledger entry;
- a Stock Entry cannot be cancelled after its remnants have been consumed or scrapped.

## 10. Full application suite

After focused tests pass:

```bash
bench --site almadina.horizontechco.com run-tests --app wood_factory
```

Save the full output for the production-readiness review.

## Exit criteria

The End-to-End stage is complete only when all of the following are true:

- migration succeeds;
- assets build successfully;
- Arabic, security, MaxRects, and E2E test modules pass;
- runtime acceptance reports zero critical failures;
- stock and accounting checks pass on the selected company;
- Arabic and English user checks pass;
- no production data is damaged or duplicated;
- discovered defects are fixed and the tests are rerun.
