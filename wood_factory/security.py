import frappe
from frappe import _


FACTORY_MANAGER = "Factory Manager"
FACTORY_SUPERVISOR = "Factory Supervisor"
FACTORY_PLANNER = "Factory Planner"
FACTORY_ACCOUNTANT = "Factory Accountant"
FACTORY_CUTTING_OPERATOR = "Factory Cutting Operator"
FACTORY_EDGE_OPERATOR = "Factory Edge Banding Operator"
FACTORY_DRILLING_OPERATOR = "Factory Drilling Operator"
FACTORY_ASSEMBLY_OPERATOR = "Factory Assembly Operator"
FACTORY_QUALITY_INSPECTOR = "Factory Quality Inspector"
FACTORY_PACKING_OPERATOR = "Factory Packing Operator"
FACTORY_DELIVERY_USER = "Factory Delivery User"

MANAGEMENT_ROLES = {"System Manager", "Manufacturing Manager", FACTORY_MANAGER}
SUPERVISION_ROLES = MANAGEMENT_ROLES | {FACTORY_SUPERVISOR}
PLANNING_ROLES = SUPERVISION_ROLES | {FACTORY_PLANNER}
ACCOUNTING_ROLES = {"System Manager", "Accounts Manager", FACTORY_MANAGER, FACTORY_ACCOUNTANT}
DELIVERY_ROLES = SUPERVISION_ROLES | {FACTORY_DELIVERY_USER}
CUTTING_PLANNING_ROLES = PLANNING_ROLES | {FACTORY_CUTTING_OPERATOR}
MATERIAL_POSTING_ROLES = PLANNING_ROLES | {"Stock Manager"}

STAGE_ROLE_MAP = {
    "Cutting": FACTORY_CUTTING_OPERATOR,
    "Edge Banding": FACTORY_EDGE_OPERATOR,
    "Drilling": FACTORY_DRILLING_OPERATOR,
    "Assembly": FACTORY_ASSEMBLY_OPERATOR,
    "Quality Inspection": FACTORY_QUALITY_INSPECTOR,
    "Packing": FACTORY_PACKING_OPERATOR,
}
STAGE_ROLES = set(STAGE_ROLE_MAP.values())
OPERATIONAL_ROLES = PLANNING_ROLES | STAGE_ROLES | {FACTORY_DELIVERY_USER, FACTORY_ACCOUNTANT, "Accounts Manager", "Stock Manager"}
READ_TYPES = {None, "read", "select", "report", "export", "print", "email"}


def get_user_roles(user=None):
    user = user or frappe.session.user
    if user == "Administrator":
        return {"System Manager"}
    return set(frappe.get_roles(user))


def has_any_role(allowed, user=None):
    return bool(get_user_roles(user) & set(allowed))


def require_any_role(allowed, message=None, user=None):
    if not has_any_role(allowed, user=user):
        frappe.throw(message or _("You do not have permission to perform this factory action"), frappe.PermissionError)


def require_operational_view(user=None):
    require_any_role(OPERATIONAL_ROLES, _("A factory operational role is required"), user=user)


def require_management(user=None):
    require_any_role(MANAGEMENT_ROLES, _("Factory Manager permission is required"), user=user)


def require_supervision(user=None):
    require_any_role(SUPERVISION_ROLES, _("Factory Supervisor permission is required"), user=user)


def require_planning(user=None):
    require_any_role(PLANNING_ROLES, _("Factory planning permission is required"), user=user)


def require_accounting(user=None):
    require_any_role(ACCOUNTING_ROLES, _("Factory accounting permission is required"), user=user)


def require_delivery(user=None):
    require_any_role(DELIVERY_ROLES, _("Factory delivery permission is required"), user=user)


def require_cutting_planning(user=None):
    require_any_role(CUTTING_PLANNING_ROLES, _("Cutting planning permission is required"), user=user)


def require_material_posting(user=None):
    require_any_role(MATERIAL_POSTING_ROLES, _("Material posting permission is required"), user=user)


def require_stage_access(stage, user=None):
    if has_any_role(SUPERVISION_ROLES, user=user):
        return
    required_role = STAGE_ROLE_MAP.get(stage)
    if not required_role or not has_any_role({required_role}, user=user):
        frappe.throw(_("Your role does not allow work on production stage {0}").format(stage), frappe.PermissionError)


def stage_accessible_to_user(stage, user=None):
    roles = get_user_roles(user)
    return bool(roles & SUPERVISION_ROLES) or bool(STAGE_ROLE_MAP.get(stage) and STAGE_ROLE_MAP[stage] in roles)


def accessible_stages(user=None):
    roles = get_user_roles(user)
    if roles & SUPERVISION_ROLES:
        return list(STAGE_ROLE_MAP)
    return [stage for stage, role in STAGE_ROLE_MAP.items() if role in roles]


def can_view_financials(user=None):
    return has_any_role(ACCOUNTING_ROLES | MANAGEMENT_ROLES, user=user)


def require_alert_access(alert=None, user=None):
    user = user or frappe.session.user
    if has_any_role(SUPERVISION_ROLES, user=user):
        return
    if alert and user in {alert.responsible, alert.escalated_to}:
        return
    frappe.throw(_("You are not responsible for this factory alert"), frappe.PermissionError)


def factory_order_query(user=None):
    user = user or frappe.session.user
    roles = get_user_roles(user)
    if roles & (PLANNING_ROLES | ACCOUNTING_ROLES | {"Stock Manager"}):
        return ""
    clauses = []
    stages = accessible_stages(user)
    if stages:
        clauses.append("`tabFactory Order`.`current_stage` in ({})".format(",".join(frappe.db.escape(stage) for stage in stages)))
    if FACTORY_DELIVERY_USER in roles:
        clauses.append("`tabFactory Order`.`status` in ('Ready for Delivery','Delivered')")
    return " or ".join(clauses) if clauses else "1=0"


def factory_piece_query(user=None):
    user = user or frappe.session.user
    roles = get_user_roles(user)
    if roles & (PLANNING_ROLES | ACCOUNTING_ROLES | {"Stock Manager"}):
        return ""
    clauses = []
    stages = accessible_stages(user)
    if stages:
        clauses.append("`tabFactory Piece`.`current_stage` in ({})".format(",".join(frappe.db.escape(stage) for stage in stages)))
    if FACTORY_DELIVERY_USER in roles:
        clauses.append("`tabFactory Piece`.`status`='Completed'")
    return " or ".join(clauses) if clauses else "1=0"


def piece_exception_query(user=None):
    user = user or frappe.session.user
    roles = get_user_roles(user)
    if roles & SUPERVISION_ROLES:
        return ""
    clauses = [
        "`tabPiece Exception`.`reported_by`={}".format(frappe.db.escape(user)),
        "`tabPiece Exception`.`responsible`={}".format(frappe.db.escape(user)),
    ]
    stages = accessible_stages(user)
    if stages:
        clauses.append("`tabPiece Exception`.`reported_stage` in ({})".format(",".join(frappe.db.escape(stage) for stage in stages)))
    return " or ".join(clauses) if clauses else "1=0"


def factory_alert_query(user=None):
    user = user or frappe.session.user
    if has_any_role(SUPERVISION_ROLES, user=user):
        return ""
    escaped = frappe.db.escape(user)
    return f"(`tabFactory Alert Log`.`responsible`={escaped} or `tabFactory Alert Log`.`escalated_to`={escaped})"


def factory_order_permission(doc, user=None, permission_type=None):
    user = user or frappe.session.user
    roles = get_user_roles(user)
    if permission_type not in READ_TYPES:
        return bool(roles & PLANNING_ROLES)
    if roles & (PLANNING_ROLES | ACCOUNTING_ROLES | {"Stock Manager"}):
        return True
    if FACTORY_DELIVERY_USER in roles and getattr(doc, "status", None) in ("Ready for Delivery", "Delivered"):
        return True
    return stage_accessible_to_user(getattr(doc, "current_stage", None), user=user)


def factory_piece_permission(doc, user=None, permission_type=None):
    user = user or frappe.session.user
    roles = get_user_roles(user)
    if permission_type not in READ_TYPES:
        return bool(roles & PLANNING_ROLES)
    if roles & (PLANNING_ROLES | ACCOUNTING_ROLES | {"Stock Manager"}):
        return True
    if FACTORY_DELIVERY_USER in roles and getattr(doc, "status", None) == "Completed":
        return True
    return stage_accessible_to_user(getattr(doc, "current_stage", None), user=user)


def piece_exception_permission(doc, user=None, permission_type=None):
    user = user or frappe.session.user
    roles = get_user_roles(user)
    if permission_type == "create":
        return bool(roles & (SUPERVISION_ROLES | STAGE_ROLES))
    if permission_type not in READ_TYPES:
        return bool(roles & SUPERVISION_ROLES)
    if roles & SUPERVISION_ROLES:
        return True
    return user in {getattr(doc, "reported_by", None), getattr(doc, "responsible", None)} or stage_accessible_to_user(getattr(doc, "reported_stage", None), user=user)


def factory_alert_permission(doc, user=None, permission_type=None):
    user = user or frappe.session.user
    if permission_type not in READ_TYPES:
        return has_any_role(SUPERVISION_ROLES, user=user)
    if has_any_role(SUPERVISION_ROLES, user=user):
        return True
    return user in {getattr(doc, "responsible", None), getattr(doc, "escalated_to", None)}


def financial_document_permission(doc, user=None, permission_type=None):
    user = user or frappe.session.user
    roles = get_user_roles(user)
    if permission_type in READ_TYPES:
        return bool(roles & (ACCOUNTING_ROLES | MANAGEMENT_ROLES))
    return bool(roles & (ACCOUNTING_ROLES | MANAGEMENT_ROLES))


def operational_document_permission(doc, user=None, permission_type=None):
    return has_any_role(OPERATIONAL_ROLES, user=user)
