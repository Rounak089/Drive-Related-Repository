"""
Concurrency tests: Verifies that simultaneous booking attempts for the same doctor
and slot never result in double-booking (race condition safety).
"""

import os
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from clinic.models import Doctor, Patient
from clinic.repository import ClinicRepository
from clinic.service import ClinicService, ConflictError


class TestConcurrencySafety(unittest.TestCase):
    def setUp(self):
        # Use an on-disk SQLite file in WAL mode to test real multi-connection concurrency
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "clinic_concurrency.db")
        self.repo = ClinicRepository(self.db_path)
        self.service = ClinicService(self.repo)

        # Setup doctor
        self.doc = Doctor(
            id="doc_busy", name="Dr. Busy", specialty="Urgent Care", room="101",
            work_start_time="08:00", work_end_time="18:00", working_days=[0, 1, 2, 3, 4, 5, 6]
        )
        self.repo.save_doctor(self.doc)

        # Register 12 distinct patients
        self.patients = []
        for i in range(12):
            p = Patient(id=f"pat_{i}", name=f"Patient {i}", phone=f"555-000{i}")
            self.repo.save_patient(p)
            self.patients.append(p)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_concurrent_booking_for_same_slot_guarantees_single_winner(self):
        """
        When 10 threads simultaneously attempt to book the exact same slot
        for the same doctor, exactly ONE must succeed, and 9 must be rejected
        with ConflictError. Zero double-booking is tolerated.
        """
        target_slot_start = datetime(2026, 9, 28, 14, 0)
        target_slot_end = datetime(2026, 9, 28, 14, 30)

        successes = []
        conflicts = []
        errors = []

        barrier = threading.Barrier(10)

        def attempt_booking(patient_id: str):
            # Wait until all 10 threads are ready, then fire at the exact same millisecond
            barrier.wait()
            # Each thread uses a service instance connected to the same DB
            thread_service = ClinicService(self.repo)
            try:
                appt = thread_service.book_appointment(
                    doctor_id=self.doc.id,
                    patient_id_or_name=patient_id,
                    start_time=target_slot_start,
                    end_time=target_slot_end,
                    notes=f"Concurrent attempt by {patient_id}",
                )
                successes.append(appt)
            except ConflictError as ce:
                conflicts.append(str(ce))
            except Exception as e:
                errors.append(str(e))

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(attempt_booking, self.patients[i].id)
                for i in range(10)
            ]
            for f in futures:
                f.result()

        # Assertions
        self.assertEqual(len(errors), 0, f"Unexpected errors occurred: {errors}")
        self.assertEqual(len(successes), 1, f"Expected exactly 1 booking, got {len(successes)}")
        self.assertEqual(len(conflicts), 9, f"Expected 9 conflict rejections, got {len(conflicts)}")

        # Verify database state has strictly 1 confirmed appointment
        day_schedule = self.service.get_doctor_day_schedule(self.doc.id, target_slot_start)
        self.assertEqual(day_schedule["active_appointment_count"], 1)


if __name__ == "__main__":
    unittest.main()

