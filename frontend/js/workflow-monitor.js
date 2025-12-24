/**
 * Workflow Execution Monitor - Real-time monitoring with modal popup
 * Polls the API and displays stage-by-stage progress
 */

const API_BASE = 'http://localhost:8002';
let monitoringInterval = null;
let currentExecutionId = null;
let workflowData = null;

// Initialize event listeners
document.addEventListener('DOMContentLoaded', () => {
    const startBtn = document.getElementById('startMonitorBtn');
    const stopBtn = document.getElementById('stopMonitorBtn');
    const closeBtn = document.getElementById('closeModalBtn');
    const modal = document.getElementById('workflowModal');

    if (startBtn) {
        startBtn.addEventListener('click', startMonitoring);
    }

    if (stopBtn) {
        stopBtn.addEventListener('click', stopMonitoring);
    }

    if (closeBtn) {
        closeBtn.addEventListener('click', () => {
            modal.style.display = 'none';
        });
    }

    // Close modal when clicking outside
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.style.display = 'none';
        }
    });
});

async function startMonitoring() {
    const executionIdInput = document.getElementById('workflowExecutionId');
    const inputValue = executionIdInput.value.trim();

    try {
        showStatus('Searching for workflow execution...', 'info');

        if (inputValue) {
            currentExecutionId = inputValue;
        } else {
            const executions = await fetch(`${API_BASE}/workflows`).then(r => r.json());

            if (!executions || executions.length === 0) {
                throw new Error('No workflow executions found. Please run the E2E test first.');
            }

            const latestWorkflow = executions[0];
            if (latestWorkflow.latest_execution) {
                currentExecutionId = latestWorkflow.latest_execution.id;
            } else {
                throw new Error('No active execution found');
            }
        }

        await fetchWorkflowData();
        openModal();
        startPolling();

        document.getElementById('startMonitorBtn').style.display = 'none';
        document.getElementById('stopMonitorBtn').style.display = 'inline-flex';
        showStatus(`Monitoring execution: ${currentExecutionId}`, 'success');

    } catch (error) {
        console.error('Error starting monitor:', error);
        showStatus(`Error: ${error.message}`, 'error');
    }
}

function stopMonitoring() {
    if (monitoringInterval) {
        clearInterval(monitoringInterval);
        monitoringInterval = null;
    }

    document.getElementById('startMonitorBtn').style.display = 'inline-flex';
    document.getElementById('stopMonitorBtn').style.display = 'none';
    document.getElementById('workflowModal').style.display = 'none';
    showStatus('Monitoring stopped', 'info');
}

function openModal() {
    const modal = document.getElementById('workflowModal');
    modal.style.display = 'flex';
    lucide.createIcons();
}

function startPolling() {
    updateMonitorDisplay();
    monitoringInterval = setInterval(updateMonitorDisplay, 2000);
}

async function fetchWorkflowData() {
    try {
        const workflows = await fetch(`${API_BASE}/workflows`).then(r => r.json());

        for (const workflow of workflows) {
            if (workflow.executions && workflow.executions.length > 0) {
                const execution = workflow.executions.find(e => e.id === currentExecutionId);
                if (execution) {
                    workflowData = {
                        workflow: workflow,
                        stages: workflow.stages
                    };
                    break;
                }
            }
        }

        if (!workflowData) {
            const response = await fetch(`${API_BASE}/workflows`);
            const data = await response.json();
            if (data && data.length > 0) {
                workflowData = {
                    workflow: data[0],
                    stages: data[0].stages
                };
            }
        }
    } catch (error) {
        console.error('Error fetching workflow data:', error);
    }
}

async function updateMonitorDisplay() {
    try {
        const response = await fetch(`${API_BASE}/workflows`);
        const workflows = await response.json();

        let execution = null;
        let workflow = null;

        for (const wf of workflows) {
            if (wf.latest_execution && wf.latest_execution.id === currentExecutionId) {
                execution = wf.latest_execution;
                workflow = wf;
                break;
            }

            if (wf.executions) {
                const found = wf.executions.find(e => e.id === currentExecutionId);
                if (found) {
                    execution = found;
                    workflow = wf;
                    break;
                }
            }
        }

        if (!execution || !workflow) {
            console.error('Execution not found');
            return;
        }

        // Update overview
        document.getElementById('modalExecutionId').textContent = currentExecutionId.substring(0, 8) + '...';

        const statusBadge = document.getElementById('modalStatus');
        statusBadge.textContent = execution.status;
        statusBadge.className = `value badge ${execution.status}`;

        document.getElementById('modalCurrentStage').textContent = execution.current_stage || '-';

        // Calculate duration
        if (execution.created_at) {
            const created = new Date(execution.created_at);
            const now = execution.updated_at ? new Date(execution.updated_at) : new Date();
            const durationMs = now - created;
            const minutes = Math.floor(durationMs / 60000);
            const seconds = Math.floor((durationMs % 60000) / 1000);
            document.getElementById('modalDuration').textContent = `${minutes}m ${seconds}s`;
        }

        // Update progress bar
        const stages = Object.keys(workflow.stages);
        const currentStageIndex = stages.indexOf(execution.current_stage);
        const progress = ((currentStageIndex + 1) / stages.length) * 100;

        document.getElementById('progressFill').style.width = `${progress}%`;
        document.getElementById('progressStageText').textContent = `${currentStageIndex + 1} / ${stages.length} stages completed`;
        document.getElementById('progressPercentText').textContent = `${Math.round(progress)}%`;

        // Update metrics
        const metrics = execution.metrics || {};
        document.getElementById('metricConsumers').textContent = metrics.consumers_total || 0;
        document.getElementById('metricEmailsSent').textContent = metrics.emails_sent || 0;
        document.getElementById('metricEmailsOpened').textContent = metrics.emails_opened || 0;
        document.getElementById('metricBookings').textContent = metrics.bookings_completed || 0;

        const emailsSent = metrics.emails_sent || 1;
        const openRate = ((metrics.emails_opened || 0) / emailsSent * 100).toFixed(1);
        const conversionRate = ((metrics.bookings_completed || 0) / emailsSent * 100).toFixed(2);

        document.getElementById('metricOpenRate').textContent = `${openRate}% open rate`;
        document.getElementById('metricConversionRate').textContent = `${conversionRate}% conversion`;

        // Update stage timeline
        updateStageTimeline(workflow.stages, execution.current_stage, metrics);

        // Stop monitoring if completed
        if (execution.status === 'completed') {
            setTimeout(() => {
                stopMonitoring();
                showStatus('Workflow execution completed!', 'success');
            }, 3000);
        }

    } catch (error) {
        console.error('Error updating monitor:', error);
        showStatus(`Error updating: ${error.message}`, 'error');
    }
}

function updateStageTimeline(stages, currentStage, metrics) {
    const timeline = document.getElementById('stageTimelineContent');
    timeline.textContent = ''; // Clear existing content safely

    const stageKeys = Object.keys(stages);
    const currentStageIndex = stageKeys.indexOf(currentStage);

    stageKeys.forEach((stageKey, index) => {
        const stage = stages[stageKey];
        const isCompleted = index < currentStageIndex;
        const isActive = stageKey === currentStage;
        const isPending = index > currentStageIndex;

        // Create timeline item
        const timelineItem = document.createElement('div');
        timelineItem.className = 'timeline-item';

        // Create marker
        const marker = document.createElement('div');
        let markerClass = 'pending';
        let markerContent = (index + 1).toString();

        if (isCompleted) {
            markerClass = 'completed';
            markerContent = '✓';
        } else if (isActive) {
            markerClass = 'active';
        }
        marker.className = `timeline-marker ${markerClass}`;
        marker.textContent = markerContent;

        // Create content
        const content = document.createElement('div');
        content.className = `timeline-content ${isActive ? 'active' : ''}`;

        // Header
        const header = document.createElement('div');
        header.className = 'timeline-header';

        const stageName = document.createElement('span');
        stageName.className = 'timeline-stage-name';
        stageName.textContent = formatStageName(stageKey);

        const day = document.createElement('span');
        day.className = 'timeline-day';
        day.textContent = `Day ${stage.day || index + 1}`;

        header.appendChild(stageName);
        header.appendChild(day);

        // Actions
        const actions = document.createElement('div');
        actions.className = 'timeline-actions';
        actions.textContent = stage.actions ? stage.actions.slice(0, 2).join(', ') : 'No actions';

        content.appendChild(header);
        content.appendChild(actions);

        // Metrics (only for completed or active stages)
        if (isCompleted || isActive) {
            const emailsForStage = metrics.consumers_total || 100;
            const opensForStage = Math.round(emailsForStage * 0.25);
            const clicksForStage = Math.round(emailsForStage * 0.10);
            const bookingsForStage = Math.round(emailsForStage * 0.02);

            const metricsDiv = document.createElement('div');
            metricsDiv.className = 'timeline-metrics';

            // Helper to create metric
            const createMetric = (icon, value, label) => {
                const metricDiv = document.createElement('div');
                metricDiv.className = 'timeline-metric';

                const iconEl = document.createElement('i');
                iconEl.setAttribute('data-lucide', icon);

                const valueSpan = document.createElement('span');
                valueSpan.textContent = value.toString();

                const labelText = document.createTextNode(` ${label}`);

                metricDiv.appendChild(iconEl);
                metricDiv.appendChild(valueSpan);
                metricDiv.appendChild(labelText);

                return metricDiv;
            };

            metricsDiv.appendChild(createMetric('mail', emailsForStage, 'sent'));
            metricsDiv.appendChild(createMetric('mail-open', opensForStage, 'opened'));
            metricsDiv.appendChild(createMetric('mouse-pointer-click', clicksForStage, 'clicked'));
            metricsDiv.appendChild(createMetric('calendar-check', bookingsForStage, 'bookings'));

            content.appendChild(metricsDiv);
        }

        timelineItem.appendChild(marker);
        timelineItem.appendChild(content);
        timeline.appendChild(timelineItem);
    });

    lucide.createIcons();
}

function formatStageName(stageKey) {
    return stageKey
        .split('_')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' ');
}

function showStatus(message, type) {
    const statusDiv = document.getElementById('workflowMonitorStatus');
    statusDiv.textContent = message;
    statusDiv.className = `alert alert-${type}`;
    statusDiv.style.display = 'block';

    setTimeout(() => {
        statusDiv.style.display = 'none';
    }, 5000);
}
