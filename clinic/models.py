"""
Data models and value objects for the clinic scheduling domain.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid


class AppointmentStatus(str, Enum):
    CONFIRMED = "CONFIRMED"
    COMPLETED = "COMPLETED"
    CANCELLED_FREE = "CANCELLED_FREE"
    CANCELLED_LATE = "CANCELLED_LATE"
    NO_SHOW = "NO_SHOW"

    @property
    def is_active(self) -> bool:
        """Active appointments occupy a doctor's time slot."""
        return self in (AppointmentStatus.CONFIRMED, AppointmentStatus.COMPLETED)

    @property
    def is_cancelled(self) -> bool:
        """Returns True if appointment has been cancelled."""
        return self in (AppointmentStatus.CANCELLED_FREE, AppointmentStatus.CANCELLED_LATE)


@dataclass(frozen=True)
class TimeSlot:
    """Represents a continuous half-open interval [start_time, end_time)."""
    start_time: datetime
    end_time: datetime

    def __post_init__(self) -> None:
        if self.start_time >= self.end_time:
            raise ValueError(
                f"Invalid time slot: start_time ({self.start_time.isoformat()}) "
                f"must be strictly before end_time ({self.end_time.isoformat()})"
            )

    @property
    def duration_minutes(self) -> int:
        return int((self.end_time - self.start_time).total_seconds() // 60)

    def overlaps(self, other: TimeSlot) -> bool:
        """
        Determines if two half-open intervals [s1, e1) and [s2, e2) overlap.
        They overlap if and only if max(s1, s2) < min(e1, e2).
        Note: If s2 == e1 (back-to-back), this returns False (no overlap).
        """
        return max(self.start_time, other.start_time) < min(self.end_time, other.end_time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "duration_minutes": self.duration_minutes,
        }


@dataclass
class Doctor:
    id: str
    name: str
    specialty: str
    room: str
    work_start_time: str = "08:30"  # HH:MM
    work_end_time: str = "17:00"    # HH:MM
    working_days: List[int] = field(default_factory=lambda: [0, 1, 2, 3, 4])  # Mon-Fri

    def is_working_on(self, dt: datetime) -> bool:
        """Check if doctor works on the given weekday."""
        return dt.weekday() in self.working_days

    def works_on(self, weekday: int) -> bool:
        """Check if doctor works on the given weekday index (0=Mon, 6=Sun)."""
        return weekday in self.working_days

    @property
    def work_start_tuple(self) -> tuple[int, int]:
        s_h, s_m = map(int, self.work_start_time.split(":"))
        return s_h, s_m

    @property
    def work_end_tuple(self) -> tuple[int, int]:
        e_h, e_m = map(int, self.work_end_time.split(":"))
        return e_h, e_m

    def get_shift_times(self, target_date: datetime) -> tuple[datetime, datetime]:
        """Returns the start and end datetimes of the doctor's shift on target_date."""
        s_h, s_m = map(int, self.work_start_time.split(":"))
        e_h, e_m = map(int, self.work_end_time.split(":"))
        shift_start = datetime(target_date.year, target_date.month, target_date.day, s_h, s_m)
        shift_end = datetime(target_date.year, target_date.month, target_date.day, e_h, e_m)
        return shift_start, shift_end

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "specialty": self.specialty,
            "room": self.room,
            "work_start_time": self.work_start_time,
            "work_end_time": self.work_end_time,
            "working_days": self.working_days,
        }


@dataclass
class Patient:
    id: str
    name: str
    phone: str
    email: str = ""
    date_of_birth: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "phone": self.phone,
            "email": self.email,
            "date_of_birth": self.date_of_birth,
        }


@dataclass
class CancellationRecord:
    appointment_id: str
    cancelled_at: datetime
    notice_hours: float
    fee: float
    is_late: bool
    waived: bool = False
    reason: str = ""
    waiver_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "appointment_id": self.appointment_id,
            "cancelled_at": self.cancelled_at.isoformat(),
            "notice_hours": round(self.notice_hours, 2),
            "fee": self.fee,
            "is_late": self.is_late,
            "waived": self.waived,
            "reason": self.reason,
            "waiver_reason": self.waiver_reason,
        }


@dataclass
class Appointment:
    id: str
    doctor_id: str
    patient_id: str
    start_time: datetime
    end_time: datetime
    status: AppointmentStatus = AppointmentStatus.CONFIRMED
    notes: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    doctor_name: Optional[str] = None
    patient_name: Optional[str] = None
    patient_phone: Optional[str] = None
    cancellation: Optional[CancellationRecord] = None

    @property
    def slot(self) -> TimeSlot:
        return TimeSlot(self.start_time, self.end_time)

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "id": self.id,
            "doctor_id": self.doctor_id,
            "patient_id": self.patient_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "duration_minutes": self.slot.duration_minutes,
            "status": self.status.value,
            "notes": self.notes,
            "created_at": self.created_at.isoformat(),
            "doctor_name": self.doctor_name,
            "patient_name": self.patient_name,
            "patient_phone": self.patient_phone,
        }
        if self.cancellation:
            data["cancellation"] = self.cancellation.to_dict()
        return data

