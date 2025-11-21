/**
 * Nexus Campaign Console - Main Application
 */

class Console {
    constructor() {
        this.output = document.getElementById('output');
        this.input = document.getElementById('command-input');
        this.prompt = document.getElementById('prompt');
        this.userStatus = document.getElementById('user-status');
        this.connectionStatus = document.getElementById('connection-status');

        this.currentSession = null;
        this.commandHistory = [];
        this.historyIndex = -1;
        this.inputMode = null; // For multi-step inputs
        this.inputBuffer = {};
        this.watchInterval = null;

        this.init();
    }

    init() {
        // Event listeners
        this.input.addEventListener('keydown', (e) => this.handleKeyDown(e));

        // Load API configuration from server
        this.loadConfig();

        // Focus input
        this.input.focus();
        document.addEventListener('click', () => this.input.focus());
    }

    async loadConfig() {
        try {
            const response = await fetch('/config');
            if (response.ok) {
                const config = await response.json();
                if (config.apiUrl) {
                    api.setBaseURL(config.apiUrl);
                    this.print(`Connected to backend: ${config.apiUrl}`, 'dim');
                }
            }
        } catch (error) {
            // Config endpoint not available, use default
        }

        // Check connection after config load
        this.checkConnection();
    }

    async checkConnection() {
        try {
            const response = await fetch(`${api.baseURL}/docs`);
            if (response.ok || response.status === 404) {
                this.connectionStatus.textContent = 'Connected';
                this.connectionStatus.className = 'connected';
            } else {
                throw new Error('Not connected');
            }
        } catch {
            this.connectionStatus.textContent = 'Disconnected';
            this.connectionStatus.className = 'disconnected';
        }
    }

    updatePrompt() {
        if (api.isAuthenticated()) {
            this.prompt.textContent = `${api.getUsername()}@nexus:~$`;
            this.userStatus.textContent = `Logged in as ${api.getUsername()}`;
        } else {
            this.prompt.textContent = 'guest@nexus:~$';
            this.userStatus.textContent = 'Not logged in';
        }
    }

    handleKeyDown(e) {
        if (e.key === 'Enter') {
            const command = this.input.value.trim();
            if (command) {
                this.commandHistory.push(command);
                this.historyIndex = this.commandHistory.length;
            }
            this.executeCommand(command);
            this.input.value = '';
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            if (this.historyIndex > 0) {
                this.historyIndex--;
                this.input.value = this.commandHistory[this.historyIndex];
            }
        } else if (e.key === 'ArrowDown') {
            e.preventDefault();
            if (this.historyIndex < this.commandHistory.length - 1) {
                this.historyIndex++;
                this.input.value = this.commandHistory[this.historyIndex];
            } else {
                this.historyIndex = this.commandHistory.length;
                this.input.value = '';
            }
        } else if (e.key === 'Tab') {
            e.preventDefault();
            this.autoComplete();
        } else if (e.key === 'c' && e.ctrlKey) {
            this.cancelInput();
        }
    }

    autoComplete() {
        const commands = ['help', 'login', 'signup', 'logout', 'status', 'connect-x',
                         'create-strategy', 'view-strategy', 'create-campaign',
                         'view-plan', 'approve', 'watch', 'map', 'list', 'stop',
                         'resume', 'clear', 'trending', 'set-url'];
        const input = this.input.value.toLowerCase();
        const matches = commands.filter(c => c.startsWith(input));

        if (matches.length === 1) {
            this.input.value = matches[0];
        } else if (matches.length > 1) {
            this.print(`\nMatches: ${matches.join(', ')}`, 'dim');
        }
    }

    cancelInput() {
        if (this.inputMode) {
            this.inputMode = null;
            this.inputBuffer = {};
            this.print('^C', 'error');
            this.updatePrompt();
        }
        if (this.watchInterval) {
            clearInterval(this.watchInterval);
            this.watchInterval = null;
            this.print('\nStopped watching.', 'warning');
        }
    }

    async executeCommand(rawCommand) {
        // Show command in output
        this.printCommand(rawCommand);

        // Handle input mode (multi-step inputs)
        if (this.inputMode) {
            await this.handleInputMode(rawCommand);
            return;
        }

        const [command, ...args] = rawCommand.toLowerCase().split(' ');
        const fullArgs = args.join(' ');

        switch (command) {
            case '':
                break;
            case 'help':
                this.showHelp();
                break;
            case 'clear':
                this.clear();
                break;
            case 'login':
                this.startLogin();
                break;
            case 'signup':
                this.startSignup();
                break;
            case 'logout':
                await this.logout();
                break;
            case 'status':
                await this.showStatus();
                break;
            case 'connect-x':
                this.startConnectX();
                break;
            case 'create-strategy':
                this.startCreateStrategy();
                break;
            case 'view-strategy':
                await this.viewStrategy(fullArgs);
                break;
            case 'create-campaign':
                this.startCreateCampaign();
                break;
            case 'view-plan':
                await this.viewPlan(fullArgs);
                break;
            case 'approve':
                await this.approvePlan(fullArgs);
                break;
            case 'watch':
                await this.watchStream(fullArgs);
                break;
            case 'map':
                await this.viewMap(fullArgs);
                break;
            case 'list':
                await this.listCampaigns();
                break;
            case 'stop':
                await this.stopCampaign(fullArgs);
                break;
            case 'resume':
                await this.resumeCampaign(fullArgs);
                break;
            case 'trending':
                await this.showTrending(fullArgs);
                break;
            case 'set-url':
                this.setApiUrl(fullArgs);
                break;
            case 'use':
                this.useSession(fullArgs);
                break;
            default:
                this.print(`Unknown command: ${command}. Type 'help' for available commands.`, 'error');
        }

        this.scrollToBottom();
    }

    async handleInputMode(value) {
        const mode = this.inputMode;

        switch (mode) {
            case 'login-email':
                this.inputBuffer.email = value;
                this.prompt.textContent = 'Password: ';
                this.input.type = 'password';
                this.inputMode = 'login-password';
                break;
            case 'login-password':
                this.input.type = 'text';
                await this.completeLogin(this.inputBuffer.email, value);
                this.inputMode = null;
                this.inputBuffer = {};
                this.updatePrompt();
                break;
            case 'signup-username':
                this.inputBuffer.username = value;
                this.prompt.textContent = 'Email: ';
                this.inputMode = 'signup-email';
                break;
            case 'signup-email':
                this.inputBuffer.email = value;
                this.prompt.textContent = 'Password: ';
                this.input.type = 'password';
                this.inputMode = 'signup-password';
                break;
            case 'signup-password':
                this.inputBuffer.password = value;
                this.prompt.textContent = 'Confirm Password: ';
                this.inputMode = 'signup-confirm';
                break;
            case 'signup-confirm':
                this.input.type = 'text';
                await this.completeSignup(
                    this.inputBuffer.username,
                    this.inputBuffer.email,
                    this.inputBuffer.password,
                    value
                );
                this.inputMode = null;
                this.inputBuffer = {};
                this.updatePrompt();
                break;
            case 'x-consumer-key':
                this.inputBuffer.consumerKey = value;
                this.prompt.textContent = 'API Secret: ';
                this.inputMode = 'x-consumer-secret';
                break;
            case 'x-consumer-secret':
                this.inputBuffer.consumerSecret = value;
                this.prompt.textContent = 'Access Token: ';
                this.inputMode = 'x-access-token';
                break;
            case 'x-access-token':
                this.inputBuffer.accessToken = value;
                this.prompt.textContent = 'Access Token Secret: ';
                this.inputMode = 'x-access-secret';
                break;
            case 'x-access-secret':
                await this.completeConnectX(
                    this.inputBuffer.consumerKey,
                    this.inputBuffer.consumerSecret,
                    this.inputBuffer.accessToken,
                    value
                );
                this.inputMode = null;
                this.inputBuffer = {};
                this.updatePrompt();
                break;
            case 'strategy-name':
                this.inputBuffer.name = value;
                this.prompt.textContent = 'Description: ';
                this.inputMode = 'strategy-description';
                break;
            case 'strategy-description':
                this.inputBuffer.description = value;
                this.prompt.textContent = 'Target Audience: ';
                this.inputMode = 'strategy-audience';
                break;
            case 'strategy-audience':
                this.inputBuffer.audience = value;
                this.inputBuffer.goals = [];
                this.print('Enter goals (empty line to finish):', 'warning');
                this.prompt.textContent = 'Goal: ';
                this.inputMode = 'strategy-goals';
                break;
            case 'strategy-goals':
                if (value === '') {
                    await this.completeCreateStrategy(
                        this.inputBuffer.name,
                        this.inputBuffer.description,
                        this.inputBuffer.audience,
                        this.inputBuffer.goals
                    );
                    this.inputMode = null;
                    this.inputBuffer = {};
                    this.updatePrompt();
                } else {
                    this.inputBuffer.goals.push(value);
                    this.prompt.textContent = 'Goal: ';
                }
                break;
            case 'campaign-name':
                this.inputBuffer.name = value;
                this.prompt.textContent = 'Description: ';
                this.inputMode = 'campaign-description';
                break;
            case 'campaign-description':
                this.inputBuffer.description = value;
                this.prompt.textContent = 'Target Audience: ';
                this.inputMode = 'campaign-audience';
                break;
            case 'campaign-audience':
                this.inputBuffer.audience = value;
                this.inputBuffer.goals = [];
                this.print('Enter goals (empty line to finish):', 'warning');
                this.prompt.textContent = 'Goal: ';
                this.inputMode = 'campaign-goals';
                break;
            case 'campaign-goals':
                if (value === '') {
                    await this.completeCreateCampaign(
                        this.inputBuffer.name,
                        this.inputBuffer.description,
                        this.inputBuffer.audience,
                        this.inputBuffer.goals
                    );
                    this.inputMode = null;
                    this.inputBuffer = {};
                    this.updatePrompt();
                } else {
                    this.inputBuffer.goals.push(value);
                    this.prompt.textContent = 'Goal: ';
                }
                break;
        }

        this.scrollToBottom();
    }

    // Output methods
    print(text, type = 'info') {
        const line = document.createElement('div');
        line.className = `output-line output-${type}`;
        line.textContent = text;
        this.output.appendChild(line);
    }

    printHTML(html) {
        const line = document.createElement('div');
        line.className = 'output-line';
        line.innerHTML = html;
        this.output.appendChild(line);
    }

    printCommand(command) {
        const line = document.createElement('div');
        line.className = 'output-line output-command';
        line.innerHTML = `<span class="prompt">${this.prompt.textContent}</span> ${this.escapeHtml(command)}`;
        this.output.appendChild(line);
    }

    printDivider() {
        this.print('─'.repeat(60), 'dim');
    }

    printHeader(text) {
        this.print('');
        this.print('═'.repeat(60), 'cyan');
        this.print(`  ${text}`, 'cyan');
        this.print('═'.repeat(60), 'cyan');
        this.print('');
    }

    clear() {
        this.output.innerHTML = '';
    }

    scrollToBottom() {
        this.output.scrollTop = this.output.scrollHeight;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Commands
    showHelp() {
        this.printHeader('AVAILABLE COMMANDS');

        this.printHTML('<span class="output-cyan output-bold">[Authentication]</span>');
        this.printHTML('  <span class="menu-number">login</span>        - Login to your account');
        this.printHTML('  <span class="menu-number">signup</span>       - Create a new account');
        this.printHTML('  <span class="menu-number">logout</span>       - Logout from current session');
        this.printHTML('  <span class="menu-number">status</span>       - Show current status');

        this.print('');
        this.printHTML('<span class="output-cyan output-bold">[X Integration]</span>');
        this.printHTML('  <span class="menu-number">connect-x</span>    - Connect your X account');

        this.print('');
        this.printHTML('<span class="output-cyan output-bold">[Strategy]</span>');
        this.printHTML('  <span class="menu-number">create-strategy</span> - Create 9-week strategic plan');
        this.printHTML('  <span class="menu-number">view-strategy</span>   - View strategy table');

        this.print('');
        this.printHTML('<span class="output-cyan output-bold">[Campaign]</span>');
        this.printHTML('  <span class="menu-number">create-campaign</span> - Create new marketing campaign');
        this.printHTML('  <span class="menu-number">view-plan</span>       - View campaign plan');
        this.printHTML('  <span class="menu-number">approve</span>         - Approve or reject plan');

        this.print('');
        this.printHTML('<span class="output-cyan output-bold">[Monitoring]</span>');
        this.printHTML('  <span class="menu-number">watch</span>        - Watch stream in real-time');
        this.printHTML('  <span class="menu-number">map</span>          - View strategic map with progress');
        this.printHTML('  <span class="menu-number">list</span>         - List all campaigns');
        this.printHTML('  <span class="menu-number">trending</span>     - Show trending topics');

        this.print('');
        this.printHTML('<span class="output-cyan output-bold">[Control]</span>');
        this.printHTML('  <span class="menu-number">stop</span>         - Stop running campaign');
        this.printHTML('  <span class="menu-number">resume</span>       - Resume stopped campaign');
        this.printHTML('  <span class="menu-number">use [id]</span>     - Set current session');

        this.print('');
        this.printHTML('<span class="output-cyan output-bold">[System]</span>');
        this.printHTML('  <span class="menu-number">set-url [url]</span> - Set API URL');
        this.printHTML('  <span class="menu-number">clear</span>        - Clear console');
        this.printHTML('  <span class="menu-number">help</span>         - Show this help');

        this.print('');
        this.print('Tip: Use Tab for autocomplete, Arrow keys for history', 'dim');
    }

    // Authentication commands
    startLogin() {
        this.printHeader('LOGIN');
        this.prompt.textContent = 'Email: ';
        this.inputMode = 'login-email';
    }

    async completeLogin(email, password) {
        this.print('Logging in...', 'dim');
        const result = await api.login(email, password);

        if (result.error) {
            this.print(`Login failed: ${result.error}`, 'error');
        } else {
            this.print(`Welcome back, ${result.username}!`, 'success');
            this.checkConnection();
        }
    }

    startSignup() {
        this.printHeader('SIGN UP');
        this.prompt.textContent = 'Username: ';
        this.inputMode = 'signup-username';
    }

    async completeSignup(username, email, password, confirmPassword) {
        if (password !== confirmPassword) {
            this.print('Passwords do not match', 'error');
            return;
        }
        if (password.length < 6) {
            this.print('Password must be at least 6 characters', 'error');
            return;
        }

        this.print('Creating account...', 'dim');
        const result = await api.signup(username, email, password);

        if (result.error) {
            this.print(`Signup failed: ${result.error}`, 'error');
        } else {
            this.print(`Account created! Welcome, ${result.username}!`, 'success');
            this.checkConnection();
        }
    }

    async logout() {
        if (!api.isAuthenticated()) {
            this.print('Not logged in', 'warning');
            return;
        }

        const result = await api.logout();
        if (result.error) {
            this.print(`Logout failed: ${result.error}`, 'error');
        } else {
            this.print('Logged out successfully', 'success');
            this.currentSession = null;
            this.updatePrompt();
        }
    }

    async showStatus() {
        this.printHeader('STATUS');

        if (!api.isAuthenticated()) {
            this.print('Not logged in. Use "login" or "signup" to get started.', 'warning');
            return;
        }

        this.printHTML(`<span class="output-bold">User:</span> <span class="output-cyan">${api.getUsername()}</span> <span class="output-dim">(${api.getUserId().substring(0, 8)}...)</span>`);

        const xStatus = await api.getXStatus();
        if (xStatus.connected) {
            this.printHTML(`<span class="output-bold">X Connected:</span> <span class="output-success">✓ @${xStatus.username || 'Connected'}</span>`);
        } else {
            this.printHTML(`<span class="output-bold">X Connected:</span> <span class="output-error">✗ Not connected</span>`);
        }

        const campaigns = await api.listCampaigns();
        const count = campaigns.campaigns ? campaigns.campaigns.length : 0;
        this.printHTML(`<span class="output-bold">Active Campaigns:</span> <span class="output-warning">${count}</span>`);

        if (this.currentSession) {
            const status = await api.getCampaignStatus(this.currentSession);
            this.printHTML(`<span class="output-bold">Current Session:</span> <span class="output-dim">${this.currentSession.substring(0, 8)}...</span> (<span class="output-cyan">${status.status || 'unknown'}</span>)`);
        }
    }

    // X Integration
    startConnectX() {
        if (!api.isAuthenticated()) {
            this.print('Please login first', 'error');
            return;
        }

        this.printHeader('CONNECT X ACCOUNT');
        this.print('Enter your X API credentials (from developer.twitter.com):', 'info');
        this.print('');
        this.prompt.textContent = 'API Key: ';
        this.inputMode = 'x-consumer-key';
    }

    async completeConnectX(consumerKey, consumerSecret, accessToken, accessSecret) {
        this.print('Validating credentials...', 'dim');
        const result = await api.validateX(consumerKey, consumerSecret, accessToken, accessSecret);

        if (result.error) {
            this.print(`Failed: ${result.error}`, 'error');
        } else {
            this.print('X account connected successfully!', 'success');
        }
    }

    // Strategy commands
    startCreateStrategy() {
        if (!api.isAuthenticated()) {
            this.print('Please login first', 'error');
            return;
        }

        this.printHeader('CREATE 9-WEEK STRATEGY');
        this.prompt.textContent = 'Project Name: ';
        this.inputMode = 'strategy-name';
    }

    async completeCreateStrategy(name, description, audience, goals) {
        if (!name || !description) {
            this.print('Name and description are required', 'error');
            return;
        }

        this.print('Creating strategy...', 'dim');
        const result = await api.createStrategy(name, description, audience, goals);

        if (result.error) {
            this.print(`Failed: ${result.error}`, 'error');
        } else {
            this.currentSession = result.session_id;
            this.print('Strategy creation started!', 'success');
            this.print(`Session ID: ${result.session_id}`, 'cyan');
            this.print('');
            this.print('Use "watch" to see progress, or "view-strategy" when complete', 'dim');
        }
    }

    async viewStrategy(sessionId) {
        if (!api.isAuthenticated()) {
            this.print('Please login first', 'error');
            return;
        }

        const id = sessionId || this.currentSession;
        if (!id) {
            this.print('No session specified. Use: view-strategy [session_id]', 'warning');
            return;
        }

        const result = await api.getStrategyTable(id);
        if (result.error) {
            this.print(`Error: ${result.error}`, 'error');
            return;
        }

        this.printHeader('9-WEEK STRATEGY TABLE');
        this.printHTML(`<span class="output-bold">Overview:</span> ${result.overview || 'N/A'}`);
        this.print('');

        const phases = result.phases || {};
        for (const [phaseName, phaseData] of Object.entries(phases)) {
            if (!phaseData) continue;

            this.printHTML(`<span class="output-warning output-bold">=== ${phaseName.toUpperCase()} (Weeks ${phaseData.weeks}) - ${phaseData.theme} ===</span>`);

            for (const track of ['marketing', 'operations', 'feedback']) {
                const tasks = phaseData[track] || [];
                if (tasks.length > 0) {
                    const color = track === 'marketing' ? 'success' : track === 'operations' ? 'cyan' : 'magenta';
                    this.printHTML(`  <span class="output-${color} output-bold">${track.toUpperCase()}:</span>`);
                    for (const task of tasks) {
                        this.print(`    Week ${task.week}: ${task.task}`, 'info');
                        this.print(`      → ${task.deliverable}`, 'dim');
                    }
                }
            }
            this.print('');
        }

        // Milestones
        if (result.milestones && result.milestones.length > 0) {
            this.printHTML('<span class="output-magenta output-bold">KEY MILESTONES:</span>');
            for (const m of result.milestones) {
                this.print(`  Week ${m.week}: ${m.milestone}`, 'cyan');
            }
        }
    }

    // Campaign commands
    startCreateCampaign() {
        if (!api.isAuthenticated()) {
            this.print('Please login first', 'error');
            return;
        }

        this.printHeader('CREATE NEW CAMPAIGN');
        this.prompt.textContent = 'Campaign Name: ';
        this.inputMode = 'campaign-name';
    }

    async completeCreateCampaign(name, description, audience, goals) {
        if (!name || !description) {
            this.print('Name and description are required', 'error');
            return;
        }

        this.print('Creating campaign...', 'dim');
        const result = await api.createCampaign(name, description, audience, goals);

        if (result.error) {
            this.print(`Failed: ${result.error}`, 'error');
        } else {
            this.currentSession = result.session_id;
            this.print('Campaign started!', 'success');
            this.print(`Session ID: ${result.session_id}`, 'cyan');
            this.print('');
            this.print('Use "watch" to see progress', 'dim');
        }
    }

    async viewPlan(sessionId) {
        if (!api.isAuthenticated()) {
            this.print('Please login first', 'error');
            return;
        }

        const id = sessionId || this.currentSession;
        if (!id) {
            this.print('No session specified. Use: view-plan [session_id]', 'warning');
            return;
        }

        const plan = await api.getCampaignPlan(id);
        if (plan.error) {
            this.print(`Error: ${plan.error}`, 'error');
            return;
        }

        this.printHeader('CAMPAIGN PLAN');
        this.printHTML(`<span class="output-bold">Strategy:</span> ${plan.strategy_summary || 'N/A'}`);

        const weeks = plan.weeks || [];
        for (const week of weeks) {
            this.print('');
            this.printHTML(`<span class="output-warning output-bold">--- Week ${week.week} - ${week.theme || ''} ---</span>`);
            for (const post of (week.posts || [])) {
                this.print(`  ${post.day} ${post.time}: ${post.topic}`, 'cyan');
                this.print(`    Type: ${post.type} | ${(post.hashtags || []).join(' ')}`, 'dim');
            }
        }
    }

    async approvePlan(sessionId) {
        if (!api.isAuthenticated()) {
            this.print('Please login first', 'error');
            return;
        }

        const id = sessionId || this.currentSession;
        if (!id) {
            this.print('No session specified. Use: approve [session_id]', 'warning');
            return;
        }

        // For simplicity, auto-approve. In a full implementation, you'd prompt for confirmation
        const result = await api.approvePlan(id, true);
        if (result.error) {
            this.print(`Error: ${result.error}`, 'error');
        } else {
            this.print(result.message || 'Plan approved!', 'success');
        }
    }

    async watchStream(sessionId) {
        if (!api.isAuthenticated()) {
            this.print('Please login first', 'error');
            return;
        }

        const id = sessionId || this.currentSession;
        if (!id) {
            this.print('No session specified. Use: watch [session_id]', 'warning');
            return;
        }

        this.printHeader('WATCHING STREAM');
        this.print('Press Ctrl+C to stop', 'warning');
        this.print('');

        let lastCount = 0;

        this.watchInterval = setInterval(async () => {
            const result = await api.getStream(id);
            const logs = result.logs || [];
            const status = result.status || 'unknown';

            // Display new logs
            if (logs.length > lastCount) {
                for (let i = lastCount; i < logs.length; i++) {
                    const log = logs[i];
                    const type = log.type === 'error' ? 'error' :
                                 log.type === 'result' ? 'success' :
                                 log.type === 'action' ? 'cyan' : 'warning';
                    this.print(`[${log.agent}] (${log.type}) ${log.content}`, type);
                }
                lastCount = logs.length;
                this.scrollToBottom();
            }

            // Check if complete
            if (['awaiting_approval', 'daily_complete', 'approved', 'running', 'strategy_complete'].includes(status)) {
                clearInterval(this.watchInterval);
                this.watchInterval = null;
                this.print('');
                this.print(`Status: ${status.toUpperCase()}`, 'cyan');
                this.printDivider();
            }
        }, 500);
    }

    async viewMap(sessionId) {
        if (!api.isAuthenticated()) {
            this.print('Please login first', 'error');
            return;
        }

        const id = sessionId || this.currentSession;
        if (!id) {
            this.print('No session specified. Use: map [session_id]', 'warning');
            return;
        }

        const map = await api.getStrategicMap(id);
        if (map.error) {
            this.print(`Error: ${map.error}`, 'error');
            return;
        }

        this.printHeader('STRATEGIC MAP');

        const progress = map.progress || {};
        this.printHTML(`<span class="output-bold">Overall Progress:</span> <span class="output-success">${(progress.completion_percentage || 0).toFixed(1)}%</span>`);
        this.print(`Completed: ${progress.completed || 0} | In Progress: ${progress.in_progress || 0} | Pending: ${progress.pending || 0}`, 'info');

        const current = map.current_position || {};
        this.printHTML(`<span class="output-bold">Current Position:</span> <span class="output-cyan">${current.description || 'Not started'}</span>`);

        this.print('');
        this.printHTML(`<span class="output-bold">Strategy:</span> ${map.strategy_summary || 'N/A'}`);

        // Weekly breakdown
        for (const week of (map.strategic_map || [])) {
            this.print('');
            this.printHTML(`<span class="output-warning output-bold">Week ${week.week} - ${week.theme || ''}</span>`);
            this.print(`Completion: ${(week.completion_percentage || 0).toFixed(0)}%`, 'dim');

            for (const post of (week.posts || [])) {
                const icon = post.status === 'completed' ? '✓' :
                             post.status === 'in_progress' ? '◐' : '○';
                const color = post.status === 'completed' ? 'success' :
                              post.status === 'in_progress' ? 'warning' : 'dim';
                this.printHTML(`  <span class="output-${color}">${icon}</span> <span class="output-cyan">${post.day} ${post.time}:</span> ${(post.topic || '').substring(0, 50)}`);
            }
        }
    }

    async listCampaigns() {
        if (!api.isAuthenticated()) {
            this.print('Please login first', 'error');
            return;
        }

        const result = await api.listCampaigns();
        if (result.error) {
            this.print(`Error: ${result.error}`, 'error');
            return;
        }

        this.printHeader('YOUR CAMPAIGNS');

        const campaigns = result.campaigns || [];
        if (campaigns.length === 0) {
            this.print('No campaigns found.', 'warning');
            return;
        }

        for (let i = 0; i < campaigns.length; i++) {
            const camp = campaigns[i];
            const status = camp.status || 'unknown';
            const color = ['approved', 'running', 'strategy_complete'].includes(status) ? 'success' : 'warning';

            this.print('');
            this.printHTML(`<span class="output-magenta output-bold">${i + 1}.</span> ${camp.session_id.substring(0, 8)}...`);
            this.printHTML(`   <span class="output-bold">Status:</span> <span class="output-${color}">${status}</span>`);
            this.print(`   Started: ${camp.started_at || 'N/A'}`, 'dim');
        }

        this.print('');
        this.print('Use "use [session_id]" to set current session', 'dim');
    }

    async stopCampaign(sessionId) {
        if (!api.isAuthenticated()) {
            this.print('Please login first', 'error');
            return;
        }

        const id = sessionId || this.currentSession;
        if (!id) {
            this.print('No session specified. Use: stop [session_id]', 'warning');
            return;
        }

        const result = await api.stopCampaign(id);
        if (result.error) {
            this.print(`Error: ${result.error}`, 'error');
        } else {
            this.print(result.message || 'Campaign stopped', 'success');
        }
    }

    async resumeCampaign(sessionId) {
        if (!api.isAuthenticated()) {
            this.print('Please login first', 'error');
            return;
        }

        const id = sessionId || this.currentSession;
        if (!id) {
            this.print('No session specified. Use: resume [session_id]', 'warning');
            return;
        }

        const result = await api.resumeCampaign(id);
        if (result.error) {
            this.print(`Error: ${result.error}`, 'error');
        } else {
            this.print(result.message || 'Campaign resumed', 'success');
        }
    }

    async showTrending(query) {
        if (!api.isAuthenticated()) {
            this.print('Please login first', 'error');
            return;
        }

        this.print('Fetching trending topics...', 'dim');
        const result = await api.getTrending(query || 'trending topics today');

        if (result.error) {
            this.print(`Error: ${result.error}`, 'error');
            return;
        }

        this.printHeader('TRENDING TOPICS');

        const trends = result.trends || [];
        if (trends.length === 0) {
            this.print('No trends found.', 'warning');
            return;
        }

        for (let i = 0; i < Math.min(trends.length, 20); i++) {
            const trend = trends[i];
            this.printHTML(`<span class="output-cyan output-bold">${i + 1}.</span> ${trend.name || 'N/A'}`);
            if (trend.snippet) {
                this.print(`   ${trend.snippet.substring(0, 100)}...`, 'dim');
            }
        }
    }

    setApiUrl(url) {
        if (!url) {
            this.print(`Current API URL: ${api.baseURL}`, 'info');
            this.print('Usage: set-url https://your-api-url', 'dim');
            return;
        }

        api.setBaseURL(url);
        this.print(`API URL set to: ${api.baseURL}`, 'success');
        this.checkConnection();
    }

    useSession(sessionId) {
        if (!sessionId) {
            if (this.currentSession) {
                this.print(`Current session: ${this.currentSession}`, 'info');
            } else {
                this.print('No session selected. Usage: use [session_id]', 'warning');
            }
            return;
        }

        this.currentSession = sessionId;
        this.print(`Session set to: ${sessionId}`, 'success');
    }
}

// Initialize console
const console_app = new Console();
