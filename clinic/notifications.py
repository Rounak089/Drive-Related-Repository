"""
Notification service and outbox logging for patient appointment reminders.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from .models import AppointmentStatus


@dataclass
class Notification:
    id: str
    recipient_id: str
    recipient_name: str
    recipient_contact: str
    appointment_id: str
    doctor_id: str
    doctor_name: str
    appointment_time: datetime
    message: str
    notification_type: str = "REMINDER"
    created_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "recipient_id": self.recipient_id,
            "recipient_name": self.recipient_name,
            "recipient_contact": self.recipient_contact,
            "appointment_id": self.appointment_id,
            "doctor_id": self.doctor_id,
            "doctor_name": self.doctor_name,
            "appointment_time": self.appointment_time.isoformat(),
            "message": self.message,
            "notification_type": self.notification_type,
            "created_at": self.created_at.isoformat(),
        }
