import unittest

from wood_factory import demo_data


class TestFactoryDemoDataBlueprint(unittest.TestCase):
    def test_scenario_codes_are_unique(self):
        codes = [row["code"] for row in demo_data.SCENARIOS]
        self.assertEqual(len(codes), len(set(codes)))
        self.assertEqual(len(codes), 6)

    def test_required_operational_scenarios_exist(self):
        by_code = {row["code"]: row for row in demo_data.SCENARIOS}
        self.assertEqual(by_code["NORMAL-CUTTING"]["current_stage"], "Cutting")
        self.assertEqual(by_code["DELAYED-BLOCKED"]["stage_status"], "Blocked")
        self.assertLess(by_code["DELAYED-BLOCKED"]["delivery_offset"], 0)
        self.assertEqual(by_code["DAMAGED-REMNANT"]["exception_mode"], "remnant")
        self.assertEqual(by_code["WRONG-DIM-NEW-BOARD"]["exception_mode"], "new_board")
        self.assertTrue(by_code["READY-DELIVERY"]["ready_for_delivery"])
        self.assertTrue(by_code["DELIVERED"]["delivered"])

    def test_every_production_stage_has_a_demo_worker_and_workstation(self):
        worker_stages = set(demo_data.ROLE_USERS) & set(demo_data.STAGES)
        workstation_stages = {row[1] for row in demo_data.WORKSTATIONS}
        self.assertEqual(worker_stages, set(demo_data.STAGES))
        self.assertEqual(workstation_stages, set(demo_data.STAGES))

    def test_demo_items_cover_exact_material_matching(self):
        boards = {row["board"] for row in demo_data.SCENARIOS}
        self.assertEqual(boards, {"white_board", "oak_board"})


if __name__ == "__main__":
    unittest.main()
