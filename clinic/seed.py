"""
Seed data generator for demo and testing.
Populates realistic doctors, patients, appointments, and cancellation records.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from .models import AppointmentStatus, Doctor, Patient
from .repository import ClinicRepository
from .service import ClinicService


def seed_clinic_data(service: ClinicService, base_date: Optional[datetime] = None) -> None:
    """Populates the repository with realistic clinic data anchored to base_date (defaults to now)."""
    now = base_date or datetime.now()
    today = datetime(now.year, now.month, now.day)
    tomorrow = today + timedelta(days=1)
    day_after = today + timedelta(days=2)

    repo = service.repo

    # 1. Doctors
    doctors = [
        Doctor(
            id="doc_chen",
            name="Dr. Sarah Chen",
            specialty="General Practice & Family Medicine",
            room="Room 101",
            work_start_time="08:30",
            work_end_time="16:30",
            working_days=[0, 1, 2, 3, 4, 5],
        ),
        Doctor(
            id="doc_vance",
            name="Dr. Marcus Vance",
            specialty="Pediatrics",
            room="Room 204",
            work_start_time="09:00",
            work_end_time="17:00",
            working_days=[0, 1, 2, 3, 4],
        ),
        Doctor(
            id="doc_rostova",
            name="Dr. Elena Rostova",
            specialty="Cardiology",
            room="Room 310",
            work_start_time="08:00",
            work_end_time="15:00",
            working_days=[0, 1, 2, 3, 4],
        ),
    ]
    for d in doctors:
        repo.save_doctor(d)

    # 2. Patients
    patients = [
        Patient(id="pat_alice", name="Alice Smith", phone="555-0101", email="alice@example.com", date_of_birth="1988-04-12"),
        Patient(id="pat_bob", name="Bob Johnson", phone="555-0102", email="bob@example.com", date_of_birth="1975-11-23"),
        Patient(id="pat_charlie", name="Charlie Brown", phone="555-0103", email="charlie@example.com", date_of_birth="1995-02-18"),
        Patient(id="pat_diana", name="Diana Prince", phone="555-0104", email="diana@example.com", date_of_birth="1982-08-30"),
        Patient(id="pat_edward", name="Edward Miller", phone="555-0105", email="edward@example.com", date_of_birth="1963-06-05"),
        Patient(id="pat_fiona", name="Fiona Gallagher", phone="555-0106", email="fiona@example.com", date_of_birth="2000-10-15"),
    ]
    for p in patients:
        repo.save_patient(p)

    # 3. Appointments for Today
    # Dr. Chen
    service.book_appointment(
        doctor_id="doc_chen",
        patient_id_or_name="pat_alice",
        start_time=today.replace(hour=9, minute=0),
        end_time=today.replace(hour=9, minute=30),
        notes="Annual physical checkup",
        allow_outside_shift=True,
    )
    service.book_appointment(
        doctor_id="doc_chen",
        patient_id_or_name="pat_bob",
        start_time=today.replace(hour=10, minute=0),
        end_time=today.replace(hour=10, minute=45),
        notes="Hypertension follow-up",
        allow_outside_shift=True,
    )
    # Book and cancel one for Dr. Chen (cancelled in good time)
    appt_chen_cancel = service.book_appointment(
        doctor_id="doc_chen",
        patient_id_or_name="pat_charlie",
        start_time=today.replace(hour=13, minute=0),
        end_time=today.replace(hour=13, minute=30),
        notes="Routine consultation",
        allow_outside_shift=True,
    )
    service.cancel_appointment(
        appointment_id=appt_chen_cancel.id,
        cancellation_time=today - timedelta(days=2),  # 48 hours notice -> Free
        reason="Patient rescheduled due to work trip",
    )

    # Now someone else books into a slot later in the day
    service.book_appointment(
        doctor_id="doc_chen",
        patient_id_or_name="pat_diana",
        start_time=today.replace(hour=14, minute=0),
        end_time=today.replace(hour=14, minute=30),
        notes="Lab results review",
        allow_outside_shift=True,
    )

    # Dr. Vance
    service.book_appointment(
        doctor_id="doc_vance",
        patient_id_or_name="pat_edward",
        start_time=today.replace(hour=9, minute=30),
        end_time=today.replace(hour=10, minute=15),
        notes="Child vaccination and wellness check",
        allow_outside_shift=True,
    )
    # Book and late-cancel for Dr. Vance (less than 24h notice -> $25 fee)
    appt_vance_cancel = service.book_appointment(
        doctor_id="doc_vance",
        patient_id_or_name="pat_fiona",
        start_time=today.replace(hour=11, minute=0),
        end_time=today.replace(hour=11, minute=30),
        notes="Ear ache evaluation",
        allow_outside_shift=True,
    )
    service.cancel_appointment(
        appointment_id=appt_vance_cancel.id,
        cancellation_time=today.replace(hour=8, minute=0),  # Only 3 hours notice -> Late fee!
        reason="Woke up feeling better, called morning of",
    )

    # Dr. Rostova
    service.book_appointment(
        doctor_id="doc_rostova",
        patient_id_or_name="pat_bob",
        start_time=today.replace(hour=11, minute=30),
        end_time=today.replace(hour=12, minute=15),
        notes="ECG and stress test follow-up",
        allow_outside_shift=True,
    )

    # 4. Tomorrow appointments (for booking and testing future cancellation rules)
    service.book_appointment(
        doctor_id="doc_chen",
        patient_id_or_name="pat_fiona",
        start_time=tomorrow.replace(hour=9, minute=30),
        end_time=tomorrow.replace(hour=10, minute=0),
        notes="Follow up",
        allow_outside_shift=True,
    )
    service.book_appointment(
        doctor_id="doc_vance",
        patient_id_or_name="pat_alice",
        start_time=tomorrow.replace(hour=10, minute=0),
        end_time=tomorrow.replace(hour=10, minute=45),
        notes="Well-child visit",
        allow_outside_shift=True,
    )
    service.book_appointment(
        doctor_id="doc_rostova",
        patient_id_or_name="pat_charlie",
        start_time=day_after.replace(hour=9, minute=0),
        end_time=day_after.replace(hour=9, minute=45),
        notes="Cardiac screening",
        allow_outside_shift=True,
    )

