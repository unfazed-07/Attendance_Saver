from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import StudentProfile
from app.services.auth_service import get_current_student, issue_session_token
from app.services.bootstrap import ensure_fixed_session

router = APIRouter(prefix="/api/auth", tags=["authentication"])


@router.post("/guest")
def create_guest_profile(db: Session = Depends(get_db)):
    """Create an anonymous prototype profile; its identifier is kept inside the app."""
    session = ensure_fixed_session(db)
    student = StudentProfile(session_id=session.session_id)
    db.add(student)
    db.commit()
    token = issue_session_token(student.student_id)
    return {"access_token": token, "token_type": "bearer", "student_id": student.student_id}


@router.get("/me")
def who_am_i(student: StudentProfile = Depends(get_current_student)):
    return {"student_name": student.student_name}
