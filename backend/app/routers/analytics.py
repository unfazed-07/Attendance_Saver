from collections import Counter
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AcademicSession, AttendanceRecord, CalendarDay, StudentProfile, TimetableSlot
from app.schemas import SimulateInput
from app.services.auth_service import require_matching_student
from app.services.math_engine import attendance_percent, course_projection, marks_for, slab_plan

router = APIRouter(prefix="/api/student", tags=["analytics"])


def load_data(student_id: str, db: Session):
    student = db.get(StudentProfile, student_id)
    if student is None:
        raise HTTPException(404, "Student profile was not found")
    session = db.get(AcademicSession, student.session_id)
    records = db.scalars(select(AttendanceRecord).where(AttendanceRecord.student_id == student_id).order_by(AttendanceRecord.course_code)).all()
    slots = db.scalars(select(TimetableSlot).where(TimetableSlot.student_id == student_id)).all()
    days = db.scalars(select(CalendarDay).where(
        CalendarDay.session_id == student.session_id,
        CalendarDay.calendar_date > session.reference_today,
        CalendarDay.calendar_date <= session.end_date,
        CalendarDay.day_type == "TEACHING",
    )).all()
    return student, session, records, slots, days


def remaining_by_course(records, slots, days) -> dict[str, int]:
    units_by_course_day: dict[str, Counter[str]] = {}
    for slot in slots:
        units_by_course_day.setdefault(slot.course_code, Counter())[slot.day_of_week] += slot.attendance_units
    day_counts = Counter(day.day_of_week for day in days)
    return {r.course_code: sum(units_by_course_day.get(r.course_code, {}).get(day, 0) * count for day, count in day_counts.items()) for r in records}


def build_dashboard(student, session, records, slots, days, strict: bool = True):
    future = remaining_by_course(records, slots, days)
    courses = [course_projection({
        "course_code": row.course_code,
        "course_name": row.course_name,
        "total_delivered": row.total_delivered,
        "total_attended": row.total_attended,
        "duty_leave": row.duty_leave,
        "first_week_bonus": row.first_week_bonus,
    }, future[row.course_code], strict) for row in records]
    delivered = sum(row.total_delivered for row in records)
    attended = sum(row.total_attended + row.duty_leave + row.first_week_bonus for row in records)
    remaining = sum(future.values())
    pct = attendance_percent(attended, delivered)
    return {
        "student_id": student.student_id,
        "session": {"name": session.session_name, "start_date": session.start_date, "end_date": session.end_date, "reference_today": session.reference_today},
        "aggregate": {"current_pct": pct, "current_marks": marks_for(pct), "total_attended": attended, "total_delivered": delivered, "remaining_classes": remaining, "remaining_teaching_days": len(days), "slabs": slab_plan(attended, delivered, remaining, strict)},
        "courses": courses,
    }


@router.get("/{student_id}/dashboard")
def dashboard(student_id: str, strict_thresholds: bool = True, db: Session = Depends(get_db), _student=Depends(require_matching_student)):
    return build_dashboard(*load_data(student_id, db), strict=strict_thresholds)


@router.post("/{student_id}/simulate")
def simulate(student_id: str, payload: SimulateInput, db: Session = Depends(get_db), _student=Depends(require_matching_student)):
    student, session, records, slots, days = load_data(student_id, db)
    by_course = remaining_by_course(records, slots, days)
    units_by_course_day: dict[str, Counter[str]] = {}
    for slot in slots:
        units_by_course_day.setdefault(slot.course_code, Counter())[slot.day_of_week] += slot.attendance_units
    day_types = {row.calendar_date: row.day_type for row in db.scalars(select(CalendarDay).where(CalendarDay.session_id == session.session_id)).all()}
    skipped_per_course: dict[str, int] = Counter()
    for skipped_date in payload.skipped_dates:
        if skipped_date <= session.reference_today or skipped_date > session.end_date or day_types.get(skipped_date) != "TEACHING":
            continue
        weekday = skipped_date.strftime("%A")
        for course_code, units in units_by_course_day.items():
            skipped_per_course[course_code] += units.get(weekday, 0)
    for code, count in payload.extra_bunks_per_course.items():
        if count < 0:
            raise HTTPException(422, f"Bunk count for {code} must not be negative")
        skipped_per_course[code] += count

    projections = []
    for row in records:
        remaining = by_course[row.course_code]
        skipped = min(remaining, skipped_per_course.get(row.course_code, 0))
        attended = row.total_attended + row.duty_leave + row.first_week_bonus + remaining - skipped
        projected_pct = attendance_percent(attended, row.total_delivered + remaining)
        projections.append({
            "course_code": row.course_code,
            "skipped_classes": skipped,
            "projected_pct": projected_pct,
            "projected_marks": marks_for(projected_pct),
            "status_badge": "REAPPEAR" if projected_pct < 75 else ("BORDERLINE" if projected_pct < 85 else "SAFE"),
        })
    aggregate_attended = sum(row.total_attended + row.duty_leave + row.first_week_bonus for row in records)
    aggregate_delivered = sum(row.total_delivered for row in records)
    aggregate_remaining = sum(by_course.values())
    aggregate_skipped = sum(item["skipped_classes"] for item in projections)
    aggregate_pct = attendance_percent(aggregate_attended + aggregate_remaining - aggregate_skipped, aggregate_delivered + aggregate_remaining)
    return {"aggregate": {"projected_pct": aggregate_pct, "projected_marks": marks_for(aggregate_pct), "status_badge": "REAPPEAR" if aggregate_pct < 75 else "SAFE"}, "courses": projections}
