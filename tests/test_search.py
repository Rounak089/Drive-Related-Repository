"""
Unit tests for front desk patient search by name and appointment history lookup.
"""

import unittest
from datetime import datetime

from clinic.models import AppointmentStatus, Doctor, Patient
from clinic.repository import ClinicRepository
from clinic.service import ClinicService


class TestPatientSearch(unittest.TestCase):
    def setUp(self):
        self.repo = ClinicRepository(":memory:")
        self.service = ClinicService(self.repo)

        # Doctor
        self.doctor = Doctor(
            id="doc1", name="Dr. Marcus Vance", specialty="Pediatrics", room="204",
            work_start_time="08:00", work_end_time="17:00", working_days=[0, 1, 2, 3, 4, 5, 6]
        )
        self.repo.save_doctor(self.doctor)

        # Patients
        self.p1 = Patient(id="p1", name="Alice Wonderland", phone="555-1001", email="alice@magic.com")
        self.p2 = Patient(id="p2", name="Bob Robertson", phone="555-1002", email="bob@builder.com")
        self.p3 = Patient(id="p3", name="Charlie Brown", phone="555-1003", email="charlie@peanuts.com")
        self.repo.save_patient(self.p1)
        self.repo.save_patient(self.p2)
        self.repo.save_patient(self.p3)

        # Book an active appointment for Alice
        self.service.book_appointment(
            doctor_id="doc1",
            patient_id_or_name="p1",
            start_time=datetime(2026, 9, 23, 10, 0),
            end_time=datetime(2026, 9, 23, 10, 30),
            notes="Routine pediatric consultation",
        )

        # Book and cancel an appointment for Bob
        appt_bob = self.service.book_appointment(
            doctor_id="doc1",
            patient_id_or_name="p2",
            start_time=datetime(2026, 9, 23, 11, 0),
            end_time=datetime(2026, 9, 23, 11, 30),
            notes="Check allergy reaction",
        )
        self.service.cancel_appointment(appt_bob.id, reason="Symptoms cleared up")

    def test_search_by_exact_name_case_insensitive(self):
        """Exact name in any case matches the patient."""
        res_lower = self.service.search_patient_appointments("alice wonderland")
        res_upper = self.service.search_patient_appointments("ALICE WONDERLAND")
        res_mixed = self.service.search_patient_appointments("Alice Wonderland")

        self.assertEqual(len(res_lower), 1)
        self.assertEqual(len(res_upper), 1)
        self.assertEqual(len(res_mixed), 1)
        self.assertEqual(res_lower[0]["patient"]["name"], "Alice Wonderland")
        self.assertEqual(len(res_lower[0]["appointments"]), 1)
        self.assertEqual(res_lower[0]["appointments"][0]["status"], AppointmentStatus.CONFIRMED.value)

    def test_search_by_partial_substring(self):
        """Partial name query matches all patients containing that substring."""
        # 'obert' should match 'Bob Robertson'
        res = self.service.search_patient_appointments("obert")
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["patient"]["name"], "Bob Robertson")
        self.assertEqual(len(res[0]["appointments"]), 1)
        self.assertEqual(res[0]["appointments"][0]["status"], AppointmentStatus.CANCELLED_FREE.value)

    def test_search_returns_cancellation_and_fee_history(self):
        """Search results include fee history and cancellation metadata."""
        res = self.service.search_patient_appointments("bob")
        self.assertEqual(len(res), 1)
        appt_data = res[0]["appointments"][0]
        self.assertIn("cancellation", appt_data)
        self.assertEqual(appt_data["cancellation"]["reason"], "Symptoms cleared up")

    def test_search_empty_or_no_match(self):
        """Empty or non-matching query returns empty list without error."""
        self.assertEqual(self.service.search_patient_appointments(""), [])
        self.assertEqual(self.service.search_patient_appointments("   "), [])
        self.assertEqual(self.service.search_patient_appointments("Zaphod Beeblebrox"), [])


if __name__ == "__main__":
    unittest.main()

