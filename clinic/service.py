"""
High-level Clinic Service orchestrating conflict-free booking, cancellation rules,
day schedules, and patient search.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from .models import (
    Appointment,
    AppointmentStatus,
    Doctor,
    Patient,
    TimeSlot,
)
from .policy import CancellationPolicy
from .repository import ClinicRepository


class ClinicError(Exception):
    """Base exception for clinic domain errors."""
    pass


class NotFoundError(ClinicError):
    """Raised when an entity (doctor, patient, appointment) is not found."""
    pass


class ValidationError(ClinicError):
    """Raised when request data fails domain validation rules."""
    pass


class ConflictError(ClinicError):
    """Raised when an appointment conflicts with an existing booking."""
    def __init__(self, message: str, conflicting_appointment: Optional[Appointment] = None, suggested_slots: Optional[List[Dict[str, Any]]] = None):
        super().__init__(message)
        self.conflicting_appointment = conflicting_appointment
        self.suggested_slots = suggested_slots or []


class ClinicService:
    def __init__(
        self,
        repository: ClinicRepository,
        policy: Optional[CancellationPolicy] = None,
    ):
        self.repo = repository
        self.policy = policy or CancellationPolicy(cutoff_hours=24.0, late_fee=25.0)

    # ------------------ Doctor Management ------------------

    def add_doctor(
        self,
        name: str,
        specialty: str,
        room: str,
        work_start_time: str = "08:30",
        work_end_time: str = "17:00",
        working_days: Optional[List[int]] = None,
        doctor_id: Optional[str] = None,
    ) -> Doctor:
        """
        Onboards a new doctor to the clinic.
        Validates doctor profile, operating shifts, and working days.
        """
        clean_name = name.strip()
        if not clean_name:
            raise ValidationError("Doctor name cannot be empty.")
        if not clean_name.startswith("Dr."):
            clean_name = f"Dr. {clean_name}"

        clean_specialty = specialty.strip()
        if not clean_specialty:
            raise ValidationError("Specialty / Department cannot be empty.")

        clean_room = room.strip()
        if not clean_room:
            raise ValidationError("Room / Office location cannot be empty.")

        # Validate shift times
        try:
            s_h, s_m = map(int, work_start_time.split(":"))
            e_h, e_m = map(int, work_end_time.split(":"))
            if not (0 <= s_h <= 23 and 0 <= s_m <= 59 and 0 <= e_h <= 23 and 0 <= e_m <= 59):
                raise ValueError()
        except Exception:
            raise ValidationError(
                f"Invalid shift time format. Must be HH:MM (got start='{work_start_time}', end='{work_end_time}')."
            )

        if (s_h * 60 + s_m) >= (e_h * 60 + e_m):
            raise ValidationError(
                f"Shift start time ({work_start_time}) must be strictly earlier than shift end time ({work_end_time})."
            )

        # Validate working days (0=Mon, 6=Sun)
        if working_days is None or len(working_days) == 0:
            days = [0, 1, 2, 3, 4]  # Default Mon-Fri
        else:
            days = []
            for d in working_days:
                if not isinstance(d, int) or d < 0 or d > 6:
                    raise ValidationError(f"Invalid working day: {d}. Must be an integer between 0 (Monday) and 6 (Sunday).")
                if d not in days:
                    days.append(d)
            days.sort()

        if not doctor_id:
            slug = "".join(c for c in clean_name.replace("Dr.", "").strip().lower().replace(" ", "_") if c.isalnum() or c == "_")
            slug = slug[:12] or "new"
            doctor_id = f"doc_{slug}_{uuid.uuid4().hex[:4]}"

        # Check existing doctor with same ID
        if self.repo.get_doctor(doctor_id):
            raise ConflictError(f"A doctor with ID '{doctor_id}' already exists.")

        doctor = Doctor(
            id=doctor_id,
            name=clean_name,
            specialty=clean_specialty,
            room=clean_room,
            work_start_time=work_start_time,
            work_end_time=work_end_time,
            working_days=days,
        )
        self.repo.save_doctor(doctor)
        return doctor

    # ------------------ Booking ------------------

    def book_appointment(
        self,
        doctor_id: str,
        patient_id_or_name: str,
        start_time: datetime,
        end_time: datetime,
        patient_phone: str = "",
        patient_email: str = "",
        notes: str = "",
        allow_outside_shift: bool = False,
    ) -> Appointment:
        """
        Books an appointment with strict overlap validation.
        Guarantees:
        1. Start time must precede end time.
        2. Doctor must exist.
        3. Within doctor's shift (unless overridden).
        4. Patient must not have a conflicting appointment at the same time.
        5. Zero overlap with any active appointment for this doctor.
        """
        if start_time >= end_time:
            raise ValidationError(
                f"Invalid duration: start_time ({start_time.strftime('%H:%M')}) "
                f"must be strictly earlier than end_time ({end_time.strftime('%H:%M')})."
            )

        doctor = self.repo.get_doctor(doctor_id)
        if not doctor:
            raise NotFoundError(f"Doctor with ID '{doctor_id}' was not found.")

        # Shift validation
        shift_start, shift_end = doctor.get_shift_times(start_time)
        if not allow_outside_shift:
            if not doctor.is_working_on(start_time):
                raise ValidationError(
                    f"Dr. {doctor.name} does not have clinic hours on {start_time.strftime('%A')}."
                )
            if start_time < shift_start or end_time > shift_end:
                raise ValidationError(
                    f"Booking [{start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')}] "
                    f"is outside Dr. {doctor.name}'s working hours "
                    f"[{doctor.work_start_time} - {doctor.work_end_time}]."
                )

        # Resolve or create patient
        patient = self._resolve_or_create_patient(
            patient_id_or_name,
            phone=patient_phone,
            email=patient_email,
        )

        # Check patient-side overlap (patient cannot see two doctors at once)
        patient_conflicts = self.repo.find_patient_conflicting_appointments(
            patient_id=patient.id,
            start_time=start_time,
            end_time=end_time,
        )
        if patient_conflicts:
            pc = patient_conflicts[0]
            raise ConflictError(
                f"Patient '{patient.name}' is already booked with Dr. {pc.doctor_name} "
                f"from {pc.start_time.strftime('%H:%M')} to {pc.end_time.strftime('%H:%M')}."
            )

        # Create appointment model
        appt_id = f"apt_{uuid.uuid4().hex[:10]}"
        appointment = Appointment(
            id=appt_id,
            doctor_id=doctor.id,
            patient_id=patient.id,
            start_time=start_time,
            end_time=end_time,
            status=AppointmentStatus.CONFIRMED,
            notes=notes,
            created_at=datetime.now(),
            doctor_name=doctor.name,
            patient_name=patient.name,
            patient_phone=patient.phone,
        )

        # Atomic insert with doctor overlap prevention
        success, conflict = self.repo.insert_appointment_atomic(appointment)
        if not success and conflict:
            # Find nearest alternative slots for convenience
            suggested = self.get_available_slots(
                doctor_id=doctor.id,
                target_date=start_time,
                slot_duration_minutes=appointment.slot.duration_minutes,
            )
            doc_display = doctor.name if doctor.name.startswith("Dr.") else f"Dr. {doctor.name}"
            raise ConflictError(
                f"Double-booking prevented! {doc_display} is already booked from "
                f"{conflict.start_time.strftime('%H:%M')} to {conflict.end_time.strftime('%H:%M')} "
                f"(Patient: {conflict.patient_name}).",
                conflicting_appointment=conflict,
                suggested_slots=suggested[:3],
            )

        return appointment

    # ------------------ Cancellations ------------------

    def preview_cancellation(
        self,
        appointment_id: str,
        as_of: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Calculates late fee and notice for an appointment without cancelling it."""
        appointment = self.repo.get_appointment(appointment_id)
        if not appointment:
            raise NotFoundError(f"Appointment '{appointment_id}' not found.")
        if appointment.status.is_cancelled:
            raise ValidationError(f"Appointment is already cancelled ({appointment.status.value}).")

        preview = self.policy.preview(appointment.start_time, as_of=as_of)
        preview["appointment_id"] = appointment.id
        preview["doctor_name"] = appointment.doctor_name
        preview["patient_name"] = appointment.patient_name
        return preview

    def cancel_appointment(
        self,
        appointment_id: str,
        cancellation_time: Optional[datetime] = None,
        waive_fee: bool = False,
        reason: str = "",
        waiver_reason: Optional[str] = None,
    ) -> Appointment:
        """
        Cancels an appointment, evaluating the cancellation policy rules.
        If cancelled with >= cutoff notice: Free cancellation ($0).
        If cancelled with < cutoff notice: Assesses late fee ($25), unless waived.
        The slot is freed immediately for other patients.
        """
        appointment = self.repo.get_appointment(appointment_id)
        if not appointment:
            raise NotFoundError(f"Appointment '{appointment_id}' was not found.")

        if appointment.status.is_cancelled:
            raise ValidationError(
                f"Appointment '{appointment_id}' has already been cancelled."
            )

        record, new_status = self.policy.evaluate(
            appointment_id=appointment.id,
            appointment_start=appointment.start_time,
            cancellation_time=cancellation_time,
            waive_fee=waive_fee,
            reason=reason,
            waiver_reason=waiver_reason,
        )

        self.repo.cancel_appointment_atomic(appointment_id, record, new_status)
        appointment.status = new_status
        appointment.cancellation = record
        return appointment

    # ------------------ Doctor's Day Schedule ------------------

    def get_doctor_day_schedule(
        self,
        doctor_id: str,
        target_date: datetime,
        include_cancelled: bool = True,
    ) -> Dict[str, Any]:
        """
        Provides the front desk with a doctor's full day schedule.
        Breaks down the entire shift into contiguous timeline blocks:
        - Booked appointments (with patient and time details)
        - Open free gaps available for new bookings
        - Cancelled appointments (if include_cancelled is True)
        """
        doctor = self.repo.get_doctor(doctor_id)
        if not doctor:
            raise NotFoundError(f"Doctor '{doctor_id}' was not found.")

        shift_start, shift_end = doctor.get_shift_times(target_date)
        is_working_day = doctor.is_working_on(target_date)

        # Fetch active appointments
        active_appts = self.repo.get_doctor_appointments_for_day(
            doctor_id=doctor_id,
            target_date=target_date,
            include_cancelled=False,
        )

        timeline: List[Dict[str, Any]] = []
        current_cursor = shift_start
        total_booked_minutes = 0

        for appt in active_appts:
            # Free gap before this appointment
            if appt.start_time > current_cursor:
                gap_duration = int((appt.start_time - current_cursor).total_seconds() // 60)
                if gap_duration > 0:
                    timeline.append({
                        "type": "FREE",
                        "start_time": current_cursor.isoformat(),
                        "end_time": appt.start_time.isoformat(),
                        "duration_minutes": gap_duration,
                    })

            # The booked appointment
            appt_duration = appt.slot.duration_minutes
            total_booked_minutes += appt_duration
            timeline.append({
                "type": "BOOKED",
                "start_time": appt.start_time.isoformat(),
                "end_time": appt.end_time.isoformat(),
                "duration_minutes": appt_duration,
                "appointment": appt.to_dict(),
            })

            # Advance cursor
            if appt.end_time > current_cursor:
                current_cursor = appt.end_time

        # Free gap after the last appointment until shift end
        if current_cursor < shift_end:
            gap_duration = int((shift_end - current_cursor).total_seconds() // 60)
            if gap_duration > 0:
                timeline.append({
                    "type": "FREE",
                    "start_time": current_cursor.isoformat(),
                    "end_time": shift_end.isoformat(),
                    "duration_minutes": gap_duration,
                })

        total_shift_minutes = int((shift_end - shift_start).total_seconds() // 60)
        total_free_minutes = max(0, total_shift_minutes - total_booked_minutes)
        utilization = (
            round((total_booked_minutes / total_shift_minutes) * 100, 1)
            if total_shift_minutes > 0
            else 0.0
        )

        # Also get cancelled appointments for history/audit view if requested
        cancelled_appts = []
        if include_cancelled:
            all_appts = self.repo.get_doctor_appointments_for_day(
                doctor_id=doctor_id,
                target_date=target_date,
                include_cancelled=True,
            )
            cancelled_appts = [a.to_dict() for a in all_appts if a.status.is_cancelled]

        return {
            "doctor": doctor.to_dict(),
            "date": target_date.strftime("%Y-%m-%d"),
            "is_working_day": is_working_day,
            "shift_start": shift_start.isoformat(),
            "shift_end": shift_end.isoformat(),
            "shift_duration_minutes": total_shift_minutes,
            "booked_minutes": total_booked_minutes,
            "free_minutes": total_free_minutes,
            "utilization_percent": utilization,
            "active_appointment_count": len(active_appts),
            "timeline": timeline,
            "cancelled_appointments": cancelled_appts,
        }

    # ------------------ Patient Search & Lookups ------------------

    def search_patient_appointments(self, query: str) -> List[Dict[str, Any]]:
        """
        Finds a patient's appointments by name (case-insensitive substring match).
        Returns patient information alongside all their appointments.
        """
        query = query.strip()
        if not query:
            return []

        patients = self.repo.search_patients_by_name(query)
        results: List[Dict[str, Any]] = []

        for p in patients:
            appts = self.repo.get_patient_appointments(p.id)
            results.append({
                "patient": p.to_dict(),
                "appointments": [a.to_dict() for a in appts],
            })

        return results

    # ------------------ Slot Availability Helper ------------------

    def get_available_slots(
        self,
        doctor_id: str,
        target_date: datetime,
        slot_duration_minutes: int = 30,
    ) -> List[Dict[str, Any]]:
        """
        Calculates all bookable discrete time slots of the given duration
        within the doctor's free intervals for that day.
        """
        day_schedule = self.get_doctor_day_schedule(doctor_id, target_date, include_cancelled=False)
        step = timedelta(minutes=slot_duration_minutes)
        slots: List[Dict[str, Any]] = []

        for block in day_schedule["timeline"]:
            if block["type"] == "FREE":
                b_start = datetime.fromisoformat(block["start_time"])
                b_end = datetime.fromisoformat(block["end_time"])
                curr = b_start
                while curr + step <= b_end:
                    slot_end = curr + step
                    slots.append({
                        "start_time": curr.isoformat(),
                        "end_time": slot_end.isoformat(),
                        "formatted": f"{curr.strftime('%H:%M')} - {slot_end.strftime('%H:%M')}",
                        "duration_minutes": slot_duration_minutes,
                    })
                    curr += step

        return slots

    # ------------------ Patient Resolution Helper ------------------

    def _resolve_or_create_patient(
        self,
        patient_id_or_name: str,
        phone: str = "",
        email: str = "",
    ) -> Patient:
        # Check if already a valid patient ID
        existing = self.repo.get_patient(patient_id_or_name)
        if existing:
            return existing

        # Check if exact name match already exists
        exact_matches = [
            p for p in self.repo.search_patients_by_name(patient_id_or_name)
            if p.name.strip().lower() == patient_id_or_name.strip().lower()
        ]
        if exact_matches:
            return exact_matches[0]

        # Auto-create new patient
        new_id = f"pat_{uuid.uuid4().hex[:8]}"
        patient = Patient(
            id=new_id,
            name=patient_id_or_name.strip(),
            phone=phone.strip() or "N/A",
            email=email.strip(),
        )
        self.repo.save_patient(patient)
        return patient
