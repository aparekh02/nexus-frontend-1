/**
 * API Communication Layer for Nexus Campaign Console
 */

class NexusAPI {
    constructor() {
        // Default to localhost, can be overridden
        this.baseURL = 'http://localhost:8000';
        this.token = null;
        this.userId = null;
        this.username = null;
    }

    setBaseURL(url) {
        this.baseURL = url.replace(/\/$/, ''); // Remove trailing slash
    }

    async request(method, endpoint, data = null, authRequired = true) {
        const headers = {
            'Content-Type': 'application/json'
        };

        if (authRequired && this.token) {
            headers['Authorization'] = `Bearer ${this.token}`;
        }

        const options = {
            method,
            headers
        };

        if (data && (method === 'POST' || method === 'PUT')) {
            options.body = JSON.stringify(data);
        }

        try {
            const response = await fetch(`${this.baseURL}${endpoint}`, options);
            const result = await response.json();

            if (!response.ok) {
                return { error: result.detail || 'Request failed' };
            }

            return result;
        } catch (error) {
            return { error: error.message || 'Network error' };
        }
    }

    // Authentication
    async signup(username, email, password) {
        const result = await this.request('POST', '/auth/signup', {
            username,
            email,
            password
        }, false);

        if (!result.error) {
            this.token = result.token;
            this.userId = result.user_id;
            this.username = result.username;
        }

        return result;
    }

    async login(email, password) {
        const result = await this.request('POST', '/auth/login', {
            email,
            password
        }, false);

        if (!result.error) {
            this.token = result.token;
            this.userId = result.user_id;
            this.username = result.username;
        }

        return result;
    }

    async logout() {
        const result = await this.request('POST', '/auth/logout');
        this.token = null;
        this.userId = null;
        this.username = null;
        return result;
    }

    async getMe() {
        return await this.request('GET', '/auth/me');
    }

    // X Credentials
    async validateX(consumerKey, consumerSecret, accessToken, accessTokenSecret) {
        return await this.request('POST', '/auth/validate-x', {
            consumer_key: consumerKey,
            consumer_secret: consumerSecret,
            access_token: accessToken,
            access_token_secret: accessTokenSecret
        });
    }

    async getXStatus() {
        return await this.request('GET', '/auth/x-status');
    }

    // Strategy
    async createStrategy(name, description, audience, goals) {
        return await this.request('POST', '/strategy/create', {
            name,
            description,
            target_audience: audience,
            goals,
            duration_weeks: 9
        });
    }

    async getStrategy(sessionId) {
        return await this.request('GET', `/strategy/${sessionId}`);
    }

    async getStrategyTable(sessionId) {
        return await this.request('GET', `/strategy/${sessionId}/table`);
    }

    // Campaigns
    async createCampaign(name, description, audience, goals) {
        return await this.request('POST', '/campaign/create', {
            name,
            description,
            target_audience: audience,
            goals,
            duration_weeks: 3
        });
    }

    async getCampaignStatus(sessionId) {
        return await this.request('GET', `/campaign/${sessionId}/status`);
    }

    async getCampaignPlan(sessionId) {
        return await this.request('GET', `/campaign/${sessionId}/plan`);
    }

    async approvePlan(sessionId, approved, feedback = null) {
        return await this.request('POST', `/campaign/${sessionId}/approve`, {
            approved,
            feedback
        });
    }

    async getStream(sessionId) {
        return await this.request('GET', `/campaign/${sessionId}/stream`);
    }

    async listCampaigns() {
        return await this.request('GET', '/campaigns');
    }

    // Monitoring
    async getMonitor(sessionId) {
        return await this.request('GET', `/monitor/${sessionId}`);
    }

    async getStrategicMap(sessionId) {
        return await this.request('GET', `/monitor/${sessionId}/strategic-map`);
    }

    async stopCampaign(sessionId) {
        return await this.request('POST', `/monitor/${sessionId}/stop`);
    }

    async resumeCampaign(sessionId) {
        return await this.request('POST', `/monitor/${sessionId}/resume`);
    }

    async getTrending(query = 'trending topics today') {
        return await this.request('GET', `/trending?query=${encodeURIComponent(query)}`);
    }

    // Utility
    isAuthenticated() {
        return !!this.token;
    }

    getUsername() {
        return this.username;
    }

    getUserId() {
        return this.userId;
    }
}

// Global API instance
const api = new NexusAPI();
