from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AcademicSession(Base):
    __tablename__ = "AcademicSessions"
    session_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_name: Mapped[str] = mapped_column(String(100), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    reference_today: Mapped[date] = mapped_column(Date, nullable=False)
    calendar_blob_url: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    days: Mapped[list["CalendarDay"]] = relationship(back_populates="session", cascade="all, delete-orphan")


class CalendarDay(Base):
    __tablename__ = "CalendarDays"
    __table_args__ = (UniqueConstraint("session_id", "calendar_date", name="UQ_Session_Date"),)
    day_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("AcademicSessions.session_id", ondelete="CASCADE"), nullable=False)
    calendar_date: Mapped[date] = mapped_column(Date, nullable=False)
    day_of_week: Mapped[str] = mapped_column(String(15), nullable=False)
    day_type: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str | None] = mapped_column(String(100))
    session: Mapped[AcademicSession] = relationship(back_populates="days")


class StudentProfile(Base):
    __tablename__ = "StudentProfiles"
    student_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    student_name: Mapped[str | None] = mapped_column(String(100))
    session_id: Mapped[int] = mapped_column(ForeignKey("AcademicSessions.session_id"), nullable=False)
    timetable_blob_url: Mapped[str | None] = mapped_column(String(500))
    attendance_blob_url: Mapped[str | None] = mapped_column(String(500))
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    slots: Mapped[list["TimetableSlot"]] = relationship(back_populates="student", cascade="all, delete-orphan")
    records: Mapped[list["AttendanceRecord"]] = relationship(back_populates="student", cascade="all, delete-orphan")


class TimetableSlot(Base):
    __tablename__ = "TimetableSlots"
    slot_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("StudentProfiles.student_id", ondelete="CASCADE"), nullable=False)
    day_of_week: Mapped[str] = mapped_column(String(15), nullable=False)
    time_slot: Mapped[str] = mapped_column(String(30), nullable=False)
    course_code: Mapped[str] = mapped_column(String(20), nullable=False)
    class_type: Mapped[str] = mapped_column(String(15), nullable=False)
    attendance_units: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    student: Mapped[StudentProfile] = relationship(back_populates="slots")


class AttendanceRecord(Base):
    __tablename__ = "AttendanceRecords"
    record_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("StudentProfiles.student_id", ondelete="CASCADE"), nullable=False)
    course_code: Mapped[str] = mapped_column(String(20), nullable=False)
    course_name: Mapped[str] = mapped_column(String(150), nullable=False)
    total_delivered: Mapped[int] = mapped_column(Integer, nullable=False)
    total_attended: Mapped[int] = mapped_column(Integer, nullable=False)
    duty_leave: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    first_week_bonus: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reported_percentage: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    student: Mapped[StudentProfile] = relationship(back_populates="records")
