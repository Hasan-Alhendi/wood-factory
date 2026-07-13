import csv
import json
import re
from pathlib import Path

import frappe

from wood_factory.security import require_management


APP_ROOT = Path(__file__).resolve().parent
TRANSLATION_FILE = APP_ROOT / "translations" / "ar.csv"
JS_TRANSLATION_RE = re.compile(r"__\(\s*([\"'])(.*?)\1", re.DOTALL)
PY_TRANSLATION_RE = re.compile(r"(?<![A-Za-z0-9_])_\(\s*([\"'])(.*?)\1", re.DOTALL)

# Values that are technical, dynamic, or translated by Frappe itself rather than by
# this application's terminology file.
IGNORED_SOURCES = {
    "",
    "Administrator",
    "Company",
    "Customer",
    "Currency",
    "Date",
    "Datetime",
    "DocType",
    "Item",
    "Link",
    "Project",
    "Small Text",
    "Stock Entry",
    "System Manager",
    "User",
    "Warehouse",
}


@frappe.whitelist()
def audit_arabic_translations(limit=250):
    """Return user-facing source strings that lack an app Arabic translation.

    This is a static audit of DocType labels/options and literal translation calls.
    It does not mutate data and is restricted to factory management roles.
    """
    require_management()
    translations = load_arabic_translations()
    sources = collect_user_facing_sources()
    missing = sorted(source for source in sources if source not in translations and source not in IGNORED_SOURCES)
    return {
        "translation_file": str(TRANSLATION_FILE.relative_to(APP_ROOT.parent)),
        "source_count": len(sources),
        "app_translation_count": len(translations),
        "covered_source_count": len(sources - set(missing)),
        "missing_count": len(missing),
        "missing": missing[: int(limit or 250)],
        "truncated": len(missing) > int(limit or 250),
    }


def load_arabic_translations():
    if not TRANSLATION_FILE.exists():
        return {}
    result = {}
    with TRANSLATION_FILE.open(encoding="utf-8", newline="") as handle:
        for row in csv.reader(handle):
            if len(row) < 2:
                continue
            source, translation = row[0].strip(), row[1].strip()
            if source and translation:
                result[source] = translation
    return result


def collect_user_facing_sources():
    sources = set()
    module_root = APP_ROOT / "wood_factory"
    if not module_root.exists():
        return sources

    for path in module_root.rglob("*.json"):
        _collect_json_sources(path, sources)
    for path in module_root.rglob("*.js"):
        _collect_literal_sources(path, JS_TRANSLATION_RE, sources)
    for path in module_root.rglob("*.py"):
        _collect_literal_sources(path, PY_TRANSLATION_RE, sources)
    return {source.strip() for source in sources if _is_user_facing(source)}


def _collect_json_sources(path, sources):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return

    def visit(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in {"label", "title", "description"} and isinstance(item, str):
                    sources.add(item)
                elif key == "options" and isinstance(item, str) and "\n" in item:
                    sources.update(option.strip() for option in item.splitlines())
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(data)


def _collect_literal_sources(path, pattern, sources):
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return
    for match in pattern.finditer(content):
        literal = match.group(2)
        if "${" not in literal and "\\n" not in literal:
            sources.add(literal)


def _is_user_facing(source):
    if not source or source in IGNORED_SOURCES:
        return False
    if source.startswith(("wood_factory.", "/app/", "WF:")):
        return False
    if re.fullmatch(r"[a-z0-9_./:-]+", source):
        return False
    return bool(re.search(r"[A-Za-z]", source))
