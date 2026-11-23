from app.services.attendance_parser import parse_document_rows


def test_maps_course_rows_and_skips_aggregate():
    rows = {
        0: {0: "Course", 1: "Delivered", 2: "Attended", 3: "Duty Leave", 4: "Bonus", 5: "Percentage"},
        1: {0: "CSB204: AZURE DATA FUNDAMENTALS", 1: "49", 2: "41", 3: "0", 4: "0", 5: "84%"},
        2: {0: "* Aggregate Attendance", 1: "49", 2: "41", 3: "0", 4: "0", 5: "84%"},
    }
    parsed = parse_document_rows(rows)
    assert len(parsed) == 1
    assert parsed[0].course_code == "CSB204"
    assert parsed[0].course_name == "AZURE DATA FUNDAMENTALS"
    assert parsed[0].total_delivered == 49
    assert parsed[0].reported_percentage == 84
