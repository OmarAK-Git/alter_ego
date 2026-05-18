// State
let currentAlerts = [];
let currentDetailDecisionId = null;

// DOM Elements
const viewTriage = document.getElementById('view-triage');
const viewDetail = document.getElementById('view-detail');
const viewSuppressed = document.getElementById('view-suppressed');
const viewReplay = document.getElementById('view-replay');
const navLinks = document.querySelectorAll('.nav-links a');

const alertsBody = document.getElementById('alerts-body');
const suppressedBody = document.getElementById('suppressed-body');

const modal = document.getElementById('clear-modal');
const btnCancelClear = document.getElementById('btn-cancel-clear');
const btnConfirmClear = document.getElementById('btn-confirm-clear');
const clearReasonInput = document.getElementById('clear-reason-input');

// Event Listeners
document.getElementById('refresh-alerts').addEventListener('click', loadAlerts);
document.getElementById('back-to-triage').addEventListener('click', () => {
    navLinks.forEach(l => l.classList.remove('active'));
    document.querySelector('[data-view="triage"]').classList.add('active');
    switchView('triage');
});

document.getElementById('btn-acknowledge').addEventListener('click', () => updateWorkflowState('acknowledged'));
document.getElementById('btn-investigate').addEventListener('click', () => updateWorkflowState('investigating'));
document.getElementById('btn-clear').addEventListener('click', () => showClearModal());
document.getElementById('btn-contain').addEventListener('click', queueContainment);
document.getElementById('btn-generate-explanation').addEventListener('click', generateExplanation);

btnCancelClear.addEventListener('click', () => modal.classList.add('hidden'));
btnConfirmClear.addEventListener('click', submitClearAlert);

navLinks.forEach(link => {
    link.addEventListener('click', (e) => {
        e.preventDefault();
        navLinks.forEach(l => l.classList.remove('active'));
        link.classList.add('active');
        switchView(link.dataset.view);
    });
});

// Functions
function switchView(viewName) {
    // Hide all views by removing 'active' (CSS: .view { display:none } / .view.active { display:block })
    [viewTriage, viewDetail, viewSuppressed, viewReplay].forEach(v => {
        v.classList.remove('active');
    });

    // Update nav highlight
    navLinks.forEach(l => l.classList.remove('active'));
    const navLink = document.querySelector(`[data-view="${viewName}"]`);
    if (navLink) navLink.classList.add('active');

    if (viewName === 'triage') {
        viewTriage.classList.add('active');
        loadAlerts();
    } else if (viewName === 'detail') {
        viewDetail.classList.add('active');
    } else if (viewName === 'suppressed') {
        viewSuppressed.classList.add('active');
        loadSuppressed();
    } else if (viewName === 'replay') {
        viewReplay.classList.add('active');
    }
}

async function loadAlerts() {
    try {
        const res = await fetch('/api/alerts');
        const alerts = await res.json();
        currentAlerts = alerts;
        
        alertsBody.innerHTML = '';
        if (alerts.length === 0) {
            alertsBody.innerHTML = '<tr><td colspan="6" style="text-align:center; color:var(--text-muted);">No active alerts.</td></tr>';
            return;
        }
        
        alerts.forEach(alert => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${alert.entity_id}</td>
                <td>${new Date(alert.timestamp).toLocaleString()}</td>
                <td>${alert.score.toFixed(2)}</td>
                <td>${(alert.confidence * 100).toFixed(0)}%</td>
                <td><span class="badge ${alert.state === 'new' ? 'new' : 'warning'}">${alert.state}</span></td>
                <td><button class="btn small secondary view-btn" data-id="${alert.decision_id}">Review</button></td>
            `;
            alertsBody.appendChild(tr);
        });

        document.querySelectorAll('.view-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                loadDetail(e.target.dataset.id);
            });
        });
    } catch (e) {
        console.error("Failed to load alerts", e);
    }
}

async function loadSuppressed() {
    try {
        const res = await fetch('/api/suppressed');
        const alerts = await res.json();
        
        suppressedBody.innerHTML = '';
        if (alerts.length === 0) {
            suppressedBody.innerHTML = '<tr><td colspan="4" style="text-align:center; color:var(--text-muted);">No suppressed decisions.</td></tr>';
            return;
        }
        
        alerts.forEach(alert => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${alert.entity_id}</td>
                <td>${new Date(alert.timestamp).toLocaleString()}</td>
                <td>${alert.score.toFixed(2)}</td>
                <td><span class="badge danger">${(alert.confidence * 100).toFixed(0)}%</span></td>
            `;
            suppressedBody.appendChild(tr);
        });
    } catch (e) {
        console.error("Failed to load suppressed", e);
    }
}

async function loadDetail(decisionId) {
    currentDetailDecisionId = decisionId;
    try {
        const res = await fetch(`/api/alerts/${decisionId}`);
        const data = await res.json();
        
        // Populate left pane
        document.getElementById('detail-score').textContent = data.decision.score.toFixed(2);
        document.getElementById('detail-confidence').textContent = (data.decision.confidence * 100).toFixed(0) + '%';
        document.getElementById('detail-state').textContent = data.state.state;
        
        const contList = document.getElementById('detail-contributions');
        contList.innerHTML = '';
        data.decision.contributions.sort((a,b) => b.contribution_score - a.contribution_score).forEach(c => {
            contList.innerHTML += `<li>
                <strong>${c.feature_name}</strong>: +${c.contribution_score.toFixed(2)}
                <span class="text-muted" style="font-size: 0.8rem; margin-left:8px;">(weight: ${c.confidence_weight})</span>
            </li>`;
        });
        
        // Populate right pane
        const expBox = document.getElementById('explanation-content');
        const cfList = document.getElementById('detail-counterfactuals');
        
        if (data.explanation) {
            document.getElementById('btn-generate-explanation').disabled = true;
            document.getElementById('btn-generate-explanation').textContent = "Generated";
            
            expBox.innerHTML = `
                <p><strong>Summary:</strong> ${data.explanation.summary_text}</p>
                ${data.explanation.claim_objects.map(c => `
                    <div class="claim-item">
                        <div>${c.claim_text}</div>
                        <span class="badge" style="margin-top:8px;">Confidence: ${c.confidence_label}</span>
                    </div>
                `).join('')}
                <div class="text-muted" style="margin-top: 16px; font-size:0.8rem;">
                    Validation: ${data.explanation.validation_status}
                </div>
            `;
            
            cfList.innerHTML = data.explanation.counterfactuals.map(c => `
                <li>${c.counterfactual_text}</li>
            `).join('');
            
        } else {
            document.getElementById('btn-generate-explanation').disabled = false;
            document.getElementById('btn-generate-explanation').textContent = "Generate";
            expBox.innerHTML = '<p class="text-muted">No explanation generated yet.</p>';
            cfList.innerHTML = '<li class="text-muted">Not available until explanation is generated.</li>';
        }
        
        switchView('detail');
    } catch (e) {
        console.error("Failed to load detail", e);
    }
}

async function updateWorkflowState(state) {
    if (!currentDetailDecisionId) return;
    try {
        await fetch(`/api/alerts/${currentDetailDecisionId}/workflow`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ state: state })
        });
        loadDetail(currentDetailDecisionId);
    } catch (e) {
        console.error("Failed to update state", e);
    }
}

function showClearModal() {
    clearReasonInput.value = '';
    modal.classList.remove('hidden');
}

async function submitClearAlert() {
    const reason = clearReasonInput.value.trim();
    if (!reason) {
        alert("Please provide a reason.");
        return;
    }
    
    if (!currentDetailDecisionId) return;
    try {
        await fetch(`/api/alerts/${currentDetailDecisionId}/workflow`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ state: 'cleared', clear_reason: reason })
        });
        modal.classList.add('hidden');
        switchView('triage');
    } catch (e) {
        console.error("Failed to clear", e);
    }
}

async function queueContainment() {
    if (!currentDetailDecisionId) return;
    try {
        await fetch(`/api/alerts/${currentDetailDecisionId}/contain`, {
            method: 'POST'
        });
        alert("Containment action queued.");
    } catch (e) {
        console.error("Failed to queue containment", e);
    }
}

async function generateExplanation() {
    if (!currentDetailDecisionId) return;
    
    const btn = document.getElementById('btn-generate-explanation');
    btn.disabled = true;
    btn.textContent = "Generating...";
    
    try {
        await fetch(`/api/alerts/${currentDetailDecisionId}/explain`, {
            method: 'POST'
        });
        loadDetail(currentDetailDecisionId);
    } catch (e) {
        console.error("Failed to generate explanation", e);
        btn.disabled = false;
        btn.textContent = "Generate";
    }
}

// Initial load — use switchView so active class is always set by JS
switchView('triage');
