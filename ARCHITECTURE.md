# Wood Factory Architecture

## Principle

Wood Factory is an operations layer on top of ERPNext. It must not duplicate Sales Order, Work Order, Job Card, Quality Inspection, Delivery Note, Item, Warehouse, or accounting documents.

## A-to-Z order flow

Sales Order -> Factory Order -> Material readiness -> Cutting Order -> Board optimization -> Work Order / Job Cards -> Quality -> Packing -> Ready for delivery -> Delivery Note -> Invoice / Payment -> Closed.

## Factory Order

`Factory Order` is the operational tracking aggregate. It links one Sales Order to the current factory stage, responsible user, expected delivery date, delay reason, progress, and an ordered stage timeline. Stage rows may link dynamically to ERPNext documents such as Work Order, Job Card, Quality Inspection, and Delivery Note.

## Cutting Order

`Cutting Order` is the woodworking-specific cutting request linked to a Factory Order and an ERPNext board Item. Board dimensions are stored in millimetres and the default saw kerf is 3 mm.

The parts table represents doors and rectangular parts. Every row stores width, height, quantity, rotation permission, grain direction, four edge-banding flags, and an optional ERPNext Item for the edge band.

## Nesting target

The optimizer will expand quantities into physical pieces and evaluate MaxRects strategies. `Auto` will compare supported strategies and select the result with the lowest board count, then lowest waste. Every placed piece must persist board number, x, y, width, height, and rotation state in a Board Layout placement model.

Saw kerf must be respected between cuts. Rotation must never be applied when disabled and must respect grain direction.

## Next implementation slice

1. Board Layout and Board Layout Placement DocTypes.
2. Pure-Python MaxRects optimizer with deterministic tests.
3. Cutting Order optimize/approve actions.
4. Stock reservation/consumption integration using ERPNext stock documents.
5. Edge-band length and cost calculation.
6. Cutting cost calculation at 1 USD per consumed board, with company-currency conversion handled through ERPNext accounting conventions.
7. Factory Order synchronization from Work Order, Job Card, Quality Inspection, and Delivery Note events.
