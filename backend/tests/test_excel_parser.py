from io import BytesIO

from openpyxl import Workbook

from app.services.excel_parser import parse_timetable


def test_parses_weekday_classes_and_merged_practical_units():
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"])
    sheet["A2"] = "09:00 - 10:00 - L - CSB204K3P25BX"
    sheet["B2"] = "10:00 - 11:00 - T - CSE214"
    sheet["C2"] = "10:00 - 12:00 - P - CSB213"
    sheet.merge_cells("C2:C3")
    output = BytesIO()
    workbook.save(output)

    slots = parse_timetable(output.getvalue())

    assert [(slot.day_of_week, slot.course_code, slot.class_type, slot.attendance_units) for slot in slots] == [
        ("Monday", "CSB204", "L", 1),
        ("Tuesday", "CSE214", "T", 1),
        ("Wednesday", "CSB213", "P", 2),
    ]


def test_ignores_break_and_errors_when_no_class_rows():
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"])
    sheet.append(["Lunch", "Break", None, None, None, None])
    output = BytesIO()
    workbook.save(output)

    try:
        parse_timetable(output.getvalue())
    except ValueError as error:
        assert "No timetable grid" in str(error)
    else:
        raise AssertionError("Expected malformed timetable to be rejected")


def test_accepts_weekdays_in_rows_and_horizontally_merged_practical():
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Day", "09:00 - 11:00", "", "11:00 - 12:00", "12:00 - 13:00", "13:00 - 14:00", "14:00 - 15:00"])
    for row, day in enumerate(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"], start=2):
        sheet.cell(row=row, column=1, value=day)
    sheet["B2"] = "P - CSB204"
    sheet.merge_cells("B2:C2")
    output = BytesIO()
    workbook.save(output)

    slots = parse_timetable(output.getvalue())

    assert len(slots) == 1
    assert slots[0].day_of_week == "Monday"
    assert slots[0].attendance_units == 2
