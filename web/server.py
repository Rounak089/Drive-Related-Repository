"""
Clinic Front Desk Web Server and REST API.
Zero-dependency implementation using Python's standard library.
"""

from __future__ import annotations

import json
import mimetypes
import os
import urllib.parse
from datetime import datetime, timedelta
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Optional

from clinic.models import AppointmentStatus
from clinic.service import ClinicService, ConflictError, NotFoundError, ValidationError

WEB_DIR = os.path.dirname(os.path.abspath(__file__))


class ClinicApiHandler(BaseHTTPRequestHandler):
    service: ClinicService

    def log_message(self, format: str, *args: Any) -> None:
        # Clean logging
        sys_time = datetime.now().strftime("%H:%M:%S")
        print(f"[{sys_time}] {self.command} {self.path} - {args[1] if len(args) > 1 else ''}")

    def _set_headers(self, status: int = 200, content_type: str = "application/json") -> None:
        self.send_response(status)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()

    def do_OPTIONS(self) -> None:
        self._set_headers(204)

    def _send_json(self, data: Any, status: int = 200) -> None:
        self._set_headers(status, "application/json")
        body = json.dumps(data, indent=2).encode("utf-8")
        self.wfile.write(body)

    def _send_error(self, message: str, status: int = 400, extra: Optional[Dict[str, Any]] = None) -> None:
        payload = {"error": message, "status": status}
        if extra:
            payload.update(extra)
        self._send_json(payload, status=status)

    def _parse_body(self) -> Dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            return {}
        raw = self.rfile.read(content_length)
        return json.loads(raw.decode("utf-8"))

    # ------------------ Router ------------------

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # Static assets
        if path in ("/", "/index.html"):
            return self._serve_static("index.html", "text/html")
        elif path == "/styles.css":
            return self._serve_static("styles.css", "text/css")
        elif path == "/app.js":
            return self._serve_static("app.js", "application/javascript")

        # Clock & Outbox Endpoints (Twists 2 & 3)
        if path in ("/clock", "/api/clock"):
            return self._send_json({"current_time": self.service.get_clock_time().isoformat()})

        elif path in ("/outbox", "/api/outbox"):
            outbox = self.service.get_outbox()
            return self._send_json(outbox)

        # API Endpoints
        elif path == "/api/doctors":
            doctors = [d.to_dict() for d in self.service.repo.list_doctors()]
            return self._send_json({"doctors": doctors})

        elif path == "/api/schedule":
            doctor_id = query.get("doctor_id", [""])[0]
            date_str = query.get("date", [""])[0]
            if not doctor_id:
                return self._send_error("doctor_id parameter is required", 400)
            try:
                target_date = datetime.strptime(date_str, "%Y-%m-%d") if date_str else datetime.now()
            except ValueError:
                return self._send_error("date must be in YYYY-MM-DD format", 400)

            try:
                sched = self.service.get_doctor_day_schedule(doctor_id, target_date)
                return self._send_json(sched)
            except NotFoundError as e:
                return self._send_error(str(e), 404)

        elif path == "/api/available-slots":
            doctor_id = query.get("doctor_id", [""])[0]
            date_str = query.get("date", [""])[0]
            duration = int(query.get("duration", ["30"])[0])
            if not doctor_id:
                return self._send_error("doctor_id parameter is required", 400)
            target_date = datetime.strptime(date_str, "%Y-%m-%d") if date_str else datetime.now()

            slots = self.service.get_available_slots(doctor_id, target_date, slot_duration_minutes=duration)
            return self._send_json({"slots": slots})

        elif path == "/api/patients/search":
            q = query.get("query", [""])[0]
            results = self.service.search_patient_appointments(q)
            return self._send_json({"results": results})

        elif path == "/api/ledger":
            records = self.service.repo.list_cancellation_records()
            total_fees = sum(r["fee"] for r in records if not r["waived"])
            total_waived = sum(r["fee"] for r in records if r["waived"])
            return self._send_json({
                "records": records,
                "summary": {
                    "total_cancellations": len(records),
                    "total_fees_collected": total_fees,
                    "total_fees_waived": total_waived,
                    "late_cancellations": sum(1 for r in records if r["is_late"]),
                    "free_cancellations": sum(1 for r in records if not r["is_late"]),
                }
            })

        elif path.startswith("/api/appointments/") and path.endswith("/preview-cancel"):
            appt_id = path.replace("/api/appointments/", "").replace("/preview-cancel", "")
            try:
                preview = self.service.preview_cancellation(appt_id)
                return self._send_json(preview)
            except NotFoundError as e:
                return self._send_error(str(e), 404)
            except ValidationError as ve:
                return self._send_error(str(ve), 400)

        # Fallback 404
        self._send_error(f"Route '{path}' not found", 404)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # Clock Advancement (Twists 2 & 3)
        if path in ("/clock", "/api/clock"):
            try:
                body = self._parse_body()
                time_val = (
                    body.get("current_time")
                    or body.get("time")
                    or body.get("timestamp")
                    or body.get("datetime")
                )
                if not time_val and isinstance(body, str):
                    time_val = body
                if not time_val:
                    return self._send_error("current_time / time is required in request body", 400)

                dt = self.service.advance_clock(time_val)
                return self._send_json({
                    "status": "ok",
                    "current_time": dt.isoformat(),
                    "message": f"Clock advanced to {dt.isoformat()}",
                })
            except Exception as ex:
                return self._send_error(f"Clock update error: {ex}", 400)

        elif path == "/api/doctors":
            # Onboard new doctor
            try:
                body = self._parse_body()
                name = body.get("name", "")
                specialty = body.get("specialty", "")
                room = body.get("room", "")
                work_start_time = body.get("work_start_time", "08:30")
                work_end_time = body.get("work_end_time", "17:00")
                working_days = body.get("working_days", [0, 1, 2, 3, 4])
                doctor_id = body.get("doctor_id")

                doctor = self.service.add_doctor(
                    name=name,
                    specialty=specialty,
                    room=room,
                    work_start_time=work_start_time,
                    work_end_time=work_end_time,
                    working_days=working_days,
                    doctor_id=doctor_id,
                )
                return self._send_json({"success": True, "doctor": doctor.to_dict()}, 201)
            except ValidationError as ve:
                return self._send_error(str(ve), 400)
            except ConflictError as ce:
                return self._send_error(str(ce), 409)
            except Exception as ex:
                return self._send_error(f"Internal error: {ex}", 500)

        elif path == "/api/appointments":
            # Book appointment
            try:
                body = self._parse_body()
                doctor_id = body.get("doctor_id")
                patient_name = body.get("patient_name")
                start_iso = body.get("start_time")
                duration = int(body.get("duration_minutes", 30))
                patient_phone = body.get("patient_phone", "")
                patient_email = body.get("patient_email", "")
                notes = body.get("notes", "")

                if not doctor_id or not patient_name or not start_iso:
                    return self._send_error("doctor_id, patient_name, and start_time are required", 400)

                start_time = datetime.fromisoformat(start_iso)
                end_time = start_time + timedelta(minutes=duration)

                appt = self.service.book_appointment(
                    doctor_id=doctor_id,
                    patient_id_or_name=patient_name,
                    start_time=start_time,
                    end_time=end_time,
                    patient_phone=patient_phone,
                    patient_email=patient_email,
                    notes=notes,
                )
                return self._send_json({"success": True, "appointment": appt.to_dict()}, 201)
            except ConflictError as ce:
                return self._send_error(
                    str(ce),
                    status=409,
                    extra={
                        "conflicting_appointment": ce.conflicting_appointment.to_dict() if ce.conflicting_appointment else None,
                        "suggested_slots": ce.suggested_slots,
                    }
                )
            except ValidationError as ve:
                return self._send_error(str(ve), 400)
            except NotFoundError as ne:
                return self._send_error(str(ne), 404)
            except Exception as ex:
                return self._send_error(f"Internal error: {ex}", 500)

        elif (path.startswith("/api/appointments/") or path.startswith("/appointments/")) and path.endswith("/reschedule"):
            # Reschedule appointment (Twist 1 / T6)
            clean_path = path.replace("/api/appointments/", "").replace("/appointments/", "")
            appt_id = clean_path.replace("/reschedule", "")
            try:
                body = self._parse_body()
                new_start_time = body.get("new_start_time") or body.get("start_time")
                new_end_time = body.get("new_end_time") or body.get("end_time")
                duration_minutes = body.get("duration_minutes")

                if not new_start_time:
                    return self._send_error("new_start_time (or start_time) is required", 400)

                updated_appt = self.service.reschedule_appointment(
                    appointment_id=appt_id,
                    new_start_time=new_start_time,
                    new_end_time=new_end_time,
                    duration_minutes=int(duration_minutes) if duration_minutes else None,
                )
                return self._send_json({"success": True, "appointment": updated_appt.to_dict()})
            except ConflictError as ce:
                return self._send_error(
                    str(ce),
                    status=409,
                    extra={
                        "conflicting_appointment": ce.conflicting_appointment.to_dict() if ce.conflicting_appointment else None,
                        "suggested_slots": ce.suggested_slots,
                    }
                )
            except NotFoundError as ne:
                return self._send_error(str(ne), 404)
            except ValidationError as ve:
                return self._send_error(str(ve), 400)
            except Exception as ex:
                return self._send_error(f"Internal error: {ex}", 500)

        elif (path.startswith("/api/appointments/") or path.startswith("/appointments/")) and path.endswith("/complete"):
            # Complete appointment
            clean_path = path.replace("/api/appointments/", "").replace("/appointments/", "")
            appt_id = clean_path.replace("/complete", "")
            try:
                completed_appt = self.service.complete_appointment(appt_id)
                return self._send_json({"success": True, "appointment": completed_appt.to_dict()})
            except NotFoundError as ne:
                return self._send_error(str(ne), 404)
            except ValidationError as ve:
                return self._send_error(str(ve), 400)
            except Exception as ex:
                return self._send_error(f"Internal error: {ex}", 500)

        elif path.startswith("/api/appointments/") and path.endswith("/cancel"):
            # Cancel appointment
            appt_id = path.replace("/api/appointments/", "").replace("/cancel", "")
            try:
                body = self._parse_body()
                reason = body.get("reason", "")
                waive = bool(body.get("waive", False))
                waiver_reason = body.get("waiver_reason", "")

                cancelled = self.service.cancel_appointment(
                    appointment_id=appt_id,
                    waive_fee=waive,
                    reason=reason,
                    waiver_reason=waiver_reason if waive else None,
                )
                return self._send_json({"success": True, "appointment": cancelled.to_dict()})
            except NotFoundError as ne:
                return self._send_error(str(ne), 404)
            except ValidationError as ve:
                return self._send_error(str(ve), 400)
            except Exception as ex:
                return self._send_error(f"Internal error: {ex}", 500)

        self._send_error(f"Endpoint '{path}' not found", 404)

    def do_DELETE(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path in ("/outbox", "/api/outbox"):
            self.service.clear_outbox()
            return self._send_json({"status": "ok", "message": "Outbox cleared"})

        self._send_error(f"Endpoint '{path}' not found", 404)

    def _serve_static(self, filename: str, content_type: str) -> None:
        filepath = os.path.join(WEB_DIR, filename)
        if not os.path.exists(filepath):
            return self._send_error(f"File {filename} not found", 404)
        with open(filepath, "rb") as f:
            content = f.read()
        self._set_headers(200, content_type)
        self.wfile.write(content)


def create_server(service: ClinicService, host: str = "127.0.0.1", port: int = 8000) -> ThreadingHTTPServer:
    class CustomHandler(ClinicApiHandler):
        pass

    CustomHandler.service = service
    server = ThreadingHTTPServer((host, port), CustomHandler)
    return server

