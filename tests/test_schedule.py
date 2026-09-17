"""
Unit tests for the doctor's daily schedule view and free slot calculations.
"""

import unittest
from datetime import datetime

from clinic.models import Doctor, Patient
from clinic.repository import ClinicRepository
from clinic.service import ClinicService


class TestDoctorDaySchedule(unittest.TestCase):
    def setUp(self):
        self.repo = ClinicRepository(":memory:")
        self.service = ClinicService(self.repo)

        self.doctor = Doctor(
            id="doc1",
            name="Dr. Sarah Chen",
            specialty="Family Medicine",
            room="101",
            work_start_time="08:30",
            work_end_time="16:30",  # 8 hours = 480 minutes
            working_days=[0, 1, 2, 3, 4, 5, 6],
        )
        self.repo.save_doctor(self.doctor)

        self.pat1 = Patient(id="pat1", name="Alice", phone="111")
        self.pat2 = Patient(id="pat2", name="Bob", phone="222")
        self.repo.save_patient(self.pat1)
        self.repo.save_patient(self.pat2)

        self.target_date = datetime(2026, 9, 22)

    def test_empty_day_schedule_is_entirely_free(self):
        """When there are no bookings, the timeline is one continuous FREE block covering the shift."""
        sched = self.service.get_doctor_day_schedule(self.doctor.id, self.target_date)

        self.assertEqual(sched["booked_minutes"], 0)
        self.assertEqual(sched["free_minutes"], 480)
        self.assertEqual(sched["utilization_percent"], 0.0)
        self.assertEqual(len(sched["timeline"]), 1)
        self.assertEqual(sched["timeline"][0]["type"], "FREE")
        self.assertEqual(sched["timeline"][0]["duration_minutes"], 480)

    def test_schedule_timeline_with_appointments_and_gaps(self):
        """Tests that appointments slice the timeline cleanly into alternating FREE and BOOKED intervals."""
        # Appt 1: 09:00 - 09:30 (30 min)
        self.service.book_appointment(
            doctor_id=self.doctor.id,
            patient_id_or_name=self.pat1.id,
            start_time=datetime(2026, 9, 22, 9, 0),
            end_time=datetime(2026, 9, 22, 9, 30),
        )
        # Appt 2: 11:00 - 11:45 (45 min)
        self.service.book_appointment(
            doctor_id=self.doctor.id,
            patient_id_or_name=self.pat2.id,
            start_time=datetime(2026, 9, 22, 11, 0),
            end_time=datetime(2026, 9, 22, 11, 45),
        )

        sched = self.service.get_doctor_day_schedule(self.doctor.id, self.target_date)

        self.assertEqual(sched["booked_minutes"], 75)
        self.assertEqual(sched["free_minutes"], 405)
        self.assertEqual(sched["active_appointment_count"], 2)

        timeline = sched["timeline"]
        # Expected sequence:
        # 1. FREE: 08:30 - 09:00 (30 min)
        # 2. BOOKED: 09:00 - 09:30 (30 min, Alice)
        # 3. FREE: 09:30 - 11:00 (90 min)
        # 4. BOOKED: 11:00 - 11:45 (45 min, Bob)
        # 5. FREE: 11:45 - 16:30 (285 min)
        self.assertEqual(len(timeline), 5)

        self.assertEqual(timeline[0]["type"], "FREE")
        self.assertEqual(timeline[0]["duration_minutes"], 30)

        self.assertEqual(timeline[1]["type"], "BOOKED")
        self.assertEqual(timeline[1]["duration_minutes"], 30)
        self.assertEqual(timeline[1]["appointment"]["patient_name"], "Alice")

        self.assertEqual(timeline[2]["type"], "FREE")
        self.assertEqual(timeline[2]["duration_minutes"], 90)

        self.assertEqual(timeline[3]["type"], "BOOKED")
        self.assertEqual(timeline[3]["duration_minutes"], 45)

        self.assertEqual(timeline[4]["type"], "FREE")
        self.assertEqual(timeline[4]["duration_minutes"], 285)

    def test_available_slots_generator(self):
        """Generates valid bookable 30-min discrete slots within the free gaps."""
        self.service.book_appointment(
            doctor_id=self.doctor.id,
            patient_id_or_name=self.pat1.id,
            start_time=datetime(2026, 9, 22, 9, 0),
            end_time=datetime(2026, 9, 22, 10, 0),
        )

        slots = self.service.get_available_slots(self.doctor.id, self.target_date, slot_duration_minutes=30)
        # Shift is 08:30 - 16:30 with 09:00 - 10:00 booked.
        # Free interval 1: 08:30 - 09:00 -> 1 slot [08:30-09:00]
        # Free interval 2: 10:00 - 16:30 (390 min) -> 13 slots
        # Total = 14 slots
        self.assertEqual(len(slots), 14)
        self.assertEqual(slots[0]["formatted"], "08:30 - 09:00")
        self.assertEqual(slots[1]["formatted"], "10:00 - 10:30")


if __name__ == "__main__":
    unittest.main()

