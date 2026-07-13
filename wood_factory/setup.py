import frappe

from wood_factory.security import (
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


def ensure_factory_roles():
    for role_name in FACTORY_ROLES:
        if not frappe.db.exists("Role", role_name):
            role = frappe.new_doc("Role")
            role.role_name = role_name
            role.desk_access = 1
            role.insert(ignore_permissions=True)
    _ensure_role_profiles()
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
