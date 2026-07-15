import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
HOOKS = APP_ROOT / "hooks.py"
CSS = APP_ROOT / "public" / "css" / "wood_factory_rtl.css"
JS = APP_ROOT / "public" / "js" / "wood_factory_ux.js"
TRANSLATIONS = APP_ROOT / "translations" / "ar.csv"


class TestFactoryUIUXAssets(unittest.TestCase):
	def test_global_ux_assets_are_registered(self):
		hooks = HOOKS.read_text(encoding="utf-8")
		self.assertIn("/assets/wood_factory/css/wood_factory_rtl.css", hooks)
		self.assertIn("/assets/wood_factory/js/wood_factory_ux.js", hooks)

	def test_rtl_covers_forms_grids_lists_reports_and_dialogs(self):
		css = CSS.read_text(encoding="utf-8")
		for selector in (
			'html[dir="rtl"] .form-layout',
			'html[dir="rtl"] .form-grid',
			'html[dir="rtl"] .list-row',
			'html[dir="rtl"] .report-wrapper',
			'html[dir="rtl"] .modal-content',
		):
			self.assertIn(selector, css)
		self.assertIn(".factory-grid-keyboard-hint", css)

	def test_spreadsheet_navigation_contract_is_present(self):
		javascript = JS.read_text(encoding="utf-8")
		for token in (
			'event.key !== "Enter" && event.key !== "Tab"',
			"moveVertically",
			"moveHorizontally",
			"grid.add_new_row",
			"event.isComposing",
			"autocompleteIsOpen",
			"textarea",
			"Shift+Tab",
		):
			self.assertIn(token, javascript)

	def test_keyboard_help_is_translated(self):
		translations = TRANSLATIONS.read_text(encoding="utf-8")
		self.assertIn("Spreadsheet navigation,التنقل كجداول البيانات", translations)
		self.assertIn(
			"Enter: next row · Tab: next cell · Shift+Tab: previous cell,"
			"Enter: الصف التالي · Tab: الخلية المجاورة · Shift+Tab: الخلية السابقة",
			translations,
		)


if __name__ == "__main__":
	unittest.main()
