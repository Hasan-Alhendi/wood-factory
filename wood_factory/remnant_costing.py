import frappe
from frappe.utils import flt

from wood_factory.accounting import _create_cost_ledger, resolve_accounting_context, sync_factory_order_costs


def calculate_remnant_value(remnant):
    if remnant.parent_remnant:
        parent = frappe.db.get_value(
            "Board Remnant",
            remnant.parent_remnant,
            ["valuation_rate_per_m2", "currency"],
            as_dict=True,
        )
        rate = flt(parent.valuation_rate_per_m2) if parent else 0
        return {
            "rate_per_m2": flt(rate, 4),
            "estimated_value": flt(remnant.area_m2 * rate, 2),
            "currency": parent.currency if parent else None,
        }
    if not remnant.source_cutting_order:
        return {"rate_per_m2": 0, "estimated_value": 0, "currency": None}
    cutting = frappe.get_doc("Cutting Order", remnant.source_cutting_order)
    if cutting.order_type != "Internal Replacement":
        return {"rate_per_m2": 0, "estimated_value": 0, "currency": cutting.currency}
    stock_entry_name = cutting.material_stock_entry
    if not stock_entry_name:
        stock_entry_name = frappe.db.get_value(
            "Factory Cost Ledger",
            {"cutting_order": cutting.name, "transaction_type": "Internal Replacement Material", "status": "Posted"},
            "accounting_document",
        )
    if not stock_entry_name:
        return {"rate_per_m2": 0, "estimated_value": 0, "currency": cutting.currency}
    stock_entry = frappe.get_doc("Stock Entry", stock_entry_name)
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
    company = cutting.company or frappe.db.get_value("Factory Order", cutting.factory_order, "company")
    return {
        "rate_per_m2": flt(rate, 4),
        "estimated_value": flt(value, 2),
        "currency": cutting.currency or frappe.db.get_value("Company", company, "default_currency"),
    }


def post_remnant_recovery(remnant):
    if remnant.parent_remnant or flt(remnant.estimated_value) <= 0 or not remnant.source_cutting_order:
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


def post_remnant_consumption(remnant, factory_piece, consumed_value):
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
        amount=abs(flt(consumed_value, 2)),
        accounting_document_type="Board Remnant",
        accounting_document=remnant.name,
        remarks=f"Factory-owned remnant {remnant.name} partially consumed for replacement piece {piece.name}",
    )
    sync_factory_order_costs(piece.factory_order)
    return ledger


def post_remnant_scrap_loss(remnant, amount, factory_piece=None, reason="Residual scrap"):
    amount = abs(flt(amount, 2))
    if amount <= 0:
        return None
    piece = frappe.get_doc("Factory Piece", factory_piece) if factory_piece else None
    if piece:
        factory_order = piece.factory_order
        cutting_order = piece.cutting_order
        exception = frappe.db.get_value("Piece Exception", {"replacement_piece": piece.name}, "name")
        piece_name = piece.name
        suffix = f"{piece.name}|Residual"
    else:
        cutting = frappe.get_doc("Cutting Order", remnant.source_cutting_order) if remnant.source_cutting_order else None
        if not cutting:
            return None
        factory_order = cutting.factory_order
        cutting_order = cutting.name
        exception = cutting.piece_exception
        piece_name = None
        suffix = "Scrapped"
    context = resolve_accounting_context(factory_order, internal_replacement=True, expense_kind="material")
    ledger = _create_cost_ledger(
        transaction_key=f"Board Remnant|{remnant.name}|Waste|{suffix}",
        factory_order=factory_order,
        cutting_order=cutting_order,
        piece_exception=exception,
        factory_piece=piece_name,
        production_stage="Cutting",
        transaction_type="Waste Cost",
        context=context,
        amount=amount,
        accounting_document_type="Board Remnant",
        accounting_document=remnant.name,
        remarks=f"{reason}: value lost from remnant {remnant.name}",
    )
    sync_factory_order_costs(factory_order)
    return ledger


def reverse_remnant_recovery(remnant):
    ledger = frappe.db.get_value(
        "Factory Cost Ledger",
        {"transaction_key": f"Board Remnant|{remnant.name}|Recovery", "status": "Posted"},
        ["name", "factory_order"],
        as_dict=True,
    )
    if not ledger:
        return False
    frappe.db.set_value("Factory Cost Ledger", ledger.name, "status", "Reversed", update_modified=False)
    sync_factory_order_costs(ledger.factory_order)
    return True
