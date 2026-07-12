import frappe
from frappe.model.document import Document


class FactoryAccountingSettings(Document):
    def validate(self):
        if not self.enabled:
            return
        self._validate_cost_center(self.customer_cost_center, "Customer Order Cost Center")
        self._validate_cost_center(self.internal_rework_cost_center, "Internal Rework Cost Center")
        self._validate_expense_account(self.material_expense_account, "Material Consumption Expense Account")
        self._validate_expense_account(self.internal_rework_expense_account, "Internal Rework Expense Account")
        if self.require_cost_center and not self.customer_cost_center:
            frappe.throw("Customer Order Cost Center is required when accounting integration is enabled")
        if self.require_cost_center and not self.internal_rework_cost_center:
            frappe.throw("Internal Rework Cost Center is required when accounting integration is enabled")
        if not self.material_expense_account:
            frappe.throw("Material Consumption Expense Account is required when accounting integration is enabled")
        if not self.internal_rework_expense_account:
            frappe.throw("Internal Rework Expense Account is required when accounting integration is enabled")

    def _validate_cost_center(self, name, label):
        if not name:
            return
        company = frappe.db.get_value("Cost Center", name, "company")
        if company and company != self.company:
            frappe.throw(f"{label} belongs to {company}, not {self.company}")

    def _validate_expense_account(self, name, label):
        if not name:
            return
        account = frappe.db.get_value("Account", name, ["company", "root_type", "is_group"], as_dict=True)
        if not account:
            frappe.throw(f"{label} does not exist")
        if account.company and account.company != self.company:
            frappe.throw(f"{label} belongs to {account.company}, not {self.company}")
        if account.is_group:
            frappe.throw(f"{label} cannot be a group account")
        if account.root_type and account.root_type != "Expense":
            frappe.throw(f"{label} must be an Expense account")
