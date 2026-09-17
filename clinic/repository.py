"""
SQLite-backed persistence layer for clinic operations with atomic transaction safety.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Generator, List, Optional

from .models import (
    Appointment,
    AppointmentStatus,
    CancellationRecord,
    Doctor,
    Patient,
    TimeSlot,
)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS doctors (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    specialty TEXT NOT NULL,
    room TEXT NOT NULL,
    work_start_time TEXT NOT NULL,
    work_end_time TEXT NOT NULL,
    working_days TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS patients (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    phone TEXT NOT NULL,
    email TEXT DEFAULT '',
    date_of_birth TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS appointments (
    id TEXT PRIMARY KEY,
    doctor_id TEXT NOT NULL REFERENCES doctors(id),
    patient_id TEXT NOT NULL REFERENCES patients(id),
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    status TEXT NOT NULL,
    notes TEXT DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cancellations (
    appointment_id TEXT PRIMARY KEY REFERENCES appointments(id),
    cancelled_at TEXT NOT NULL,
    notice_hours REAL NOT NULL,
    fee REAL NOT NULL,
    is_late INTEGER NOT NULL,
    waived INTEGER NOT NULL,
    reason TEXT DEFAULT '',
    waiver_reason TEXT
);

CREATE INDEX IF NOT EXISTS idx_appt_doc_active 
    ON appointments(doctor_id, status, start_time, end_time);

CREATE INDEX IF NOT EXISTS idx_appt_patient_active 
    ON appointments(patient_id, status, start_time, end_time);

CREATE INDEX IF NOT EXISTS idx_patients_name 
    ON patients(name COLLATE NOCASE);
"""


class ClinicRepository:
    """
    Thread-safe repository using SQLite with WAL mode and immediate transactions
    to guarantee zero double-booking under concurrent front-desk operations.
    """

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self._lock = threading.RLock()
        self._mem_conn: Optional[sqlite3.Connection] = None

        if self.db_path == ":memory:":
            self._mem_conn = sqlite3.connect(
                ":memory:",
                check_same_thread=False,
                isolation_level=None
            )
            self._mem_conn.row_factory = sqlite3.Row
            self._mem_conn.execute("PRAGMA foreign_keys = ON;")

        self._init_db()

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Provides a configured SQLite connection with foreign keys and row factory."""
        if self._mem_conn is not None:
            with self._lock:
                yield self._mem_conn
        else:
            conn = sqlite3.connect(
                self.db_path,
                timeout=30.0,
                check_same_thread=False,
                isolation_level=None  # Managed explicitly with BEGIN
            )
            conn.row_factory = sqlite3.Row
            try:
                conn.execute("PRAGMA foreign_keys = ON;")
                conn.execute("PRAGMA journal_mode = WAL;")
                conn.execute("PRAGMA busy_timeout = 5000;")
                yield conn
            finally:
                conn.close()

    def _init_db(self) -> None:
        """Create database tables and indices."""
        with self._lock:
            with self.get_connection() as conn:
                conn.executescript(SCHEMA_SQL)

    # ------------------ Doctors ------------------

    def save_doctor(self, doctor: Doctor) -> None:
        with self._lock:
            with self.get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO doctors (id, name, specialty, room, work_start_time, work_end_time, working_days)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        name = excluded.name,
                        specialty = excluded.specialty,
                        room = excluded.room,
                        work_start_time = excluded.work_start_time,
                        work_end_time = excluded.work_end_time,
                        working_days = excluded.working_days;
                    """,
                    (
                        doctor.id,
                        doctor.name,
                        doctor.specialty,
                        doctor.room,
                        doctor.work_start_time,
                        doctor.work_end_time,
                        json.dumps(doctor.working_days),
                    ),
                )

    def get_doctor(self, doctor_id: str) -> Optional[Doctor]:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM doctors WHERE id = ?", (doctor_id,)).fetchone()
            if not row:
                return None
            return Doctor(
                id=row["id"],
                name=row["name"],
                specialty=row["specialty"],
                room=row["room"],
                work_start_time=row["work_start_time"],
                work_end_time=row["work_end_time"],
                working_days=json.loads(row["working_days"]),
            )

    def list_doctors(self) -> List[Doctor]:
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM doctors ORDER BY name ASC").fetchall()
            return [
                Doctor(
                    id=row["id"],
                    name=row["name"],
                    specialty=row["specialty"],
                    room=row["room"],
                    work_start_time=row["work_start_time"],
                    work_end_time=row["work_end_time"],
                    working_days=json.loads(row["working_days"]),
                )
                for row in rows
            ]

    # ------------------ Patients ------------------

    def save_patient(self, patient: Patient) -> None:
        with self._lock:
            with self.get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO patients (id, name, phone, email, date_of_birth)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        name = excluded.name,
                        phone = excluded.phone,
                        email = excluded.email,
                        date_of_birth = excluded.date_of_birth;
                    """,
                    (patient.id, patient.name, patient.phone, patient.email, patient.date_of_birth),
                )

    def get_patient(self, patient_id: str) -> Optional[Patient]:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone()
            if not row:
                return None
            return Patient(
                id=row["id"],
                name=row["name"],
                phone=row["phone"],
                email=row["email"],
                date_of_birth=row["date_of_birth"],
            )

    def search_patients_by_name(self, name_query: str) -> List[Patient]:
        with self.get_connection() as conn:
            query = f"%{name_query.strip()}%"
            rows = conn.execute(
                "SELECT * FROM patients WHERE name LIKE ? ORDER BY name ASC",
                (query,),
            ).fetchall()
            return [
                Patient(
                    id=row["id"],
                    name=row["name"],
                    phone=row["phone"],
                    email=row["email"],
                    date_of_birth=row["date_of_birth"],
                )
                for row in rows
            ]

    def list_patients(self) -> List[Patient]:
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM patients ORDER BY name ASC").fetchall()
            return [
                Patient(
                    id=row["id"],
                    name=row["name"],
                    phone=row["phone"],
                    email=row["email"],
                    date_of_birth=row["date_of_birth"],
                )
                for row in rows
            ]

    # ------------------ Appointments & Conflict Queries ------------------

    def find_conflicting_appointments(
        self,
        doctor_id: str,
        start_time: datetime,
        end_time: datetime,
        exclude_appointment_id: Optional[str] = None,
        conn: Optional[sqlite3.Connection] = None,
    ) -> List[Appointment]:
        """
        Finds any ACTIVE appointments for the doctor that overlap with [start_time, end_time).
        Mathematical overlap condition for [s1, e1) and [s2, e2):
        s1 < e2 AND e1 > s2
        """
        start_iso = start_time.isoformat()
        end_iso = end_time.isoformat()

        sql = """
            SELECT a.*, d.name AS doctor_name, p.name AS patient_name, p.phone AS patient_phone
            FROM appointments a
            JOIN doctors d ON a.doctor_id = d.id
            JOIN patients p ON a.patient_id = p.id
            WHERE a.doctor_id = ?
              AND a.status IN ('CONFIRMED', 'COMPLETED')
              AND a.start_time < ?
              AND a.end_time > ?
        """
        params = [doctor_id, end_iso, start_iso]

        if exclude_appointment_id:
            sql += " AND a.id != ?"
            params.append(exclude_appointment_id)

        if conn is not None:
            rows = conn.execute(sql, params).fetchall()
            return [self._row_to_appointment(row) for row in rows]
        else:
            with self.get_connection() as c:
                rows = c.execute(sql, params).fetchall()
                return [self._row_to_appointment(row) for row in rows]

    def find_patient_conflicting_appointments(
        self,
        patient_id: str,
        start_time: datetime,
        end_time: datetime,
        exclude_appointment_id: Optional[str] = None,
        conn: Optional[sqlite3.Connection] = None,
    ) -> List[Appointment]:
        """Checks if the patient already has an active appointment at the given time."""
        start_iso = start_time.isoformat()
        end_iso = end_time.isoformat()

        sql = """
            SELECT a.*, d.name AS doctor_name, p.name AS patient_name, p.phone AS patient_phone
            FROM appointments a
            JOIN doctors d ON a.doctor_id = d.id
            JOIN patients p ON a.patient_id = p.id
            WHERE a.patient_id = ?
              AND a.status IN ('CONFIRMED', 'COMPLETED')
              AND a.start_time < ?
              AND a.end_time > ?
        """
        params = [patient_id, end_iso, start_iso]

        if exclude_appointment_id:
            sql += " AND a.id != ?"
            params.append(exclude_appointment_id)

        if conn is not None:
            rows = conn.execute(sql, params).fetchall()
            return [self._row_to_appointment(row) for row in rows]
        else:
            with self.get_connection() as c:
                rows = c.execute(sql, params).fetchall()
                return [self._row_to_appointment(row) for row in rows]

    def insert_appointment_atomic(
        self,
        appointment: Appointment,
    ) -> tuple[bool, Optional[Appointment]]:
        """
        Atomically checks for doctor overlap within an IMMEDIATE transaction
        and inserts the appointment.
        Returns (True, None) if booked successfully.
        Returns (False, conflicting_appointment) if an overlap was detected.
        """
        with self._lock:
            with self.get_connection() as conn:
                conn.execute("BEGIN IMMEDIATE;")
                try:
                    conflicts = self.find_conflicting_appointments(
                        doctor_id=appointment.doctor_id,
                        start_time=appointment.start_time,
                        end_time=appointment.end_time,
                        conn=conn,
                    )
                    if conflicts:
                        conn.execute("ROLLBACK;")
                        return False, conflicts[0]

                    conn.execute(
                        """
                        INSERT INTO appointments (id, doctor_id, patient_id, start_time, end_time, status, notes, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            appointment.id,
                            appointment.doctor_id,
                            appointment.patient_id,
                            appointment.start_time.isoformat(),
                            appointment.end_time.isoformat(),
                            appointment.status.value,
                            appointment.notes,
                            appointment.created_at.isoformat(),
                        ),
                    )
                    conn.execute("COMMIT;")
                    return True, None
                except Exception:
                    conn.execute("ROLLBACK;")
                    raise

    def get_appointment(self, appointment_id: str) -> Optional[Appointment]:
        with self.get_connection() as conn:
            row = conn.execute(
                """
                SELECT a.*, d.name AS doctor_name, p.name AS patient_name, p.phone AS patient_phone,
                       c.cancelled_at, c.notice_hours, c.fee, c.is_late, c.waived, c.reason, c.waiver_reason
                FROM appointments a
                JOIN doctors d ON a.doctor_id = d.id
                JOIN patients p ON a.patient_id = p.id
                LEFT JOIN cancellations c ON a.id = c.appointment_id
                WHERE a.id = ?
                """,
                (appointment_id,),
            ).fetchone()
            if not row:
                return None
            return self._row_to_appointment(row)

    def cancel_appointment_atomic(
        self,
        appointment_id: str,
        record: CancellationRecord,
        new_status: AppointmentStatus,
    ) -> None:
        """
        Atomically updates the appointment status to cancelled and persists
        the CancellationRecord, freeing the doctor's slot immediately.
        """
        with self._lock:
            with self.get_connection() as conn:
                conn.execute("BEGIN IMMEDIATE;")
                try:
                    conn.execute(
                        "UPDATE appointments SET status = ? WHERE id = ?",
                        (new_status.value, appointment_id),
                    )
                    conn.execute(
                        """
                        INSERT INTO cancellations (
                            appointment_id, cancelled_at, notice_hours, fee, is_late, waived, reason, waiver_reason
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(appointment_id) DO UPDATE SET
                            cancelled_at = excluded.cancelled_at,
                            notice_hours = excluded.notice_hours,
                            fee = excluded.fee,
                            is_late = excluded.is_late,
                            waived = excluded.waived,
                            reason = excluded.reason,
                            waiver_reason = excluded.waiver_reason;
                        """,
                        (
                            record.appointment_id,
                            record.cancelled_at.isoformat(),
                            record.notice_hours,
                            record.fee,
                            1 if record.is_late else 0,
                            1 if record.waived else 0,
                            record.reason,
                            record.waiver_reason,
                        ),
                    )
                    conn.execute("COMMIT;")
                except Exception:
                    conn.execute("ROLLBACK;")
                    raise

    def get_doctor_appointments_for_day(
        self,
        doctor_id: str,
        target_date: datetime,
        include_cancelled: bool = False,
    ) -> List[Appointment]:
        """Fetches all appointments for the doctor on the specified day in chronological order."""
        day_start = datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0).isoformat()
        day_end = datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59).isoformat()

        sql = """
            SELECT a.*, d.name AS doctor_name, p.name AS patient_name, p.phone AS patient_phone,
                   c.cancelled_at, c.notice_hours, c.fee, c.is_late, c.waived, c.reason, c.waiver_reason
            FROM appointments a
            JOIN doctors d ON a.doctor_id = d.id
            JOIN patients p ON a.patient_id = p.id
            LEFT JOIN cancellations c ON a.id = c.appointment_id
            WHERE a.doctor_id = ?
              AND a.start_time >= ?
              AND a.start_time <= ?
        """
        params: List[Any] = [doctor_id, day_start, day_end]

        if not include_cancelled:
            sql += " AND a.status IN ('CONFIRMED', 'COMPLETED')"

        sql += " ORDER BY a.start_time ASC"

        with self.get_connection() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [self._row_to_appointment(row) for row in rows]

    def get_patient_appointments(
        self,
        patient_id: str,
    ) -> List[Appointment]:
        """Fetches all appointments for a patient (upcoming, past, cancelled) ordered by start_time."""
        sql = """
            SELECT a.*, d.name AS doctor_name, p.name AS patient_name, p.phone AS patient_phone,
                   c.cancelled_at, c.notice_hours, c.fee, c.is_late, c.waived, c.reason, c.waiver_reason
            FROM appointments a
            JOIN doctors d ON a.doctor_id = d.id
            JOIN patients p ON a.patient_id = p.id
            LEFT JOIN cancellations c ON a.id = c.appointment_id
            WHERE a.patient_id = ?
            ORDER BY a.start_time DESC
        """
        with self.get_connection() as conn:
            rows = conn.execute(sql, (patient_id,)).fetchall()
            return [self._row_to_appointment(row) for row in rows]

    def list_cancellation_records(self) -> List[Dict[str, Any]]:
        """List all cancellation records with appointment, patient, and doctor metadata."""
        sql = """
            SELECT c.*, a.start_time, a.end_time, a.status,
                   d.name AS doctor_name, p.name AS patient_name, p.phone AS patient_phone
            FROM cancellations c
            JOIN appointments a ON c.appointment_id = a.id
            JOIN doctors d ON a.doctor_id = d.id
            JOIN patients p ON a.patient_id = p.id
            ORDER BY c.cancelled_at DESC
        """
        with self.get_connection() as conn:
            rows = conn.execute(sql).fetchall()
            return [
                {
                    "appointment_id": row["appointment_id"],
                    "cancelled_at": row["cancelled_at"],
                    "notice_hours": row["notice_hours"],
                    "fee": row["fee"],
                    "is_late": bool(row["is_late"]),
                    "waived": bool(row["waived"]),
                    "reason": row["reason"],
                    "waiver_reason": row["waiver_reason"],
                    "start_time": row["start_time"],
                    "end_time": row["end_time"],
                    "doctor_name": row["doctor_name"],
                    "patient_name": row["patient_name"],
                    "patient_phone": row["patient_phone"],
                    "status": row["status"],
                }
                for row in rows
            ]

    def _row_to_appointment(self, row: sqlite3.Row) -> Appointment:
        cancellation = None
        if "cancelled_at" in row.keys() and row["cancelled_at"] is not None:
            cancellation = CancellationRecord(
                appointment_id=row["id"],
                cancelled_at=datetime.fromisoformat(row["cancelled_at"]),
                notice_hours=row["notice_hours"],
                fee=row["fee"],
                is_late=bool(row["is_late"]),
                waived=bool(row["waived"]),
                reason=row["reason"] or "",
                waiver_reason=row["waiver_reason"],
            )

        return Appointment(
            id=row["id"],
            doctor_id=row["doctor_id"],
            patient_id=row["patient_id"],
            start_time=datetime.fromisoformat(row["start_time"]),
            end_time=datetime.fromisoformat(row["end_time"]),
            status=AppointmentStatus(row["status"]),
            notes=row["notes"] or "",
            created_at=datetime.fromisoformat(row["created_at"]),
            doctor_name=row["doctor_name"] if "doctor_name" in row.keys() else None,
            patient_name=row["patient_name"] if "patient_name" in row.keys() else None,
            patient_phone=row["patient_phone"] if "patient_phone" in row.keys() else None,
            cancellation=cancellation,
        )

