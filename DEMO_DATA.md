# Wood Factory Demo Dataset

The demo dataset is prepared in code but is **not created automatically** during installation or migration. It must be generated explicitly after the application has been migrated on the target ERPNext site.

## Safety model

- Uses a company-specific prefix such as `WF-DEMO-HT`.
- Is idempotent: rerunning it repairs or refreshes missing demo records instead of duplicating the scenarios.
- Never deletes production records.
- Creates example users as disabled System Users and does not send welcome emails.
- Creates a submitted Material Receipt only when `include_stock=1`; the receipt is created once per company.
- Marks synthetic historical cost ledger rows with `[WOOD_FACTORY_DEMO]` and does not present them as real Material Issue Stock Entries.
- Restricts the management page and server methods to factory management roles.

## Generated master data

For the selected ERPNext Company, the generator creates or reuses:

- a selling Price List in the company currency;
- a demo Item Group, Customer Group, and Territory;
- raw-board, edge-band, work-in-progress, finished-goods, and remnant warehouses;
- white and oak MDF board Items;
- matching white and oak edge-band Items;
- a non-stock custom-job sales Item;
- six demo Customers;
- disabled demo users for planning, supervision, accounting, every production stage, and delivery;
- worker hourly cost rates;
- eight Factory Workstations, including a second edge bander under maintenance;
- optional opening demo stock through one submitted Material Receipt.

## Realistic scenarios

| Code | Scenario |
| --- | --- |
| `NORMAL-CUTTING` | Normal customer order waiting for the cutting stage |
| `DELAYED-BLOCKED` | Late order blocked in edge banding with an unavailable machine |
| `DAMAGED-REMNANT` | Damaged piece at quality inspection with a replacement reserved from an exact matching remnant |
| `WRONG-DIM-NEW-BOARD` | Wrong-dimension piece requiring a factory-funded replacement from a new full board, with recovered factory-owned remainder |
| `READY-DELIVERY` | Fully completed order ready for delivery |
| `DELIVERED` | Historical delivered order for profitability, productivity, and waste reports |

Each scenario includes a Sales Order, Factory Order, Cutting Order, board layouts, generated pieces, production stages, operating time, cost records, and the relevant exception, remnant, alert, or delivery status.

## Management page

After migration, open:

```text
Factory Control Center → Demo Data
```

or navigate directly to:

```text
/app/factory-demo-data
```

Select the Company, decide whether to create disabled users and opening demo stock, then use **Generate Demo Dataset**.

## Deployment commands

These commands are examples for the current factory site and have not been executed yet:

```bash
bench --site almadina.horizontechco.com migrate
bench --site almadina.horizontechco.com clear-cache
```

Generate from the command line using the safer orchestration module:

```bash
bench --site almadina.horizontechco.com execute \
  wood_factory.demo_dataset.create_demo_dataset \
  --kwargs '{"company":"<ERPNext Company>","include_users":1,"include_stock":1}'
```

Check status without creating data:

```bash
bench --site almadina.horizontechco.com execute \
  wood_factory.demo_dataset.get_demo_status \
  --kwargs '{"company":"<ERPNext Company>"}'
```

## Important runtime note

ERPNext installations may differ in stock accounts, warehouse roots, stock-freeze dates, currencies, and mandatory Sales Order fields. The generator treats an optional Material Receipt failure as a visible warning and continues creating the non-stock operational scenarios. Full execution and permission behavior must be verified on the real Frappe site during the end-to-end testing stage.
