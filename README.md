# Apex Care Clinic — Front Desk Booking & Conflict Management System

A high-reliability scheduling and appointment management system designed specifically to eliminate the front desk's biggest operational headaches: **double-booking doctors**, **unfair cancellation fee disputes**, **conflict-free rescheduling**, and **automated morning reminders & no-show management**.

---

## Key Features

1. **Zero Double-Booking Guarantee (Mathematical Overlap Prevention)**:
   - Evaluates interval conflicts using strict half-open interval intersection:
     $$\max(\text{start}_1, \text{start}_2) < \min(\text{end}_1, \text{end}_2)$$
   - Back-to-back appointments (e.g. 09:00–09:30 and 09:30–10:00) are permitted and supported.
   - Partial overlaps, enclosed appointments, and enclosing appointments are rejected immediately with clear error explanations and **instant suggestions for next available free slots**.
   - Concurrency-safe: SQLite in WAL mode with `BEGIN IMMEDIATE` transactions prevents race conditions even if two desk clerks click "Book" simultaneously.

2. **Level 1 — T6 (lifecycle): Conflict-Free Appointment Rescheduling**:
   - Reschedule any existing appointment to a new date/time while keeping the same doctor and patient.
   - Strictly re-evaluates doctor and patient conflict checks without colliding with its own previous slot.
   - Validates doctor operating hours and working clinic days.

3. **Level 2 — T1 (integrate): Morning Patient Reminders & Notification Outbox**:
   - Each morning, automatically dispatches reminder notifications to patients with scheduled appointments for that day.
   - Logged into the Notification Service Outbox (`GET /outbox`, `DELETE /outbox`).
   - Triggered automatically when advancing the system clock via `POST /clock`.
   - Reminders are strictly idempotent per day (prevents duplicate spamming).

4. **Level 3 — T2 (automation): Auto-Mark No-Shows via Simulated Clock**:
   - Automated background job that auto-marks appointments as `NO_SHOW` 30 minutes after their start time if not `COMPLETED` or `CANCELLED`.
   - Front desk staff can mark attended visits as `COMPLETED` (`POST /api/appointments/<id>/complete`) to prevent no-show flagging.
   - Graded and evaluated via `POST /clock`.

5. **Fair & Transparent Cancellation Policy**:
   - **Timely Cancellation ($\ge 24\text{ hours}$ notice)**: **$0.00 Fee** (`CANCELLED_FREE`).
   - **Late Cancellation ($< 24\text{ hours}$ notice)**: **$25.00 Late Fee** (`CANCELLED_LATE`).
   - **Emergency Supervisor Waiver**: Desk staff can waive the fee for verified emergencies with mandatory audit justification.
   - **Immediate Slot Freeing**: Once an appointment is cancelled, that doctor's time slot is released instantly for other patients to book.

6. **New Doctor Onboarding**:
   - Easily register new doctors joining the hospital/clinic with full specialty/department details, room/office location, operating shift hours, and working clinic days.
   - Immediately makes the new doctor's schedule available for appointments across both the Web UI and CLI.

7. **Doctor Daily Schedule View ("A Doctor's Day")**:
   - Interactive visual timeline displaying every block in the doctor's shift.
   - Distinct visualization for **Booked slots** (with patient name, phone, clinical notes) and **Free gaps** (showing exact duration available and "+ Book Slot" quick-action).
   - Real-time metrics: Booked minutes, Free minutes, Utilization percentage, Active appointment count.

8. **Instant Patient Search**:
   - Case-insensitive, partial-match lookup by patient name.
   - Shows patient contact details and full historical records across active bookings, completed visits, and cancelled appointments with cancellation fee metadata.

9. **Dual User Interfaces**:
   - **Interactive Web Dashboard**: Modern single-page app with live timeline, conflict modal with suggested slots, cancellation preview, doctor onboarding dialog, reschedule modal, clock advancement controls, and outbox viewer.
   - **Command Line Interface (`cli.py`)**: Fast keyboard-driven interface featuring interactive menus and scriptable subcommands.

---

## Directory Structure

```
clinic_booking_system/
├── clinic/
│   ├── __init__.py           # Package exports (models, clock, notifications, service)
│   ├── clock.py              # SystemClock: simulated time & automated event triggers
│   ├── notifications.py      # Notification dataclass & outbox representation
│   ├── models.py             # Doctor, Patient, Appointment, TimeSlot, CancellationRecord
│   ├── policy.py             # CancellationPolicy engine (notice cutoff & fee calculations)
│   ├── repository.py         # SQLite persistence with WAL mode & atomic transactions
│   ├── service.py            # ClinicService: business logic, conflict rejection, timeline calculation
│   └── seed.py               # Pre-seeded demo doctors, patients, and schedule
├── web/
│   ├── server.py             # REST API (Clock, Outbox, Appointments, Reschedule, Doctors)
│   ├── index.html            # Front desk single-page app
│   ├── styles.css            # Healthcare-themed modern styling
│   └── app.js                # Frontend reactive controller & API client
├── tests/
│   ├── __init__.py
│   ├── test_overlap.py       # Overlap math, boundary tests, back-to-back, re-booking
│   ├── test_reschedule.py    # Level 1 T6: Reschedule conflict checks & self-overlap
│   ├── test_notifications.py # Level 2 T1: Morning reminders, idempotency & /outbox
│   ├── test_no_show.py       # Level 3 T2: Auto-mark no-shows & clock automation API
│   ├── test_cancellation.py  # Timely vs late cancellations, fee waivers, notice cutoff
│   ├── test_doctor.py        # Doctor onboarding, shifts, and schedules
│   ├── test_schedule.py      # Timeline generation, free gaps, utilization metrics
│   ├── test_search.py        # Case-insensitive patient search & appointment history
│   └── test_concurrency.py   # Multi-threaded race condition tests (10 simultaneous bookings)
├── cli.py                    # Terminal CLI (interactive menu & subcommands)
├── run_server.py             # Web dashboard runner
├── clinic.db                 # SQLite database (auto-created and seeded)
└── README.md                 # System documentation
```

---

## Quick Start

### 1. Launch the Web Dashboard
Run the built-in HTTP server:
```powershell
py run_server.py
```
Open your browser to: **[http://127.0.0.1:8000](http://127.0.0.1:8000)**

Web portal tabs:
- **Doctor's Day**: Browse doctors and dates to see daily timeline with Reschedule, Complete, and Cancel actions.
- **Patient Lookup**: Live search bar to search any patient name.
- **Cancellation Ledger**: Audit trail of all cancellations and fee billing.
- **Clock & Outbox**: Advance simulated system time, view dispatched morning reminders, and manage the notification outbox.

---

### 2. Using the Command Line Interface (CLI)

#### Interactive Menu Mode
Simply run without arguments:
```powershell
py cli.py
```

#### Direct CLI Subcommands

**List Doctors:**
```powershell
py cli.py doctors
```

**Onboard a New Doctor:**
```powershell
py cli.py add-doctor --name "Dr. Gregory House" --specialty "Diagnostic Medicine" --room "Room 402" --start "09:00" --end "16:00"
```

**View Doctor's Schedule for a Given Date:**
```powershell
py cli.py schedule --doctor doc_chen --date 2026-09-17
```

**Book an Appointment (Conflict-Free):**
```powershell
py cli.py book --doctor doc_chen --patient "Jane Doe" --start "2026-09-17 14:30" --duration 30 --phone "555-0188"
```

**Reschedule an Appointment:**
```powershell
py cli.py reschedule apt_12345 --start "2026-09-17 15:30" --duration 30
```

**Mark Appointment as Completed:**
```powershell
py cli.py complete apt_12345
```

**Simulate / Advance System Clock:**
```powershell
py cli.py clock --set "2026-09-17 08:00"
```

**Inspect or Clear Notification Outbox:**
```powershell
py cli.py outbox
py cli.py outbox --clear
```

**Cancel an Appointment:**
```powershell
py cli.py cancel apt_12345 --reason "Patient rescheduled"
```

**Cancel with Supervisor Fee Waiver (for Emergencies):**
```powershell
py cli.py cancel apt_12345 --waive --waiver-reason "Medical emergency approved by clinic supervisor"
```

---

## API Endpoints

- `GET /clock`: Returns `{"current_time": "<iso>"}`.
- `POST /clock`: Advances simulated time `{"current_time": "<iso>"}`. Triggers morning reminders & auto-no-show checks.
- `GET /outbox`: Returns array of reminder notifications dispatched to patients.
- `DELETE /outbox`: Clears outbox records.
- `POST /api/appointments`: Books a new conflict-free appointment.
- `POST /api/appointments/<id>/reschedule`: Reschedules appointment with conflict verification.
- `POST /api/appointments/<id>/complete`: Marks appointment completed.
- `POST /api/appointments/<id>/cancel`: Cancels appointment with notice calculation & late fee evaluation.
- `GET /api/schedule?doctor_id=...&date=...`: Returns timeline schedule.
- `POST /api/doctors`: Onboards new doctor.

---

## Running the Automated Test Suite

Run all 47 tests across all 9 test suites:
```powershell
py -m unittest discover -s tests -v
```
