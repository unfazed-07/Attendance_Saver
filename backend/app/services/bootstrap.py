from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AcademicSession, CalendarDay
from app.services.calendar_parser import END_DATE, REFERENCE_TODAY, SESSION_NAME, START_DATE, build_calendar_days


def ensure_fixed_session(db: Session) -> AcademicSession:
    session = db.scalar(select(AcademicSession).where(AcademicSession.session_name == SESSION_NAME))
    if session is None:
        session = AcademicSession(
            session_name=SESSION_NAME,
            start_date=START_DATE,
            end_date=END_DATE,
            reference_today=REFERENCE_TODAY,
            is_active=True,
        )
        db.add(session)
        db.flush()
        db.add_all([CalendarDay(session_id=session.session_id, **row) for row in build_calendar_days()])
        db.commit()
        db.refresh(session)
    return session
