from datetime import date

from app.services.calendar_parser import END_DATE, HOLIDAYS, MIDTERM_DAYS, START_DATE, build_calendar_days, remaining_teaching_days


def test_fixed_calendar_range_and_classifications():
    calendar = build_calendar_days()
    by_date = {row["calendar_date"]: row["day_type"] for row in calendar}
    assert calendar[0]["calendar_date"] == START_DATE
    assert calendar[-1]["calendar_date"] == END_DATE
    assert by_date[date(2026, 10, 13)] == "MTT"
    assert by_date[date(2026, 11, 24)] == "HOLIDAY"
    assert by_date[date(2026, 11, 8)] == "WEEKEND"


def test_remaining_teaching_days_excludes_reference_day_and_non_teaching():
    days = remaining_teaching_days(date(2026, 11, 23))
    assert date(2026, 11, 23) not in days
    assert date(2026, 11, 24) not in days
    assert date(2026, 11, 29) not in days
    assert all(day not in HOLIDAYS and day not in MIDTERM_DAYS for day in days)
