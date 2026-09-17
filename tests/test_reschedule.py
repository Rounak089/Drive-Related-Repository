"""
Unit tests for Level 1 — T6 (lifecycle): Appointment Rescheduling.
Validates conflict-free rescheduling, overlap re-checks, self-collision handling,
schedule bounds, and patient/doctor identity preservation.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from clinic.models import AppointmentStatus, Doctor, Patient
from clinic.repository import ClinicRepository
from clinic.service import ClinicService, ConflictError, NotFoundError, ValidationError


class TestAppointmentReschedule(unittest.TestCase):
    def setUp(self):
        self.repo = ClinicRepository(":memory:")
        self.service = ClinicService(self.repo)

        # Create doctor working Mon-Fri 08:30 - 17:00
        self.doctor = self.service.add_doctor(
            name="Dr. Gregory House",
            specialty="Diagnostic Medicine",
            room="Room 401",
            work_start_time="08:30",
            work_end_time="17:00",
            working_days=[0, 1, 2, 3, 4],
            doctor_id="doc_house",
        )

        # Create 2nd doctor
        self.doctor2 = self.service.add_doctor(
            name="Dr. Allison Cameron",
            specialty="Immunology",
            room="Room 402",
            work_start_time="08:30",
            work_end_time="17:00",
            working_days=[0, 1, 2, 3, 4],
            doctor_id="doc_cameron",
        )

        # Create patient
        self.patient = Patient(id="pat_wilson", name="James Wilson", phone="555-0101")
        self.repo.save_patient(self.patient)

        # Base date: A Monday (2026-09-21)
        self.base_date = datetime(2026, 9, 21, 9, 0)

    def test_successful_reschedule_to_open_slot(self):
        """Rescheduling to a free time slot succeeds and updates start and end time."""
        appt = self.service.book_appointment(
            doctor_id=self.doctor.id,
            patient_id_or_name=self.patient.id,
            start_time=self.base_date,  # 09:00 - 09:30
            end_time=self.base_date + timedelta(minutes=30),
        )

        new_start = datetime(2026, 9, 21, 14, 0)
        updated = self.service.reschedule_appointment(
            appointment_id=appt.id,
            new_start_time=new_start,
            duration_minutes=30,
        )

        self.assertEqual(updated.id, appt.id)
        self.assertEqual(updated.doctor_id, self.doctor.id)
        self.assertEqual(updated.patient_id, self.patient.id)
        self.assertEqual(updated.start_time, new_start)
        self.assertEqual(updated.end_time, new_start + timedelta(minutes=30))
        self.assertEqual(updated.status, AppointmentStatus.CONFIRMED)

    def test_reschedule_preserves_duration_when_unspecified(self):
        """When new duration or end_time is not given, original duration is preserved."""
        appt = self.service.book_appointment(
            doctor_id=self.doctor.id,
            patient_id_or_name=self.patient.id,
            start_time=self.base_date,  # 09:00 - 09:45 (45 min)
            end_time=self.base_date + timedelta(minutes=45),
        )

        new_start = datetime(2026, 9, 21, 11, 0)
        updated = self.service.reschedule_appointment(
            appointment_id=appt.id,
            new_start_time=new_start,
        )

        self.assertEqual(updated.start_time, new_start)
        self.assertEqual(updated.end_time, new_start + timedelta(minutes=45))

    def test_reschedule_self_overlap_is_allowed(self):
        """
        Shifting an appointment slightly so it overlaps with its own previous interval
        (e.g., 09:00-09:30 shifted to 09:15-09:45) must NOT collide with itself.
        """
        appt = self.service.book_appointment(
            doctor_id=self.doctor.id,
            patient_id_or_name=self.patient.id,
            start_time=datetime(2026, 9, 21, 9, 0),
            end_time=datetime(2026, 9, 21, 9, 30),
        )

        new_start = datetime(2026, 9, 21, 9, 15)
        new_end = datetime(2026, 9, 21, 9, 45)

        updated = self.service.reschedule_appointment(
            appointment_id=appt.id,
            new_start_time=new_start,
            new_end_time=new_end,
        )

        self.assertEqual(updated.start_time, new_start)
        self.assertEqual(updated.end_time, new_end)

    def test_reschedule_doctor_conflict_is_rejected(self):
        """Rescheduling to a slot where the doctor already has another appointment fails with ConflictError."""
        appt1 = self.service.book_appointment(
            doctor_id=self.doctor.id,
            patient_id_or_name=self.patient.id,
            start_time=datetime(2026, 9, 21, 9, 0),
            end_time=datetime(2026, 9, 21, 9, 30),
        )
        appt2 = self.service.book_appointment(
            doctor_id=self.doctor.id,
            patient_id_or_name="Lisa Cuddy",
            start_time=datetime(2026, 9, 21, 10, 0),
            end_time=datetime(2026, 9, 21, 10, 30),
        )

        with self.assertRaises(ConflictError) as ctx:
            self.service.reschedule_appointment(
                appointment_id=appt1.id,
                new_start_time=datetime(2026, 9, 21, 10, 15),  # overlaps appt2
                duration_minutes=30,
            )

        self.assertIn("already booked", str(ctx.exception))
        self.assertTrue(len(ctx.exception.suggested_slots) > 0)

    def test_reschedule_patient_conflict_is_rejected(self):
        """Rescheduling when the patient has another appointment with a different doctor fails with ConflictError."""
        appt_house = self.service.book_appointment(
            doctor_id=self.doctor.id,
            patient_id_or_name=self.patient.id,
            start_time=datetime(2026, 9, 21, 9, 0),
            end_time=datetime(2026, 9, 21, 9, 30),
        )
        appt_cameron = self.service.book_appointment(
            doctor_id=self.doctor2.id,
            patient_id_or_name=self.patient.id,
            start_time=datetime(2026, 9, 21, 11, 0),
            end_time=datetime(2026, 9, 21, 11, 30),
        )

        with self.assertRaises(ConflictError) as ctx:
            self.service.reschedule_appointment(
                appointment_id=appt_house.id,
                new_start_time=datetime(2026, 9, 21, 11, 15),  # overlaps appt_cameron
                duration_minutes=30,
            )

        self.assertIn("Patient already has another confirmed appointment", str(ctx.exception))

    def test_reschedule_outside_shift_hours_fails(self):
        """Rescheduling outside doctor shift hours raises ValidationError."""
        appt = self.service.book_appointment(
            doctor_id=self.doctor.id,
            patient_id_or_name=self.patient.id,
            start_time=self.base_date,
            end_time=self.base_date + timedelta(minutes=30),
        )

        with self.assertRaises(ValidationError):
            self.service.reschedule_appointment(
                appointment_id=appt.id,
                new_start_time=datetime(2026, 9, 21, 7, 0),  # Doctor starts at 08:30
                duration_minutes=30,
            )

    def test_reschedule_on_non_working_day_fails(self):
        """Rescheduling to a day doctor does not work (e.g. Sunday) raises ValidationError."""
        appt = self.service.book_appointment(
            doctor_id=self.doctor.id,
            patient_id_or_name=self.patient.id,
            start_time=self.base_date,
            end_time=self.base_date + timedelta(minutes=30),
        )

        sunday = datetime(2026, 9, 27, 10, 0)
        with self.assertRaises(ValidationError):
            self.service.reschedule_appointment(
                appointment_id=appt.id,
                new_start_time=sunday,
                duration_minutes=30,
            )

    def test_reschedule_cancelled_appointment_fails(self):
        """Cannot reschedule an already cancelled appointment."""
        appt = self.service.book_appointment(
            doctor_id=self.doctor.id,
            patient_id_or_name=self.patient.id,
            start_time=self.base_date,
            end_time=self.base_date + timedelta(minutes=30),
        )
        self.service.cancel_appointment(appt.id)

        with self.assertRaises(ValidationError):
            self.service.reschedule_appointment(
                appointment_id=appt.id,
                new_start_time=datetime(2026, 9, 21, 14, 0),
            )

    def test_reschedule_non_existent_appointment_fails(self):
        with self.assertRaises(NotFoundError):
            self.service.reschedule_appointment(
                appointment_id="non_existent_id",
                new_start_time=datetime(2026, 9, 21, 14, 0),
            )


if __name__ == "__main__":
    unittest.main()
