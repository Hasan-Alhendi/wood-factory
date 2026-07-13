import unittest
from unittest.mock import patch

import frappe

from wood_factory import security


class TestFactorySecurityPolicy(unittest.TestCase):
    def roles(self, *roles):
        return patch("wood_factory.security.get_user_roles", return_value=set(roles))

    def test_cutting_operator_cannot_access_other_stage(self):
        with self.roles(security.FACTORY_CUTTING_OPERATOR):
            self.assertTrue(security.stage_accessible_to_user("Cutting"))
            self.assertFalse(security.stage_accessible_to_user("Edge Banding"))
            self.assertFalse(security.can_view_financials())

    def test_supervisor_can_access_all_production_stages(self):
        with self.roles(security.FACTORY_SUPERVISOR):
            for stage in security.STAGE_ROLE_MAP:
                self.assertTrue(security.stage_accessible_to_user(stage))

    def test_accountant_sees_financials_but_not_stage_operations(self):
        with self.roles(security.FACTORY_ACCOUNTANT):
            self.assertTrue(security.can_view_financials())
            self.assertFalse(security.stage_accessible_to_user("Cutting"))
            self.assertFalse(security.stage_accessible_to_user("Packing"))

    def test_factory_order_permission_is_stage_scoped(self):
        cutting_order = frappe._dict(current_stage="Cutting", status="In Production")
        edging_order = frappe._dict(current_stage="Edge Banding", status="In Production")
        with self.roles(security.FACTORY_CUTTING_OPERATOR):
            self.assertTrue(security.factory_order_permission(cutting_order))
            self.assertFalse(security.factory_order_permission(edging_order))

    def test_delivery_user_only_sees_delivery_orders(self):
        in_production = frappe._dict(current_stage="Packing", status="In Production")
        ready = frappe._dict(current_stage=None, status="Ready for Delivery")
        delivered = frappe._dict(current_stage=None, status="Delivered")
        with self.roles(security.FACTORY_DELIVERY_USER):
            self.assertFalse(security.factory_order_permission(in_production))
            self.assertTrue(security.factory_order_permission(ready))
            self.assertTrue(security.factory_order_permission(delivered))

    def test_piece_visibility_follows_stage(self):
        cutting_piece = frappe._dict(current_stage="Cutting", status="Ready")
        quality_piece = frappe._dict(current_stage="Quality Inspection", status="Ready")
        with self.roles(security.FACTORY_QUALITY_INSPECTOR):
            self.assertFalse(security.factory_piece_permission(cutting_piece))
            self.assertTrue(security.factory_piece_permission(quality_piece))

    def test_alert_is_visible_only_to_assignee_or_supervisor(self):
        alert = frappe._dict(responsible="worker@example.com", escalated_to="manager@example.com")
        with self.roles(security.FACTORY_CUTTING_OPERATOR):
            self.assertTrue(security.factory_alert_permission(alert, user="worker@example.com"))
            self.assertFalse(security.factory_alert_permission(alert, user="other@example.com"))
        with self.roles(security.FACTORY_SUPERVISOR):
            self.assertTrue(security.factory_alert_permission(alert, user="supervisor@example.com"))

    def test_planner_can_plan_without_financial_access(self):
        with self.roles(security.FACTORY_PLANNER):
            self.assertTrue(security.has_any_role(security.PLANNING_ROLES))
            self.assertFalse(security.can_view_financials())


if __name__ == "__main__":
    unittest.main()
