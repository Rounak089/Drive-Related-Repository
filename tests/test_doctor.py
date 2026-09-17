"""
Unit tests for onboarding and managing new doctors in the hospital.
"""

import unittest
from datetime import datetime

from clinic.repository import ClinicRepository
from clinic.service import ClinicService, ConflictError, ValidationError


class TestDoctorOnboarding(unittest.TestCase):
    def setUp(self):
        self.repo = ClinicRepository(":memory:")
        self.service = ClinicService(self.repo)

    def test_add_doctor_successfully(self):
        """Successfully adds a new doctor with custom shift hours and working days."""
        doc = self.service.add_doctor(
            name="Gregory House",
            specialty="Diagnostic Medicine",
            room="Room 402",
            work_start_time="09:00",
            work_end_time="16:00",
            working_days=[0, 1, 2, 3, 4],
        )

        self.assertIsNotNone(doc.id)
        self.assertEqual(doc.name, "Dr. Gregory House")
        self.assertEqual(doc.specialty, "Diagnostic Medicine")
        self.assertEqual(doc.room, "Room 402")
        self.assertEqual(doc.work_start_time, "09:00")
        self.assertEqual(doc.work_end_time, "16:00")
        self.assertEqual(doc.working_days, [0, 1, 2, 3, 4])

        # Verify saved in repository
        fetched = self.repo.get_doctor(doc.id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.name, "Dr. Gregory House")

    def test_empty_fields_raise_validation_error(self):
        """Empty name, specialty, or room must raise ValidationError."""
        with self.assertRaises(ValidationError):
            self.service.add_doctor(name="", specialty="Cardiology", room="101")

        with self.assertRaises(ValidationError):
            self.service.add_doctor(name="Dr. Smith", specialty="", room="101")

        with self.assertRaises(ValidationError):
            self.service.add_doctor(name="Dr. Smith", specialty="Cardiology", room="")

    def test_invalid_shift_hours_raise_validation_error(self):
        """Invalid time format or start time >= end time must raise ValidationError."""
        # Malformed times
        with self.assertRaises(ValidationError):
            self.service.add_doctor(name="Dr. Who", specialty="General", room="TARDIS", work_start_time="25:00")

        with self.assertRaises(ValidationError):
            self.service.add_doctor(name="Dr. Who", specialty="General", room="TARDIS", work_end_time="invalid")

        # Start time after or equal to end time
        with self.assertRaises(ValidationError):
            self.service.add_doctor(
                name="Dr. Night", specialty="ER", room="ER 1",
                work_start_time="17:00", work_end_time="08:00"
            )

        with self.assertRaises(ValidationError):
            self.service.add_doctor(
                name="Dr. Zero", specialty="ER", room="ER 1",
                work_start_time="09:00", work_end_time="09:00"
            )

    def test_invalid_working_days_raise_validation_error(self):
        """Days outside 0..6 must raise ValidationError."""
        with self.assertRaises(ValidationError):
            self.service.add_doctor(
                name="Dr. Weekend", specialty="Pediatrics", room="201",
                working_days=[0, 7]  # 7 is invalid
            )

    def test_new_doctor_schedule_and_booking(self):
        """Verifies schedule generation and booking for newly added doctor."""
        doc = self.service.add_doctor(
            name="Dr. Allison Cameron",
            specialty="Immunology",
            room="Room 305",
            work_start_time="08:30",
            work_end_time="16:30",
            working_days=[0, 1, 2, 3, 4, 5],
        )

        # On a valid working day (e.g. 2026-09-22 is a Tuesday = 1)
        test_date = datetime(2026, 9, 22, 10, 0)
        sched = self.service.get_doctor_day_schedule(doc.id, test_date)

        self.assertEqual(sched["doctor"]["name"], "Dr. Allison Cameron")
        self.assertEqual(sched["free_minutes"], 480)
        self.assertEqual(sched["booked_minutes"], 0)

        # Book an appointment for the new doctor
        appt = self.service.book_appointment(
            doctor_id=doc.id,
            patient_id_or_name="Wilson",
            start_time=test_date,
            end_time=datetime(2026, 9, 22, 10, 30),
            notes="Allergy testing",
        )
        self.assertIsNotNone(appt.id)

        # Confirm updated schedule reflects 30 min booked
        updated_sched = self.service.get_doctor_day_schedule(doc.id, test_date)
        self.assertEqual(updated_sched["booked_minutes"], 30)
        self.assertEqual(updated_sched["free_minutes"], 450)


if __name__ == "__main__":
    unittest.main()
