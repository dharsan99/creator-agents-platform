/**
 * Dashboard JavaScript for Creator Agents Platform
 * Handles API interactions and UI updates
 */

const API_BASE_URL = 'http://localhost:8002';

// ============================================================================
// Helper Functions
// ============================================================================

function showStatus(elementId, message, type = 'loading') {
    const element = document.getElementById(elementId);
    element.textContent = message;
    element.className = `status-message status-${type}`;
    element.style.display = 'block';
}

function hideStatus(elementId) {
    const element = document.getElementById(elementId);
    element.style.display = 'none';
}

function showError(message) {
    console.error(message);
    const notification = document.createElement('div');
    notification.className = 'notification notification-error show';
    notification.innerHTML = `<strong>Error:</strong> ${message}`;
    document.body.appendChild(notification);
    setTimeout(() => notification.remove(), 5000);
}

function showSuccess(message) {
    const notification = document.createElement('div');
    notification.className = 'notification notification-success show';
    notification.innerHTML = `<strong>Success:</strong> ${message}`;
    document.body.appendChild(notification);
    setTimeout(() => notification.remove(), 5000);
}

async function fetchAPI(endpoint, options = {}) {
    try {
        const response = await fetch(`${API_BASE_URL}${endpoint}`, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        });

        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
            throw new Error(error.detail || `API error: ${response.status}`);
        }

        return await response.json();
    } catch (error) {
        console.error(`API Error: ${error.message}`);
        throw error;
    }
}

// ============================================================================
// Tab Navigation
// ============================================================================

document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', function() {
        const tabName = this.getAttribute('data-tab');

        // Hide all tabs
        document.querySelectorAll('.tab-content').forEach(tab => {
            tab.classList.remove('active');
        });

        // Remove active class from all buttons
        document.querySelectorAll('.tab-btn').forEach(b => {
            b.classList.remove('active');
        });

        // Show selected tab
        document.getElementById(`${tabName}-tab`).classList.add('active');
        this.classList.add('active');

        // Load tab-specific data
        if (tabName === 'events') {
            loadEvents();
        } else if (tabName === 'creators') {
            loadCreators();
        } else if (tabName === 'deploy-agent') {
            loadCreatorsForDeployment();
        } else if (tabName === 'send-event') {
            loadCreatorsForEventTrigger();
        }
    });
});

// ============================================================================
// Dashboard Stats
// ============================================================================

async function loadStats() {
    try {
        const stats = await fetchAPI('/admin/stats');

        document.getElementById('totalCreators').textContent = stats.creators || 0;
        document.getElementById('totalAgents').textContent = stats.agents || 0;
        document.getElementById('totalConsumers').textContent = stats.consumers || 0;
        document.getElementById('totalEvents').textContent = stats.events || 0;
    } catch (error) {
        console.error('Failed to load stats:', error);
        // Set to dash if error
        document.getElementById('totalCreators').textContent = '-';
        document.getElementById('totalAgents').textContent = '-';
        document.getElementById('totalConsumers').textContent = '-';
        document.getElementById('totalEvents').textContent = '-';
    }
}

// ============================================================================
// Onboarding
// ============================================================================

document.getElementById('onboardingForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    const username = document.getElementById('usernameInput').value.trim();
    const name = document.getElementById('nameInput').value.trim();
    const email = document.getElementById('emailInput').value.trim();

    if (!username) {
        showError('Please enter a username');
        return;
    }

    showStatus('onboardingStatus', 'Onboarding creator...', 'loading');

    try {
        const payload = { username };
        if (name) payload.name = name;
        if (email) payload.email = email;

        const result = await fetchAPI('/onboarding/', {
            method: 'POST',
            body: JSON.stringify(payload)
        });

        // Display result
        const resultDiv = document.getElementById('onboardingResult');
        resultDiv.innerHTML = `
            <h3>Onboarding Successful</h3>
            <div class="result-grid">
                <div class="result-item">
                    <span class="result-label">Creator ID</span>
                    <span class="result-value">${result.creator_id}</span>
                </div>
                <div class="result-item">
                    <span class="result-label">Username</span>
                    <span class="result-value">${result.username}</span>
                </div>
                <div class="result-item">
                    <span class="result-label">Profile Generated</span>
                    <span class="result-value">${result.profile_generated ? 'Yes' : 'No'}</span>
                </div>
                <div class="result-item">
                    <span class="result-label">Status</span>
                    <span class="result-value">${result.status}</span>
                </div>
            </div>
        `;
        resultDiv.style.display = 'block';

        showStatus('onboardingStatus', 'Creator onboarded successfully!', 'success');
        document.getElementById('onboardingForm').reset();
        loadStats();
    } catch (error) {
        showStatus('onboardingStatus', `Error: ${error.message}`, 'error');
    }
});

// ============================================================================
// Deploy Agent
// ============================================================================

async function loadCreatorsForDeployment() {
    try {
        const creators = await fetchAPI('/creators');
        const select = document.getElementById('creatorSelectDeploy');
        select.innerHTML = '<option value="">Choose a creator...</option>';

        creators.forEach(creator => {
            const option = document.createElement('option');
            option.value = creator.id;
            option.textContent = creator.name || creator.id;
            select.appendChild(option);
        });
    } catch (error) {
        console.error('Failed to load creators:', error);
    }
}

document.getElementById('deployAgentForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    const creatorId = document.getElementById('creatorSelectDeploy').value;

    if (!creatorId) {
        showError('Please select a creator');
        return;
    }

    showStatus('deployAgentStatus', 'Deploying agent...', 'loading');

    try {
        const result = await fetchAPI(`/onboarding/deploy-agent/${creatorId}`, {
            method: 'POST'
        });

        const resultDiv = document.getElementById('deployAgentResult');
        resultDiv.innerHTML = `
            <h3>Agent Deployed Successfully</h3>
            <div class="result-grid">
                <div class="result-item">
                    <span class="result-label">Agent ID</span>
                    <span class="result-value">${result.agent_id}</span>
                </div>
                <div class="result-item">
                    <span class="result-label">Agent Name</span>
                    <span class="result-value">${result.agent_name}</span>
                </div>
                <div class="result-item">
                    <span class="result-label">Status</span>
                    <span class="result-value">${result.status}</span>
                </div>
                <div class="result-item">
                    <span class="result-label">Triggers Created</span>
                    <span class="result-value">${result.triggers_created}</span>
                </div>
            </div>
        `;
        resultDiv.style.display = 'block';

        showStatus('deployAgentStatus', 'Agent deployed successfully!', 'success');
        loadStats();
    } catch (error) {
        showStatus('deployAgentStatus', `Error: ${error.message}`, 'error');
    }
});

// ============================================================================
// Send Event
// ============================================================================

async function loadCreatorsForEventTrigger() {
    try {
        const creators = await fetchAPI('/creators');
        const select = document.getElementById('creatorSelectEvent');
        select.innerHTML = '<option value="">Choose a creator...</option>';

        creators.forEach(creator => {
            const option = document.createElement('option');
            option.value = creator.id;
            option.textContent = creator.name || creator.id;
            select.appendChild(option);
        });
    } catch (error) {
        console.error('Failed to load creators:', error);
    }
}

document.getElementById('sendEventForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    const creatorId = document.getElementById('creatorSelectEvent').value;
    const consumerEmail = document.getElementById('consumerEmailInput').value.trim();
    const eventType = document.getElementById('eventTypeSelect').value;

    if (!creatorId || !consumerEmail || !eventType) {
        showError('Please fill in all fields');
        return;
    }

    showStatus('sendEventStatus', 'Sending event...', 'loading');

    try {
        // First, find or create consumer
        const consumers = await fetchAPI(`/consumers?creator_id=${creatorId}`);
        let consumer = consumers.find(c => c.email === consumerEmail);

        if (!consumer) {
            // Create new consumer
            const newConsumer = await fetchAPI('/consumers', {
                method: 'POST',
                body: JSON.stringify({
                    creator_id: creatorId,
                    email: consumerEmail,
                    name: consumerEmail.split('@')[0]
                })
            });
            consumer = newConsumer;
        }

        // Send event
        const result = await fetchAPI('/events', {
            method: 'POST',
            body: JSON.stringify({
                creator_id: creatorId,
                consumer_id: consumer.id,
                type: eventType,
                source: 'api',
                payload: {}
            })
        });

        showStatus('sendEventStatus', `Event "${eventType}" sent successfully!`, 'success');
        document.getElementById('sendEventForm').reset();
        loadStats();
    } catch (error) {
        showStatus('sendEventStatus', `Error: ${error.message}`, 'error');
    }
});

// ============================================================================
// Events Viewer
// ============================================================================

let eventsCurrentPage = 1;
let eventsPageSize = 20;
let eventsTotal = 0;
let eventsFilter = '';

async function loadEvents(page = 1) {
    const filterCreator = document.getElementById('filterCreatorInput').value.trim();
    eventsFilter = filterCreator;
    eventsCurrentPage = page;

    const tableDiv = document.getElementById('eventsTable');
    const loadingDiv = document.getElementById('eventsLoading');

    loadingDiv.style.display = 'flex';
    tableDiv.innerHTML = '';

    try {
        let endpoint = `/admin/events?limit=${eventsPageSize}&skip=${(page - 1) * eventsPageSize}`;
        if (filterCreator) {
            endpoint += `&creator_id=${encodeURIComponent(filterCreator)}`;
        }

        const data = await fetchAPI(endpoint);

        if (!data.items || data.items.length === 0) {
            tableDiv.innerHTML = '<div class="empty-state">No events found</div>';
            loadingDiv.style.display = 'none';
            return;
        }

        eventsTotal = data.total;

        // Build table
        let html = `
            <table class="data-table">
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Creator</th>
                        <th>Consumer</th>
                        <th>Type</th>
                        <th>Source</th>
                        <th>Timestamp</th>
                    </tr>
                </thead>
                <tbody>
        `;

        data.items.forEach(event => {
            html += `
                <tr>
                    <td>${event.id.substring(0, 8)}...</td>
                    <td>${event.creator_id.substring(0, 8)}...</td>
                    <td>${event.consumer_id.substring(0, 8)}...</td>
                    <td><span class="badge badge-info">${event.type}</span></td>
                    <td><span class="badge badge-default">${event.source}</span></td>
                    <td>${new Date(event.timestamp).toLocaleString()}</td>
                </tr>
            `;
        });

        html += `
                </tbody>
            </table>
        `;

        tableDiv.innerHTML = html;
        loadingDiv.style.display = 'none';

        // Show pagination
        updatePagination();
    } catch (error) {
        tableDiv.innerHTML = `<div class="empty-state" style="color: var(--danger-color);">Error: ${error.message}</div>`;
        loadingDiv.style.display = 'none';
    }
}

function updatePagination() {
    const totalPages = Math.ceil(eventsTotal / eventsPageSize);
    const paginationDiv = document.getElementById('eventsPagination');

    if (totalPages <= 1) {
        paginationDiv.style.display = 'none';
        return;
    }

    paginationDiv.style.display = 'flex';

    // Update pagination info
    const start = (eventsCurrentPage - 1) * eventsPageSize + 1;
    const end = Math.min(eventsCurrentPage * eventsPageSize, eventsTotal);
    document.getElementById('paginationRange').textContent = `${start}-${end}`;
    document.getElementById('paginationTotal').textContent = eventsTotal;

    // Update page buttons
    const pagesDiv = document.getElementById('paginationPages');
    pagesDiv.innerHTML = '';

    for (let i = 1; i <= Math.min(totalPages, 5); i++) {
        const btn = document.createElement('button');
        btn.className = 'btn btn-sm';
        if (i === eventsCurrentPage) btn.classList.add('active');
        btn.textContent = i;
        btn.addEventListener('click', () => loadEvents(i));
        pagesDiv.appendChild(btn);
    }

    // Update buttons
    document.getElementById('firstPageBtn').onclick = () => loadEvents(1);
    document.getElementById('prevPageBtn').onclick = () => loadEvents(Math.max(1, eventsCurrentPage - 1));
    document.getElementById('nextPageBtn').onclick = () => loadEvents(Math.min(totalPages, eventsCurrentPage + 1));
    document.getElementById('lastPageBtn').onclick = () => loadEvents(totalPages);

    document.getElementById('firstPageBtn').disabled = eventsCurrentPage === 1;
    document.getElementById('prevPageBtn').disabled = eventsCurrentPage === 1;
    document.getElementById('nextPageBtn').disabled = eventsCurrentPage === totalPages;
    document.getElementById('lastPageBtn').disabled = eventsCurrentPage === totalPages;
}

document.getElementById('filterEventsBtn').addEventListener('click', () => {
    loadEvents(1);
});

document.getElementById('pageSizeSelect').addEventListener('change', (e) => {
    eventsPageSize = parseInt(e.target.value);
    loadEvents(1);
});

// ============================================================================
// Creators List with Workflow Details
// ============================================================================

async function loadCreators() {
    const creatorsGrid = document.getElementById('creatorsGrid');
    const loadingDiv = document.getElementById('creatorsLoading');

    loadingDiv.style.display = 'flex';
    creatorsGrid.innerHTML = '';

    try {
        const creators = await fetchAPI('/creators');

        if (!creators || creators.length === 0) {
            creatorsGrid.innerHTML = '<div class="empty-state">No creators onboarded yet</div>';
            loadingDiv.style.display = 'none';
            return;
        }

        let html = '';
        for (const creator of creators) {
            try {
                const agents = await fetchAPI(`/onboarding/agents/${creator.id}`);
                const agentCount = agents.length;

                // Fetch creator profile
                let profile = null;
                try {
                    profile = await fetchAPI(`/onboarding/profile/${creator.id}`);
                } catch (e) {
                    console.warn(`No profile found for creator ${creator.id}`);
                }

                // Fetch workflows for this creator
                let workflows = [];
                try {
                    workflows = await fetchAPI(`/workflows?creator_id=${creator.id}`);
                } catch (e) {
                    console.warn(`No workflows found for creator ${creator.id}`);
                }

                html += `
                    <div class="creator-card">
                        <div class="creator-header">
                            <h3>${creator.name || 'Unnamed Creator'}</h3>
                            <p>${creator.email || 'No email'}</p>
                        </div>

                        <div class="result-grid">
                            <div class="result-item">
                                <span class="result-label">ID</span>
                                <span class="result-value">${creator.id.substring(0, 8)}...</span>
                            </div>
                            <div class="result-item">
                                <span class="result-label">Agents</span>
                                <span class="result-value">${agentCount}</span>
                            </div>
                            <div class="result-item">
                                <span class="result-label">Workflows</span>
                                <span class="result-value">${workflows.length}</span>
                            </div>
                            <div class="result-item">
                                <span class="result-label">Created</span>
                                <span class="result-value">${new Date(creator.created_at).toLocaleDateString()}</span>
                            </div>
                        </div>
                `;

                // Add creator profile details if available
                if (profile) {
                    html += renderCreatorProfile(profile);
                }

                // Add workflow details if available
                if (workflows.length > 0) {
                    for (const workflow of workflows) {
                        html += renderWorkflowDetails(workflow);
                    }
                } else {
                    html += `
                        <div class="workflow-empty">
                            <p>No workflows created yet</p>
                        </div>
                    `;
                }

                // Add consumer metrics (page 1, 20 per page)
                const consumerData = await loadConsumerMetrics(creator.id, 1, 20);
                if (consumerData) {
                    html += renderConsumerMetricsTable(consumerData.consumers, consumerData.total);
                }

                html += `</div>`;
            } catch (e) {
                console.error(`Failed to load data for creator ${creator.id}:`, e);
                html += `
                    <div class="creator-card">
                        <h3>${creator.name || 'Unnamed Creator'}</h3>
                        <p>${creator.email || 'No email'}</p>
                        <div class="result-grid">
                            <div class="result-item">
                                <span class="result-label">ID</span>
                                <span class="result-value">${creator.id.substring(0, 8)}...</span>
                            </div>
                        </div>
                    </div>
                `;
            }
        }

        creatorsGrid.innerHTML = html;
        loadingDiv.style.display = 'none';

        // Reinitialize Lucide icons for new content
        if (window.lucide) {
            lucide.createIcons();
        }
    } catch (error) {
        creatorsGrid.innerHTML = `<div class="empty-state" style="color: var(--danger-color);">Error: ${error.message}</div>`;
        loadingDiv.style.display = 'none';
    }
}

function renderWorkflowDetails(workflow) {
    const workflowId = workflow.id;
    const stages = workflow.stages || {};
    const stageKeys = Object.keys(stages);
    const availableTools = workflow.available_tools || [];
    const missingTools = workflow.missing_tools || [];

    let html = `
        <div class="workflow-section">
            <div class="workflow-header">
                <h4>
                    <i data-lucide="workflow"></i>
                    Workflow: ${workflow.purpose || 'Unknown'}
                </h4>
                <span class="badge badge-${workflow.workflow_type === 'conditional' ? 'info' : 'default'}">
                    ${workflow.workflow_type || 'N/A'}
                </span>
            </div>

            <div class="workflow-meta">
                <div class="workflow-meta-item">
                    <span class="meta-label">Goal:</span>
                    <span class="meta-value">${workflow.goal || 'Not specified'}</span>
                </div>
                <div class="workflow-meta-item">
                    <span class="meta-label">Version:</span>
                    <span class="meta-value">${workflow.version || 1}</span>
                </div>
                <div class="workflow-meta-item">
                    <span class="meta-label">Stages:</span>
                    <span class="meta-value">${stageKeys.length}</span>
                </div>
                <div class="workflow-meta-item">
                    <span class="meta-label">Start Date:</span>
                    <span class="meta-value">${workflow.start_date ? new Date(workflow.start_date).toLocaleDateString() : 'N/A'}</span>
                </div>
                <div class="workflow-meta-item">
                    <span class="meta-label">End Date:</span>
                    <span class="meta-value">${workflow.end_date ? new Date(workflow.end_date).toLocaleDateString() : 'N/A'}</span>
                </div>
                <div class="workflow-meta-item">
                    <span class="meta-label">Duration:</span>
                    <span class="meta-value">${workflow.start_date && workflow.end_date ? Math.ceil((new Date(workflow.end_date) - new Date(workflow.start_date)) / (1000 * 60 * 60 * 24)) + ' days' : 'N/A'}</span>
                </div>
            </div>

            <div class="workflow-tools">
                <div class="tools-section">
                    <h5>
                        <i data-lucide="wrench"></i>
                        Available Tools (${availableTools.length})
                    </h5>
                    <div class="tools-list">
                        ${availableTools.map(tool => `
                            <span class="tool-badge tool-available">${tool}</span>
                        `).join('')}
                    </div>
                </div>

                ${missingTools.length > 0 ? `
                    <div class="tools-section">
                        <h5>
                            <i data-lucide="alert-triangle"></i>
                            Missing Tools (${missingTools.length})
                        </h5>
                        <div class="tools-list">
                            ${missingTools.map(tool => `
                                <span class="tool-badge tool-missing" title="${tool.use_case || ''}">
                                    ${tool.name || tool}
                                    <small>(${tool.priority || 'N/A'})</small>
                                </span>
                            `).join('')}
                        </div>
                    </div>
                ` : ''}
            </div>

            <div class="workflow-stages">
                <h5>
                    <i data-lucide="layers"></i>
                    Workflow Stages
                </h5>
                <div class="stages-timeline">
                    ${stageKeys.map((stageKey, index) => {
                        const stage = stages[stageKey];
                        return `
                            <div class="stage-item">
                                <div class="stage-marker">${index + 1}</div>
                                <div class="stage-content">
                                    <div class="stage-title">
                                        ${stageKey}
                                        ${stage.day ? `<span style="color: var(--primary-color); font-weight: 500; margin-left: 0.5rem;">Day ${stage.day}</span>` : ''}
                                    </div>
                                    <div class="stage-goal">${stage.goal || 'No goal specified'}</div>
                                    ${stage.conditions ? `
                                        <div class="stage-conditions">
                                            <strong>Conditions:</strong> ${JSON.stringify(stage.conditions)}
                                        </div>
                                    ` : ''}
                                    ${stage.actions && stage.actions.length > 0 ? `
                                        <div class="stage-actions">
                                            <strong>Actions:</strong>
                                            <ul>
                                                ${stage.actions.map(action => `<li>${action}</li>`).join('')}
                                            </ul>
                                        </div>
                                    ` : ''}
                                </div>
                            </div>
                        `;
                    }).join('')}
                </div>
            </div>

            <div style="margin-top: 1rem; padding-top: 1rem; border-top: 1px solid var(--border-color); font-size: 0.85rem; color: var(--text-secondary);">
                <strong>Workflow ID:</strong> ${workflowId}
            </div>
        </div>
    `;

    return html;
}

// ============================================================================
// Health Check & Refresh
// ============================================================================
// Creator Profile Details
// ============================================================================

function renderCreatorProfile(profile) {
    if (!profile) return '';

    return `
        <div class="creator-profile-section">
            <h4>
                <i data-lucide="user-circle"></i>
                Creator Profile
            </h4>

            ${profile.llm_summary ? `
                <div class="profile-section">
                    <h5>LLM Summary</h5>
                    <p class="profile-text">${profile.llm_summary}</p>
                </div>
            ` : ''}

            ${profile.sales_pitch ? `
                <div class="profile-section">
                    <h5>Sales Pitch</h5>
                    <p class="profile-text">${profile.sales_pitch}</p>
                </div>
            ` : ''}

            ${profile.agent_instructions ? `
                <div class="profile-section">
                    <h5>Agent Instructions</h5>
                    <p class="profile-text">${profile.agent_instructions}</p>
                </div>
            ` : ''}

            ${profile.target_audience_description ? `
                <div class="profile-section">
                    <h5>Target Audience</h5>
                    <p class="profile-text">${profile.target_audience_description}</p>
                </div>
            ` : ''}

            ${profile.value_propositions && profile.value_propositions.length > 0 ? `
                <div class="profile-section">
                    <h5>Value Propositions</h5>
                    <ul class="profile-list">
                        ${profile.value_propositions.map(vp => `
                            <li><strong>${vp.title}:</strong> ${vp.description}</li>
                        `).join('')}
                    </ul>
                </div>
            ` : ''}

            ${profile.services && profile.services.length > 0 ? `
                <div class="profile-section">
                    <h5>Services (${profile.services.length})</h5>
                    <div class="services-grid">
                        ${profile.services.map(service => `
                            <div class="service-card">
                                <h6>${service.name}</h6>
                                ${service.price ? `<p class="service-price">${service.price}</p>` : ''}
                                ${service.description ? `<p class="service-desc">${service.description}</p>` : ''}
                            </div>
                        `).join('')}
                    </div>
                </div>
            ` : ''}

            <div class="profile-metadata">
                <small>Profile created: ${profile.created_at ? new Date(profile.created_at).toLocaleString() : 'N/A'}</small>
                ${profile.last_synced_at ? `<small>Last synced: ${new Date(profile.last_synced_at).toLocaleString()}</small>` : ''}
            </div>
        </div>
    `;
}

// ============================================================================
// Consumer Metrics
// ============================================================================

// State for consumer metrics pagination
let consumerMetricsState = {
    creatorId: null,
    currentPage: 1,
    pageSize: 20,
    total: 0
};

async function loadConsumerMetrics(creatorId, page = 1, pageSize = 20) {
    try {
        const response = await fetch(`${API_BASE_URL}/consumers?page=${page}&page_size=${pageSize}`, {
            headers: {
                'X-Creator-ID': creatorId
            }
        });

        if (!response.ok) {
            throw new Error(`Failed to load consumers: ${response.statusText}`);
        }

        const data = await response.json();

        // Update state
        consumerMetricsState = {
            creatorId,
            currentPage: page,
            pageSize: pageSize,
            total: data.total
        };

        return data;
    } catch (error) {
        console.error('Error loading consumer metrics:', error);
        return null;
    }
}

async function loadConsumerTimeline(creatorId, consumerId) {
    try {
        const response = await fetch(`${API_BASE_URL}/events?consumer_id=${consumerId}&limit=50`, {
            headers: {
                'X-Creator-ID': creatorId
            }
        });

        if (!response.ok) {
            throw new Error(`Failed to load timeline: ${response.statusText}`);
        }

        const data = await response.json();

        // API returns array directly, wrap in object for consistency
        return { items: Array.isArray(data) ? data : [] };
    } catch (error) {
        console.error('Error loading consumer timeline:', error);
        return null;
    }
}

function renderConsumerMetricsTable(consumers, total) {
    if (!consumers || consumers.length === 0) {
        return `
            <div class="consumer-metrics-section">
                <h4>Consumer Metrics</h4>
                <div class="empty-state">No consumers yet</div>
            </div>
        `;
    }

    const { currentPage, pageSize } = consumerMetricsState;
    const totalPages = Math.ceil(total / pageSize);
    const startIndex = (currentPage - 1) * pageSize + 1;
    const endIndex = Math.min(currentPage * pageSize, total);

    let html = `
        <div class="consumer-metrics-section">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                <h4>Consumer Metrics (${total} total)</h4>
                <div style="display: flex; gap: 0.5rem; align-items: center;">
                    <label for="consumerPageSize" style="font-size: 0.875rem;">Per page:</label>
                    <select id="consumerPageSize" class="input-sm" style="padding: 0.25rem 0.5rem;">
                        <option value="10" ${pageSize === 10 ? 'selected' : ''}>10</option>
                        <option value="20" ${pageSize === 20 ? 'selected' : ''}>20</option>
                        <option value="50" ${pageSize === 50 ? 'selected' : ''}>50</option>
                        <option value="100" ${pageSize === 100 ? 'selected' : ''}>100</option>
                    </select>
                </div>
            </div>
            <div class="table-container">
                <table class="consumer-metrics-table">
                    <thead>
                        <tr>
                            <th>Name</th>
                            <th>Email</th>
                            <th>Stage</th>
                            <th>Delivered</th>
                            <th>Opened</th>
                            <th>Clicks</th>
                            <th>Bookings</th>
                            <th>Last Activity</th>
                        </tr>
                    </thead>
                    <tbody>
    `;

    for (const consumer of consumers) {
        const openRate = consumer.emails_delivered > 0
            ? ((consumer.emails_opened / consumer.emails_delivered) * 100).toFixed(1)
            : '0';
        const clickRate = consumer.emails_opened > 0
            ? ((consumer.emails_clicked / consumer.emails_opened) * 100).toFixed(1)
            : '0';

        const stageBadge = getStageHTML(consumer.stage);
        const lastActivity = consumer.last_activity
            ? new Date(consumer.last_activity).toLocaleString()
            : 'Never';

        html += `
            <tr class="consumer-row" data-consumer-id="${consumer.id}" style="cursor: pointer;">
                <td>${consumer.name || 'N/A'}</td>
                <td>${consumer.email || 'N/A'}</td>
                <td>${stageBadge}</td>
                <td>${consumer.emails_delivered}</td>
                <td>
                    ${consumer.emails_opened}
                    <span style="color: var(--text-secondary); font-size: 0.875rem;">(${openRate}%)</span>
                </td>
                <td>
                    ${consumer.emails_clicked}
                    <span style="color: var(--text-secondary); font-size: 0.875rem;">(${clickRate}%)</span>
                </td>
                <td>
                    <span style="font-weight: 600; color: ${consumer.bookings > 0 ? 'var(--success-color)' : 'inherit'}">
                        ${consumer.bookings}
                    </span>
                </td>
                <td style="font-size: 0.875rem; color: var(--text-secondary);">
                    ${lastActivity}
                </td>
            </tr>
        `;
    }

    html += `
                    </tbody>
                </table>
            </div>
            <div style="margin-top: 1rem; display: flex; justify-content: space-between; align-items: center;">
                <div style="color: var(--text-secondary); font-size: 0.875rem;">
                    Showing ${startIndex}-${endIndex} of ${total} consumers
                </div>
                <div style="display: flex; gap: 0.5rem;">
                    <button class="btn btn-sm" id="consumerPrevPage" ${currentPage === 1 ? 'disabled' : ''}>
                        <i data-lucide="chevron-left"></i>
                        Previous
                    </button>
                    <span style="padding: 0.5rem 1rem; color: var(--text-secondary);">
                        Page ${currentPage} of ${totalPages}
                    </span>
                    <button class="btn btn-sm" id="consumerNextPage" ${currentPage === totalPages ? 'disabled' : ''}>
                        Next
                        <i data-lucide="chevron-right"></i>
                    </button>
                </div>
            </div>
        </div>
    `;

    return html;
}

function getStageHTML(stage) {
    const stageColors = {
        'new': '#6b7280',
        'interested': '#3b82f6',
        'engaged': '#8b5cf6',
        'converted': '#10b981',
        'churned': '#ef4444'
    };
    const color = stageColors[stage] || '#6b7280';
    return `<span class="stage-badge" style="background-color: ${color}20; color: ${color}; padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.875rem; font-weight: 500;">${stage}</span>`;
}

// ============================================================================
// Consumer Timeline Modal & Pagination Handlers
// ============================================================================

// Event delegation for consumer row clicks and pagination
document.addEventListener('click', async (e) => {
    const row = e.target.closest('.consumer-row');
    if (row) {
        const consumerId = row.getAttribute('data-consumer-id');
        const consumerName = row.children[0].textContent;
        const consumerEmail = row.children[1].textContent;
        const consumerStage = row.children[2].textContent.trim();

        await openConsumerTimeline(consumerId, consumerName, consumerEmail, consumerStage);
    }

    // Handle pagination buttons
    if (e.target.closest('#consumerPrevPage')) {
        await handleConsumerPagination('prev');
    } else if (e.target.closest('#consumerNextPage')) {
        await handleConsumerPagination('next');
    }

    // Handle page size change
    const pageSizeSelect = e.target.closest('#consumerPageSize');
    if (pageSizeSelect) {
        await handleConsumerPageSizeChange(parseInt(pageSizeSelect.value));
    }
});

async function openConsumerTimeline(consumerId, name, email, stage) {
    const modal = document.getElementById('consumerTimelineModal');
    const { creatorId } = consumerMetricsState;

    if (!creatorId) {
        showError('Creator ID not found');
        return;
    }

    // Set consumer info
    document.getElementById('timelineConsumerName').textContent = name || 'N/A';
    document.getElementById('timelineConsumerEmail').textContent = email || 'N/A';
    document.getElementById('timelineConsumerStage').innerHTML = getStageHTML(stage);

    // Show modal
    modal.style.display = 'flex';

    // Load timeline
    const timelineContent = document.getElementById('consumerTimelineContent');
    timelineContent.innerHTML = '<div class="loading"><i data-lucide="loader-2"></i> Loading timeline...</div>';

    // Reinitialize icons
    if (window.lucide) {
        lucide.createIcons();
    }

    const data = await loadConsumerTimeline(creatorId, consumerId);

    if (!data || !data.items || data.items.length === 0) {
        timelineContent.innerHTML = '<div class="empty-state">No events found for this consumer</div>';
        document.getElementById('timelineEventCount').textContent = '0';
        return;
    }

    document.getElementById('timelineEventCount').textContent = data.items.length;

    // Render timeline
    renderTimelineEvents(data.items);
}

function renderTimelineEvents(events) {
    const timelineContent = document.getElementById('consumerTimelineContent');

    // Group events by date
    const eventsByDate = {};
    events.forEach(event => {
        const date = new Date(event.timestamp).toLocaleDateString();
        if (!eventsByDate[date]) {
            eventsByDate[date] = [];
        }
        eventsByDate[date].push(event);
    });

    let html = '';
    Object.keys(eventsByDate).sort((a, b) => new Date(b) - new Date(a)).forEach(date => {
        html += `
            <div class="timeline-date-group">
                <h4 class="timeline-date">${date}</h4>
                <div class="timeline-events">
        `;

        eventsByDate[date].forEach(event => {
            const time = new Date(event.timestamp).toLocaleTimeString();
            const eventTypeColor = getEventTypeColor(event.type);

            html += `
                <div class="timeline-event">
                    <div class="timeline-marker" style="background-color: ${eventTypeColor};"></div>
                    <div class="timeline-event-content">
                        <div class="timeline-event-header">
                            <span class="timeline-event-type" style="color: ${eventTypeColor};">${event.type}</span>
                            <span class="timeline-event-time">${time}</span>
                        </div>
                        ${event.payload && Object.keys(event.payload).length > 0 ? `
                            <div class="timeline-event-details">
                                ${renderEventPayload(event.payload)}
                            </div>
                        ` : ''}
                    </div>
                </div>
            `;
        });

        html += `
                </div>
            </div>
        `;
    });

    timelineContent.innerHTML = html;

    // Reinitialize icons
    if (window.lucide) {
        lucide.createIcons();
    }
}

function getEventTypeColor(eventType) {
    const colors = {
        'email_delivered': '#3b82f6',
        'email_opened': '#8b5cf6',
        'email_clicked': '#10b981',
        'booking_created': '#22c55e',
        'page_view': '#6b7280',
        'service_click': '#f59e0b'
    };
    return colors[eventType] || '#6b7280';
}

function renderEventPayload(payload) {
    if (!payload || typeof payload !== 'object') return '';

    let html = '<ul class="payload-list">';

    // Priority order for display
    const displayOrder = ['subject', 'email_subject', 'body', 'message', 'stage', 'campaign', 'service_id', 'message_id', 'workflow_execution_id'];

    // Display ordered fields first
    displayOrder.forEach(key => {
        if (payload[key]) {
            const value = payload[key];
            const label = key.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');

            if (key === 'body' || key === 'message') {
                // Display email body with text truncation
                const bodyText = typeof value === 'string' ? value : JSON.stringify(value);
                const truncated = bodyText.length > 200 ? bodyText.substring(0, 200) + '...' : bodyText;
                html += `<li><strong>${label}:</strong><div class="email-body">${truncated}</div></li>`;
            } else if (key === 'workflow_execution_id') {
                // Show shortened ID
                html += `<li><strong>${label}:</strong> <code>${value.substring(0, 13)}...</code></li>`;
            } else {
                html += `<li><strong>${label}:</strong> ${value}</li>`;
            }
        }
    });

    // Display remaining fields
    Object.entries(payload).forEach(([key, value]) => {
        if (!displayOrder.includes(key)) {
            if (typeof value === 'string' || typeof value === 'number') {
                const label = key.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
                html += `<li><strong>${label}:</strong> ${value}</li>`;
            }
        }
    });

    // Note if email body is not stored
    if (!payload.body && !payload.message && (payload.subject || payload.email_subject)) {
        html += `<li class="note"><em>Note: Email body not stored in events</em></li>`;
    }

    html += '</ul>';
    return html;
}

async function handleConsumerPagination(direction) {
    const { creatorId, currentPage, pageSize, total } = consumerMetricsState;
    const totalPages = Math.ceil(total / pageSize);

    let newPage = currentPage;
    if (direction === 'prev' && currentPage > 1) {
        newPage = currentPage - 1;
    } else if (direction === 'next' && currentPage < totalPages) {
        newPage = currentPage + 1;
    }

    if (newPage !== currentPage) {
        await reloadConsumerMetrics(creatorId, newPage, pageSize);
    }
}

async function handleConsumerPageSizeChange(newPageSize) {
    const { creatorId } = consumerMetricsState;
    await reloadConsumerMetrics(creatorId, 1, newPageSize);
}

async function reloadConsumerMetrics(creatorId, page, pageSize) {
    // Find the creator card containing the consumer metrics
    const creatorsGrid = document.getElementById('creatorsGrid');
    if (!creatorsGrid) return;

    try {
        // Load new data
        const data = await loadConsumerMetrics(creatorId, page, pageSize);

        if (data) {
            // Find the consumer metrics section in the DOM
            const metricsSection = document.querySelector('.consumer-metrics-section');
            if (metricsSection) {
                // Replace the consumer metrics section
                const newMetricsHTML = renderConsumerMetricsTable(data.consumers, data.total);
                const tempDiv = document.createElement('div');
                tempDiv.innerHTML = newMetricsHTML;
                metricsSection.replaceWith(tempDiv.firstElementChild);

                // Reinitialize Lucide icons
                if (window.lucide) {
                    lucide.createIcons();
                }
            }
        }
    } catch (error) {
        showError(`Failed to reload consumer metrics: ${error.message}`);
    }
}

// Close modal handler
document.getElementById('closeConsumerModalBtn')?.addEventListener('click', () => {
    document.getElementById('consumerTimelineModal').style.display = 'none';
});

// Close modal on background click
document.getElementById('consumerTimelineModal')?.addEventListener('click', (e) => {
    if (e.target.id === 'consumerTimelineModal') {
        document.getElementById('consumerTimelineModal').style.display = 'none';
    }
});

// ============================================================================

document.getElementById('healthCheckBtn').addEventListener('click', async () => {
    try {
        const health = await fetchAPI('/health').catch(() => ({ status: 'unavailable' }));
        if (health.status === 'ok') {
            showSuccess('API is healthy ✓');
        } else {
            showError('API is not healthy');
        }
    } catch (error) {
        showError(`Health check failed: ${error.message}`);
    }
});

document.getElementById('refreshBtn').addEventListener('click', () => {
    loadStats();
    showSuccess('Stats refreshed');
});

// ============================================================================
// Initialize
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
    console.log('Dashboard initialized');
    loadStats();
});
