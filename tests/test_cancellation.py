"""
Unit tests for the cancellation policy rules, fee assessments, and clerk fee waivers.
"""

import unittest
from datetime import datetime, timedelta

from clinic.models import AppointmentStatus, Doctor, Patient
from clinic.policy import CancellationPolicy
from clinic.repository import ClinicRepository
from clinic.service import ClinicService, ValidationError


class TestCancellationRules(unittest.TestCase):
    def setUp(self):
        self.repo = ClinicRepository(":memory:")
        self.policy = CancellationPolicy(cutoff_hours=24.0, late_fee=25.0)
        self.service = ClinicService(self.repo, self.policy)

        # Setup doctor & patient
        self.doctor = Doctor(
            id="doc1", name="Dr. Chen", specialty="General", room="101",
            work_start_time="08:00", work_end_time="17:00", working_days=[0, 1, 2, 3, 4, 5, 6]
        )
        self.patient = Patient(id="pat1", name="Alice Smith", phone="555-0199")
        self.repo.save_doctor(self.doctor)
        self.repo.save_patient(self.patient)

        # Appointment on Sept 25, 2026 at 10:00 AM
        self.appt_start = datetime(2026, 9, 25, 10, 0)
        self.appt_end = datetime(2026, 9, 25, 10, 30)

    def _book_sample_appt(self):
        return self.service.book_appointment(
            doctor_id="doc1",
            patient_id_or_name="pat1",
            start_time=self.appt_start,
            end_time=self.appt_end,
        )

    def test_timely_cancellation_is_free(self):
        """Cancelling 48 hours in advance must incur $0 fee and status CANCELLED_FREE."""
        appt = self._book_sample_appt()
        cancel_time = self.appt_start - timedelta(hours=48)

        cancelled = self.service.cancel_appointment(
            appointment_id=appt.id,
            cancellation_time=cancel_time,
            reason="Schedule conflict resolved",
        )

        self.assertEqual(cancelled.status, AppointmentStatus.CANCELLED_FREE)
        self.assertIsNotNone(cancelled.cancellation)
        self.assertEqual(cancelled.cancellation.fee, 0.0)
        self.assertFalse(cancelled.cancellation.is_late)
        self.assertFalse(cancelled.cancellation.waived)
        self.assertAlmostEqual(cancelled.cancellation.notice_hours, 48.0, places=2)

    def test_cancellation_exactly_at_cutoff_boundary(self):
        """Cancelling exactly 24.0 hours before appointment is on-time (free)."""
        appt = self._book_sample_appt()
        cancel_time = self.appt_start - timedelta(hours=24)

        cancelled = self.service.cancel_appointment(
            appointment_id=appt.id,
            cancellation_time=cancel_time,
            reason="Cancelled exactly 24 hours prior",
        )

        self.assertEqual(cancelled.status, AppointmentStatus.CANCELLED_FREE)
        self.assertEqual(cancelled.cancellation.fee, 0.0)
        self.assertFalse(cancelled.cancellation.is_late)

    def test_late_cancellation_carries_fee(self):
        """Cancelling with only 3 hours notice incurs the configured $25 fee."""
        appt = self._book_sample_appt()
        cancel_time = self.appt_start - timedelta(hours=3)

        cancelled = self.service.cancel_appointment(
            appointment_id=appt.id,
            cancellation_time=cancel_time,
            reason="Woke up sick with headache",
        )

        self.assertEqual(cancelled.status, AppointmentStatus.CANCELLED_LATE)
        self.assertIsNotNone(cancelled.cancellation)
        self.assertEqual(cancelled.cancellation.fee, 25.0)
        self.assertTrue(cancelled.cancellation.is_late)
        self.assertFalse(cancelled.cancellation.waived)
        self.assertAlmostEqual(cancelled.cancellation.notice_hours, 3.0, places=2)

    def test_clerk_fee_waiver_for_emergencies(self):
        """Front desk can waive the fee for emergencies, recording the waiver audit trail."""
        appt = self._book_sample_appt()
        cancel_time = self.appt_start - timedelta(hours=2)

        cancelled = self.service.cancel_appointment(
            appointment_id=appt.id,
            cancellation_time=cancel_time,
            waive_fee=True,
            reason="Emergency hospitalization in family",
            waiver_reason="Desk supervisor waiver authorized per clinic policy",
        )

        self.assertEqual(cancelled.status, AppointmentStatus.CANCELLED_LATE)
        self.assertEqual(cancelled.cancellation.fee, 0.0)
        self.assertTrue(cancelled.cancellation.is_late)
        self.assertTrue(cancelled.cancellation.waived)
        self.assertEqual(
            cancelled.cancellation.waiver_reason,
            "Desk supervisor waiver authorized per clinic policy",
        )

    def test_preview_cancellation(self):
        """Preview reflects notice and fee without altering database state."""
        appt = self._book_sample_appt()
        cancel_time = self.appt_start - timedelta(hours=10)

        preview = self.service.preview_cancellation(appt.id, as_of=cancel_time)
        self.assertTrue(preview["is_late"])
        self.assertEqual(preview["fee"], 25.0)
        self.assertAlmostEqual(preview["notice_hours"], 10.0, places=2)

        # Confirm the appointment is still CONFIRMED in database
        fresh = self.repo.get_appointment(appt.id)
        self.assertEqual(fresh.status, AppointmentStatus.CONFIRMED)

    def test_double_cancellation_is_rejected(self):
        """Attempting to cancel an appointment twice raises ValidationError."""
        appt = self._book_sample_appt()
        self.service.cancel_appointment(appt.id, reason="First cancel")

        with self.assertRaises(ValidationError):
            self.service.cancel_appointment(appt.id, reason="Second cancel attempt")


if __name__ == "__main__":
    unittest.main()

