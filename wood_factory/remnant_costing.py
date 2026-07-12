import frappe
from frappe.utils import flt

from wood_factory.accounting import _create_cost_ledger, resolve_accounting_context, sync_factory_order_costs


def calculate_remnant_value(remnant):
    if not remnant.source_cutting_order:
        return {"rate_per_m2": 0, "estimated_value": 0, "currency": None}
    cutting = frappe.get_doc("Cutting Order", remnant.source_cutting_order)
    if cutting.order_type != "Internal Replacement" or not cutting.material_stock_entry:
        return {"rate_per_m2": 0, "estimated_value": 0, "currency": cutting.currency}
    stock_entry = frappe.get_doc("Stock Entry", cutting.material_stock_entry)
    board_value = 0
    for row in stock_entry.items or []:
        if row.item_code != cutting.board_item:
            continue
        amount = flt(row.get("basic_amount") or row.get("amount"))
        if not amount:
            qty = flt(row.get("transfer_qty") or row.get("qty"))
            amount = qty * flt(row.get("valuation_rate") or row.get("basic_rate"))
        board_value += abs(amount)
    total_area = flt(cutting.board_count) * flt(cutting.board_width_mm) * flt(cutting.board_height_mm) / 1_000_000
    rate = board_value / total_area if total_area else 0
    value = flt(remnant.area_m2) * rate
    return {
        "rate_per_m2": flt(rate, 4),
        "estimated_value": flt(value, 2),
        "currency": cutting.currency or frappe.db.get_value("Company", cutting.company, "default_currency"),
    }


def post_remnant_recovery(remnant):
    if flt(remnant.estimated_value) <= 0 or not remnant.source_cutting_order:
        return None
    cutting = frappe.get_doc("Cutting Order", remnant.source_cutting_order)
    if cutting.order_type != "Internal Replacement":
        return None
    context = resolve_accounting_context(cutting.factory_order, internal_replacement=True, expense_kind="material")
    ledger = _create_cost_ledger(
        transaction_key=f"Board Remnant|{remnant.name}|Recovery",
        factory_order=cutting.factory_order,
        cutting_order=cutting.name,
        piece_exception=cutting.piece_exception,
        transaction_type="Remnant Recovery",
        context=context,
        amount=-abs(flt(remnant.estimated_value, 2)),
        accounting_document_type="Board Remnant",
        accounting_document=remnant.name,
        remarks=f"Reusable factory-owned remnant recovered from internal replacement cutting {cutting.name}",
    )
    sync_factory_order_costs(cutting.factory_order)
    return ledger


def post_remnant_consumption(remnant, factory_piece):
    piece = frappe.get_doc("Factory Piece", factory_piece) if isinstance(factory_piece, str) else factory_piece
    exception = frappe.db.get_value("Piece Exception", {"replacement_piece": piece.name}, "name")
    context = resolve_accounting_context(piece.factory_order, internal_replacement=True, expense_kind="material")
    ledger = _create_cost_ledger(
        transaction_key=f"Board Remnant|{remnant.name}|Consumption|{piece.name}",
        factory_order=piece.factory_order,
        cutting_order=piece.cutting_order,
        piece_exception=exception,
        factory_piece=piece.name,
        production_stage="Cutting",
        transaction_type="Remnant Material Consumption",
        context=context,
        amount=abs(flt(remnant.estimated_value, 2)),
        accounting_document_type="Board Remnant",
        accounting_document=remnant.name,
        remarks=f"Factory-owned remnant {remnant.name} consumed for replacement piece {piece.name}",
    )
    sync_factory_order_costs(piece.factory_order)
    return ledger


def reverse_remnant_recovery(remnant):
    ledger = frappe.db.get_value("Factory Cost Ledger", {"transaction_key": f"Board Remnant|{remnant.name}|Recovery", "status": "Posted"}, ["name", "factory_order"], as_dict=True)
    if not ledger:
        return
    frappe.db.set_value("Factory Cost Ledger", ledger.name, "status", "Reversed", update_modified=False)
    sync_factory_order_costs(ledger.factory_order)
