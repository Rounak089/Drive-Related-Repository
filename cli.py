"""
Clinic Front Desk Command Line Interface (CLI).
Supports interactive menu and command-line execution.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta
from typing import Optional

from clinic.models import AppointmentStatus
from clinic.policy import CancellationPolicy
from clinic.repository import ClinicRepository
from clinic.seed import seed_clinic_data
from clinic.service import ClinicService, ConflictError, NotFoundError, ValidationError

DEFAULT_DB = "clinic.db"


def get_service(db_path: str = DEFAULT_DB) -> ClinicService:
    is_new = not os.path.exists(db_path) or os.path.getsize(db_path) == 0
    repo = ClinicRepository(db_path)
    service = ClinicService(repo, CancellationPolicy(cutoff_hours=24.0, late_fee=25.0))
    if is_new:
        print(f"[Init] New database created at {db_path}. Seeding demo doctors and appointments...")
        seed_clinic_data(service)
        print("[Init] Seeding complete.\n")
    return service


# ============================== Command Handlers ==============================

def cmd_doctors(service: ClinicService) -> None:
    doctors = service.repo.list_doctors()
    print("\n" + "=" * 60)
    print(f"{'ID':<16} {'Doctor Name':<20} {'Specialty':<22} {'Hours':<12} {'Room'}")
    print("-" * 60)
    for d in doctors:
        print(f"{d.id:<16} {d.name:<20} {d.specialty:<22} {d.work_start_time}-{d.work_end_time} {d.room}")
    print("=" * 60 + "\n")


def cmd_add_doctor(
    service: ClinicService,
    name: str,
    specialty: str,
    room: str,
    start_time: str = "08:30",
    end_time: str = "17:00",
    days: Optional[List[int]] = None,
) -> None:
    try:
        doc = service.add_doctor(
            name=name,
            specialty=specialty,
            room=room,
            work_start_time=start_time,
            work_end_time=end_time,
            working_days=days,
        )
        day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        active_days = ", ".join(day_names[d] for d in doc.working_days)
        print("\n\033[92m[SUCCESS] New Doctor Onboarded Successfully!\033[0m")
        print(f"  Doctor ID:    {doc.id}")
        print(f"  Name:         {doc.name}")
        print(f"  Department:   {doc.specialty}")
        print(f"  Room/Office:  {doc.room}")
        print(f"  Working Shift: {doc.work_start_time} - {doc.work_end_time}")
        print(f"  Clinic Days:  {active_days}\n")
    except (ValidationError, ConflictError) as e:
        print(f"\n\033[91m[ERROR] {e}\033[0m\n")


def cmd_schedule(service: ClinicService, doctor_id: str, date_str: Optional[str] = None) -> None:
    target_date = datetime.strptime(date_str, "%Y-%m-%d") if date_str else datetime.now()
    try:
        sched = service.get_doctor_day_schedule(doctor_id, target_date)
    except NotFoundError as e:
        print(f"Error: {e}")
        return

    doc = sched["doctor"]
    print("\n" + "=" * 75)
    print(f" DAILY SCHEDULE: {doc['name']} ({doc['specialty']}, {doc['room']})")
    print(f" Date: {sched['date']} | Shift: {doc['work_start_time']} - {doc['work_end_time']}")
    print(f" Booked: {sched['booked_minutes']} min | Free: {sched['free_minutes']} min | Utilization: {sched['utilization_percent']}%")
    print("-" * 75)
    print(f"{'Time Interval':<20} {'Status':<12} {'Duration':<10} {'Details'}")
    print("-" * 75)

    for block in sched["timeline"]:
        s_time = datetime.fromisoformat(block["start_time"]).strftime("%H:%M")
        e_time = datetime.fromisoformat(block["end_time"]).strftime("%H:%M")
        time_interval = f"{s_time} - {e_time}"
        b_type = block["type"]
        dur = f"{block['duration_minutes']} min"

        if b_type == "BOOKED":
            appt = block["appointment"]
            details = f"Patient: {appt['patient_name']} (Phone: {appt.get('patient_phone') or 'N/A'}) - {appt.get('notes') or 'No notes'} [ID: {appt['id']}]"
            print(f"{time_interval:<20} \033[92m{b_type:<12}\033[0m {dur:<10} {details}")
        else:
            print(f"{time_interval:<20} \033[94m{b_type:<12}\033[0m {dur:<10} (Available for booking)")

    if sched["cancelled_appointments"]:
        print("-" * 75)
        print(" Cancelled Appointments on this Day:")
        for ca in sched["cancelled_appointments"]:
            s_time = datetime.fromisoformat(ca["start_time"]).strftime("%H:%M")
            fee_info = f"Fee: ${ca['cancellation']['fee']:.2f}" if ca.get("cancellation") else ""
            print(f" - {s_time}: {ca['patient_name']} ({ca['status']}) - {fee_info} [ID: {ca['id']}]")

    print("=" * 75 + "\n")


def cmd_search(service: ClinicService, name_query: str) -> None:
    results = service.search_patient_appointments(name_query)
    if not results:
        print(f"\nNo patients found matching '{name_query}'.\n")
        return

    print("\n" + "=" * 80)
    print(f" PATIENT SEARCH RESULTS: '{name_query}' ({len(results)} found)")
    print("=" * 80)

    for r in results:
        p = r["patient"]
        appts = r["appointments"]
        print(f"\nPatient: {p['name']} | Phone: {p['phone']} | Email: {p['email'] or 'N/A'}")
        if not appts:
            print("  (No appointments recorded)")
            continue

        print(f"  {'Appointment ID':<16} {'Doctor':<20} {'Date & Time':<20} {'Status':<16} {'Fee Info'}")
        print("  " + "-" * 76)
        for a in appts:
            s_dt = datetime.fromisoformat(a["start_time"]).strftime("%Y-%m-%d %H:%M")
            fee_str = ""
            if a.get("cancellation"):
                c = a["cancellation"]
                fee_str = f"Fee: ${c['fee']:.2f} (Notice: {c['notice_hours']}h)"
                if c["waived"]:
                    fee_str += " [WAIVED]"

            status_str = a["status"]
            print(f"  {a['id']:<16} {a.get('doctor_name', 'N/A'):<20} {s_dt:<20} {status_str:<16} {fee_str}")

    print("\n" + "=" * 80 + "\n")


def cmd_book(
    service: ClinicService,
    doctor_id: str,
    patient_name: str,
    start_str: str,
    duration: int = 30,
    patient_phone: str = "",
    notes: str = "",
) -> None:
    try:
        start_time = datetime.strptime(start_str, "%Y-%m-%d %H:%M")
    except ValueError:
        try:
            start_time = datetime.fromisoformat(start_str)
        except ValueError:
            print("Error: Start time must be in 'YYYY-MM-DD HH:MM' format.")
            return

    end_time = start_time + timedelta(minutes=duration)

    try:
        appt = service.book_appointment(
            doctor_id=doctor_id,
            patient_id_or_name=patient_name,
            start_time=start_time,
            end_time=end_time,
            patient_phone=patient_phone,
            notes=notes,
        )
        print("\n\033[92m[SUCCESS] Appointment Booked Successfully!\033[0m")
        print(f"  ID:          {appt.id}")
        print(f"  Doctor:      {appt.doctor_name}")
        print(f"  Patient:     {appt.patient_name} ({appt.patient_phone})")
        print(f"  Time:        {appt.start_time.strftime('%Y-%m-%d %H:%M')} to {appt.end_time.strftime('%H:%M')} ({duration} min)")
        print(f"  Notes:       {appt.notes or 'None'}\n")
    except ConflictError as ce:
        print(f"\n\033[91m[CONFLICT] {ce}\033[0m")
        if ce.suggested_slots:
            print("  Suggested Alternative Slots Today:")
            for s in ce.suggested_slots:
                print(f"    * {s['formatted']}")
        print()
    except (ValidationError, NotFoundError) as ve:
        print(f"\n\033[91m[VALIDATION ERROR] {ve}\033[0m\n")


def cmd_cancel(
    service: ClinicService,
    appointment_id: str,
    waive_fee: bool = False,
    reason: str = "",
    waiver_reason: str = "",
) -> None:
    try:
        # Show preview first
        preview = service.preview_cancellation(appointment_id)
        print("\n--- Cancellation Evaluation ---")
        print(f"  Appointment:  {preview['appointment_id']} ({preview['patient_name']} with {preview['doctor_name']})")
        print(f"  Start Time:   {preview['appointment_start']}")
        print(f"  Notice Given: {preview['notice_hours']} hours (Policy cutoff: {preview['cutoff_hours']} hours)")
        print(f"  Rule Result:  {preview['message']}")

        cancelled = service.cancel_appointment(
            appointment_id=appointment_id,
            waive_fee=waive_fee,
            reason=reason,
            waiver_reason=waiver_reason if waive_fee else None,
        )
        print(f"\n\033[92m[SUCCESS] Appointment Cancelled ({cancelled.status.value}).\033[0m")
        c = cancelled.cancellation
        if c:
            print(f"  Fee Assessed:   ${c.fee:.2f}")
            if c.waived:
                print(f"  Fee Waived:     YES (Reason: {c.waiver_reason})")
        print("  Doctor's time slot is now IMMEDIATELY available for new bookings.\n")
    except (NotFoundError, ValidationError) as e:
        print(f"\n\033[91m[ERROR] {e}\033[0m\n")


def cmd_reschedule(
    service: ClinicService,
    appointment_id: str,
    start_time_str: str,
    duration: Optional[int] = None,
) -> None:
    try:
        new_start = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M")
    except ValueError:
        try:
            new_start = datetime.fromisoformat(start_time_str)
        except ValueError:
            print("[Error] Invalid start time format. Use 'YYYY-MM-DD HH:MM'.")
            return

    try:
        updated = service.reschedule_appointment(
            appointment_id=appointment_id,
            new_start_time=new_start,
            duration_minutes=duration,
        )
        print("\n\033[92m[SUCCESS] Appointment Rescheduled Successfully!\033[0m")
        print(f"  Appointment ID: {updated.id}")
        print(f"  Patient:        {updated.patient_name}")
        print(f"  Doctor:         {updated.doctor_name}")
        print(f"  New Time:       {updated.start_time.strftime('%Y-%m-%d %H:%M')} - {updated.end_time.strftime('%H:%M')}")
        print(f"  Status:         {updated.status.value}\n")
    except ConflictError as ce:
        print(f"\n\033[91m[CONFLICT] {ce}\033[0m")
        if ce.suggested_slots:
            print("\n  Suggested Available Slots:")
            for s in ce.suggested_slots[:5]:
                print(f"   -> {s['formatted']} ({s['start_time']})")
        print()
    except (NotFoundError, ValidationError) as e:
        print(f"\n\033[91m[ERROR] {e}\033[0m\n")


def cmd_complete(service: ClinicService, appointment_id: str) -> None:
    try:
        completed = service.complete_appointment(appointment_id)
        print(f"\n\033[92m[SUCCESS] Appointment {completed.id} marked as COMPLETED.\033[0m\n")
    except (NotFoundError, ValidationError) as e:
        print(f"\n\033[91m[ERROR] {e}\033[0m\n")


def cmd_clock(service: ClinicService, new_time_str: Optional[str] = None) -> None:
    if not new_time_str:
        curr = service.get_clock_time()
        print(f"\n[Clock] Current Simulated Time: {curr.isoformat()} ({curr.strftime('%Y-%m-%d %H:%M:%S')})\n")
        return

    try:
        dt = service.advance_clock(new_time_str)
        print(f"\n\033[92m[Clock] Advanced to: {dt.isoformat()}\033[0m")
        print("  - Morning reminders checked & dispatched to Outbox")
        print("  - 30-minute overdue appointments auto-marked as NO_SHOW\n")
    except Exception as e:
        print(f"\n\033[91m[ERROR] Could not advance clock: {e}\033[0m\n")


def cmd_outbox(service: ClinicService, clear: bool = False) -> None:
    if clear:
        service.clear_outbox()
        print("\n\033[92m[Outbox] Notification outbox cleared.\033[0m\n")
        return

    outbox = service.get_outbox()
    print("\n" + "=" * 80)
    print(" NOTIFICATION SERVICE OUTBOX")
    print("=" * 80)
    if not outbox:
        print(" Outbox is empty (no notifications queued/dispatched).")
    else:
        print(f"{'Time':<20} {'Recipient':<18} {'Type':<12} {'Message'}")
        print("-" * 80)
        for n in outbox:
            created = n.get("created_at", "")[:19]
            recip = n.get("recipient_name", "")
            ntype = n.get("notification_type", "")
            msg = n.get("message", "")
            print(f"{created:<20} {recip:<18} {ntype:<12} {msg}")
    print("=" * 80 + "\n")


# ============================== Interactive Mode ==============================

def interactive_mode(service: ClinicService) -> None:
    while True:
        print("\n" + "=" * 55)
        print(" CLINIC FRONT DESK - MAIN MENU")
        print("=" * 55)
        print(" 1. View Doctor's Day Schedule (Timeline & Free Slots)")
        print(" 2. Book New Appointment (Conflict-Free)")
        print(" 3. Reschedule Appointment (Re-check Overlap)")
        print(" 4. Mark Appointment as Completed")
        print(" 5. Search Patient by Name (Look up Appointments)")
        print(" 6. Cancel Appointment (Evaluate Notice & Late Fee)")
        print(" 7. List All Doctors")
        print(" 8. View Cancellation Fee Ledger")
        print(" 9. Onboard New Doctor to Clinic")
        print("10. Advance System Simulated Clock (Triggers Reminders & No-Shows)")
        print("11. View Notification Outbox")
        print(" 0. Exit")
        print("=" * 55)

        choice = input("Select an option [0-11]: ").strip()
        if choice == "0":
            print("Exiting front desk system. Goodbye!")
            break
        elif choice == "1":
            cmd_doctors(service)
            doc_id = input("Enter Doctor ID (e.g. doc_chen): ").strip()
            date_in = input(f"Enter Date YYYY-MM-DD (Press Enter for today {datetime.now().strftime('%Y-%m-%d')}): ").strip()
            cmd_schedule(service, doc_id, date_in or None)
        elif choice == "2":
            cmd_doctors(service)
            doc_id = input("Doctor ID: ").strip()
            pat_name = input("Patient Name: ").strip()
            pat_phone = input("Patient Phone: ").strip()
            today_str = datetime.now().strftime("%Y-%m-%d")
            start_in = input(f"Start Date & Time YYYY-MM-DD HH:MM (e.g. {today_str} 14:00): ").strip()
            dur_in = input("Duration in minutes [default 30]: ").strip()
            duration = int(dur_in) if dur_in.isdigit() else 30
            notes = input("Appointment Notes / Reason: ").strip()
            cmd_book(service, doc_id, pat_name, start_in, duration, pat_phone, notes)
        elif choice == "3":
            appt_id = input("Enter Appointment ID to reschedule: ").strip()
            start_in = input("New Start Date & Time YYYY-MM-DD HH:MM: ").strip()
            dur_in = input("Duration in minutes (Press Enter to keep existing): ").strip()
            duration = int(dur_in) if dur_in.isdigit() else None
            cmd_reschedule(service, appt_id, start_in, duration)
        elif choice == "4":
            appt_id = input("Enter Appointment ID to mark completed: ").strip()
            cmd_complete(service, appt_id)
        elif choice == "5":
            query = input("Enter patient name or partial name to search: ").strip()
            cmd_search(service, query)
        elif choice == "6":
            appt_id = input("Enter Appointment ID to cancel: ").strip()
            reason = input("Reason for cancellation: ").strip()
            waive_in = input("Waive late cancellation fee for emergency? (y/N): ").strip().lower()
            waive = waive_in == "y"
            waiver_reason = ""
            if waive:
                waiver_reason = input("Enter fee waiver justification: ").strip()
            cmd_cancel(service, appt_id, waive_fee=waive, reason=reason, waiver_reason=waiver_reason)
        elif choice == "7":
            cmd_doctors(service)
        elif choice == "8":
            records = service.repo.list_cancellation_records()
            print("\n" + "=" * 85)
            print(" CANCELLATION & FEE AUDIT LEDGER")
            print("=" * 85)
            if not records:
                print(" No cancellation records found.")
            else:
                print(f"{'Appointment ID':<16} {'Patient':<18} {'Doctor':<18} {'Notice':<10} {'Fee':<10} {'Waived'}")
                print("-" * 85)
                for r in records:
                    waived_str = f"YES ({r['waiver_reason']})" if r["waived"] else "NO"
                    print(f"{r['appointment_id']:<16} {r['patient_name']:<18} {r['doctor_name']:<18} {round(r['notice_hours'],1)}h       ${r['fee']:<9.2f} {waived_str}")
            print("=" * 85 + "\n")
        elif choice == "9":
            print("\n--- Onboard New Doctor ---")
            name = input("Doctor Full Name (e.g. Dr. Gregory House): ").strip()
            spec = input("Department / Specialty (e.g. Neurology, Cardiology): ").strip()
            room = input("Room / Office Number (e.g. Room 402): ").strip()
            s_time = input("Shift Start Time [default 08:30]: ").strip() or "08:30"
            e_time = input("Shift End Time [default 17:00]: ").strip() or "17:00"
            days_in = input("Working days 0-6 (0=Mon, 4=Fri) comma-separated [default 0,1,2,3,4]: ").strip()
            days = [int(d.strip()) for d in days_in.split(",") if d.strip().isdigit()] if days_in else [0, 1, 2, 3, 4]
            cmd_add_doctor(service, name, spec, room, s_time, e_time, days)
        elif choice == "10":
            time_in = input("Enter new simulated time (YYYY-MM-DD HH:MM or ISO string): ").strip()
            cmd_clock(service, time_in or None)
        elif choice == "11":
            cmd_outbox(service)
        else:
            print("Invalid selection. Please choose an option from the menu.")


def main():
    parser = argparse.ArgumentParser(description="Clinic Front Desk Booking & Conflict Management CLI")
    parser.add_argument("--db", default=DEFAULT_DB, help="Path to SQLite database")
    subparsers = parser.add_subparsers(dest="command")

    # Doctors command
    subparsers.add_parser("doctors", help="List doctors")

    # Schedule command
    p_sched = subparsers.add_parser("schedule", help="View doctor's day schedule")
    p_sched.add_argument("--doctor", required=True, help="Doctor ID (e.g. doc_chen)")
    p_sched.add_argument("--date", help="Date in YYYY-MM-DD format (defaults to today)")

    # Search command
    p_search = subparsers.add_parser("search", help="Search patient appointments by name")
    p_search.add_argument("name", help="Patient name or partial substring")

    # Book command
    p_book = subparsers.add_parser("book", help="Book an appointment")
    p_book.add_argument("--doctor", required=True, help="Doctor ID")
    p_book.add_argument("--patient", required=True, help="Patient Name")
    p_book.add_argument("--start", required=True, help="Start time 'YYYY-MM-DD HH:MM'")
    p_book.add_argument("--duration", type=int, default=30, help="Duration in minutes (default: 30)")
    p_book.add_argument("--phone", default="", help="Patient phone number")
    p_book.add_argument("--notes", default="", help="Appointment notes")

    # Reschedule command (Twist 1 / T6)
    p_resched = subparsers.add_parser("reschedule", help="Reschedule an appointment to a new time")
    p_resched.add_argument("appointment_id", help="Appointment ID to reschedule")
    p_resched.add_argument("--start", required=True, help="New start time 'YYYY-MM-DD HH:MM'")
    p_resched.add_argument("--duration", type=int, help="Duration in minutes (optional, keeps original if omitted)")

    # Complete command
    p_comp = subparsers.add_parser("complete", help="Mark an appointment as completed")
    p_comp.add_argument("appointment_id", help="Appointment ID")

    # Cancel command
    p_cancel = subparsers.add_parser("cancel", help="Cancel an appointment")
    p_cancel.add_argument("appointment_id", help="Appointment ID")
    p_cancel.add_argument("--reason", default="", help="Reason for cancellation")
    p_cancel.add_argument("--waive", action="store_true", help="Waive cancellation fee")
    p_cancel.add_argument("--waiver-reason", default="", help="Reason for waiving fee")

    # Add-doctor command
    p_add_doc = subparsers.add_parser("add-doctor", help="Onboard a new doctor to the clinic")
    p_add_doc.add_argument("--name", required=True, help="Doctor full name")
    p_add_doc.add_argument("--specialty", required=True, help="Specialty or department")
    p_add_doc.add_argument("--room", required=True, help="Room or office location")
    p_add_doc.add_argument("--start", default="08:30", help="Shift start time HH:MM (default: 08:30)")
    p_add_doc.add_argument("--end", default="17:00", help="Shift end time HH:MM (default: 17:00)")
    p_add_doc.add_argument("--days", type=int, nargs="+", default=[0, 1, 2, 3, 4], help="Working days (0=Mon, 6=Sun)")

    # Clock command (Twist 2 & 3)
    p_clock = subparsers.add_parser("clock", help="Simulate / advance clock time")
    p_clock.add_argument("--set", dest="new_time", help="Set clock time to 'YYYY-MM-DD HH:MM' or ISO string")

    # Outbox command
    p_outbox = subparsers.add_parser("outbox", help="View or clear notification outbox")
    p_outbox.add_argument("--clear", action="store_true", help="Clear outbox")

    # Interactive command
    subparsers.add_parser("interactive", help="Start interactive front desk terminal menu")

    args = parser.parse_args()
    service = get_service(args.db)

    if args.command == "doctors":
        cmd_doctors(service)
    elif args.command == "add-doctor":
        cmd_add_doctor(service, args.name, args.specialty, args.room, args.start, args.end, args.days)
    elif args.command == "schedule":
        cmd_schedule(service, args.doctor, args.date)
    elif args.command == "search":
        cmd_search(service, args.name)
    elif args.command == "book":
        cmd_book(service, args.doctor, args.patient, args.start, args.duration, args.phone, args.notes)
    elif args.command == "reschedule":
        cmd_reschedule(service, args.appointment_id, args.start, args.duration)
    elif args.command == "complete":
        cmd_complete(service, args.appointment_id)
    elif args.command == "cancel":
        cmd_cancel(service, args.appointment_id, args.waive, args.reason, args.waiver_reason)
    elif args.command == "clock":
        cmd_clock(service, args.new_time)
    elif args.command == "outbox":
        cmd_outbox(service, args.clear)
    else:
        # Default to interactive menu if no command provided
        interactive_mode(service)


if __name__ == "__main__":
    main()

