"""
Unit tests for Level 3 — T2 (automation): Auto No-Show Marking and Clock API.
Validates that appointments are auto-marked as NO_SHOW 30 minutes after their start time
unless marked as COMPLETED or CANCELLED, and verifies REST API endpoints.
"""

from __future__ import annotations

import json
import threading
import time
import unittest
import urllib.request
from datetime import datetime, timedelta

from clinic.clock import SystemClock
from clinic.models import AppointmentStatus, Patient
from clinic.repository import ClinicRepository
from clinic.service import ClinicService
from web.server import create_server


class TestAutoNoShow(unittest.TestCase):
    def setUp(self):
        self.repo = ClinicRepository(":memory:")
        self.clock = SystemClock(initial_time=datetime(2026, 9, 21, 8, 0))
        self.service = ClinicService(self.repo, clock=self.clock)

        self.doctor = self.service.add_doctor(
            name="Dr. Robert Chase",
            specialty="Surgeon",
            room="Room 202",
            work_start_time="08:30",
            work_end_time="17:00",
            working_days=[0, 1, 2, 3, 4],
            doctor_id="doc_chase",
        )

        self.patient1 = Patient(id="pat_john", name="John Doe", phone="555-1111")
        self.patient2 = Patient(id="pat_jane", name="Jane Roe", phone="555-2222")
        self.repo.save_patient(self.patient1)
        self.repo.save_patient(self.patient2)

    def test_appointment_marked_no_show_after_30_minutes(self):
        """Appointment starting at 09:00 is marked NO_SHOW at 09:30 (30 min after start)."""
        appt = self.service.book_appointment(
            doctor_id=self.doctor.id,
            patient_id_or_name=self.patient1.id,
            start_time=datetime(2026, 9, 21, 9, 0),
            end_time=datetime(2026, 9, 21, 9, 30),
        )

        # 1. Advance to 09:20 (20 min after start) -> Still CONFIRMED
        self.service.advance_clock(datetime(2026, 9, 21, 9, 20))
        fetched = self.repo.get_appointment(appt.id)
        self.assertEqual(fetched.status, AppointmentStatus.CONFIRMED)

        # 2. Advance to 09:29 (29 min after start) -> Still CONFIRMED
        self.service.advance_clock(datetime(2026, 9, 21, 9, 29))
        fetched = self.repo.get_appointment(appt.id)
        self.assertEqual(fetched.status, AppointmentStatus.CONFIRMED)

        # 3. Advance to 09:30 (exactly 30 min after start) -> Transitions to NO_SHOW
        self.service.advance_clock(datetime(2026, 9, 21, 9, 30))
        fetched = self.repo.get_appointment(appt.id)
        self.assertEqual(fetched.status, AppointmentStatus.NO_SHOW)

    def test_completed_appointment_is_not_marked_no_show(self):
        """Appointments marked as COMPLETED are never transitioned to NO_SHOW."""
        appt = self.service.book_appointment(
            doctor_id=self.doctor.id,
            patient_id_or_name=self.patient1.id,
            start_time=datetime(2026, 9, 21, 9, 0),
            end_time=datetime(2026, 9, 21, 9, 30),
        )

        # Mark appointment as completed
        completed = self.service.complete_appointment(appt.id)
        self.assertEqual(completed.status, AppointmentStatus.COMPLETED)

        # Advance clock to 10:00 (60 minutes past start)
        self.service.advance_clock(datetime(2026, 9, 21, 10, 0))

        fetched = self.repo.get_appointment(appt.id)
        self.assertEqual(fetched.status, AppointmentStatus.COMPLETED)

    def test_cancelled_appointment_is_not_marked_no_show(self):
        """Cancelled appointments remain cancelled and are not overwritten by no-show job."""
        appt = self.service.book_appointment(
            doctor_id=self.doctor.id,
            patient_id_or_name=self.patient1.id,
            start_time=datetime(2026, 9, 21, 9, 0),
            end_time=datetime(2026, 9, 21, 9, 30),
        )
        self.service.cancel_appointment(appt.id)

        # Advance clock to 11:00
        self.service.advance_clock(datetime(2026, 9, 21, 11, 0))

        fetched = self.repo.get_appointment(appt.id)
        self.assertTrue(fetched.status.is_cancelled)
        self.assertNotEqual(fetched.status, AppointmentStatus.NO_SHOW)


class TestWebServerTwistsApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = ClinicRepository(":memory:")
        cls.clock = SystemClock(initial_time=datetime(2026, 9, 21, 6, 0))
        cls.service = ClinicService(cls.repo, clock=cls.clock)

        cls.doctor = cls.service.add_doctor(
            name="Dr. Lisa Cuddy",
            specialty="Endocrinology",
            room="Dean's Office",
            work_start_time="08:00",
            work_end_time="17:00",
            working_days=[0, 1, 2, 3, 4],
            doctor_id="doc_cuddy",
        )
        cls.patient = Patient(id="pat_sarah", name="Sarah Connor", phone="555-9999")
        cls.repo.save_patient(cls.patient)

        # Start background web server
        cls.port = 18090
        cls.server = create_server(cls.service, host="127.0.0.1", port=cls.port)
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def _http_get(self, path: str):
        url = f"http://127.0.0.1:{self.port}{path}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            data = resp.read().decode("utf-8")
            return resp.status, json.loads(data)

    def _http_post(self, path: str, payload: dict):
        url = f"http://127.0.0.1:{self.port}{path}"
        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data_bytes, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as resp:
                data = resp.read().decode("utf-8")
                return resp.status, json.loads(data)
        except urllib.error.HTTPError as e:
            data = e.read().decode("utf-8")
            return e.code, json.loads(data)

    def _http_delete(self, path: str):
        url = f"http://127.0.0.1:{self.port}{path}"
        req = urllib.request.Request(url, method="DELETE")
        with urllib.request.urlopen(req) as resp:
            data = resp.read().decode("utf-8")
            return resp.status, json.loads(data)

    def test_post_clock_and_outbox_api(self):
        """Test POST /clock advances time, triggers reminders into /outbox."""
        # Book appointment at 09:00 on 2026-09-21
        self.service.book_appointment(
            doctor_id=self.doctor.id,
            patient_id_or_name=self.patient.id,
            start_time=datetime(2026, 9, 21, 9, 0),
            end_time=datetime(2026, 9, 21, 9, 30),
        )

        # Advance clock via POST /clock
        status, resp = self._http_post("/clock", {"current_time": "2026-09-21T07:30:00"})
        self.assertEqual(status, 200)
        self.assertEqual(resp["status"], "ok")

        # Check GET /clock
        status, clock_resp = self._http_get("/clock")
        self.assertEqual(status, 200)
        self.assertEqual(clock_resp["current_time"], "2026-09-21T07:30:00")

        # Check GET /outbox
        status, outbox = self._http_get("/outbox")
        self.assertEqual(status, 200)
        self.assertTrue(len(outbox) >= 1)
        self.assertEqual(outbox[0]["recipient_name"], "Sarah Connor")

        # Test DELETE /outbox
        status, del_resp = self._http_delete("/outbox")
        self.assertEqual(status, 200)
        status, outbox_after = self._http_get("/outbox")
        self.assertEqual(len(outbox_after), 0)

    def test_reschedule_and_complete_api(self):
        """Test POST /api/appointments/<id>/reschedule and /complete endpoints."""
        appt = self.service.book_appointment(
            doctor_id=self.doctor.id,
            patient_id_or_name=self.patient.id,
            start_time=datetime(2026, 9, 21, 10, 0),
            end_time=datetime(2026, 9, 21, 10, 30),
        )

        # Reschedule via API
        status, resched_resp = self._http_post(
            f"/api/appointments/{appt.id}/reschedule",
            {"new_start_time": "2026-09-21T14:00:00", "duration_minutes": 30},
        )
        self.assertEqual(status, 200)
        self.assertTrue(resched_resp["success"])
        self.assertEqual(resched_resp["appointment"]["start_time"], "2026-09-21T14:00:00")

        # Complete via API
        status, comp_resp = self._http_post(
            f"/api/appointments/{appt.id}/complete",
            {},
        )
        self.assertEqual(status, 200)
        self.assertTrue(comp_resp["success"])
        self.assertEqual(comp_resp["appointment"]["status"], "COMPLETED")


if __name__ == "__main__":
    unittest.main()
