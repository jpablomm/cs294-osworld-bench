/**
 * OSWorld WebUI API Client
 * Wrapper for REST API calls to the backend
 */

const API_BASE = window.location.origin;

class OSWorldAPI {
    /**
     * Get system health status
     */
    async getHealth() {
        const response = await fetch(`${API_BASE}/api/health`);
        if (!response.ok) {
            throw new Error(`Health check failed: ${response.statusText}`);
        }
        return response.json();
    }

    /**
     * Get aggregate statistics
     */
    async getStats() {
        const response = await fetch(`${API_BASE}/api/stats`);
        if (!response.ok) {
            throw new Error(`Failed to fetch stats: ${response.statusText}`);
        }
        return response.json();
    }

    /**
     * List available OSWorld tasks
     * @param {string} domain - Optional domain filter
     */
    async listTasks(domain = null) {
        const url = new URL(`${API_BASE}/api/tasks`);
        if (domain) {
            url.searchParams.append('domain', domain);
        }

        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`Failed to fetch tasks: ${response.statusText}`);
        }
        return response.json();
    }

    /**
     * List assessments with optional filtering
     * @param {Object} filters - Filter parameters
     */
    async listAssessments(filters = {}) {
        const url = new URL(`${API_BASE}/api/assessments`);

        if (filters.limit) url.searchParams.append('limit', filters.limit);
        if (filters.offset) url.searchParams.append('offset', filters.offset);
        if (filters.status) url.searchParams.append('status', filters.status);
        if (filters.domain) url.searchParams.append('domain', filters.domain);
        if (filters.task_id) url.searchParams.append('task_id', filters.task_id);

        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`Failed to fetch assessments: ${response.statusText}`);
        }
        return response.json();
    }

    /**
     * Get single assessment by ID
     * @param {string} assessmentId - Assessment ID
     */
    async getAssessment(assessmentId) {
        const response = await fetch(`${API_BASE}/api/assessments/${assessmentId}`);
        if (!response.ok) {
            if (response.status === 404) {
                throw new Error('Assessment not found');
            }
            throw new Error(`Failed to fetch assessment: ${response.statusText}`);
        }
        return response.json();
    }

    /**
     * Launch new assessment
     * @param {Object} launchConfig - Assessment configuration
     */
    async launchAssessment(launchConfig) {
        const response = await fetch(`${API_BASE}/api/assessments`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(launchConfig)
        });

        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: response.statusText }));
            throw new Error(error.detail || 'Failed to launch assessment');
        }
        return response.json();
    }

    /**
     * Stream assessment updates via Server-Sent Events
     * @param {string} assessmentId - Assessment ID
     * @param {Function} onEvent - Callback for events
     * @param {Function} onError - Error callback
     */
    streamAssessment(assessmentId, onEvent, onError) {
        const eventSource = new EventSource(`${API_BASE}/api/stream/${assessmentId}`);

        eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                onEvent(data);

                // Close stream on completion or error
                if (data.type === 'completed' || data.type === 'error') {
                    eventSource.close();
                }
            } catch (err) {
                console.error('Failed to parse SSE event:', err);
                onError(err);
            }
        };

        eventSource.onerror = (error) => {
            console.error('SSE connection error:', error);
            eventSource.close();
            onError(error);
        };

        return eventSource;
    }

    /**
     * Get artifact URL
     * @param {string} assessmentId - Assessment ID
     * @param {string} filename - Artifact filename
     */
    getArtifactUrl(assessmentId, filename) {
        return `${API_BASE}/api/artifacts/${assessmentId}/${filename}`;
    }
}

// Create singleton instance
const api = new OSWorldAPI();
