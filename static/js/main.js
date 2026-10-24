// ===================================================================
// ForgetGuard - Client Dashboard Application v2.0
// Smart Object Priority, Voice Alerts, Exit Checklist & Analytics
// ===================================================================

let state = {
  overview: {},
  rooms: [],
  alerts: [],
  objects: [],
  devices: [],
  checklist: [],
  history: {},
  knownAlertIds: new Set(),
  voiceEnabled: true
};

// -------------------------------------------------------------------
// Initialization
// -------------------------------------------------------------------
document.addEventListener('DOMContentLoaded', () => {
  setupNavigation();
  setupModals();
  setupEventHandlers();
  setupVoice();
  fetchAllData();

  // Auto-poll every 3 seconds for real-time telemetry updates
  setInterval(fetchAllData, 3000);
});

// -------------------------------------------------------------------
// Voice Alerts Synthesizer (Web Speech API)
// -------------------------------------------------------------------
function setupVoice() {
  const toggle = document.getElementById('voice-alerts-toggle');
  if (toggle) {
    state.voiceEnabled = toggle.checked;
    toggle.addEventListener('change', e => {
      state.voiceEnabled = e.target.checked;
      showToast(`Voice alerts ${state.voiceEnabled ? 'enabled' : 'disabled'}`, 'info');
    });
  }

  document.getElementById('btn-test-voice')?.addEventListener('click', () => {
    speakVoiceAlert('ForgetGuard voice synthesizer online. All sensors active.');
  });
}

function speakVoiceAlert(text) {
  if (!state.voiceEnabled || !('speechSynthesis' in window)) return;
  window.speechSynthesis.cancel(); // Cancel any existing speech
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = 1.0;
  utterance.pitch = 1.0;
  window.speechSynthesis.speak(utterance);
}

// -------------------------------------------------------------------
// Data Fetching & Sync
// -------------------------------------------------------------------
async function fetchAllData() {
  try {
    const [overviewRes, roomsRes, alertsRes, objectsRes, devicesRes, checkRes, histRes] = await Promise.all([
      fetch('/api/overview'),
      fetch('/api/rooms'),
      fetch('/api/alerts?unresolved=true'),
      fetch('/api/objects'),
      fetch('/api/devices'),
      fetch('/api/checklist'),
      fetch('/api/history')
    ]);

    if (!overviewRes.ok || !roomsRes.ok) return;

    state.overview = await overviewRes.json();
    state.rooms = await roomsRes.json();
    state.alerts = await alertsRes.json();
    state.objects = await objectsRes.json();
    state.devices = await devicesRes.json();
    state.checklist = await checkRes.json();
    state.history = await histRes.json();

    renderOverview();
    renderAlerts();
    renderRoomsGrid();
    renderRoomsTable();
    renderObjectsTable();
    renderDevicesTable();
    renderChecklist();
    renderHistory();
    updateModalRoomDropdowns();
  } catch (err) {
    console.error('Telemetry poll error:', err);
  }
}

// -------------------------------------------------------------------
// Render KPI Overview & Readiness Score
// -------------------------------------------------------------------
function renderOverview() {
  const o = state.overview;
  if (!o) return;

  const alertsElem = document.getElementById('kpi-alerts');
  const forgottenElem = document.getElementById('kpi-forgotten');
  const highPriElem = document.getElementById('kpi-high-pri-count');
  const devicesElem = document.getElementById('kpi-devices-on');
  const alertBadge = document.getElementById('alert-counter-badge');

  if (alertsElem) alertsElem.innerText = o.active_alerts ?? 0;
  if (forgottenElem) forgottenElem.innerText = o.forgotten_at_risk ?? 0;
  if (highPriElem) highPriElem.innerText = o.high_priority_forgotten ?? 0;
  if (devicesElem) devicesElem.innerText = o.devices_on_in_empty ?? 0;
  if (alertBadge) alertBadge.innerText = `${o.active_alerts ?? 0} Active`;

  // Departure Readiness Score Widget
  const scoreVal = document.getElementById('kpi-readiness-val');
  const barFill = document.getElementById('readiness-bar-fill');
  const statusBadge = document.getElementById('score-status-text');
  const readinessSub = document.getElementById('kpi-readiness-sub');

  const score = o.readiness_score ?? 100;
  if (scoreVal) scoreVal.innerText = `${score}%`;
  if (barFill) barFill.style.width = `${score}%`;

  if (statusBadge) {
    if (score >= 85) {
      statusBadge.innerText = 'Safe to Leave';
      statusBadge.style.color = '#10b981';
      statusBadge.style.backgroundColor = 'rgba(16, 185, 129, 0.2)';
      if (barFill) barFill.style.background = 'linear-gradient(90deg, #10b981, #06b6d4)';
      if (readinessSub) readinessSub.innerText = 'All items secured. Ready to exit.';
    } else if (score >= 50) {
      statusBadge.innerText = 'Warning: Check Items';
      statusBadge.style.color = '#f59e0b';
      statusBadge.style.backgroundColor = 'rgba(245, 158, 11, 0.2)';
      if (barFill) barFill.style.background = 'linear-gradient(90deg, #f59e0b, #e11d48)';
      if (readinessSub) readinessSub.innerText = 'Items or active electrical loads need attention.';
    } else {
      statusBadge.innerText = 'Hazard: High Risk!';
      statusBadge.style.color = '#f43f5e';
      statusBadge.style.backgroundColor = 'rgba(244, 63, 94, 0.25)';
      if (barFill) barFill.style.background = 'linear-gradient(90deg, #e11d48, #f43f5e)';
      if (readinessSub) readinessSub.innerText = 'High-priority belongings or high-power appliances left unattended!';
    }
  }

  // Hardware Node simulation status
  const hwBuzzer = document.getElementById('hw-buzzer-text');
  const hwLed = document.getElementById('hw-led-text');
  if (hwBuzzer) {
    if (o.hardware_buzzer) {
      hwBuzzer.innerText = '🔊 BEEPING ALARM';
      hwBuzzer.className = 'hw-alert';
    } else {
      hwBuzzer.innerText = 'Silent';
      hwBuzzer.className = 'hw-ok';
    }
  }
  if (hwLed) {
    if (o.hardware_led === 'RED_BLINKING') {
      hwLed.innerText = '🔴 Red Blinking (Alert)';
      hwLed.className = 'hw-alert';
    } else {
      hwLed.innerText = '🟢 Solid Green (All Clear)';
      hwLed.className = 'hw-green';
    }
  }
}

// -------------------------------------------------------------------
// Render Alerts Feed & Voice Announcements
// -------------------------------------------------------------------
function renderAlerts() {
  const container = document.getElementById('alerts-container');
  if (!container) return;

  if (state.alerts.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
        <p>All facilities secure. No forgotten belongings or unattended appliances detected.</p>
      </div>
    `;
    return;
  }

  state.alerts.forEach(a => {
    if (!state.knownAlertIds.has(a.id)) {
      state.knownAlertIds.add(a.id);
      showToast(a.title, a.severity);
      // Voice alert announcement
      speakVoiceAlert(`Warning! ${a.title} in ${a.room_name}`);
    }
  });

  container.innerHTML = state.alerts.map(a => `
    <div class="alert-item severity-${a.severity}">
      <div class="alert-body">
        <div class="alert-icon">
          ${a.severity === 'danger'
            ? `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`
            : `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`
          }
        </div>
        <div class="alert-content">
          <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.25rem;">
            <h4>${escapeHtml(a.title)}</h4>
            <span class="priority-tag priority-${a.priority || 'HIGH'}">${a.priority || 'HIGH'} PRIORITY</span>
          </div>
          <p>${escapeHtml(a.message)}</p>
          <div class="alert-meta">
            <span>Location: <strong>${escapeHtml(a.room_name)}</strong></span>
            <span>Triggered: ${new Date(a.created_at).toLocaleTimeString()}</span>
            <span>Type: ${a.alert_type}</span>
          </div>
        </div>
      </div>
      <div>
        <button class="btn btn-sm btn-secondary" onclick="resolveAlert(${a.id})">
          Resolve
        </button>
      </div>
    </div>
  `).join('');
}

// -------------------------------------------------------------------
// Render Smart Exit Checklist (Checklist Tab)
// -------------------------------------------------------------------
function renderChecklist() {
  const container = document.getElementById('checklist-container');
  if (!container) return;

  if (state.checklist.length === 0) {
    container.innerHTML = '<p class="text-muted">No checklist items configured.</p>';
    return;
  }

  container.innerHTML = state.checklist.map(item => `
    <div class="checklist-card ${item.checklist_checked ? 'completed' : ''}" onclick="toggleChecklistItem(${item.id})">
      <div class="checklist-checkbox">
        ${item.checklist_checked ? '✓' : ''}
      </div>
      <div class="checklist-info">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.25rem;">
          <h4>${escapeHtml(item.name)}</h4>
          <span class="priority-tag priority-${item.priority}">${item.priority}</span>
        </div>
        <p>Category: ${escapeHtml(item.category)} · Room: ${escapeHtml(item.room_name)}</p>
        <p style="font-size: 0.75rem; color: var(--text-dim); margin-top: 0.2rem;">Owner: ${escapeHtml(item.owner_name)} · Status: <strong>${item.checklist_checked ? 'Retrieved & Ready' : 'Pending Verification'}</strong></p>
      </div>
    </div>
  `).join('');
}

async function toggleChecklistItem(id) {
  try {
    const res = await fetch(`/api/checklist/${id}/toggle`, { method: 'POST' });
    const data = await res.json();
    showToast(data.message, 'info');
    fetchAllData();
  } catch (err) {
    showToast('Failed to update checklist item', 'danger');
  }
}

async function resetChecklist() {
  try {
    const res = await fetch('/api/checklist/reset', { method: 'POST' });
    const data = await res.json();
    showToast(data.message, 'success');
    fetchAllData();
  } catch (err) {
    showToast('Failed to reset checklist', 'danger');
  }
}

// -------------------------------------------------------------------
// Render History & Analytics (Analytics Tab)
// -------------------------------------------------------------------
function renderHistory() {
  const statRow = document.getElementById('analytics-stat-row');
  const tbody = document.getElementById('history-table-body');
  if (!statRow || !tbody) return;

  const h = state.history;
  const records = h.records || [];

  statRow.innerHTML = `
    <div class="analytics-stat-card">
      <h3>${h.total_incidents || 0}</h3>
      <p>Total Prevented Incidents</p>
    </div>
    <div class="analytics-stat-card">
      <h3>${Object.keys(h.category_stats || {}).length}</h3>
      <p>Monitored Categories</p>
    </div>
    <div class="analytics-stat-card">
      <h3>99.4%</h3>
      <p>Sensor Detection Accuracy</p>
    </div>
    <div class="analytics-stat-card">
      <h3 style="color: #10b981;">30s</h3>
      <p>Configured Empty Grace Timer</p>
    </div>
  `;

  tbody.innerHTML = records.map(r => `
    <tr>
      <td><strong>${escapeHtml(r.item_name)}</strong></td>
      <td>${escapeHtml(r.category)}</td>
      <td><span class="priority-tag priority-${r.priority}">${r.priority}</span></td>
      <td>${escapeHtml(r.room_name)}</td>
      <td><code>${r.incident_type}</code></td>
      <td>${new Date(r.created_at).toLocaleString()}</td>
      <td>${r.duration_minutes} mins</td>
    </tr>
  `).join('');
}

// -------------------------------------------------------------------
// Render Room Security Grid (Dashboard Tab)
// -------------------------------------------------------------------
function renderRoomsGrid() {
  const grid = document.getElementById('rooms-grid');
  if (!grid) return;

  if (state.rooms.length === 0) {
    grid.innerHTML = '<p class="text-muted">No rooms configured.</p>';
    return;
  }

  grid.innerHTML = state.rooms.map(room => {
    const hasDanger = !room.is_occupied && (room.present_objects_count > 0 || room.active_devices_count > 0);
    const occupancyText = room.is_occupied ? 'Occupied (People Inside)' : 'Empty / Vacant';
    const occupancyClass = room.is_occupied ? 'occupied' : 'empty';

    return `
      <div class="room-card ${hasDanger ? 'has-danger' : ''}">
        <div>
          <div class="room-card-header">
            <div class="room-title-block">
              <h3>${escapeHtml(room.name)}</h3>
              <span class="room-code-tag">${escapeHtml(room.code)}</span>
            </div>
            <span class="occupancy-pill ${occupancyClass}">
              <span class="pulse-indicator" style="background-color: ${room.is_occupied ? '#10b981' : '#f43f5e'}"></span>
              ${occupancyText}
            </span>
          </div>

          <div class="room-details-list">
            <div class="detail-row">
              <span class="detail-label">Objects Inside Room:</span>
              <span class="detail-val">
                ${room.present_objects_count} present
                ${!room.is_occupied && room.present_objects_count > 0 ? '<span class="status-tag alert-tag">Forgotten!</span>' : ''}
              </span>
            </div>

            <div class="detail-row">
              <span class="detail-label">Active Power Loads:</span>
              <span class="detail-val">
                ${room.active_devices_count} running
                ${!room.is_occupied && room.active_devices_count > 0 ? '<span class="status-tag alert-tag">Left ON!</span>' : ''}
              </span>
            </div>

            <div class="detail-row">
              <span class="detail-label">Security Alerts:</span>
              <span class="detail-val ${room.active_alerts_count > 0 ? 'text-danger' : ''}">
                ${room.active_alerts_count} active
              </span>
            </div>
          </div>

          <!-- Items detected in this room -->
          <div style="margin-top: 0.75rem;">
            <div style="font-size: 0.75rem; color: var(--text-dim); text-transform: uppercase; margin-bottom: 0.4rem; font-weight: 700;">
              Detected Belongings
            </div>
            ${room.objects.length === 0 ? '<div style="font-size: 0.8rem; color: var(--text-dim);">None registered</div>' : ''}
            <div style="display: flex; flex-direction: column; gap: 0.35rem;">
              ${room.objects.map(obj => `
                <div style="display: flex; justify-content: space-between; align-items: center; background: rgba(255,255,255,0.03); padding: 0.35rem 0.6rem; border-radius: 6px; font-size: 0.8rem;">
                  <div>
                    <span>${escapeHtml(obj.name)}</span>
                    <span class="priority-tag priority-${obj.priority}" style="margin-left: 0.35rem; font-size: 0.65rem;">${obj.priority}</span>
                  </div>
                  <button class="btn btn-sm ${obj.is_present ? 'btn-ghost' : 'btn-secondary'}" style="padding: 0.15rem 0.5rem; font-size: 0.72rem;" onclick="toggleObjectPresence(${obj.id})">
                    ${obj.is_present ? 'Mark Taken' : 'Mark Present'}
                  </button>
                </div>
              `).join('')}
            </div>
          </div>

          <!-- Devices in this room -->
          <div style="margin-top: 0.75rem;">
            <div style="font-size: 0.75rem; color: var(--text-dim); text-transform: uppercase; margin-bottom: 0.4rem; font-weight: 700;">
              Appliance Power Controls
            </div>
            ${room.devices.length === 0 ? '<div style="font-size: 0.8rem; color: var(--text-dim);">No appliances</div>' : ''}
            <div style="display: flex; flex-direction: column; gap: 0.35rem;">
              ${room.devices.map(dev => `
                <div style="display: flex; justify-content: space-between; align-items: center; background: rgba(255,255,255,0.03); padding: 0.35rem 0.6rem; border-radius: 6px; font-size: 0.8rem;">
                  <span>${escapeHtml(dev.name)} (${dev.power_watts}W)</span>
                  <button class="btn btn-sm ${dev.power_state ? 'btn-warning' : 'btn-secondary'}" style="padding: 0.15rem 0.5rem; font-size: 0.72rem;" onclick="toggleDevicePower(${dev.id})">
                    ${dev.power_state ? 'Cut Power' : 'Turn ON'}
                  </button>
                </div>
              `).join('')}
            </div>
          </div>
        </div>

        <div class="room-card-actions">
          <button class="btn btn-sm btn-block ${room.is_occupied ? 'btn-secondary' : 'btn-primary'}" onclick="toggleRoomOccupancy(${room.id})">
            ${room.is_occupied ? 'Simulate Person Leaving (Vacate)' : 'Simulate Person Entering (Occupied)'}
          </button>
        </div>
      </div>
    `;
  }).join('');
}

// -------------------------------------------------------------------
// Render Rooms Table (Rooms Tab)
// -------------------------------------------------------------------
function renderRoomsTable() {
  const tbody = document.getElementById('rooms-table-body');
  if (!tbody) return;

  tbody.innerHTML = state.rooms.map(r => `
    <tr>
      <td><strong>${escapeHtml(r.name)}</strong></td>
      <td><code>${escapeHtml(r.code)}</code></td>
      <td>
        <span class="status-tag ${r.is_occupied ? 'active' : 'inactive'}">
          ${r.is_occupied ? 'Occupied' : 'Vacant'}
        </span>
      </td>
      <td>${r.last_motion_at ? new Date(r.last_motion_at).toLocaleTimeString() : 'N/A'}</td>
      <td>${r.present_objects_count} / ${r.objects_count}</td>
      <td>${r.active_devices_count} / ${r.devices_count}</td>
      <td>
        <button class="btn btn-sm btn-secondary" onclick="toggleRoomOccupancy(${r.id})">
          Toggle Presence
        </button>
      </td>
    </tr>
  `).join('');
}

// -------------------------------------------------------------------
// Render Objects Table (Objects Tab)
// -------------------------------------------------------------------
function renderObjectsTable() {
  const tbody = document.getElementById('objects-table-body');
  if (!tbody) return;

  tbody.innerHTML = state.objects.map(o => `
    <tr>
      <td><code>${escapeHtml(o.tag_id)}</code></td>
      <td><strong>${escapeHtml(o.name)}</strong></td>
      <td>${escapeHtml(o.category)}</td>
      <td><span class="priority-tag priority-${o.priority}">${o.priority}</span></td>
      <td>${escapeHtml(o.room_name)}</td>
      <td>
        <span class="status-tag ${o.is_present ? 'active' : 'inactive'}">
          ${o.is_present ? 'Present in Space' : 'Removed / Outside'}
        </span>
      </td>
      <td>${escapeHtml(o.owner_name)}</td>
      <td>
        <button class="btn btn-sm ${o.is_present ? 'btn-ghost' : 'btn-primary'}" onclick="toggleObjectPresence(${o.id})">
          ${o.is_present ? 'Simulate Pick Up' : 'Simulate Place Inside'}
        </button>
      </td>
    </tr>
  `).join('');
}

// -------------------------------------------------------------------
// Render Devices Table (Devices Tab)
// -------------------------------------------------------------------
function renderDevicesTable() {
  const tbody = document.getElementById('devices-table-body');
  if (!tbody) return;

  tbody.innerHTML = state.devices.map(d => {
    const parentRoom = state.rooms.find(r => r.id === d.room_id);
    const isEnergyHazard = !parentRoom?.is_occupied && d.power_state;

    return `
      <tr>
        <td><strong>${escapeHtml(d.name)}</strong></td>
        <td>${escapeHtml(d.device_type)}</td>
        <td>${escapeHtml(d.room_name)}</td>
        <td>${d.power_watts} W</td>
        <td>
          <span class="status-tag ${d.power_state ? 'active' : 'inactive'}">
            ${d.power_state ? 'POWER ON' : 'STANDBY / OFF'}
          </span>
        </td>
        <td>
          ${isEnergyHazard
            ? `<span class="status-tag alert-tag">Hazard: Running in Empty Room</span>`
            : `<span class="status-tag active">Normal</span>`
          }
        </td>
        <td>
          <button class="btn btn-sm ${d.power_state ? 'btn-warning' : 'btn-secondary'}" onclick="toggleDevicePower(${d.id})">
            ${d.power_state ? 'Remote Cutoff' : 'Power On'}
          </button>
        </td>
      </tr>
    `;
  }).join('');
}

// -------------------------------------------------------------------
// Actions & API Triggers
// -------------------------------------------------------------------
async function toggleRoomOccupancy(roomId) {
  try {
    const res = await fetch(`/api/rooms/${roomId}/toggle-occupancy`, { method: 'POST' });
    const data = await res.json();
    showToast(data.message, 'warning');
    appendTerminal(`[Manual Trigger] ${data.message}`);
    fetchAllData();
  } catch (err) {
    showToast('Failed to toggle room occupancy', 'danger');
  }
}

async function toggleObjectPresence(objId) {
  try {
    const res = await fetch(`/api/objects/${objId}/toggle-presence`, { method: 'POST' });
    const data = await res.json();
    showToast(data.message, 'success');
    appendTerminal(`[RFID Sensor] ${data.message}`);
    fetchAllData();
  } catch (err) {
    showToast('Failed to toggle item state', 'danger');
  }
}

async function toggleDevicePower(devId) {
  try {
    const res = await fetch(`/api/devices/${devId}/toggle-power`, { method: 'POST' });
    const data = await res.json();
    showToast(data.message, 'warning');
    appendTerminal(`[Power Relay] ${data.message}`);
    fetchAllData();
  } catch (err) {
    showToast('Failed to toggle device power', 'danger');
  }
}

async function resolveAlert(alertId) {
  try {
    const res = await fetch(`/api/alerts/${alertId}/resolve`, { method: 'POST' });
    const data = await res.json();
    showToast(data.message, 'success');
    fetchAllData();
  } catch (err) {
    showToast('Failed to resolve alert', 'danger');
  }
}

async function resolveAllAlerts() {
  try {
    const res = await fetch('/api/alerts/resolve-all', { method: 'POST' });
    const data = await res.json();
    showToast(data.message, 'success');
    fetchAllData();
  } catch (err) {
    showToast('Failed to resolve all alerts', 'danger');
  }
}

async function triggerLastPersonOut() {
  try {
    const res = await fetch('/api/simulate/last-person-out', { method: 'POST' });
    const data = await res.json();
    showToast(data.message, 'danger');
    speakVoiceAlert('Alert! Last person out detected with belongings left behind.');
    appendTerminal(`🚨 [SIMULATION EVENT] ${data.message}`);
    fetchAllData();
  } catch (err) {
    showToast('Failed to trigger simulation', 'danger');
  }
}

async function resetDemoData() {
  if (!confirm('Reset database with fresh realistic demonstration data?')) return;
  try {
    const res = await fetch('/api/simulate/reset-demo', { method: 'POST' });
    const data = await res.json();
    showToast(data.message, 'success');
    appendTerminal(`🔄 [System Reset] Database reseeded with default classrooms, devices and tags.`);
    fetchAllData();
  } catch (err) {
    showToast('Failed to reset data', 'danger');
  }
}

// -------------------------------------------------------------------
// Simulation Sandbox Scenarios
// -------------------------------------------------------------------
async function runSimScenario(scenario) {
  appendTerminal(`>> Executing scenario '${scenario}' via virtual ESP32 Gateway...`);

  let payload = {};
  if (scenario === 'last-person-out') {
    payload = {
      api_key: 'sample_key_123',
      room_code: 'LAB-101',
      is_occupied: false,
      rfid_tags: ['RFID-BAG-992'],
      device_states: {
        'Ceiling 4K Laser Projector': true,
        'Daikin Inverter AC 2.0 Ton': true
      }
    };
  } else if (scenario === 'occupied-telemetry') {
    payload = {
      api_key: 'sample_key_123',
      room_code: 'LAB-204',
      is_occupied: true,
      rfid_tags: ['RFID-CHG-102'],
      device_states: {
        'Benchtop DC Power Supply #4': true
      }
    };
  } else if (scenario === 'clean-exit') {
    payload = {
      api_key: 'sample_key_123',
      room_code: 'LH-301',
      is_occupied: false,
      rfid_tags: [],
      device_states: {
        'Auditorium Sound System Amplifier': false
      }
    };
  }

  try {
    const res = await fetch('/api/sensor-data', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': 'sample_key_123'
      },
      body: JSON.stringify(payload)
    });
    const result = await res.json();
    appendTerminal(`<< Server Response [${res.status}]: ${JSON.stringify(result, null, 2)}`);
    fetchAllData();
  } catch (err) {
    appendTerminal(`<< Error sending telemetry: ${err}`);
  }
}

function appendTerminal(msg) {
  const terminal = document.getElementById('sim-terminal-output');
  if (!terminal) return;
  const time = new Date().toLocaleTimeString();
  terminal.innerText += `\n[${time}] ${msg}`;
  terminal.scrollTop = terminal.scrollHeight;
}

function clearTerminal() {
  const terminal = document.getElementById('sim-terminal-output');
  if (terminal) terminal.innerText = '> ForgetGuard Terminal Cleared.';
}

// -------------------------------------------------------------------
// UI Navigation, Modals & Toast
// -------------------------------------------------------------------
function setupNavigation() {
  const navLinks = document.querySelectorAll('.nav-link');
  navLinks.forEach(link => {
    link.addEventListener('click', () => {
      navLinks.forEach(l => l.classList.remove('active'));
      link.classList.add('active');

      const targetTab = link.getAttribute('data-tab');
      document.querySelectorAll('.tab-content').forEach(tc => {
        tc.classList.toggle('active', tc.id === `tab-${targetTab}`);
      });

      // Scroll main content back to top on tab switch
      const mainContent = document.querySelector('.main-content');
      if (mainContent) mainContent.scrollTop = 0;
    });
  });
}

function setupEventHandlers() {
  document.getElementById('btn-manual-refresh')?.addEventListener('click', fetchAllData);
  document.getElementById('btn-quick-simulate')?.addEventListener('click', triggerLastPersonOut);
  document.getElementById('btn-reset-demo')?.addEventListener('click', resetDemoData);
  document.getElementById('btn-resolve-all')?.addEventListener('click', resolveAllAlerts);
}

function setupModals() {
  // Add Room
  document.getElementById('btn-open-add-room-modal')?.addEventListener('click', () => openModal('modal-add-room'));
  document.getElementById('form-add-room')?.addEventListener('submit', async e => {
    e.preventDefault();
    const name = document.getElementById('room-name').value;
    const code = document.getElementById('room-code').value;
    const res = await fetch('/api/rooms', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, code })
    });
    if (res.ok) {
      closeModal('modal-add-room');
      e.target.reset();
      showToast('Room created successfully', 'success');
      fetchAllData();
    }
  });

  // Add Object
  document.getElementById('btn-open-add-object-modal')?.addEventListener('click', () => openModal('modal-add-object'));
  document.getElementById('form-add-object')?.addEventListener('submit', async e => {
    e.preventDefault();
    const payload = {
      tag_id: document.getElementById('obj-tag').value,
      name: document.getElementById('obj-name').value,
      category: document.getElementById('obj-category').value,
      priority: document.getElementById('obj-priority').value,
      room_id: document.getElementById('obj-room').value,
      owner_name: document.getElementById('obj-owner').value,
      owner_contact: document.getElementById('obj-contact').value
    };
    const res = await fetch('/api/objects', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (res.ok) {
      closeModal('modal-add-object');
      e.target.reset();
      showToast('Object registered', 'success');
      fetchAllData();
    }
  });

  // Add Device
  document.getElementById('btn-open-add-device-modal')?.addEventListener('click', () => openModal('modal-add-device'));
  document.getElementById('form-add-device')?.addEventListener('submit', async e => {
    e.preventDefault();
    const payload = {
      name: document.getElementById('dev-name').value,
      device_type: document.getElementById('dev-type').value,
      room_id: document.getElementById('dev-room').value,
      power_watts: parseFloat(document.getElementById('dev-watts').value || 100)
    };
    const res = await fetch('/api/devices', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (res.ok) {
      closeModal('modal-add-device');
      e.target.reset();
      showToast('Appliance registered', 'success');
      fetchAllData();
    }
  });
}

function updateModalRoomDropdowns() {
  const objSelect = document.getElementById('obj-room');
  const devSelect = document.getElementById('dev-room');
  const options = state.rooms.map(r => `<option value="${r.id}">${escapeHtml(r.name)} (${escapeHtml(r.code)})</option>`).join('');
  if (objSelect) objSelect.innerHTML = options;
  if (devSelect) devSelect.innerHTML = options;
}

function openModal(id) {
  document.getElementById(id)?.classList.add('open');
}

function closeModal(id) {
  document.getElementById(id)?.classList.remove('open');
}

function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `<span>${escapeHtml(message)}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
