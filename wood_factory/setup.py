import frappe

from wood_factory.security import (
    ACCOUNTING_ROLES,
    FACTORY_ACCOUNTANT,
    FACTORY_ASSEMBLY_OPERATOR,
    FACTORY_CUTTING_OPERATOR,
    FACTORY_DELIVERY_USER,
    FACTORY_DRILLING_OPERATOR,
    FACTORY_EDGE_OPERATOR,
    FACTORY_MANAGER,
    FACTORY_PACKING_OPERATOR,
    FACTORY_PLANNER,
    FACTORY_QUALITY_INSPECTOR,
    FACTORY_SUPERVISOR,
    MANAGEMENT_ROLES,
    STAGE_ROLES,
)


FACTORY_ROLES = (
    FACTORY_MANAGER,
    FACTORY_SUPERVISOR,
    FACTORY_PLANNER,
    FACTORY_ACCOUNTANT,
    FACTORY_CUTTING_OPERATOR,
    FACTORY_EDGE_OPERATOR,
    FACTORY_DRILLING_OPERATOR,
    FACTORY_ASSEMBLY_OPERATOR,
    FACTORY_QUALITY_INSPECTOR,
    FACTORY_PACKING_OPERATOR,
    FACTORY_DELIVERY_USER,
)

ROLE_PROFILES = {
    "Factory Management": [FACTORY_MANAGER, FACTORY_SUPERVISOR, FACTORY_PLANNER],
    "Factory Supervisor": [FACTORY_SUPERVISOR],
    "Factory Planner": [FACTORY_PLANNER],
    "Factory Accountant": [FACTORY_ACCOUNTANT],
    "Factory Cutting Worker": [FACTORY_CUTTING_OPERATOR],
    "Factory Edge Banding Worker": [FACTORY_EDGE_OPERATOR],
    "Factory Drilling Worker": [FACTORY_DRILLING_OPERATOR],
    "Factory Assembly Worker": [FACTORY_ASSEMBLY_OPERATOR],
    "Factory Quality Inspector": [FACTORY_QUALITY_INSPECTOR],
    "Factory Packing Worker": [FACTORY_PACKING_OPERATOR],
    "Factory Delivery User": [FACTORY_DELIVERY_USER],
}

FULL = {"read": 1, "write": 1, "create": 1, "delete": 1, "report": 1, "export": 1, "print": 1, "email": 1, "share": 1}
EDIT = {"read": 1, "write": 1, "create": 1, "report": 1, "export": 1, "print": 1}
WRITE = {"read": 1, "write": 1, "report": 1, "export": 1, "print": 1}
READ = {"read": 1, "report": 1, "print": 1}
READ_EXPORT = {"read": 1, "report": 1, "export": 1, "print": 1}


def _entry(role, permissions, permlevel=0):
    return {"role": role, "permlevel": permlevel, **permissions}


def _manager_rows(permissions=FULL, permlevel=0):
    return [_entry(role, permissions, permlevel) for role in ("System Manager", "Manufacturing Manager", FACTORY_MANAGER)]


def _account_rows(permissions=READ_EXPORT, permlevel=0):
    return [_entry(role, permissions, permlevel) for role in ("Accounts Manager", FACTORY_ACCOUNTANT)]


DOC_PERMISSION_MATRIX = {
    "Factory Order": _manager_rows() + [
        _entry(FACTORY_SUPERVISOR, WRITE), _entry(FACTORY_PLANNER, EDIT),
        *_account_rows(), _entry("Stock Manager", READ),
        *[_entry(role, READ) for role in STAGE_ROLES], _entry(FACTORY_DELIVERY_USER, READ),
        *_manager_rows(WRITE, 1), *_account_rows(READ_EXPORT, 1),
    ],
    "Cutting Order": _manager_rows() + [
        _entry(FACTORY_SUPERVISOR, WRITE), _entry(FACTORY_PLANNER, EDIT),
        _entry("Stock Manager", WRITE), *_account_rows(),
        *[_entry(role, READ) for role in STAGE_ROLES],
        *_manager_rows(WRITE, 1), *_account_rows(READ_EXPORT, 1),
    ],
    "Factory Piece": _manager_rows() + [
        _entry(FACTORY_SUPERVISOR, WRITE), _entry(FACTORY_PLANNER, WRITE),
        *[_entry(role, READ) for role in STAGE_ROLES], _entry(FACTORY_DELIVERY_USER, READ),
        *_manager_rows(READ_EXPORT, 1), *_account_rows(READ_EXPORT, 1),
    ],
    "Piece Exception": _manager_rows() + [
        _entry(FACTORY_SUPERVISOR, EDIT), _entry(FACTORY_PLANNER, WRITE),
        _entry(FACTORY_QUALITY_INSPECTOR, EDIT),
        *[_entry(role, {"read": 1, "create": 1, "report": 1, "print": 1}) for role in STAGE_ROLES if role != FACTORY_QUALITY_INSPECTOR],
    ],
    "Board Layout": _manager_rows() + [
        _entry(FACTORY_SUPERVISOR, WRITE), _entry(FACTORY_PLANNER, EDIT),
        *[_entry(role, READ) for role in STAGE_ROLES],
    ],
    "Board Remnant": _manager_rows() + [
        _entry(FACTORY_SUPERVISOR, EDIT), _entry(FACTORY_PLANNER, EDIT),
        _entry(FACTORY_CUTTING_OPERATOR, READ), *_account_rows(),
        *_manager_rows(READ_EXPORT, 1), *_account_rows(READ_EXPORT, 1),
    ],
    "Factory Workstation": _manager_rows() + [
        _entry(FACTORY_SUPERVISOR, EDIT), _entry(FACTORY_PLANNER, EDIT),
        *[_entry(role, READ) for role in STAGE_ROLES], *_account_rows(),
        *_manager_rows(WRITE, 1), *_account_rows(READ_EXPORT, 1),
    ],
    "Factory Alert Log": _manager_rows() + [
        _entry(FACTORY_SUPERVISOR, WRITE), _entry(FACTORY_PLANNER, READ),
        *[_entry(role, READ) for role in STAGE_ROLES], _entry(FACTORY_DELIVERY_USER, READ),
    ],
    "Factory Alert Settings": _manager_rows(),
    "Factory Capacity Settings": _manager_rows() + [_entry(FACTORY_SUPERVISOR, WRITE), _entry(FACTORY_PLANNER, WRITE)],
    "Factory Accounting Settings": _manager_rows() + _account_rows(WRITE),
    "Factory Worker Cost Rate": _manager_rows() + _account_rows(EDIT),
    "Factory Cost Ledger": _manager_rows(READ_EXPORT) + _account_rows(READ_EXPORT),
    "Factory Piece Stage Cost": _manager_rows(READ_EXPORT) + _account_rows(READ_EXPORT),
    "Factory Order Event": _manager_rows(READ_EXPORT) + [
        _entry(FACTORY_SUPERVISOR, READ_EXPORT), _entry(FACTORY_PLANNER, READ_EXPORT),
        *[_entry(role, READ) for role in STAGE_ROLES], _entry(FACTORY_DELIVERY_USER, READ),
    ],
}

PAGE_ROLE_MATRIX = {
    "factory-worker": list(MANAGEMENT_ROLES | {FACTORY_SUPERVISOR} | STAGE_ROLES),
    "factory-scan": list(MANAGEMENT_ROLES | {FACTORY_SUPERVISOR} | STAGE_ROLES | {FACTORY_DELIVERY_USER}),
    "factory-control-center": list(MANAGEMENT_ROLES | {FACTORY_SUPERVISOR}),
    "factory-dashboard": list(MANAGEMENT_ROLES | {FACTORY_SUPERVISOR, FACTORY_PLANNER}),
    "factory-schedule": list(MANAGEMENT_ROLES | {FACTORY_SUPERVISOR, FACTORY_PLANNER}),
    "factory-capacity": list(MANAGEMENT_ROLES | {FACTORY_SUPERVISOR, FACTORY_PLANNER}),
    "factory-reports": list(MANAGEMENT_ROLES | ACCOUNTING_ROLES),
    "factory-performance": list(MANAGEMENT_ROLES | {FACTORY_SUPERVISOR, FACTORY_PLANNER} | ACCOUNTING_ROLES),
    "factory-issue-analysis": list(MANAGEMENT_ROLES | {FACTORY_SUPERVISOR, FACTORY_QUALITY_INSPECTOR}),
    "factory-order-timeline": list(MANAGEMENT_ROLES | {FACTORY_SUPERVISOR, FACTORY_PLANNER} | STAGE_ROLES | {FACTORY_DELIVERY_USER}),
}

REPORT_ROLE_MATRIX = {
    "Factory Order Profitability": list(MANAGEMENT_ROLES | ACCOUNTING_ROLES),
    "Factory Waste Analysis": list(MANAGEMENT_ROLES | {FACTORY_SUPERVISOR, FACTORY_PLANNER} | ACCOUNTING_ROLES),
    "Factory Production Performance": list(MANAGEMENT_ROLES | {FACTORY_SUPERVISOR, FACTORY_PLANNER} | ACCOUNTING_ROLES),
}


def ensure_factory_roles():
    for role_name in FACTORY_ROLES:
        if not frappe.db.exists("Role", role_name):
            role = frappe.new_doc("Role")
            role.role_name = role_name
            role.desk_access = 1
            role.insert(ignore_permissions=True)
    _ensure_role_profiles()
    _ensure_doc_permissions()
    _ensure_page_roles()
    _ensure_report_roles()
    frappe.clear_cache()


def _ensure_role_profiles():
    if not frappe.db.exists("DocType", "Role Profile"):
        return
    for profile_name, roles in ROLE_PROFILES.items():
        if frappe.db.exists("Role Profile", profile_name):
            profile = frappe.get_doc("Role Profile", profile_name)
            existing = {row.role for row in profile.roles}
            changed = False
            for role in roles:
                if role not in existing:
                    profile.append("roles", {"role": role})
                    changed = True
            if changed:
                profile.save(ignore_permissions=True)
            continue
        profile = frappe.new_doc("Role Profile")
        profile.role_profile = profile_name
        for role in roles:
            profile.append("roles", {"role": role})
        profile.insert(ignore_permissions=True)


def _ensure_doc_permissions():
    if not frappe.db.exists("DocType", "Custom DocPerm"):
        return
    managed_roles = set(FACTORY_ROLES) | {"System Manager", "Manufacturing Manager", "Accounts Manager", "Stock Manager"}
    for doctype, rows in DOC_PERMISSION_MATRIX.items():
        if not frappe.db.exists("DocType", doctype):
            continue
        existing = frappe.get_all("Custom DocPerm", filters={"parent": doctype, "role": ["in", list(managed_roles)]}, pluck="name", limit_page_length=0)
        for name in existing:
            frappe.delete_doc("Custom DocPerm", name, ignore_permissions=True, force=True)
        for values in rows:
            permission = frappe.new_doc("Custom DocPerm")
            permission.parent = doctype
            permission.parenttype = "DocType"
            permission.parentfield = "permissions"
            for key, value in values.items():
                permission.set(key, value)
            permission.insert(ignore_permissions=True)
        frappe.clear_cache(doctype=doctype)


def _ensure_page_roles():
    for page_name, roles in PAGE_ROLE_MATRIX.items():
        if not frappe.db.exists("Page", page_name):
            continue
        page = frappe.get_doc("Page", page_name)
        page.set("roles", [])
        for role in sorted(set(roles)):
            page.append("roles", {"role": role})
        page.flags.ignore_validate = True
        page.save(ignore_permissions=True)


def _ensure_report_roles():
    for report_name, roles in REPORT_ROLE_MATRIX.items():
        if not frappe.db.exists("Report", report_name):
            continue
        report = frappe.get_doc("Report", report_name)
        report.set("roles", [])
        for role in sorted(set(roles)):
            report.append("roles", {"role": role})
        report.flags.ignore_validate = True
        report.save(ignore_permissions=True)
