# Wood Factory Security and Role Matrix

The application uses server-side authorization in addition to Frappe DocType, Page, Report, and field-level permissions. Hiding a button is never treated as sufficient authorization.

## Roles

| Role | Main responsibility |
| --- | --- |
| Factory Manager | Full factory management, supervision, planning, and financial visibility |
| Factory Supervisor | Production supervision, exceptions, delivery readiness, alerts, and queue rebalancing |
| Factory Planner | Orders, cutting plans, workstations, capacity, ETA, and production scheduling |
| Factory Accountant | Factory costing, rates, ledgers, and profitability reports without shop-floor actions |
| Factory Cutting Operator | Cutting-stage queue and actions only |
| Factory Edge Banding Operator | Edge-banding-stage queue and actions only |
| Factory Drilling Operator | Drilling-stage queue and actions only |
| Factory Assembly Operator | Assembly-stage queue and actions only |
| Factory Quality Inspector | Quality-inspection-stage queue, issue reporting, and issue analysis |
| Factory Packing Operator | Packing-stage queue and actions only |
| Factory Delivery User | Ready-for-delivery and delivered orders only |

## Core enforcement rules

1. A stage operator can read orders and exception pieces only while they are in that operator's stage.
2. Stage operators cannot edit raw Factory Order or Factory Piece documents. Start, block, resume, and complete actions run through guarded server methods.
3. A worker cannot complete or block another worker's active operation unless the user has planning or supervision authority.
4. Piece exceptions can be reported by the current-stage operator, but replacement decisions, closure, and cancellation require supervision.
5. Cutting optimization is available to cutting planning roles. Material posting is limited to planning roles and Stock Manager.
6. Financial fields use separate permission levels and are not returned by shop-floor APIs.
7. Factory Cost Ledger, worker rates, accounting settings, and profitability reports are restricted to accounting and management roles.
8. Delivery users cannot edit Factory Orders. They use guarded Ready for Delivery and Delivered actions after production and exception validation.
9. Alert acknowledgement is limited to the assigned or escalated user; resolution requires supervision.
10. Query conditions and document-level permission hooks prevent opening another stage's record by guessing its name.
11. QR/barcode scanning validates the scanned document's read permission before returning operational data.
12. Timeline events are exposed to operators only through an authorized Factory Order timeline, not through the global event list.

## Installation and migration

`wood_factory.setup.ensure_factory_roles` runs during installation and migration. It creates factory roles and role profiles, installs Custom DocPerm rows, and synchronizes Page and Report role lists.

Run after deployment:

```bash
bench --site <site> migrate
bench --site <site> clear-cache
```

Then assign one role profile or the required individual roles to each user.

## Tests

The baseline policy tests are located at:

```text
wood_factory/tests/test_security.py
```

Full permission behavior, migration, field visibility, and API denial tests must also be exercised on a real Frappe site as part of the end-to-end test stage.
