from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import AttendanceRecord, StudentProfile, TimetableSlot
from app.schemas import VerifyDataInput
from app.services.attendance_parser import parse_attendance_image
from app.services.blob_service import store_upload
from app.services.auth_service import get_current_student, require_matching_student
from app.services.excel_parser import parse_timetable

router = APIRouter(prefix="/api/student", tags=["student"])


@router.post("/upload-timetable")
async def upload_timetable(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    student: StudentProfile = Depends(get_current_student),
):
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(400, "Upload a .xlsx timetable")
    content = await file.read()
    try:
        slots = parse_timetable(content)
    except Exception as exc:
        raise HTTPException(422, f"Could not parse timetable: {exc}") from exc
    blob_url = store_upload("student-timetables", file.filename, content)
    db.execute(delete(TimetableSlot).where(TimetableSlot.student_id == student.student_id))
    db.add_all([TimetableSlot(student_id=student.student_id, **slot.as_dict()) for slot in slots])
    student.timetable_blob_url = blob_url
    db.commit()
    return {"student_id": student.student_id, "timetable_blob_url": blob_url, "slots": [slot.as_dict() for slot in slots]}


@router.post("/upload-attendance")
async def upload_attendance(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    student: StudentProfile = Depends(get_current_student),
):
    if not file.filename or not file.filename.lower().endswith((".png", ".jpg", ".jpeg")):
        raise HTTPException(400, "Upload a PNG or JPEG attendance summary")
    content = await file.read()
    blob_url = store_upload("attendance-summaries", file.filename, content)
    student.attendance_blob_url = blob_url
    db.commit()
    settings = get_settings()
    try:
        rows = parse_attendance_image(content, settings.azure_document_intelligence_endpoint, settings.azure_document_intelligence_key)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(502, f"Azure Document Intelligence could not read the uploaded image: {exc}") from exc
    db.execute(delete(AttendanceRecord).where(AttendanceRecord.student_id == student.student_id))
    records = [AttendanceRecord(student_id=student.student_id, **row.as_dict()) for row in rows]
    db.add_all(records)
    student.attendance_blob_url = blob_url
    db.commit()
    return {"student_id": student.student_id, "attendance_blob_url": blob_url, "rows": [row.as_dict() for row in rows]}


@router.put("/{student_id}/verify-data")
def verify_data(student_id: str, payload: VerifyDataInput, db: Session = Depends(get_db), student: StudentProfile = Depends(require_matching_student)):
    if payload.timetable_slots is not None:
        db.execute(delete(TimetableSlot).where(TimetableSlot.student_id == student.student_id))
        db.add_all([TimetableSlot(student_id=student.student_id, **row.model_dump()) for row in payload.timetable_slots])
    if payload.attendance_records is not None:
        db.execute(delete(AttendanceRecord).where(AttendanceRecord.student_id == student.student_id))
        db.add_all([AttendanceRecord(student_id=student.student_id, **row.model_dump()) for row in payload.attendance_records])
    db.commit()
    return {"student_id": student.student_id, "verified": True}


@router.get("/{student_id}/data")
def get_student_data(student_id: str, db: Session = Depends(get_db), student: StudentProfile = Depends(require_matching_student)):
    return {
        "student_id": student.student_id,
        "timetable_slots": [{"day_of_week": s.day_of_week, "time_slot": s.time_slot, "course_code": s.course_code, "class_type": s.class_type, "attendance_units": s.attendance_units} for s in student.slots],
        "attendance_records": [{"course_code": r.course_code, "course_name": r.course_name, "total_delivered": r.total_delivered, "total_attended": r.total_attended, "duty_leave": r.duty_leave, "first_week_bonus": r.first_week_bonus, "reported_percentage": r.reported_percentage} for r in student.records],
    }
