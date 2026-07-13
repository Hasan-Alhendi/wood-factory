import frappe

from wood_factory.security import require_operational_view


@frappe.whitelist()
def resolve_scan(code):
    require_operational_view()
    code = (code or "").strip()
    if not code:
        frappe.throw("Scan or enter a factory code")

    order_name = _extract_code(code, "FO")
    piece_uid = _extract_code(code, "FP")

    order = _find_order(order_name or code)
    if order:
        _require_read("Factory Order", order)
        return _order_result(order)

    piece = _find_piece(piece_uid or code)
    if piece:
        _require_read("Factory Piece", piece)
        if not piece.is_exception:
            order = frappe.get_doc("Factory Order", piece.factory_order)
            _require_read("Factory Order", order)
            result = _order_result(order)
            result["message"] = "This is a normal piece. Work is controlled by the whole Factory Order."
            return result
        return _piece_result(piece)

    frappe.throw(f"No Factory Order or Factory Piece matches code {code}")


def _require_read(doctype, doc):
    if not frappe.has_permission(doctype, ptype="read", doc=doc):
        frappe.throw(f"You are not permitted to view this {doctype}", frappe.PermissionError)


def _extract_code(value, prefix):
    marker = f"WF:{prefix}:"
    return value.split(marker, 1)[1].strip() if marker in value else None


def _find_order(value):
    name = frappe.db.exists("Factory Order", value)
    return frappe.get_doc("Factory Order", name) if name else None


def _find_piece(value):
    name = frappe.db.exists("Factory Piece", value) or frappe.db.get_value("Factory Piece", {"piece_uid": value}, "name")
    return frappe.get_doc("Factory Piece", name) if name else None


def _order_result(order):
    stage = next((row for row in order.production_stages if row.stage == order.current_stage), None)
    return {
        "kind": "order",
        "name": order.name,
        "scan_code": f"WF:FO:{order.name}",
        "customer": order.customer,
        "stage": order.current_stage,
        "status": stage.status if stage else order.status,
        "progress_percent": order.progress_percent,
        "route": ["factory-worker"],
    }


def _piece_result(piece):
    return {
        "kind": "piece",
        "name": piece.name,
        "scan_code": f"WF:FP:{piece.piece_uid}",
        "piece_uid": piece.piece_uid,
        "factory_order": piece.factory_order,
        "part_name": piece.part_name,
        "width_mm": piece.width_mm,
        "height_mm": piece.height_mm,
        "stage": piece.current_stage,
        "status": piece.status,
        "route": ["Form", "Factory Piece", piece.name],
    }
