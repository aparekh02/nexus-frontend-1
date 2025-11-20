/**
 * Simple server for Nexus Campaign Console
 * Serves static files and provides API URL configuration
 */

require('dotenv').config();
const express = require('express');
const path = require('path');

const app = express();
const PORT = process.env.FRONTEND_PORT || 3000;
const API_URL = process.env.API_URL || 'http://localhost:8000';

// Serve static files
app.use(express.static(__dirname));

// Endpoint to get API configuration
app.get('/config', (req, res) => {
    res.json({
        apiUrl: API_URL
    });
});

// Serve index.html for all other routes
app.get('*', (req, res) => {
    res.sendFile(path.join(__dirname, 'index.html'));
});

app.listen(PORT, () => {
    console.log('');
    console.log('╔══════════════════════════════════════════════════════════╗');
    console.log('║        NEXUS CAMPAIGN CONSOLE - FRONTEND SERVER          ║');
    console.log('╚══════════════════════════════════════════════════════════╝');
    console.log('');
    console.log(`  Frontend:  http://localhost:${PORT}`);
    console.log(`  Backend:   ${API_URL}`);
    console.log('');
    console.log('  Open your browser to access the console.');
    console.log('');
});
