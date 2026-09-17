# Apex Care Clinic — Front Desk Booking & Conflict Management System

A high-reliability scheduling and appointment management system designed specifically to eliminate the front desk's biggest operational headaches: **double-booking doctors** and **unfair cancellation fee disputes**.

---

## Key Features

1. **Zero Double-Booking Guarantee (Mathematical Overlap Prevention)**:
   - Evaluates interval conflicts using strict half-open interval intersection:
     $$\max(\text{start}_1, \text{start}_2) < \min(\text{end}_1, \text{end}_2)$$
   - Back-to-back appointments (e.g. 09:00–09:30 and 09:30–10:00) are permitted and supported.
   - Partial overlaps, enclosed appointments, and enclosing appointments are rejected immediately with clear error explanations and **instant suggestions for next available free slots**.
   - Concurrency-safe: SQLite in WAL mode with `BEGIN IMMEDIATE` transactions prevents race conditions even if two desk clerks click "Book" simultaneously.

2. **Fair & Transparent Cancellation Policy**:
   - **Timely Cancellation ($\ge 24\text{ hours}$ notice)**: **$0.00 Fee** (`CANCELLED_FREE`).
   - **Late Cancellation ($< 24\text{ hours}$ notice)**: **$25.00 Late Fee** (`CANCELLED_LATE`).
   - **Emergency Supervisor Waiver**: Desk staff can waive the fee for verified emergencies (family medical crisis, hospital admission) with mandatory audit justification.
   - **Immediate Slot Freeing**: Once an appointment is cancelled, that doctor's time slot is released instantly for other patients to book.

3. **Doctor Daily Schedule View ("A Doctor's Day")**:
   - Interactive visual timeline displaying every block in the doctor's shift.
   - Distinct visualization for **Booked slots** (with patient name, phone, clinical notes) and **Free gaps** (showing exact duration available and "+ Book Slot" quick-action).
   - Real-time metrics: Booked minutes, Free minutes, Utilization percentage, Active appointment count.

4. **Instant Patient Search**:
   - Case-insensitive, partial-match lookup by patient name (e.g., searching `"ali"` finds `"Alice Smith"`).
   - Shows patient contact details and full historical records across active bookings, completed visits, and cancelled appointments with cancellation fee metadata.

5. **Dual User Interfaces**:
   - **Interactive Web Dashboard**: Modern single-page app with zero npm/pip dependencies, live timeline, conflict modal with suggested slots, cancellation preview, and audit ledger.
   - **Command Line Interface (`cli.py`)**: Fast keyboard-driven interface featuring both interactive menus and scriptable subcommands.

---

## Directory Structure

```
clinic_booking_system/
├── clinic/
│   ├── __init__.py           # Package exports
│   ├── models.py             # Doctor, Patient, Appointment, TimeSlot, CancellationRecord
│   ├── policy.py             # CancellationPolicy engine (notice cutoff & fee calculations)
│   ├── repository.py         # SQLite persistence with WAL mode & atomic transactions
│   ├── service.py            # ClinicService: business logic, conflict rejection, timeline calculation
│   └── seed.py               # Pre-seeded demo doctors, patients, and schedule
├── web/
│   ├── server.py             # Zero-dependency Python HTTP server & REST API
│   ├── index.html            # Front desk single-page app
│   ├── styles.css            # Healthcare-themed modern styling
│   └── app.js                # Frontend reactive controller & API client
├── tests/
│   ├── __init__.py
│   ├── test_overlap.py       # Overlap math, boundary tests, back-to-back, re-booking
│   ├── test_cancellation.py  # Timely vs late cancellations, fee waivers, notice cutoff
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

Features on the web portal:
- **Doctor's Day**: Select any doctor (Dr. Chen, Dr. Vance, Dr. Rostova) and browse dates to see their schedule timeline.
- **Book Appointment**: Click "+ Book Appointment" or click any open slot. If you select an overlapping time, the system will block the booking and display alternative free slots.
- **Cancel Appointment**: Click "Cancel" on any appointment to view the real-time notice calculation, fee preview, and optional emergency waiver.
- **Patient Lookup**: Live search bar to search any patient name.
- **Cancellation Ledger**: Audit trail of all cancellations and fee billing.

---

### 2. Using the Command Line Interface (CLI)

#### Interactive Menu Mode
Simply run without arguments:
```powershell
py cli.py
```
This presents an interactive menu to view schedules, book, cancel, search, or inspect the fee ledger.

#### Direct CLI Subcommands

**List Doctors:**
```powershell
py cli.py doctors
```

**View Doctor's Schedule for a Given Date:**
```powershell
py cli.py schedule --doctor doc_chen --date 2026-09-17
```

**Search Patient by Name:**
```powershell
py cli.py search "Alice"
```

**Book an Appointment (Conflict-Free):**
```powershell
py cli.py book --doctor doc_chen --patient "Jane Doe" --start "2026-09-17 14:30" --duration 30 --phone "555-0188"
```
*(If the slot overlaps with an existing booking, the CLI prints `[CONFLICT]` with suggested alternative slots).*

**Cancel an Appointment (Automatic Policy Evaluation):**
```powershell
py cli.py cancel apt_12345 --reason "Patient rescheduled"
```

**Cancel with Supervisor Fee Waiver (for Emergencies):**
```powershell
py cli.py cancel apt_12345 --waive --waiver-reason "Medical emergency approved by clinic supervisor"
```

---

## Running the Automated Test Suite

Run all 24 unit and concurrency tests:
```powershell
py -m unittest discover -s tests -v
```

Test coverage includes:
- **`test_overlap.py`**: Identical overlap, partial start/end overlaps, enclosed/enclosing slots, back-to-back non-overlapping adjacent slots, re-booking after cancellation, patient-side double booking.
- **`test_cancellation.py`**: Free cancellation ($\ge 24\text{h}$), late fee charge ($< 24\text{h}$), exact 24h boundary condition, emergency supervisor fee waiver, cancellation preview.
- **`test_schedule.py`**: Complete day schedule calculation, timeline gap segmentation, shift metrics, utilization percent, bookable slot generator.
- **`test_search.py`**: Exact name, partial substring, case-insensitivity, and appointment history retrieval.
- **`test_concurrency.py`**: 10 threads concurrently attempting to book the exact same slot for the same doctor. Verifies strictly 1 winner and 9 clean conflict rejections with zero database corruption.

