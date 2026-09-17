/**
 * Apex Care Clinic — Front Desk Portal Frontend Application.
 */

// State
const state = {
  currentTab: 'schedule',
  doctors: [],
  selectedDoctorId: null,
  selectedDate: new Date().toISOString().split('T')[0],
  activeScheduleData: null,
  currentSimulatedTime: null,
};

// DOM Elements
const elements = {
  navTabs: document.querySelectorAll('.nav-tab'),
  tabPanes: document.querySelectorAll('.tab-pane'),
  doctorSelect: document.getElementById('doctorSelect'),
  scheduleDate: document.getElementById('scheduleDate'),
  btnPrevDay: document.getElementById('btnPrevDay'),
  btnNextDay: document.getElementById('btnNextDay'),
  btnToday: document.getElementById('btnToday'),
  doctorMetrics: document.getElementById('doctorMetrics'),
  timelineContainer: document.getElementById('timelineContainer'),
  activeApptCount: document.getElementById('activeApptCount'),
  cancelledSection: document.getElementById('cancelledSection'),
  cancelledList: document.getElementById('cancelledList'),

  // Booking Modal
  btnOpenBookModal: document.getElementById('btnOpenBookModal'),
  bookModal: document.getElementById('bookModal'),
  btnCloseBookModal: document.getElementById('btnCloseBookModal'),
  btnCancelBookModal: document.getElementById('btnCancelBookModal'),
  bookForm: document.getElementById('bookForm'),
  bookDoctor: document.getElementById('bookDoctor'),
  bookDate: document.getElementById('bookDate'),
  bookTime: document.getElementById('bookTime'),
  bookDuration: document.getElementById('bookDuration'),
  bookPatientName: document.getElementById('bookPatientName'),
  bookPatientPhone: document.getElementById('bookPatientPhone'),
  bookNotes: document.getElementById('bookNotes'),
  bookingConflictAlert: document.getElementById('bookingConflictAlert'),
  conflictTitle: document.getElementById('conflictTitle'),
  conflictMessage: document.getElementById('conflictMessage'),
  conflictSuggestions: document.getElementById('conflictSuggestions'),

  // Reschedule Modal (Twist 1 / T6)
  rescheduleModal: document.getElementById('rescheduleModal'),
  btnCloseRescheduleModal: document.getElementById('btnCloseRescheduleModal'),
  btnCancelRescheduleModal: document.getElementById('btnCancelRescheduleModal'),
  rescheduleForm: document.getElementById('rescheduleForm'),
  rescheduleApptId: document.getElementById('rescheduleApptId'),
  rescheduleApptSummary: document.getElementById('rescheduleApptSummary'),
  rescheduleConflictAlert: document.getElementById('rescheduleConflictAlert'),
  rescheduleConflictTitle: document.getElementById('rescheduleConflictTitle'),
  rescheduleConflictMessage: document.getElementById('rescheduleConflictMessage'),
  rescheduleConflictSuggestions: document.getElementById('rescheduleConflictSuggestions'),
  rescheduleDate: document.getElementById('rescheduleDate'),
  rescheduleTime: document.getElementById('rescheduleTime'),
  rescheduleDuration: document.getElementById('rescheduleDuration'),

  // Add Doctor Modal
  btnOpenAddDoctorModal: document.getElementById('btnOpenAddDoctorModal'),
  addDoctorModal: document.getElementById('addDoctorModal'),
  btnCloseAddDoctorModal: document.getElementById('btnCloseAddDoctorModal'),
  btnCancelAddDoctorModal: document.getElementById('btnCancelAddDoctorModal'),
  addDoctorForm: document.getElementById('addDoctorForm'),
  newDocName: document.getElementById('newDocName'),
  newDocSpecialty: document.getElementById('newDocSpecialty'),
  newDocRoom: document.getElementById('newDocRoom'),
  newDocStart: document.getElementById('newDocStart'),
  newDocEnd: document.getElementById('newDocEnd'),

  // Cancellation Modal
  cancelModal: document.getElementById('cancelModal'),
  btnCloseCancelModal: document.getElementById('btnCloseCancelModal'),
  btnDismissCancelModal: document.getElementById('btnDismissCancelModal'),
  cancelForm: document.getElementById('cancelForm'),
  cancelApptId: document.getElementById('cancelApptId'),
  cancelApptSummary: document.getElementById('cancelApptSummary'),
  cancelNoticeBanner: document.getElementById('cancelNoticeBanner'),
  cancelReason: document.getElementById('cancelReason'),
  waiverBox: document.getElementById('waiverBox'),
  cancelWaiveFee: document.getElementById('cancelWaiveFee'),
  waiverReasonGroup: document.getElementById('waiverReasonGroup'),
  cancelWaiverReason: document.getElementById('cancelWaiverReason'),

  // Search Tab
  patientSearchInput: document.getElementById('patientSearchInput'),
  btnClearSearch: document.getElementById('btnClearSearch'),
  searchResultsContainer: document.getElementById('searchResultsContainer'),

  // Ledger Tab
  ledgerKpis: document.getElementById('ledgerKpis'),
  ledgerTableBody: document.getElementById('ledgerTableBody'),
  btnRefreshLedger: document.getElementById('btnRefreshLedger'),

  // Clock & Outbox Tab (Twists 2 & 3)
  currentClockDisplay: document.getElementById('currentClockDisplay'),
  advanceClockInput: document.getElementById('advanceClockInput'),
  btnAdvanceClock: document.getElementById('btnAdvanceClock'),
  btnAdvance30Min: document.getElementById('btnAdvance30Min'),
  btnAdvanceTomorrowMorning: document.getElementById('btnAdvanceTomorrowMorning'),
  btnRefreshOutbox: document.getElementById('btnRefreshOutbox'),
  btnClearOutbox: document.getElementById('btnClearOutbox'),
  outboxTableBody: document.getElementById('outboxTableBody'),

  // Toast
  toastContainer: document.getElementById('toastContainer'),
};

// ============================== Initialization ==============================

async function init() {
  setupNavigation();
  setupDateControls();
  setupModals();
  setupSearch();
  setupLedger();
  setupClockAndOutbox();

  // Set default date input
  elements.scheduleDate.value = state.selectedDate;
  elements.bookDate.value = state.selectedDate;

  // Load doctors
  await loadDoctors();

  // Load initial schedule
  if (state.selectedDoctorId) {
    await loadSchedule();
  }

  // Load initial clock
  await loadClock();
}

// ============================== Tab Navigation ==============================

function setupNavigation() {
  elements.navTabs.forEach(tab => {
    tab.addEventListener('click', () => {
      const targetTab = tab.dataset.tab;
      state.currentTab = targetTab;

      elements.navTabs.forEach(t => t.classList.remove('active'));
      elements.tabPanes.forEach(p => p.classList.remove('active'));

      tab.classList.add('active');
      const pane = document.getElementById(`tab-${targetTab}`);
      if (pane) pane.classList.add('active');

      if (targetTab === 'schedule') {
        loadSchedule();
      } else if (targetTab === 'ledger') {
        loadLedger();
      } else if (targetTab === 'clock') {
        loadClock();
        loadOutbox();
      }
    });
  });
}

// ============================== Doctors & Schedules ==============================

async function loadDoctors() {
  try {
    const res = await fetch('/api/doctors');
    const data = await res.json();
    state.doctors = data.doctors || [];

    elements.doctorSelect.innerHTML = '';
    elements.bookDoctor.innerHTML = '';

    state.doctors.forEach((doc, idx) => {
      const opt1 = document.createElement('option');
      opt1.value = doc.id;
      opt1.textContent = `${doc.name} (${doc.specialty})`;
      elements.doctorSelect.appendChild(opt1);

      const opt2 = document.createElement('option');
      opt2.value = doc.id;
      opt2.textContent = `${doc.name} (${doc.specialty})`;
      elements.bookDoctor.appendChild(opt2);

      if (idx === 0) {
        state.selectedDoctorId = doc.id;
      }
    });

    elements.doctorSelect.addEventListener('change', (e) => {
      state.selectedDoctorId = e.target.value;
      loadSchedule();
    });
  } catch (err) {
    showToast(`Failed to load doctors: ${err.message}`, 'error');
  }
}

function setupDateControls() {
  elements.scheduleDate.addEventListener('change', (e) => {
    state.selectedDate = e.target.value;
    loadSchedule();
  });

  elements.btnPrevDay.addEventListener('click', () => {
    changeDay(-1);
  });

  elements.btnNextDay.addEventListener('click', () => {
    changeDay(1);
  });

  elements.btnToday.addEventListener('click', () => {
    state.selectedDate = new Date().toISOString().split('T')[0];
    elements.scheduleDate.value = state.selectedDate;
    loadSchedule();
  });
}

function changeDay(deltaDays) {
  const [y, m, d] = state.selectedDate.split('-').map(Number);
  const cur = new Date(y, m - 1, d);
  cur.setDate(cur.getDate() + deltaDays);
  state.selectedDate = cur.toISOString().split('T')[0];
  elements.scheduleDate.value = state.selectedDate;
  loadSchedule();
}

async function loadSchedule() {
  if (!state.selectedDoctorId) return;

  elements.timelineContainer.innerHTML = '<div class="loading-spinner">Loading schedule...</div>';
  elements.cancelledSection.style.display = 'none';

  try {
    const res = await fetch(`/api/schedule?doctor_id=${state.selectedDoctorId}&date=${state.selectedDate}`);
    if (!res.ok) {
      const errData = await res.json();
      throw new Error(errData.error || 'Failed to fetch schedule');
    }
    const data = await res.json();
    state.activeScheduleData = data;
    renderSchedule(data);
  } catch (err) {
    elements.timelineContainer.innerHTML = `<div class="empty-state"><p style="color: var(--danger)">${err.message}</p></div>`;
  }
}

function renderSchedule(data) {
  const doc = data.doctor;
  const isWorking = data.is_working_day;

  // Header metrics
  elements.activeApptCount.textContent = `${data.active_appointment_count} booked`;

  elements.doctorMetrics.innerHTML = `
    <div class="doctor-profile-row">
      <div class="doctor-avatar">${doc.name.replace('Dr. ', '').charAt(0)}</div>
      <div class="doctor-info">
        <h3>${escapeHtml(doc.name)}</h3>
        <p>${escapeHtml(doc.specialty)} &bull; ${escapeHtml(doc.room)}</p>
      </div>
      <div class="doctor-badge-status">
        ${isWorking ? '<span class="badge badge-success">On Duty</span>' : '<span class="badge badge-warning">Off Duty (Closed)</span>'}
      </div>
    </div>
    <div class="metrics-grid">
      <div class="metric-item">
        <span class="label">Operating Hours</span>
        <span class="value">${doc.work_start_time} - ${doc.work_end_time}</span>
      </div>
      <div class="metric-item">
        <span class="label">Booked Time</span>
        <span class="value">${data.booked_minutes} mins</span>
      </div>
      <div class="metric-item">
        <span class="label">Free Available</span>
        <span class="value">${data.free_minutes} mins</span>
      </div>
      <div class="metric-item">
        <span class="label">Doctor Utilization</span>
        <span class="value">${data.utilization_percent}%</span>
      </div>
    </div>
  `;

  // Timeline list
  elements.timelineContainer.innerHTML = '';

  if (!data.timeline || data.timeline.length === 0) {
    elements.timelineContainer.innerHTML = '<div class="empty-state"><p>No scheduled hours on this date.</p></div>';
    return;
  }

  data.timeline.forEach(block => {
    const sTime = formatTime(block.start_time);
    const eTime = formatTime(block.end_time);

    const blockDiv = document.createElement('div');
    blockDiv.className = `timeline-block ${block.type.toLowerCase()}`;

    if (block.type === 'BOOKED') {
      const appt = block.appointment;
      const statusBadge = appt.status === 'COMPLETED'
        ? '<span class="badge badge-info">Completed</span>'
        : (appt.status === 'NO_SHOW' ? '<span class="badge badge-danger">No Show</span>' : '<span class="badge badge-success">Confirmed</span>');

      blockDiv.innerHTML = `
        <div class="block-time">
          <span>${sTime} - ${eTime}</span>
          <span class="duration">${block.duration_minutes} mins</span>
        </div>
        <div class="block-content">
          <div class="block-patient-name">
            <span>${escapeHtml(appt.patient_name)}</span>
            ${statusBadge}
          </div>
          <div class="block-notes">
            ${appt.patient_phone ? `<span>Phone: ${escapeHtml(appt.patient_phone)}</span> &bull; ` : ''}
            <span>${escapeHtml(appt.notes || 'Routine consultation')}</span>
          </div>
        </div>
        <div class="block-actions">
          ${appt.status === 'CONFIRMED' ? `
            <button class="btn btn-secondary btn-sm btn-resched-appt" data-id="${appt.id}">Reschedule</button>
            <button class="btn btn-secondary btn-sm btn-comp-appt" data-id="${appt.id}" style="color: var(--success); font-weight: 600;">Complete</button>
            <button class="btn btn-secondary btn-sm btn-cancel-appt" data-id="${appt.id}">Cancel</button>
          ` : ''}
        </div>
      `;

      if (appt.status === 'CONFIRMED') {
        blockDiv.querySelector('.btn-resched-appt').addEventListener('click', () => {
          openRescheduleModal(appt);
        });
        blockDiv.querySelector('.btn-comp-appt').addEventListener('click', () => {
          completeAppointment(appt.id);
        });
        blockDiv.querySelector('.btn-cancel-appt').addEventListener('click', () => {
          openCancelModal(appt.id);
        });
      }
    } else {
      // FREE slot
      blockDiv.innerHTML = `
        <div class="block-time">
          <span>${sTime} - ${eTime}</span>
          <span class="duration">${block.duration_minutes} mins available</span>
        </div>
        <div class="block-content">
          <span style="color: var(--text-muted); font-size: 0.9rem;">Open Slot (No conflicts)</span>
        </div>
        <div class="block-actions">
          <button class="btn btn-secondary btn-sm btn-book-slot" 
                  data-start="${block.start_time}" 
                  data-duration="${Math.min(block.duration_minutes, 30)}">
            + Book Slot
          </button>
        </div>
      `;

      blockDiv.querySelector('.btn-book-slot').addEventListener('click', (e) => {
        const startIso = e.currentTarget.dataset.start;
        const dur = e.currentTarget.dataset.duration;
        openBookModalWithPreset(state.selectedDoctorId, startIso, dur);
      });
    }

    elements.timelineContainer.appendChild(blockDiv);
  });

  // Cancelled section
  if (data.cancelled_appointments && data.cancelled_appointments.length > 0) {
    elements.cancelledSection.style.display = 'block';
    elements.cancelledList.innerHTML = '';
    data.cancelled_appointments.forEach(ca => {
      const cTime = formatTime(ca.start_time);
      const feeText = ca.cancellation ? `Fee: $${ca.cancellation.fee.toFixed(2)} ${ca.cancellation.waived ? '(Waived)' : ''}` : '';
      const item = document.createElement('div');
      item.className = 'cancelled-card';
      item.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <strong>${escapeHtml(ca.patient_name)} (${cTime})</strong>
          <span class="badge ${ca.status === 'CANCELLED_LATE' ? 'badge-danger' : 'badge-warning'}">${ca.status}</span>
        </div>
        <div style="font-size: 0.85rem; color: var(--text-muted); margin-top: 4px;">
          ${feeText ? `<span>${feeText}</span> &bull; ` : ''}
          <span>Reason: ${escapeHtml(ca.cancellation?.reason || 'No reason provided')}</span>
        </div>
      `;
      elements.cancelledList.appendChild(item);
    });
  }
}

// ============================== Modal Setup ==============================

function setupModals() {
  // Booking modal
  elements.btnOpenBookModal.addEventListener('click', () => {
    openBookModalWithPreset(state.selectedDoctorId, null, 30);
  });
  elements.btnCloseBookModal.addEventListener('click', closeBookModal);
  elements.btnCancelBookModal.addEventListener('click', closeBookModal);
  elements.bookForm.addEventListener('submit', handleBookSubmit);

  // Add Doctor modal
  elements.btnOpenAddDoctorModal.addEventListener('click', openAddDoctorModal);
  elements.btnCloseAddDoctorModal.addEventListener('click', closeAddDoctorModal);
  elements.btnCancelAddDoctorModal.addEventListener('click', closeAddDoctorModal);
  elements.addDoctorForm.addEventListener('submit', handleAddDoctorSubmit);

  // Cancellation modal
  elements.btnCloseCancelModal.addEventListener('click', closeCancelModal);
  elements.btnDismissCancelModal.addEventListener('click', closeCancelModal);
  elements.cancelForm.addEventListener('submit', handleCancelSubmit);

  // Reschedule modal (Twist 1 / T6)
  elements.btnCloseRescheduleModal.addEventListener('click', closeRescheduleModal);
  elements.btnCancelRescheduleModal.addEventListener('click', closeRescheduleModal);
  elements.rescheduleForm.addEventListener('submit', handleRescheduleSubmit);

  // Waiver toggle
  elements.cancelWaiveFee.addEventListener('change', (e) => {
    elements.waiverReasonGroup.style.display = e.target.checked ? 'block' : 'none';
    elements.cancelWaiverReason.required = e.target.checked;
  });
}

// ============================== Booking Modal ==============================

function openBookModalWithPreset(doctorId, startIso, duration) {
  elements.bookingConflictAlert.style.display = 'none';
  elements.bookDoctor.value = doctorId || (state.doctors[0]?.id || '');

  if (startIso) {
    const dt = new Date(startIso);
    const y = dt.getFullYear();
    const m = String(dt.getMonth() + 1).padStart(2, '0');
    const d = String(dt.getDate()).padStart(2, '0');
    const hh = String(dt.getHours()).padStart(2, '0');
    const mm = String(dt.getMinutes()).padStart(2, '0');

    elements.bookDate.value = `${y}-${m}-${d}`;
    elements.bookTime.value = `${hh}:${mm}`;
  } else {
    elements.bookDate.value = state.selectedDate;
    elements.bookTime.value = '09:00';
  }

  elements.bookDuration.value = String(duration || 30);
  elements.bookPatientName.value = '';
  elements.bookPatientPhone.value = '';
  elements.bookNotes.value = '';

  elements.bookModal.style.display = 'flex';
}

function closeBookModal() {
  elements.bookModal.style.display = 'none';
}

async function handleBookSubmit(e) {
  e.preventDefault();

  const docId = elements.bookDoctor.value;
  const patientName = elements.bookPatientName.value.trim();
  const dateStr = elements.bookDate.value;
  const timeStr = elements.bookTime.value;
  const duration = parseInt(elements.bookDuration.value, 10);
  const patientPhone = elements.bookPatientPhone.value.trim();
  const notes = elements.bookNotes.value.trim();

  if (!docId || !patientName || !dateStr || !timeStr) {
    showToast('Please fill in all required fields.', 'error');
    return;
  }

  const startIso = `${dateStr}T${timeStr}:00`;

  try {
    const res = await fetch('/api/appointments', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        doctor_id: docId,
        patient_name: patientName,
        start_time: startIso,
        duration_minutes: duration,
        patient_phone: patientPhone,
        notes: notes,
      }),
    });

    const data = await res.json();

    if (res.status === 409) {
      renderConflictAlert(data);
      return;
    }

    if (!res.ok) {
      throw new Error(data.error || 'Failed to book appointment');
    }

    closeBookModal();
    showToast(`Appointment booked successfully for ${patientName}!`, 'success');

    if (state.currentTab === 'schedule') {
      state.selectedDoctorId = docId;
      elements.doctorSelect.value = docId;
      state.selectedDate = dateStr;
      elements.scheduleDate.value = dateStr;
      loadSchedule();
    }
  } catch (err) {
    showToast(err.message, 'error');
  }
}

function renderConflictAlert(data) {
  elements.conflictTitle.textContent = "Double-Booking Prevented!";
  elements.conflictMessage.textContent = data.error;

  elements.conflictSuggestions.innerHTML = '';
  if (data.suggested_slots && data.suggested_slots.length > 0) {
    const title = document.createElement('p');
    title.innerHTML = '<strong>Next Available Free Slots on this Day:</strong>';
    elements.conflictSuggestions.appendChild(title);

    const list = document.createElement('ul');
    data.suggested_slots.forEach(slot => {
      const li = document.createElement('li');
      const btn = document.createElement('a');
      btn.href = '#';
      btn.style.color = 'var(--primary)';
      btn.style.fontWeight = '600';
      btn.textContent = slot.formatted;
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        const dt = new Date(slot.start_time);
        const hours = String(dt.getHours()).padStart(2, '0');
        const mins = String(dt.getMinutes()).padStart(2, '0');
        elements.bookTime.value = `${hours}:${mins}`;
        elements.bookingConflictAlert.style.display = 'none';
      });
      li.appendChild(btn);
      list.appendChild(li);
    });
    elements.conflictSuggestions.appendChild(list);
  }

  elements.bookingConflictAlert.style.display = 'block';
}

// ============================== Reschedule Modal (Twist 1 / T6) ==============================

function openRescheduleModal(appt) {
  elements.rescheduleConflictAlert.style.display = 'none';
  elements.rescheduleApptId.value = appt.id;

  const dt = new Date(appt.start_time);
  const y = dt.getFullYear();
  const m = String(dt.getMonth() + 1).padStart(2, '0');
  const d = String(dt.getDate()).padStart(2, '0');
  const hh = String(dt.getHours()).padStart(2, '0');
  const mm = String(dt.getMinutes()).padStart(2, '0');

  elements.rescheduleDate.value = `${y}-${m}-${d}`;
  elements.rescheduleTime.value = `${hh}:${mm}`;
  elements.rescheduleDuration.value = '';

  elements.rescheduleApptSummary.innerHTML = `
    <div><strong>Patient:</strong> ${escapeHtml(appt.patient_name)}</div>
    <div><strong>Doctor:</strong> ${escapeHtml(appt.doctor_name || state.doctors.find(d => d.id === appt.doctor_id)?.name || '')}</div>
    <div><strong>Current Scheduled Time:</strong> ${dt.toLocaleString()}</div>
  `;

  elements.rescheduleModal.style.display = 'flex';
}

function closeRescheduleModal() {
  elements.rescheduleModal.style.display = 'none';
}

async function handleRescheduleSubmit(e) {
  e.preventDefault();
  const apptId = elements.rescheduleApptId.value;
  const dateStr = elements.rescheduleDate.value;
  const timeStr = elements.rescheduleTime.value;
  const durationVal = elements.rescheduleDuration.value;

  const newStartIso = `${dateStr}T${timeStr}:00`;

  try {
    const payload = {
      new_start_time: newStartIso,
    };
    if (durationVal) {
      payload.duration_minutes = parseInt(durationVal, 10);
    }

    const res = await fetch(`/api/appointments/${apptId}/reschedule`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    const data = await res.json();

    if (res.status === 409) {
      renderRescheduleConflictAlert(data);
      return;
    }

    if (!res.ok) {
      throw new Error(data.error || 'Failed to reschedule appointment');
    }

    closeRescheduleModal();
    showToast('Appointment rescheduled successfully (conflict-free)!', 'success');

    if (state.currentTab === 'schedule') {
      loadSchedule();
    } else if (state.currentTab === 'search') {
      executePatientSearch();
    }
  } catch (err) {
    showToast(err.message, 'error');
  }
}

function renderRescheduleConflictAlert(data) {
  elements.rescheduleConflictTitle.textContent = "Scheduling Conflict Detected!";
  elements.rescheduleConflictMessage.textContent = data.error;

  elements.rescheduleConflictSuggestions.innerHTML = '';
  if (data.suggested_slots && data.suggested_slots.length > 0) {
    const title = document.createElement('p');
    title.innerHTML = '<strong>Next Available Free Slots on this Day:</strong>';
    elements.rescheduleConflictSuggestions.appendChild(title);

    const list = document.createElement('ul');
    data.suggested_slots.forEach(slot => {
      const li = document.createElement('li');
      const btn = document.createElement('a');
      btn.href = '#';
      btn.style.color = 'var(--primary)';
      btn.style.fontWeight = '600';
      btn.textContent = slot.formatted;
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        const dt = new Date(slot.start_time);
        const hours = String(dt.getHours()).padStart(2, '0');
        const mins = String(dt.getMinutes()).padStart(2, '0');
        elements.rescheduleTime.value = `${hours}:${mins}`;
        elements.rescheduleConflictAlert.style.display = 'none';
      });
      li.appendChild(btn);
      list.appendChild(li);
    });
    elements.rescheduleConflictSuggestions.appendChild(list);
  }

  elements.rescheduleConflictAlert.style.display = 'block';
}

// ============================== Complete Appointment ==============================

async function completeAppointment(appointmentId) {
  try {
    const res = await fetch(`/api/appointments/${appointmentId}/complete`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.error || 'Failed to complete appointment');
    }
    showToast('Appointment marked as COMPLETED!', 'success');
    if (state.currentTab === 'schedule') {
      loadSchedule();
    } else if (state.currentTab === 'search') {
      executePatientSearch();
    }
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// ============================== Add Doctor Modal ==============================

function openAddDoctorModal() {
  elements.newDocName.value = '';
  elements.newDocSpecialty.value = '';
  elements.newDocRoom.value = '';
  elements.newDocStart.value = '08:30';
  elements.newDocEnd.value = '17:00';
  document.querySelectorAll('input[name="workDay"]').forEach(cb => {
    cb.checked = parseInt(cb.value, 10) < 5;
  });
  elements.addDoctorModal.style.display = 'flex';
}

function closeAddDoctorModal() {
  elements.addDoctorModal.style.display = 'none';
}

async function handleAddDoctorSubmit(e) {
  e.preventDefault();
  const name = elements.newDocName.value.trim();
  const specialty = elements.newDocSpecialty.value.trim();
  const room = elements.newDocRoom.value.trim();
  const startTime = elements.newDocStart.value.trim();
  const endTime = elements.newDocEnd.value.trim();

  const workingDays = [];
  document.querySelectorAll('input[name="workDay"]:checked').forEach(cb => {
    workingDays.push(parseInt(cb.value, 10));
  });

  if (workingDays.length === 0) {
    showToast('Please select at least one working day for the doctor.', 'error');
    return;
  }

  try {
    const res = await fetch('/api/doctors', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: name,
        specialty: specialty,
        room: room,
        work_start_time: startTime,
        work_end_time: endTime,
        working_days: workingDays,
      }),
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.error || 'Failed to onboard doctor');
    }

    closeAddDoctorModal();
    showToast(`Doctor ${data.doctor.name} onboarded successfully!`, 'success');

    await loadDoctors();
    state.selectedDoctorId = data.doctor.id;
    elements.doctorSelect.value = data.doctor.id;
    loadSchedule();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// ============================== Cancellation Modal ==============================

async function openCancelModal(appointmentId) {
  try {
    const res = await fetch(`/api/appointments/${appointmentId}/preview-cancel`);
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.error || 'Failed to preview cancellation');
    }
    const preview = await res.json();

    elements.cancelApptId.value = appointmentId;
    elements.cancelReason.value = '';
    elements.cancelWaiveFee.checked = false;
    elements.waiverReasonGroup.style.display = 'none';
    elements.cancelWaiverReason.value = '';

    elements.cancelApptSummary.innerHTML = `
      <div><strong>Patient:</strong> ${escapeHtml(preview.patient_name)}</div>
      <div><strong>Doctor:</strong> ${escapeHtml(preview.doctor_name)}</div>
      <div><strong>Scheduled For:</strong> ${new Date(preview.appointment_start).toLocaleString()}</div>
      <div><strong>Notice Given:</strong> ${preview.notice_hours} hours</div>
    `;

    if (preview.is_late) {
      elements.cancelNoticeBanner.className = 'alert alert-danger';
      elements.cancelNoticeBanner.innerHTML = `
        <strong>Late Cancellation Notice (&lt; 24h)</strong>
        <p>This cancellation gives only ${preview.notice_hours} hours notice. Per clinic policy, a <strong>$${preview.fee.toFixed(2)} late fee</strong> will be assessed.</p>
      `;
      elements.waiverBox.style.display = 'block';
    } else {
      elements.cancelNoticeBanner.className = 'alert alert-success';
      elements.cancelNoticeBanner.innerHTML = `
        <strong>Adequate Notice Given (&ge; 24h)</strong>
        <p>This cancellation qualifies for <strong>Free Cancellation ($0.00 fee)</strong>.</p>
      `;
      elements.waiverBox.style.display = 'none';
    }

    elements.cancelModal.style.display = 'flex';
  } catch (err) {
    showToast(`Error: ${err.message}`, 'error');
  }
}

function closeCancelModal() {
  elements.cancelModal.style.display = 'none';
}

async function handleCancelSubmit(e) {
  e.preventDefault();
  const apptId = elements.cancelApptId.value;
  const reason = elements.cancelReason.value.trim();
  const waive = elements.cancelWaiveFee.checked;
  const waiverReason = elements.cancelWaiverReason.value.trim();

  try {
    const res = await fetch(`/api/appointments/${apptId}/cancel`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        reason: reason,
        waive: waive,
        waiver_reason: waiverReason,
      }),
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.error || 'Failed to cancel appointment');
    }

    closeCancelModal();
    const feeInfo = data.appointment.cancellation?.fee > 0 ? `Assessed fee: $${data.appointment.cancellation.fee.toFixed(2)}` : 'Cancellation was free.';
    showToast(`Appointment cancelled. Slot freed immediately! ${feeInfo}`, 'success');

    if (state.currentTab === 'schedule') {
      loadSchedule();
    } else if (state.currentTab === 'search') {
      executePatientSearch();
    } else if (state.currentTab === 'ledger') {
      loadLedger();
    }
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// ============================== Patient Search ==============================

let searchDebounceTimer = null;

function setupSearch() {
  elements.patientSearchInput.addEventListener('input', (e) => {
    clearTimeout(searchDebounceTimer);
    searchDebounceTimer = setTimeout(() => {
      executePatientSearch();
    }, 250);
  });

  elements.btnClearSearch.addEventListener('click', () => {
    elements.patientSearchInput.value = '';
    elements.searchResultsContainer.innerHTML = '<div class="empty-state"><p>Type a patient\'s name above to view their appointments.</p></div>';
  });
}

async function executePatientSearch() {
  const q = elements.patientSearchInput.value.trim();
  if (!q) {
    elements.searchResultsContainer.innerHTML = '<div class="empty-state"><p>Type a patient\'s name above to view their appointments.</p></div>';
    return;
  }

  try {
    const res = await fetch(`/api/patients/search?query=${encodeURIComponent(q)}`);
    const data = await res.json();
    renderSearchResults(data.results || []);
  } catch (err) {
    showToast(`Search error: ${err.message}`, 'error');
  }
}

function renderSearchResults(results) {
  elements.searchResultsContainer.innerHTML = '';

  if (results.length === 0) {
    elements.searchResultsContainer.innerHTML = '<div class="empty-state"><p>No patients found matching your search.</p></div>';
    return;
  }

  results.forEach(item => {
    const p = item.patient;
    const appts = item.appointments;

    const card = document.createElement('div');
    card.className = 'patient-search-card';

    let apptRows = '';
    if (appts.length === 0) {
      apptRows = '<tr><td colspan="5" class="text-center" style="color: var(--text-muted);">No booking history on file.</td></tr>';
    } else {
      appts.forEach(a => {
        const sDt = new Date(a.start_time).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' });
        let statusBadge = `<span class="badge badge-info">${a.status}</span>`;
        if (a.status === 'CONFIRMED') statusBadge = '<span class="badge badge-success">Confirmed</span>';
        if (a.status === 'CANCELLED_LATE') statusBadge = '<span class="badge badge-danger">Late Cancel</span>';
        if (a.status === 'CANCELLED_FREE') statusBadge = '<span class="badge badge-warning">Cancelled</span>';
        if (a.status === 'NO_SHOW') statusBadge = '<span class="badge badge-danger">No Show</span>';

        const actionBtns = a.status === 'CONFIRMED' ? `
          <button class="btn btn-secondary btn-sm" onclick="openRescheduleModalById('${a.id}', '${escapeHtml(a.patient_name)}', '${escapeHtml(a.doctor_name)}', '${a.start_time}')">Reschedule</button>
          <button class="btn btn-secondary btn-sm" onclick="completeAppointment('${a.id}')">Complete</button>
          <button class="btn btn-secondary btn-sm" onclick="openCancelModal('${a.id}')">Cancel</button>
        ` : '-';

        apptRows += `
          <tr>
            <td>${sDt}</td>
            <td><strong>${escapeHtml(a.doctor_name)}</strong></td>
            <td>${statusBadge}</td>
            <td>${escapeHtml(a.notes || '')}</td>
            <td>${actionBtns}</td>
          </tr>
        `;
      });
    }

    card.innerHTML = `
      <div class="patient-card-header">
        <div>
          <h4>${escapeHtml(p.name)}</h4>
          <p>Phone: ${escapeHtml(p.phone)} ${p.email ? `&bull; Email: ${escapeHtml(p.email)}` : ''}</p>
        </div>
        <button class="btn btn-secondary btn-sm" onclick="openBookModalForPatient('${p.id}', '${escapeHtml(p.name)}', '${escapeHtml(p.phone)}')">+ Book for Patient</button>
      </div>
      <div class="table-responsive" style="margin-top: 12px;">
        <table class="data-table">
          <thead>
            <tr>
              <th>Date & Time</th>
              <th>Doctor</th>
              <th>Status</th>
              <th>Notes</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            ${apptRows}
          </tbody>
        </table>
      </div>
    `;

    elements.searchResultsContainer.appendChild(card);
  });
}

window.openBookModalForPatient = function(patientId, name, phone) {
  openBookModalWithPreset(state.selectedDoctorId, null, 30);
  elements.bookPatientName.value = name;
  elements.bookPatientPhone.value = phone;
};

window.openRescheduleModalById = function(apptId, patientName, doctorName, startTime) {
  openRescheduleModal({
    id: apptId,
    patient_name: patientName,
    doctor_name: doctorName,
    start_time: startTime,
  });
};

window.openCancelModal = openCancelModal;
window.completeAppointment = completeAppointment;

// ============================== Cancellation Ledger ==============================

function setupLedger() {
  elements.btnRefreshLedger.addEventListener('click', loadLedger);
}

async function loadLedger() {
  try {
    const res = await fetch('/api/ledger');
    const data = await res.json();
    renderLedger(data);
  } catch (err) {
    showToast(`Error loading ledger: ${err.message}`, 'error');
  }
}

function renderLedger(data) {
  const sum = data.summary;
  elements.ledgerKpis.innerHTML = `
    <div class="ledger-kpi">
      <div class="label">Total Cancellations</div>
      <div class="value">${sum.total_cancellations}</div>
    </div>
    <div class="ledger-kpi">
      <div class="label">Late Fees Billed</div>
      <div class="value" style="color: var(--danger);">$${sum.total_fees_collected.toFixed(2)}</div>
    </div>
    <div class="ledger-kpi">
      <div class="label">Fees Waived (Supervisor)</div>
      <div class="value" style="color: var(--warning);">$${sum.total_fees_waived.toFixed(2)}</div>
    </div>
    <div class="ledger-kpi">
      <div class="label">Free Cancellations</div>
      <div class="value" style="color: var(--success);">${sum.free_cancellations}</div>
    </div>
  `;

  elements.ledgerTableBody.innerHTML = '';
  if (!data.records || data.records.length === 0) {
    elements.ledgerTableBody.innerHTML = '<tr><td colspan="7" class="text-center">No cancellation records on file.</td></tr>';
    return;
  }

  data.records.forEach(r => {
    const tr = document.createElement('tr');
    const cDt = new Date(r.cancelled_at).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' });
    const feeDisplay = r.waived ? `<span style="text-decoration: line-through;">$${r.fee.toFixed(2)}</span> <span class="badge badge-warning">Waived</span>` : `$${r.fee.toFixed(2)}`;

    tr.innerHTML = `
      <td>${cDt}</td>
      <td><strong>${escapeHtml(r.patient_name)}</strong></td>
      <td>${escapeHtml(r.doctor_name)}</td>
      <td>${r.notice_hours} hrs</td>
      <td>${r.is_late ? '<span class="badge badge-danger">Late Cancellation</span>' : '<span class="badge badge-info">On-Time (Free)</span>'}</td>
      <td><strong>${feeDisplay}</strong></td>
      <td>${escapeHtml(r.reason || '')} ${r.waiver_reason ? `<em>(Waiver: ${escapeHtml(r.waiver_reason)})</em>` : ''}</td>
    `;
    elements.ledgerTableBody.appendChild(tr);
  });
}

// ============================== Clock & Outbox (Twists 2 & 3) ==============================

function setupClockAndOutbox() {
  elements.btnRefreshOutbox.addEventListener('click', loadOutbox);
  elements.btnClearOutbox.addEventListener('click', clearOutbox);

  elements.btnAdvanceClock.addEventListener('click', () => {
    const val = elements.advanceClockInput.value;
    if (!val) {
      showToast('Please select a valid date/time to advance the clock to.', 'error');
      return;
    }
    advanceClock(val);
  });

  elements.btnAdvance30Min.addEventListener('click', () => {
    if (!state.currentSimulatedTime) return;
    const cur = new Date(state.currentSimulatedTime);
    cur.setMinutes(cur.getMinutes() + 30);
    advanceClock(cur.toISOString());
  });

  elements.btnAdvanceTomorrowMorning.addEventListener('click', () => {
    if (!state.currentSimulatedTime) return;
    const cur = new Date(state.currentSimulatedTime);
    cur.setDate(cur.getDate() + 1);
    cur.setHours(8, 0, 0, 0);
    advanceClock(cur.toISOString());
  });
}

async function loadClock() {
  try {
    const res = await fetch('/clock');
    const data = await res.json();
    state.currentSimulatedTime = data.current_time;
    const dt = new Date(data.current_time);
    elements.currentClockDisplay.textContent = dt.toLocaleString();

    // Populate advance clock input with current + 30 min as default placeholder
    const nextDt = new Date(dt.getTime() + 30 * 60000);
    const localIso = new Date(nextDt.getTime() - nextDt.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
    elements.advanceClockInput.value = localIso;
  } catch (err) {
    console.error('Error loading clock:', err);
  }
}

async function advanceClock(timeStr) {
  try {
    const res = await fetch('/clock', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ current_time: timeStr }),
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.error || 'Failed to advance clock');
    }
    showToast(`System clock advanced to ${data.current_time}! Automated jobs executed.`, 'success');
    await loadClock();
    await loadOutbox();
    if (state.currentTab === 'schedule') {
      loadSchedule();
    }
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function loadOutbox() {
  try {
    const res = await fetch('/outbox');
    const outbox = await res.json();
    renderOutbox(outbox);
  } catch (err) {
    showToast(`Error loading outbox: ${err.message}`, 'error');
  }
}

async function clearOutbox() {
  try {
    const res = await fetch('/outbox', { method: 'DELETE' });
    if (!res.ok) throw new Error('Failed to clear outbox');
    showToast('Outbox cleared.', 'success');
    loadOutbox();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

function renderOutbox(outbox) {
  elements.outboxTableBody.innerHTML = '';
  if (!outbox || outbox.length === 0) {
    elements.outboxTableBody.innerHTML = '<tr><td colspan="6" class="text-center">No notifications in outbox.</td></tr>';
    return;
  }

  outbox.forEach(n => {
    const tr = document.createElement('tr');
    const createdDt = new Date(n.created_at).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' });
    const apptDt = new Date(n.appointment_time).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' });

    tr.innerHTML = `
      <td>${createdDt}</td>
      <td><strong>${escapeHtml(n.recipient_name)}</strong></td>
      <td>${escapeHtml(n.recipient_contact || 'N/A')}</td>
      <td>${escapeHtml(n.doctor_name)}</td>
      <td>${apptDt}</td>
      <td><span style="font-size: 0.9rem;">${escapeHtml(n.message)}</span></td>
    `;
    elements.outboxTableBody.appendChild(tr);
  });
}

// ============================== Helpers ==============================

function formatTime(isoString) {
  const dt = new Date(isoString);
  return dt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
}

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function showToast(message, type = 'info') {
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.textContent = message;
  elements.toastContainer.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    setTimeout(() => toast.remove(), 250);
  }, 3500);
}

// Kick off
window.addEventListener('DOMContentLoaded', init);
