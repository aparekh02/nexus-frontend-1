# Nexus Campaign Console - Frontend

A web-based terminal console that connects to the Nexus Marketing Campaign Backend.

## Quick Start

1. **Install dependencies:**
   ```bash
   cd frontend
   npm install
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   ```

   Edit `.env` to set your backend URL:
   ```
   API_URL=http://localhost:8000
   FRONTEND_PORT=3000
   ```

3. **Start the server:**
   ```bash
   npm start
   ```

4. **Open in browser:**
   ```
   http://localhost:3000
   ```

## Available Commands

### Authentication
- `login` - Login to your account
- `signup` - Create a new account
- `logout` - Logout from current session
- `status` - Show current status

### X Integration
- `connect-x` - Connect your X (Twitter) account

### Strategy
- `create-strategy` - Create a 9-week strategic plan
- `view-strategy [session_id]` - View strategy table

### Campaign
- `create-campaign` - Create new marketing campaign
- `view-plan [session_id]` - View campaign plan
- `approve [session_id]` - Approve campaign plan

### Monitoring
- `watch [session_id]` - Watch stream in real-time
- `map [session_id]` - View strategic map with progress
- `list` - List all campaigns
- `trending [query]` - Show trending topics

### Control
- `stop [session_id]` - Stop running campaign
- `resume [session_id]` - Resume stopped campaign
- `use [session_id]` - Set current session

### System
- `set-url [url]` - Set backend API URL
- `clear` - Clear console
- `help` - Show help

## Keyboard Shortcuts

- **Tab** - Autocomplete command
- **↑/↓** - Navigate command history
- **Ctrl+C** - Cancel current operation

## Running Backend

Make sure your backend is running before using the console:

```bash
# In the root nexus-mvp directory
python main.py
```

The backend should be available at `http://localhost:8000`.

## Features

- Terminal-like interface in the browser
- Real-time stream watching
- Command history with arrow keys
- Tab autocomplete
- Multi-step input for forms
- Colorful output with status indicators
