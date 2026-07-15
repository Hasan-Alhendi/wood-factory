(() => {
	"use strict";

	if (window.woodFactoryUX?.installed) {
		return;
	}

	const GRID_SELECTOR = ".form-grid";
	const ROW_SELECTOR = ".grid-body .rows > .grid-row";
	const CELL_SELECTOR = ".data-row > .grid-static-col[data-fieldname]";
	const CONTROL_SELECTOR = [
		'input:not([type="hidden"]):not([disabled]):not([readonly])',
		"select:not([disabled])",
		"textarea:not([disabled]):not([readonly])",
		'[contenteditable="true"]',
	].join(", ");
	const NON_EDITABLE_FIELD_TYPES = new Set([
		"Button",
		"Column Break",
		"Fold",
		"HTML",
		"Image",
		"Section Break",
		"Table",
	]);

	function isVisible(element) {
		if (!element) {
			return false;
		}
		const style = window.getComputedStyle(element);
		return (
			style.display !== "none" &&
			style.visibility !== "hidden" &&
			(element.offsetWidth > 0 || element.offsetHeight > 0 || element.getClientRects().length > 0)
		);
	}

	function isArabicInterface() {
		const language = String(window.frappe?.boot?.lang || "").toLowerCase();
		return document.documentElement.dir === "rtl" || language === "ar" || language.startsWith("ar-");
	}

	function gridRowModel(row) {
		return window.jQuery ? window.jQuery(row).data("grid_row") : null;
	}

	function fieldDefinition(row, fieldname) {
		return gridRowModel(row)?.columns?.[fieldname]?.df || null;
	}

	function isEditableCell(row, cell) {
		if (!cell || cell.classList.contains("search") || !isVisible(cell)) {
			return false;
		}
		const definition = fieldDefinition(row, cell.dataset.fieldname);
		if (!definition) {
			return Boolean(cell.querySelector(CONTROL_SELECTOR));
		}
		return !(
			definition.hidden ||
			definition.read_only ||
			NON_EDITABLE_FIELD_TYPES.has(definition.fieldtype)
		);
	}

	function editableCells(row) {
		return Array.from(row.querySelectorAll(CELL_SELECTOR)).filter((cell) => isEditableCell(row, cell));
	}

	function gridRows(grid) {
		return Array.from(grid.querySelectorAll(ROW_SELECTOR)).filter(
			(row) => !row.classList.contains("grid-heading-row") && row.querySelector(".data-row")
		);
	}

	function controlInCell(cell) {
		return Array.from(cell?.querySelectorAll(CONTROL_SELECTOR) || []).find(isVisible) || null;
	}

	function selectControlValue(control) {
		if (
			control instanceof HTMLInputElement &&
			!["button", "checkbox", "color", "file", "radio", "range", "submit"].includes(control.type)
		) {
			control.select();
		}
	}

	function focusCell(cell) {
		if (!cell) {
			return false;
		}

		const focus = () => {
			const control = controlInCell(cell);
			if (!control) {
				return false;
			}
			control.focus({preventScroll: true});
			control.scrollIntoView({block: "nearest", inline: "nearest"});
			selectControlValue(control);
			return true;
		};

		if (focus()) {
			return true;
		}

		cell.dispatchEvent(new MouseEvent("click", {bubbles: true, cancelable: true, view: window}));
		window.setTimeout(focus, 30);
		return true;
	}

	function autocompleteIsOpen(control) {
		if (control.getAttribute("aria-expanded") === "true") {
			return true;
		}
		const awesomplete = control.closest(".awesomplete");
		return Boolean(awesomplete?.querySelector("ul:not([hidden]) li"));
	}

	function canAddRow(row) {
		const grid = gridRowModel(row)?.grid;
		return Boolean(
			grid &&
			typeof grid.add_new_row === "function" &&
			(!grid.is_editable || grid.is_editable()) &&
			(!grid.allow_on_grid_editing || grid.allow_on_grid_editing())
		);
	}

	function addRowAndFocus(row, fieldname, fallbackToFirst) {
		const gridModel = gridRowModel(row)?.grid;
		if (!gridModel || !canAddRow(row)) {
			return false;
		}
		gridModel.add_new_row();
		window.setTimeout(() => {
			const grid = row.closest(GRID_SELECTOR);
			const rows = gridRows(grid);
			const newRow = rows.at(-1);
			const sameField = newRow?.querySelector(
				`.data-row > .grid-static-col[data-fieldname="${CSS.escape(fieldname)}"]`
			);
			const target =
				(sameField && isEditableCell(newRow, sameField) ? sameField : null) ||
				(fallbackToFirst ? editableCells(newRow)[0] : null);
			focusCell(target);
		}, 80);
		return true;
	}

	function moveVertically(row, cell) {
		const grid = row.closest(GRID_SELECTOR);
		const rows = gridRows(grid);
		const rowIndex = rows.indexOf(row);
		const fieldname = cell.dataset.fieldname;
		const nextRow = rows[rowIndex + 1];

		if (nextRow) {
			const sameField = nextRow.querySelector(
				`.data-row > .grid-static-col[data-fieldname="${CSS.escape(fieldname)}"]`
			);
			const target =
				(sameField && isEditableCell(nextRow, sameField) ? sameField : null) || editableCells(nextRow)[0];
			return focusCell(target);
		}

		return addRowAndFocus(row, fieldname, true);
	}

	function moveHorizontally(row, cell, backwards) {
		const grid = row.closest(GRID_SELECTOR);
		const rows = gridRows(grid);
		const rowIndex = rows.indexOf(row);
		const cells = editableCells(row);
		const cellIndex = cells.indexOf(cell);
		const nextCell = cells[cellIndex + (backwards ? -1 : 1)];

		if (nextCell) {
			return focusCell(nextCell);
		}

		const adjacentRow = rows[rowIndex + (backwards ? -1 : 1)];
		if (adjacentRow) {
			const adjacentCells = editableCells(adjacentRow);
			return focusCell(backwards ? adjacentCells.at(-1) : adjacentCells[0]);
		}

		if (!backwards) {
			return addRowAndFocus(row, cells[0]?.dataset.fieldname || cell.dataset.fieldname, true);
		}

		return false;
	}

	function commitCurrentControl(control) {
		control.dispatchEvent(new Event("change", {bubbles: true}));
		control.blur();
	}

	function handleGridNavigation(event) {
		if (event.defaultPrevented || event.isComposing || event.ctrlKey || event.metaKey || event.altKey) {
			return;
		}
		if (event.key !== "Enter" && event.key !== "Tab") {
			return;
		}

		const control = event.target.closest?.(CONTROL_SELECTOR);
		const row = control?.closest(".form-grid .grid-body .rows > .grid-row");
		const cell = control?.closest(".data-row > .grid-static-col[data-fieldname]");
		if (!control || !row || !cell || row.classList.contains("grid-row-open")) {
			return;
		}
		if (event.key === "Enter" && (control.matches("textarea, [contenteditable='true']") || autocompleteIsOpen(control))) {
			return;
		}

		const moved =
			event.key === "Enter"
				? moveVertically(row, cell)
				: moveHorizontally(row, cell, event.shiftKey);

		if (!moved) {
			return;
		}

		event.preventDefault();
		event.stopPropagation();
		commitCurrentControl(control);
	}

	function addKeyboardHints() {
		document.querySelectorAll(".grid-field").forEach((gridField) => {
			if (!gridField.querySelector(GRID_SELECTOR) || gridField.querySelector(":scope > .factory-grid-keyboard-hint")) {
				return;
			}
			const hint = document.createElement("div");
			hint.className = "factory-grid-keyboard-hint";
			hint.setAttribute("role", "note");
			hint.setAttribute("aria-label", window.__("Spreadsheet navigation"));
			hint.textContent = window.__("Enter: next row · Tab: next cell · Shift+Tab: previous cell");
			const container = gridField.querySelector(".form-grid-container");
			gridField.insertBefore(hint, container);
		});
	}

	let enhancementPending = false;
	function scheduleEnhancement() {
		if (enhancementPending) {
			return;
		}
		enhancementPending = true;
		window.requestAnimationFrame(() => {
			enhancementPending = false;
			document.body?.classList.add("wood-factory-ux");
			document.body?.classList.toggle("wood-factory-rtl", isArabicInterface());
			addKeyboardHints();
		});
	}

	window.woodFactoryUX = {
		installed: true,
		enhance: scheduleEnhancement,
	};

	document.addEventListener("keydown", handleGridNavigation, true);
	window.addEventListener("DOMContentLoaded", scheduleEnhancement, {once: true});

	const observer = new MutationObserver(scheduleEnhancement);
	if (document.body) {
		observer.observe(document.body, {childList: true, subtree: true});
	} else {
		window.addEventListener(
			"DOMContentLoaded",
			() => observer.observe(document.body, {childList: true, subtree: true}),
			{once: true}
		);
	}

	if (window.frappe?.router?.on) {
		window.frappe.router.on("change", scheduleEnhancement);
	}
	scheduleEnhancement();
})();
