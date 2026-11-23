from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import CalendarDay
from app.services.bootstrap import ensure_fixed_session

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/calendar")
def get_fixed_calendar(db: Session = Depends(get_db)):
    session = ensure_fixed_session(db)
    days = db.scalars(select(CalendarDay).where(CalendarDay.session_id == session.session_id).order_by(CalendarDay.calendar_date)).all()
    counts: dict[str, int] = {}
    for day in days:
        counts[day.day_type] = counts.get(day.day_type, 0) + 1
    return {
        "session_name": session.session_name,
        "start_date": session.start_date,
        "end_date": session.end_date,
        "reference_today": session.reference_today,
        "summary": counts,
        "days": [{"date": day.calendar_date, "day_of_week": day.day_of_week, "day_type": day.day_type, "description": day.description} for day in days],
    }
