const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

class ApiClient {
  private token: string | null = null;

  setToken(token: string | null) {
    this.token = token;
    if (token) {
      localStorage.setItem('token', token);
    } else {
      localStorage.removeItem('token');
    }
  }

  getToken(): string | null {
    if (this.token) return this.token;
    if (typeof window !== 'undefined') {
      this.token = localStorage.getItem('token');
    }
    return this.token;
  }

  private async request(endpoint: string, options: RequestInit = {}) {
    const token = this.getToken();
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...options.headers,
    };

    if (token) {
      (headers as Record<string, string>)['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`${API_URL}${endpoint}`, {
      ...options,
      headers,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Request failed' }));
      throw new Error(error.detail || 'Request failed');
    }

    return response.json();
  }

  // Auth
  async signup(email: string, password: string, fullName?: string, companyName?: string) {
    const data = await this.request('/auth/signup', {
      method: 'POST',
      body: JSON.stringify({ email, password, full_name: fullName, company_name: companyName }),
    });
    this.setToken(data.access_token);
    return data;
  }

  async login(email: string, password: string) {
    const data = await this.request('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    this.setToken(data.access_token);
    return data;
  }

  async getMe() {
    return this.request('/auth/me');
  }

  async updateStory(story: string) {
    return this.request('/auth/story', {
      method: 'PUT',
      body: JSON.stringify({ story }),
    });
  }

  logout() {
    this.setToken(null);
  }

  // OAuth
  async getXConnectUrl() {
    return this.request('/auth/x/connect');
  }

  async getLinkedInConnectUrl() {
    return this.request('/auth/linkedin/connect');
  }

  async getConnectedAccounts() {
    return this.request('/auth/accounts');
  }

  async disconnectAccount(platform: string) {
    return this.request(`/auth/accounts/${platform}`, { method: 'DELETE' });
  }

  // Marketing Config
  async getMarketingConfig() {
    return this.request('/marketing/config');
  }

  async updateMarketingConfig(config: any) {
    return this.request('/marketing/config', {
      method: 'PUT',
      body: JSON.stringify(config),
    });
  }

  async toggleAutoPost() {
    return this.request('/marketing/config/toggle-auto-post', { method: 'POST' });
  }

  // Strategies
  async getStrategies() {
    return this.request('/marketing/strategies');
  }

  // Posts
  async getPostQueue(platform?: string, status?: string) {
    const params = new URLSearchParams();
    if (platform) params.append('platform', platform);
    if (status) params.append('status', status);
    return this.request(`/posts/queue?${params}`);
  }

  async getPendingApproval() {
    return this.request('/posts/queue/pending-approval');
  }

  async approvePost(postId: string) {
    return this.request(`/posts/queue/${postId}/approve`, { method: 'POST' });
  }

  async rejectPost(postId: string) {
    return this.request(`/posts/queue/${postId}/reject`, { method: 'POST' });
  }

  async getPostHistory(platform?: string) {
    const params = platform ? `?platform=${platform}` : '';
    return this.request(`/posts/history${params}`);
  }

  async getEngagementTargets(status?: string) {
    const params = status ? `?status=${status}` : '';
    return this.request(`/posts/engagement-targets${params}`);
  }

  async approveReply(targetId: string) {
    return this.request(`/posts/engagement-targets/${targetId}/approve`, { method: 'POST' });
  }

  async skipTarget(targetId: string) {
    return this.request(`/posts/engagement-targets/${targetId}/skip`, { method: 'POST' });
  }

  // Swarm
  async initializeSwarm(story: string, companyName?: string) {
    return this.request('/swarm/initialize', {
      method: 'POST',
      body: JSON.stringify({ story, company_name: companyName }),
    });
  }

  async runDailyRoutine() {
    return this.request('/swarm/run-daily', { method: 'POST' });
  }

  async generateContent(platform: string, numPosts: number = 5, category?: string) {
    return this.request('/swarm/generate-content', {
      method: 'POST',
      body: JSON.stringify({ platform, num_posts: numPosts, category }),
    });
  }

  async createStrategy(platform: string) {
    return this.request(`/swarm/create-strategy/${platform}`, { method: 'POST' });
  }

  async findEngagementTargets(numTargets: number = 5) {
    return this.request(`/swarm/find-engagement-targets?num_targets=${numTargets}`, { method: 'POST' });
  }

  async getSwarmOutputs(agentName?: string, limit: number = 50) {
    const params = new URLSearchParams();
    if (agentName) params.append('agent_name', agentName);
    params.append('limit', limit.toString());
    return this.request(`/swarm/outputs?${params}`);
  }

  async getSwarmStatus() {
    return this.request('/swarm/status');
  }
}

export const api = new ApiClient();
