"""
Unit tests for Level 2 — T1 (integrate): Morning Appointment Reminders and Outbox.
Validates reminder creation, clock integration, notification formatting,
idempotency, and outbox operations.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from clinic.clock import SystemClock
from clinic.models import AppointmentStatus, Patient
from clinic.repository import ClinicRepository
from clinic.service import ClinicService


class TestMorningRemindersAndOutbox(unittest.TestCase):
    def setUp(self):
        self.repo = ClinicRepository(":memory:")
        self.clock = SystemClock(initial_time=datetime(2026, 9, 21, 6, 0))
        self.service = ClinicService(self.repo, clock=self.clock)

        self.doctor = self.service.add_doctor(
            name="Dr. Eric Foreman",
            specialty="Neurology",
            room="Room 303",
            work_start_time="08:00",
            work_end_time="16:00",
            working_days=[0, 1, 2, 3, 4],
            doctor_id="doc_foreman",
        )

        self.patient1 = Patient(id="pat_alice", name="Alice Smith", phone="555-0199")
        self.patient2 = Patient(id="pat_bob", name="Bob Jones", phone="555-0200")
        self.repo.save_patient(self.patient1)
        self.repo.save_patient(self.patient2)

    def test_morning_reminders_triggered_on_clock_advance(self):
        """Advancing clock to a day sends reminders for all confirmed appointments that day."""
        # Book 2 appointments on 2026-09-21
        appt1 = self.service.book_appointment(
            doctor_id=self.doctor.id,
            patient_id_or_name=self.patient1.id,
            start_time=datetime(2026, 9, 21, 9, 0),
            end_time=datetime(2026, 9, 21, 9, 30),
        )
        appt2 = self.service.book_appointment(
            doctor_id=self.doctor.id,
            patient_id_or_name=self.patient2.id,
            start_time=datetime(2026, 9, 21, 10, 0),
            end_time=datetime(2026, 9, 21, 10, 30),
        )
        # Book 1 appointment on tomorrow (2026-09-22)
        appt_tomorrow = self.service.book_appointment(
            doctor_id=self.doctor.id,
            patient_id_or_name=self.patient1.id,
            start_time=datetime(2026, 9, 22, 9, 0),
            end_time=datetime(2026, 9, 22, 9, 30),
        )

        # Advance clock to morning of 2026-09-21 07:30
        self.service.advance_clock(datetime(2026, 9, 21, 7, 30))

        outbox = self.service.get_outbox()
        self.assertEqual(len(outbox), 2)

        # Check notification contents
        recipients = {n["recipient_name"] for n in outbox}
        self.assertEqual(recipients, {"Alice Smith", "Bob Jones"})

        for n in outbox:
            self.assertEqual(n["notification_type"], "REMINDER")
            self.assertEqual(n["doctor_name"], "Dr. Eric Foreman")
            self.assertIn("Morning Reminder", n["message"])

    def test_reminders_are_idempotent_per_day(self):
        """Multiple clock advancements on the same day must NOT duplicate reminders for the same appointment."""
        appt = self.service.book_appointment(
            doctor_id=self.doctor.id,
            patient_id_or_name=self.patient1.id,
            start_time=datetime(2026, 9, 21, 9, 0),
            end_time=datetime(2026, 9, 21, 9, 30),
        )

        # First clock tick at 07:00
        self.service.advance_clock(datetime(2026, 9, 21, 7, 0))
        self.assertEqual(len(self.service.get_outbox()), 1)

        # Second clock tick at 08:00 on same day
        self.service.advance_clock(datetime(2026, 9, 21, 8, 0))
        self.assertEqual(len(self.service.get_outbox()), 1)

        # Third tick at 08:30 on same day
        self.service.advance_clock(datetime(2026, 9, 21, 8, 30))
        self.assertEqual(len(self.service.get_outbox()), 1)

    def test_cancelled_appointments_do_not_receive_reminders(self):
        """Cancelled appointments should not generate reminders."""
        appt = self.service.book_appointment(
            doctor_id=self.doctor.id,
            patient_id_or_name=self.patient1.id,
            start_time=datetime(2026, 9, 21, 9, 0),
            end_time=datetime(2026, 9, 21, 9, 30),
        )
        self.service.cancel_appointment(appt.id)

        # Advance clock to morning
        self.service.advance_clock(datetime(2026, 9, 21, 7, 0))
        self.assertEqual(len(self.service.get_outbox()), 0)

    def test_clear_outbox(self):
        """Clearing outbox empties all notification records."""
        self.service.book_appointment(
            doctor_id=self.doctor.id,
            patient_id_or_name=self.patient1.id,
            start_time=datetime(2026, 9, 21, 9, 0),
            end_time=datetime(2026, 9, 21, 9, 30),
        )
        self.service.advance_clock(datetime(2026, 9, 21, 7, 0))
        self.assertEqual(len(self.service.get_outbox()), 1)

        self.service.clear_outbox()
        self.assertEqual(len(self.service.get_outbox()), 0)


if __name__ == "__main__":
    unittest.main()
