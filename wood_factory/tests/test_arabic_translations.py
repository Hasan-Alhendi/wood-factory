import csv
import re
import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
TRANSLATION_FILE = APP_ROOT / "translations" / "ar.csv"
JS_ROOT = APP_ROOT / "wood_factory"
ARABIC_RE = re.compile(r"[\u0600-\u06FF]")
PLACEHOLDER_RE = re.compile(r"(?:\{\d+\}|%\([^)]+\)[sd]|%[sd])")
TEMPLATE_TRANSLATION_RE = re.compile(r"__\(\s*`")

CORE_TERMS = {
    "Wood Factory",
    "Factory Order",
    "Cutting Order",
    "Board Layout",
    "Factory Piece",
    "Piece Exception",
    "Board Remnant",
    "Factory Workstation",
    "Factory Control Center",
    "Factory Reports",
    "Factory Demo Data",
    "Translation Audit",
    "Cutting",
    "Edge Banding",
    "Drilling",
    "Assembly",
    "Quality Inspection",
    "Packing",
    "Ready for Production",
    "In Production",
    "Ready for Delivery",
    "Delivered",
    "Replacement Required",
    "Replacement In Production",
    "Replacement Completed",
    "Customer Material Consumption",
    "Internal Replacement Material",
    "Remnant Material Consumption",
    "Remnant Recovery",
    "Waste Cost",
    "Customer Billable",
    "Customer-Attributable Actual Cost",
    "Factory Error / Rework Cost",
    "Total Actual Cost",
    "Optimize Board Layout",
    "Approve & Consume Materials",
    "Find Best Remnant",
    "Create Factory-Funded Cutting Order",
    "Mark Ready for Delivery",
    "Confirm Delivered",
    "Production Bottlenecks",
    "Production Recommendations",
    "What-if Production Simulation",
}

EXPECTED_GLOSSARY = {
    "Factory Order": "أمر تشغيل المعمل",
    "Cutting Order": "أمر القص",
    "Board Layout": "مخطط اللوح",
    "Board Remnant": "فضلة لوح",
    "Edge Banding": "القشاط",
    "Drilling": "التخريم",
    "Quality Inspection": "فحص الجودة",
    "Rework": "إعادة العمل",
    "Factory Error / Rework Cost": "تكلفة خطأ المعمل وإعادة العمل",
}


def load_rows():
    with TRANSLATION_FILE.open(encoding="utf-8", newline="") as handle:
        return list(csv.reader(handle))


class TestArabicTranslations(unittest.TestCase):
    def test_translation_file_exists_and_is_not_small(self):
        self.assertTrue(TRANSLATION_FILE.exists())
        self.assertGreaterEqual(len(load_rows()), 650)

    def test_every_row_has_source_and_arabic_translation(self):
        for line_number, row in enumerate(load_rows(), start=1):
            self.assertGreaterEqual(len(row), 2, f"Invalid CSV row {line_number}")
            source, translation = row[0].strip(), row[1].strip()
            self.assertTrue(source, f"Missing source on row {line_number}")
            self.assertTrue(translation, f"Missing Arabic translation for {source}")
            self.assertRegex(translation, ARABIC_RE, f"Translation is not Arabic: {source}")

    def test_sources_are_unique(self):
        sources = [row[0].strip() for row in load_rows()]
        duplicates = sorted({source for source in sources if sources.count(source) > 1})
        self.assertEqual(duplicates, [])

    def test_core_factory_terms_are_covered(self):
        translations = {row[0].strip(): row[1].strip() for row in load_rows()}
        self.assertEqual(sorted(CORE_TERMS - translations.keys()), [])

    def test_approved_glossary_is_stable(self):
        translations = {row[0].strip(): row[1].strip() for row in load_rows()}
        for source, expected in EXPECTED_GLOSSARY.items():
            self.assertEqual(translations.get(source), expected)

    def test_format_placeholders_are_preserved(self):
        for row in load_rows():
            source, translation = row[0], row[1]
            self.assertEqual(
                sorted(PLACEHOLDER_RE.findall(source)),
                sorted(PLACEHOLDER_RE.findall(translation)),
                f"Placeholder mismatch for {source}",
            )

    def test_open_status_is_not_used_as_open_action(self):
        translations = {row[0].strip(): row[1].strip() for row in load_rows()}
        self.assertEqual(translations.get("Open"), "مفتوح")
        self.assertEqual(translations.get("Open Page"), "فتح الصفحة")

    def test_js_translation_calls_do_not_use_template_literals(self):
        offenders = []
        for path in JS_ROOT.rglob("*.js"):
            content = path.read_text(encoding="utf-8")
            if TEMPLATE_TRANSLATION_RE.search(content):
                offenders.append(str(path.relative_to(APP_ROOT)))
        self.assertEqual(offenders, [], "Use literal strings with {0} placeholders in __() calls")


if __name__ == "__main__":
    unittest.main()
