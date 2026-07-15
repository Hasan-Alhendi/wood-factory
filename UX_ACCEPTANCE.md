# Factory UI/UX Acceptance

Stage 49 treats the factory interface as an operational workstation, not a collection of generic ERP forms.

## Direction and language

- Arabic Desk pages, forms, lists, dialogs, reports, custom pages and editable child tables render right-to-left.
- Labels and natural-language values align to the right.
- Document IDs, item codes, QR values, dimensions, money, percentages and durations remain visually stable in left-to-right numeric order.
- English keeps the native left-to-right layout.

## Spreadsheet keyboard entry

Editable child tables support a consistent spreadsheet workflow:

- `Enter` commits the current value and moves to the same field in the next row.
- On the final row, `Enter` creates a new row when the grid is editable and focuses the same field.
- `Tab` moves to the next editable cell in the current visual row.
- `Shift+Tab` moves to the previous editable cell.
- `Tab` at the end of a row continues at the first editable cell of the next row.
- Multi-line text keeps normal `Enter` behavior.
- Link autocomplete keeps `Enter` while a suggestion list is open.
- IME composition, modifier shortcuts and read-only fields are not intercepted.

## Input ergonomics

- Form controls use larger click targets and a clear focus ring.
- Read-only values are visibly different from editable inputs.
- Editable grid rows have comfortable height, row hover and active-row feedback.
- Checkboxes remain easy to target.
- A short keyboard hint appears above editable tables on desktop and is hidden on narrow mobile screens.

## Manual browser acceptance

Validate in both Arabic and English using current Chrome or Edge:

1. Open a new Cutting Order and add at least five parts.
2. Enter part name, width, height and quantity using only the keyboard.
3. Verify `Enter` moves vertically and creates the next row at the bottom.
4. Verify `Tab` and `Shift+Tab` move horizontally without skipping editable cells.
5. Verify Enter still selects an open Link suggestion.
6. Verify Enter creates a new line in Notes instead of leaving the field.
7. Open Factory Order, Piece Exception, Board Remnant and Factory Piece forms.
8. Open factory lists, query reports and every custom operational page.
9. Open confirmation dialogs and dropdown menus.
10. Confirm there is no clipped text, reversed number, hidden action, inaccessible horizontal scroll or misplaced modal close button.
11. Repeat the critical cutting-order flow at 1366×768, 1920×1080 and a mobile-width viewport.

Stage 49 is complete only after these checks pass on the staging site with no browser console errors.
