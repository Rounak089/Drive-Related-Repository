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

  // Set default date input
  elements.scheduleDate.value = state.selectedDate;
  elements.bookDate.value = state.selectedDate;

  // Load doctors
  await loadDoctors();

  // Load initial schedule
  if (state.selectedDoctorId) {
    await loadSchedule();
  }
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
      document.getElementById(`tab-${targetTab}`).classList.add('active');

      if (targetTab === 'schedule') {
        loadSchedule();
      } else if (targetTab === 'ledger') {
        loadLedger();
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
    const today = new Date().toISOString().split('T')[0];
    state.selectedDate = today;
    elements.scheduleDate.value = today;
    loadSchedule();
  });
}

function changeDay(offsetDays) {
  const current = new Date(state.selectedDate + 'T00:00:00');
  current.setDate(current.getDate() + offsetDays);
  const nextDate = current.toISOString().split('T')[0];
  state.selectedDate = nextDate;
  elements.scheduleDate.value = nextDate;
  loadSchedule();
}

async function loadSchedule() {
  if (!state.selectedDoctorId || !state.selectedDate) return;

  elements.timelineContainer.innerHTML = '<div class="loading-spinner">Loading doctor schedule...</div>';

  try {
    const res = await fetch(`/api/schedule?doctor_id=${state.selectedDoctorId}&date=${state.selectedDate}`);
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.error || 'Failed to load schedule');
    }
    const data = await res.json();
    state.activeScheduleData = data;
    renderSchedule(data);
  } catch (err) {
    elements.timelineContainer.innerHTML = `<div class="alert alert-danger">Error: ${err.message}</div>`;
  }
}

function renderSchedule(data) {
  const doc = data.doctor;
  elements.activeApptCount.textContent = `${data.active_appointment_count} active appointment${data.active_appointment_count === 1 ? '' : 's'}`;

  // Doctor metrics card
  elements.doctorMetrics.innerHTML = `
    <div class="metric-doctor-info">
      <h3>${doc.name}</h3>
      <p>${doc.specialty} &bull; ${doc.room}</p>
      <p style="margin-top: 4px;">Working Shift: <strong>${doc.work_start_time} - ${doc.work_end_time}</strong> ${data.is_working_day ? '' : '<span class="badge badge-warning">Off Day</span>'}</p>
    </div>
    <div class="metric-stat">
      <span class="label">Booked Time</span>
      <span class="value">${data.booked_minutes} min</span>
    </div>
    <div class="metric-stat">
      <span class="label">Open Free Time</span>
      <span class="value" style="color: var(--primary);">${data.free_minutes} min</span>
    </div>
    <div class="metric-stat">
      <span class="label">Utilization</span>
      <span class="value">${data.utilization_percent}%</span>
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
      blockDiv.innerHTML = `
        <div class="block-time">
          <span>${sTime} - ${eTime}</span>
          <span class="duration">${block.duration_minutes} mins</span>
        </div>
        <div class="block-content">
          <div class="block-patient-name">
            <span>${escapeHtml(appt.patient_name)}</span>
            <span class="badge badge-success">Confirmed</span>
          </div>
          <div class="block-notes">
            ${appt.patient_phone ? `<span>Phone: ${escapeHtml(appt.patient_phone)}</span> &bull; ` : ''}
            <span>${escapeHtml(appt.notes || 'Routine consultation')}</span>
          </div>
        </div>
        <div class="block-actions">
          <button class="btn btn-secondary btn-sm btn-cancel-appt" data-id="${appt.id}">Cancel</button>
        </div>
      `;

      blockDiv.querySelector('.btn-cancel-appt').addEventListener('click', () => {
        openCancelModal(appt.id);
      });
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
        <div>
          <strong>${cTime} &bull; ${escapeHtml(ca.patient_name)}</strong>
          <span class="badge badge-danger" style="margin-left: 8px;">${ca.status}</span>
          <p style="color: var(--text-muted); font-size: 0.8rem; margin-top: 2px;">
            Reason: ${escapeHtml(ca.cancellation?.reason || 'No reason provided')}
          </p>
        </div>
        <div style="font-weight: 600; color: ${ca.cancellation?.fee > 0 ? 'var(--danger)' : 'var(--text-muted)'};">
          ${feeText}
        </div>
      `;
      elements.cancelledList.appendChild(item);
    });
  } else {
    elements.cancelledSection.style.display = 'none';
  }
}

// ============================== Booking Modal ==============================

function setupModals() {
  elements.btnOpenBookModal.addEventListener('click', () => {
    openBookModalWithPreset(state.selectedDoctorId, null, 30);
  });

  elements.btnCloseBookModal.addEventListener('click', closeBookModal);
  elements.btnCancelBookModal.addEventListener('click', closeBookModal);

  elements.bookForm.addEventListener('submit', handleBookSubmit);

  // Cancellation modal buttons
  elements.btnCloseCancelModal.addEventListener('click', closeCancelModal);
  elements.btnDismissCancelModal.addEventListener('click', closeCancelModal);
  elements.cancelForm.addEventListener('submit', handleCancelSubmit);

  elements.cancelWaiveFee.addEventListener('change', (e) => {
    elements.waiverReasonGroup.style.display = e.target.checked ? 'block' : 'none';
    elements.cancelWaiverReason.required = e.target.checked;
  });
}

function openBookModalWithPreset(doctorId, startIso, duration) {
  elements.bookingConflictAlert.style.display = 'none';
  elements.bookForm.reset();

  if (doctorId) {
    elements.bookDoctor.value = doctorId;
  }

  if (startIso) {
    const dt = new Date(startIso);
    elements.bookDate.value = dt.toISOString().split('T')[0];
    const hours = String(dt.getHours()).padStart(2, '0');
    const mins = String(dt.getMinutes()).padStart(2, '0');
    elements.bookTime.value = `${hours}:${mins}`;
  } else {
    elements.bookDate.value = state.selectedDate;
    elements.bookTime.value = '09:00';
  }

  if (duration) {
    elements.bookDuration.value = String(duration);
  }

  elements.bookModal.style.display = 'flex';
}

function closeBookModal() {
  elements.bookModal.style.display = 'none';
  elements.bookingConflictAlert.style.display = 'none';
}

async function handleBookSubmit(e) {
  e.preventDefault();
  elements.bookingConflictAlert.style.display = 'none';

  const docId = elements.bookDoctor.value;
  const dateStr = elements.bookDate.value;
  const timeStr = elements.bookTime.value;
  const duration = parseInt(elements.bookDuration.value, 10);
  const patientName = elements.bookPatientName.value.trim();
  const patientPhone = elements.bookPatientPhone.value.trim();
  const notes = elements.bookNotes.value.trim();

  const startIso = `${dateStr}T${timeStr}:00`;

  try {
    const res = await fetch('/api/appointments', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        doctor_id: docId,
        patient_name: patientName,
        patient_phone: patientPhone,
        start_time: startIso,
        duration_minutes: duration,
        notes: notes,
      }),
    });

    const data = await res.json();

    if (res.status === 409) {
      // Conflict! Double-booking prevented!
      renderConflictAlert(data);
      return;
    }

    if (!res.ok) {
      throw new Error(data.error || 'Failed to book appointment');
    }

    closeBookModal();
    showToast(`Appointment booked successfully for ${patientName}!`, 'success');

    // If on schedule tab, refresh schedule
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

    // Refresh active views
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
    elements.searchResultsContainer.innerHTML = '<div class="empty-state"><p>Type a patient\'s name above to view appointments.</p></div>';
  });
}

async function executePatientSearch() {
  const query = elements.patientSearchInput.value.trim();
  if (!query) {
    elements.searchResultsContainer.innerHTML = '<div class="empty-state"><p>Type a patient\'s name above to view appointments.</p></div>';
    return;
  }

  try {
    const res = await fetch(`/api/patients/search?query=${encodeURIComponent(query)}`);
    const data = await res.json();
    renderSearchResults(data.results || []);
  } catch (err) {
    elements.searchResultsContainer.innerHTML = `<div class="alert alert-danger">Search error: ${err.message}</div>`;
  }
}

function renderSearchResults(results) {
  elements.searchResultsContainer.innerHTML = '';

  if (results.length === 0) {
    elements.searchResultsContainer.innerHTML = '<div class="empty-state"><p>No matching patients found.</p></div>';
    return;
  }

  results.forEach(item => {
    const p = item.patient;
    const appts = item.appointments;

    const card = document.createElement('div');
    card.className = 'patient-card';

    let apptRows = '';
    if (appts.length === 0) {
      apptRows = '<tr><td colspan="5" style="color: var(--text-muted);">No appointment records found.</td></tr>';
    } else {
      apptRows = appts.map(a => {
        const sDt = new Date(a.start_time).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' });
        let statusBadge = '';
        let actionBtn = '';

        if (a.status === 'CONFIRMED') {
          statusBadge = '<span class="badge badge-success">Confirmed</span>';
          actionBtn = `<button class="btn btn-secondary btn-sm" onclick="openCancelModal('${a.id}')">Cancel</button>`;
        } else if (a.status === 'CANCELLED_FREE') {
          statusBadge = '<span class="badge badge-info">Cancelled (Free)</span>';
        } else if (a.status === 'CANCELLED_LATE') {
          const feeStr = a.cancellation?.waived ? 'Fee: $0 (Waived)' : `$${a.cancellation?.fee.toFixed(2)}`;
          statusBadge = `<span class="badge badge-danger">Cancelled (Late) &bull; ${feeStr}</span>`;
        } else {
          statusBadge = `<span class="badge badge-warning">${a.status}</span>`;
        }

        return `
          <tr>
            <td><strong>${sDt}</strong></td>
            <td>${escapeHtml(a.doctor_name || 'N/A')}</td>
            <td>${escapeHtml(a.notes || 'General Consult')}</td>
            <td>${statusBadge}</td>
            <td>${actionBtn}</td>
          </tr>
        `;
      }).join('');
    }

    card.innerHTML = `
      <div class="patient-header">
        <div>
          <h3>${escapeHtml(p.name)}</h3>
          <div class="patient-contact">Phone: ${escapeHtml(p.phone)} ${p.email ? `&bull; Email: ${escapeHtml(p.email)}` : ''}</div>
        </div>
        <button class="btn btn-secondary btn-sm" onclick="openBookModalForPatient('${p.id}', '${escapeHtml(p.name)}', '${escapeHtml(p.phone)}')">
          + Book For Patient
        </button>
      </div>
      <div class="table-responsive">
        <table class="data-table">
          <thead>
            <tr>
              <th>Date & Time</th>
              <th>Doctor</th>
              <th>Notes / Reason</th>
              <th>Status & Fee</th>
              <th>Action</th>
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

window.openCancelModal = openCancelModal;

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

