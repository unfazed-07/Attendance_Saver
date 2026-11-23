from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class TimetableSlotInput(BaseModel):
    day_of_week: str
    time_slot: str = "Unspecified"
    course_code: str = Field(min_length=3, max_length=20)
    class_type: Literal["L", "T", "P"]
    attendance_units: int = Field(default=1, ge=1, le=12)


class AttendanceRecordInput(BaseModel):
    course_code: str
    course_name: str = ""
    total_delivered: int = Field(ge=0)
    total_attended: int = Field(ge=0)
    duty_leave: int = Field(default=0, ge=0)
    first_week_bonus: int = Field(default=0, ge=0)
    reported_percentage: int = Field(default=0, ge=0, le=100)


class VerifyDataInput(BaseModel):
    timetable_slots: list[TimetableSlotInput] | None = None
    attendance_records: list[AttendanceRecordInput] | None = None


class SimulateInput(BaseModel):
    skipped_dates: list[date] = Field(default_factory=list)
    extra_bunks_per_course: dict[str, int] = Field(default_factory=dict)
