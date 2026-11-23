from datetime import date, timedelta

SESSION_NAME = "Odd Semester Aug-Dec 2026"
START_DATE = date(2026, 8, 10)
END_DATE = date(2026, 12, 11)
REFERENCE_TODAY = date(2026, 11, 23)
HOLIDAYS = {
    date(2026, 8, 15), date(2026, 10, 2), date(2026, 10, 20),
    date(2026, 10, 26), date(2026, 11, 7), date(2026, 11, 8),
    date(2026, 11, 9), date(2026, 11, 10), date(2026, 11, 24),
}
MIDTERM_DAYS = {date(2026, 10, day) for day in range(12, 18)}


def build_calendar_days() -> list[dict[str, object]]:
    result = []
    current = START_DATE
    while current <= END_DATE:
        if current.weekday() == 6:
            kind, description = "WEEKEND", "Sunday"
        elif current in MIDTERM_DAYS:
            kind, description = "MTT", "Mid Term Test"
        elif current in HOLIDAYS:
            kind, description = "HOLIDAY", "Holiday"
        else:
            kind, description = "TEACHING", None
        result.append({"calendar_date": current, "day_of_week": current.strftime("%A"), "day_type": kind, "description": description})
        current += timedelta(days=1)
    return result


def remaining_teaching_days(today: date | None = None) -> list[date]:
    effective_today = today or REFERENCE_TODAY
    return [row["calendar_date"] for row in build_calendar_days() if effective_today < row["calendar_date"] <= END_DATE and row["day_type"] == "TEACHING"]
