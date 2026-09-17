"""
Unit tests for conflict-free booking and strict overlap prevention math.
"""

import unittest
from datetime import datetime, timedelta

from clinic.models import AppointmentStatus, Doctor, Patient, TimeSlot
from clinic.policy import CancellationPolicy
from clinic.repository import ClinicRepository
from clinic.service import ClinicService, ConflictError, ValidationError


class TestOverlapMath(unittest.TestCase):
    def test_timeslot_overlap_conditions(self):
        t1 = datetime(2026, 9, 20, 9, 0)
        t2 = datetime(2026, 9, 20, 9, 30)
        t3 = datetime(2026, 9, 20, 10, 0)
        t4 = datetime(2026, 9, 20, 10, 30)

        slot1 = TimeSlot(t1, t2)  # [09:00, 09:30)
        slot2 = TimeSlot(t2, t3)  # [09:30, 10:00)
        slot3 = TimeSlot(t1, t3)  # [09:00, 10:00)
        slot_partial = TimeSlot(datetime(2026, 9, 20, 9, 15), datetime(2026, 9, 20, 9, 45))  # [09:15, 09:45)
        slot_inside = TimeSlot(datetime(2026, 9, 20, 9, 10), datetime(2026, 9, 20, 9, 20))   # [09:10, 09:20)

        # Back-to-back should NOT overlap
        self.assertFalse(slot1.overlaps(slot2))
        self.assertFalse(slot2.overlaps(slot1))

        # Enclosing / Enclosed must overlap
        self.assertTrue(slot1.overlaps(slot3))
        self.assertTrue(slot3.overlaps(slot1))
        self.assertTrue(slot1.overlaps(slot_inside))

        # Partial overlap
        self.assertTrue(slot1.overlaps(slot_partial))
        self.assertTrue(slot2.overlaps(slot_partial))

        # Invalid slot where start >= end must raise ValueError
        with self.assertRaises(ValueError):
            TimeSlot(t2, t1)
        with self.assertRaises(ValueError):
            TimeSlot(t1, t1)


class TestBookingConflicts(unittest.TestCase):
    def setUp(self):
        self.repo = ClinicRepository(":memory:")
        self.policy = CancellationPolicy(cutoff_hours=24.0, late_fee=25.0)
        self.service = ClinicService(self.repo, self.policy)

        # Doctors
        self.doc1 = Doctor(
            id="doc1", name="Dr. Chen", specialty="Family Medicine",
            room="101", work_start_time="08:00", work_end_time="17:00",
            working_days=[0, 1, 2, 3, 4, 5, 6],
        )
        self.doc2 = Doctor(
            id="doc2", name="Dr. Vance", specialty="Pediatrics",
            room="102", work_start_time="08:00", work_end_time="17:00",
            working_days=[0, 1, 2, 3, 4, 5, 6],
        )
        self.repo.save_doctor(self.doc1)
        self.repo.save_doctor(self.doc2)

        # Patients
        self.pat1 = Patient(id="pat1", name="Alice", phone="111")
        self.pat2 = Patient(id="pat2", name="Bob", phone="222")
        self.pat3 = Patient(id="pat3", name="Charlie", phone="333")
        self.repo.save_patient(self.pat1)
        self.repo.save_patient(self.pat2)
        self.repo.save_patient(self.pat3)

        # Initial baseline booking for Dr. Chen: 10:00 - 10:30 with Alice
        self.base_start = datetime(2026, 9, 21, 10, 0)
        self.base_end = datetime(2026, 9, 21, 10, 30)
        self.service.book_appointment(
            doctor_id="doc1",
            patient_id_or_name="pat1",
            start_time=self.base_start,
            end_time=self.base_end,
        )

    def test_exact_overlap_is_rejected(self):
        """Trying to book the identical slot for the same doctor must raise ConflictError."""
        with self.assertRaises(ConflictError) as ctx:
            self.service.book_appointment(
                doctor_id="doc1",
                patient_id_or_name="pat2",
                start_time=self.base_start,
                end_time=self.base_end,
            )
        self.assertIn("Double-booking prevented", str(ctx.exception))

    def test_partial_start_overlap_is_rejected(self):
        """Starts before (09:45) and ends during (10:15) the existing appointment."""
        with self.assertRaises(ConflictError):
            self.service.book_appointment(
                doctor_id="doc1",
                patient_id_or_name="pat2",
                start_time=datetime(2026, 9, 21, 9, 45),
                end_time=datetime(2026, 9, 21, 10, 15),
            )

    def test_partial_end_overlap_is_rejected(self):
        """Starts during (10:15) and ends after (10:45) the existing appointment."""
        with self.assertRaises(ConflictError):
            self.service.book_appointment(
                doctor_id="doc1",
                patient_id_or_name="pat2",
                start_time=datetime(2026, 9, 21, 10, 15),
                end_time=datetime(2026, 9, 21, 10, 45),
            )

    def test_enclosed_overlap_is_rejected(self):
        """Starts inside and ends inside (10:05 - 10:25)."""
        with self.assertRaises(ConflictError):
            self.service.book_appointment(
                doctor_id="doc1",
                patient_id_or_name="pat2",
                start_time=datetime(2026, 9, 21, 10, 5),
                end_time=datetime(2026, 9, 21, 10, 25),
            )

    def test_enclosing_overlap_is_rejected(self):
        """Envelops the existing appointment (09:30 - 11:00)."""
        with self.assertRaises(ConflictError):
            self.service.book_appointment(
                doctor_id="doc1",
                patient_id_or_name="pat2",
                start_time=datetime(2026, 9, 21, 9, 30),
                end_time=datetime(2026, 9, 21, 11, 0),
            )

    def test_back_to_back_is_allowed(self):
        """Adjacent non-overlapping slots (before and after) MUST succeed."""
        # Immediately preceding: 09:30 - 10:00
        appt_before = self.service.book_appointment(
            doctor_id="doc1",
            patient_id_or_name="pat2",
            start_time=datetime(2026, 9, 21, 9, 30),
            end_time=datetime(2026, 9, 21, 10, 0),
        )
        self.assertIsNotNone(appt_before.id)

        # Immediately following: 10:30 - 11:00
        appt_after = self.service.book_appointment(
            doctor_id="doc1",
            patient_id_or_name="pat3",
            start_time=datetime(2026, 9, 21, 10, 30),
            end_time=datetime(2026, 9, 21, 11, 0),
        )
        self.assertIsNotNone(appt_after.id)

    def test_different_doctors_same_slot_is_allowed(self):
        """Doctor 2 should be bookable during Doctor 1's appointment slot."""
        appt_doc2 = self.service.book_appointment(
            doctor_id="doc2",
            patient_id_or_name="pat2",
            start_time=self.base_start,
            end_time=self.base_end,
        )
        self.assertIsNotNone(appt_doc2.id)

    def test_patient_double_booking_is_prevented(self):
        """The same patient cannot be booked with two doctors at the same time."""
        with self.assertRaises(ConflictError) as ctx:
            self.service.book_appointment(
                doctor_id="doc2",
                patient_id_or_name="pat1",  # Alice is already with Dr. Chen at 10:00
                start_time=self.base_start,
                end_time=self.base_end,
            )
        self.assertIn("already booked with Dr.", str(ctx.exception))

    def test_cancelled_appointment_frees_slot_for_rebooking(self):
        """Once an appointment is cancelled, that doctor's slot can be re-booked."""
        # Book a slot 14:00 - 14:30
        t_start = datetime(2026, 9, 21, 14, 0)
        t_end = datetime(2026, 9, 21, 14, 30)
        first_appt = self.service.book_appointment(
            doctor_id="doc1",
            patient_id_or_name="pat2",
            start_time=t_start,
            end_time=t_end,
        )

        # Verify another booking at 14:00 is initially blocked
        with self.assertRaises(ConflictError):
            self.service.book_appointment(
                doctor_id="doc1",
                patient_id_or_name="pat3",
                start_time=t_start,
                end_time=t_end,
            )

        # Cancel the first appointment
        self.service.cancel_appointment(first_appt.id, reason="Patient called to cancel")

        # Now booking for pat3 in that exact slot MUST succeed!
        new_appt = self.service.book_appointment(
            doctor_id="doc1",
            patient_id_or_name="pat3",
            start_time=t_start,
            end_time=t_end,
        )
        self.assertEqual(new_appt.patient_id, "pat3")
        self.assertEqual(new_appt.status, AppointmentStatus.CONFIRMED)


if __name__ == "__main__":
    unittest.main()

