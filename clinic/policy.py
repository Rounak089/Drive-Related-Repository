"""
Cancellation policy and fee calculation engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from .models import AppointmentStatus, CancellationRecord


@dataclass
class CancellationPolicy:
    """
    Configurable cancellation policy.
    - cutoff_hours: Minimum hours of notice required for free cancellation (e.g. 24.0 hours).
    - late_fee: Fee charged when cancellation is made with less than cutoff_hours notice.
    """
    cutoff_hours: float = 24.0
    late_fee: float = 25.0

    def preview(
        self,
        appointment_start: datetime,
        as_of: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Preview whether a cancellation at `as_of` time will incur a fee,
        without committing the cancellation.
        """
        as_of_time = as_of or datetime.now()
        notice_seconds = (appointment_start - as_of_time).total_seconds()
        notice_hours = notice_seconds / 3600.0

        is_late = notice_hours < self.cutoff_hours
        suggested_fee = self.late_fee if is_late else 0.0

        return {
            "appointment_start": appointment_start.isoformat(),
            "as_of": as_of_time.isoformat(),
            "notice_hours": round(notice_hours, 2),
            "cutoff_hours": self.cutoff_hours,
            "is_late": is_late,
            "fee": suggested_fee,
            "status_code": (
                AppointmentStatus.CANCELLED_LATE.value
                if is_late
                else AppointmentStatus.CANCELLED_FREE.value
            ),
            "message": (
                f"Late cancellation: {round(notice_hours, 1)}h notice given "
                f"(requires {self.cutoff_hours}h). Fee: ${suggested_fee:.2f}"
                if is_late
                else f"On-time cancellation: {round(notice_hours, 1)}h notice given. No fee."
            ),
        }

    def evaluate(
        self,
        appointment_id: str,
        appointment_start: datetime,
        cancellation_time: Optional[datetime] = None,
        waive_fee: bool = False,
        reason: str = "",
        waiver_reason: Optional[str] = None
    ) -> Tuple[CancellationRecord, AppointmentStatus]:
        """
        Calculates the cancellation fee, generates the CancellationRecord,
        and determines the resulting AppointmentStatus.
        """
        cancel_dt = cancellation_time or datetime.now()
        notice_seconds = (appointment_start - cancel_dt).total_seconds()
        notice_hours = notice_seconds / 3600.0

        is_late = notice_hours < self.cutoff_hours

        if not is_late:
            fee = 0.0
            status = AppointmentStatus.CANCELLED_FREE
        else:
            fee = 0.0 if waive_fee else self.late_fee
            status = AppointmentStatus.CANCELLED_LATE

        record = CancellationRecord(
            appointment_id=appointment_id,
            cancelled_at=cancel_dt,
            notice_hours=notice_hours,
            fee=fee,
            is_late=is_late,
            waived=waive_fee and is_late,
            reason=reason,
            waiver_reason=waiver_reason if (waive_fee and is_late) else None,
        )

        return record, status

