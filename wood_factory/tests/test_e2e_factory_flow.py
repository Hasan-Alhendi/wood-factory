import unittest

import frappe

from wood_factory import demo_data
from wood_factory.e2e import EXPECTED_SCENARIOS, run_factory_acceptance, validate_factory_acceptance


class TestFactoryEndToEndFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.previous_user = frappe.session.user
        frappe.set_user("Administrator")
        cls.company = demo_data._resolve_company()

    @classmethod
    def tearDownClass(cls):
        frappe.set_user(cls.previous_user)

    def setUp(self):
        self.savepoint = "wood_factory_e2e_test"
        frappe.db.savepoint(self.savepoint)

    def tearDown(self):
        frappe.db.rollback(save_point=self.savepoint)

    def test_complete_demo_acceptance_suite(self):
        result = run_factory_acceptance(
            company=self.company,
            include_users=0,
            include_stock=0,
        )
        validation = result["validation"]
        failed = [row["name"] for row in validation["checks"] if row["critical"] and not row["passed"]]

        self.assertTrue(result["passed"], failed)
        self.assertEqual(validation["critical_failed"], 0, failed)
        self.assertTrue(validation["ready_for_runtime_testing"])

    def test_demo_generation_is_idempotent(self):
        first = run_factory_acceptance(company=self.company, include_users=0, include_stock=0)
        first_scenarios = self._scenario_documents(first)
        first_counts = first["dataset"]["counts"].copy()

        second = run_factory_acceptance(company=self.company, include_users=0, include_stock=0)
        second_scenarios = self._scenario_documents(second)
        second_counts = second["dataset"]["counts"].copy()

        self.assertEqual(set(first_scenarios), EXPECTED_SCENARIOS)
        self.assertEqual(first_scenarios, second_scenarios)
        for key in ("factory_orders", "piece_exceptions", "remnants", "alerts"):
            self.assertEqual(first_counts.get(key), second_counts.get(key), key)

    def test_validator_is_read_only(self):
        generated = run_factory_acceptance(company=self.company, include_users=0, include_stock=0)
        before = self._scenario_documents(generated)

        validation = validate_factory_acceptance(company=self.company)
        after = self._scenario_documents({"dataset": {"scenarios": self._status_scenarios()}})

        self.assertEqual(validation["critical_failed"], 0)
        self.assertEqual(before, after)

    def _status_scenarios(self):
        context = demo_data._company_context(self.company)
        from wood_factory import demo_dataset

        return demo_dataset._status(context)["scenarios"]

    @staticmethod
    def _scenario_documents(result):
        rows = result["dataset"]["scenarios"]
        return {
            row["code"]: (row.get("sales_order"), row.get("factory_order"), row.get("status"))
            for row in rows
        }


if __name__ == "__main__":
    unittest.main()
