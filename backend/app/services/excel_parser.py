from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from io import BytesIO

from openpyxl import load_workbook

WEEKDAYS = {"MONDAY": "Monday", "TUESDAY": "Tuesday", "WEDNESDAY": "Wednesday", "THURSDAY": "Thursday", "FRIDAY": "Friday", "SATURDAY": "Saturday", "SUNDAY": "Sunday"}
COURSE_RE = re.compile(r"(?<![A-Z0-9])([A-Z]{3}\d{3})", re.IGNORECASE)
TIME_RE = re.compile(r"^\s*(\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2})")
TYPE_RE = re.compile(r"(?:^|\s|-)\s*([LTP])\s*(?:-|$)", re.IGNORECASE)
TYPE_WORDS = {"LECTURE": "L", "TUTORIAL": "T", "PRACTICAL": "P"}


@dataclass(frozen=True)
class ParsedTimetableSlot:
    day_of_week: str
    time_slot: str
    course_code: str
    class_type: str
    attendance_units: int = 1

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def parse_timetable(file_bytes: bytes) -> list[ParsedTimetableSlot]:
    """Parse a timetable grid, counting vertically merged periods as multiple units."""
    workbook = load_workbook(BytesIO(file_bytes), data_only=True, read_only=False)
    slots: list[ParsedTimetableSlot] = []
    for sheet in workbook.worksheets:
        header_row = None
        day_columns: dict[int, str] = {}
        for row in sheet.iter_rows():
            found = {cell.column: WEEKDAYS[str(cell.value).strip().upper()] for cell in row if cell.value is not None and str(cell.value).strip().upper() in WEEKDAYS}
            if len(found) >= 5:
                header_row, day_columns = row[0].row, found
                break
        merge_height: dict[tuple[int, int], int] = {}
        merge_width: dict[tuple[int, int], int] = {}
        for cell_range in sheet.merged_cells.ranges:
            if cell_range.max_row > cell_range.min_row and cell_range.max_col == cell_range.min_col:
                merge_height[(cell_range.min_row, cell_range.min_col)] = cell_range.max_row - cell_range.min_row + 1
            if cell_range.max_col > cell_range.min_col and cell_range.max_row == cell_range.min_row:
                merge_width[(cell_range.min_row, cell_range.min_col)] = cell_range.max_col - cell_range.min_col + 1

        def add_cell(row_number: int, column: int, weekday: str, units: int, header_value: object = None) -> None:
            value = sheet.cell(row=row_number, column=column).value
            if not isinstance(value, str) or not value.strip():
                return
            normalized = value.strip()
            if re.search(r"\b(lunch|break)\b", normalized, re.IGNORECASE):
                return
            code_match = COURSE_RE.search(normalized)
            type_match = TYPE_RE.search(normalized)
            full_type_match = next((kind for word, kind in TYPE_WORDS.items() if re.search(rf"\b{word}\b", normalized, re.IGNORECASE)), None)
            if not code_match or (not type_match and not full_type_match):
                return
            time_match = TIME_RE.search(normalized)
            if not time_match and isinstance(header_value, str):
                time_match = TIME_RE.search(header_value.strip())
            time_slot = time_match.group(1).replace(" ", "") if time_match else "Unspecified"
            class_type = type_match.group(1).upper() if type_match else full_type_match
            slots.append(ParsedTimetableSlot(weekday, time_slot, code_match.group(1).upper(), class_type, units))

        if header_row is not None:
            for column, weekday in day_columns.items():
                for row_number in range(header_row + 1, sheet.max_row + 1):
                    add_cell(row_number, column, weekday, merge_height.get((row_number, column), 1))
            continue

        # Also accept the common transposed format with weekdays listed down a column.
        day_rows: dict[int, tuple[int, str]] = {}
        for column in range(1, sheet.max_column + 1):
            found_rows = {
                row: WEEKDAYS[str(sheet.cell(row=row, column=column).value).strip().upper()]
                for row in range(1, sheet.max_row + 1)
                if sheet.cell(row=row, column=column).value is not None
                and str(sheet.cell(row=row, column=column).value).strip().upper() in WEEKDAYS
            }
            if len(found_rows) >= 5:
                day_rows = {row: (column, weekday) for row, weekday in found_rows.items()}
                break
        for row_number, (day_column, weekday) in day_rows.items():
            for column in range(day_column + 1, sheet.max_column + 1):
                header_value = sheet.cell(row=1, column=column).value
                add_cell(row_number, column, weekday, merge_width.get((row_number, column), 1), header_value)
    if not slots:
        raise ValueError("No timetable grid was found. Include weekday headers and course cells containing a course code and class type (L, T, or P).")
    return slots
