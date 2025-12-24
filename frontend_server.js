/**
 * Frontend Server for Creator Agents Platform Dashboard
 * Serves static HTML/CSS/JS frontend for testing the API
 */

const express = require('express');
const cors = require('cors');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 3000;

// Middleware
app.use(cors());
app.use(express.json());

// Serve static files
app.use('/static', express.static(path.join(__dirname, 'frontend')));

// Serve index.html at root
app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'frontend', 'index.html'));
});

// Health check
app.get('/api/health', (req, res) => {
    res.json({
        status: 'ok',
        service: 'frontend-server',
        timestamp: new Date().toISOString()
    });
});

// Start server
app.listen(PORT, () => {
    console.log('');
    console.log('🎨 Creator Agents Platform - Frontend Server Started');
    console.log('=' .repeat(60));
    console.log(`📍 Frontend URL: http://localhost:${PORT}`);
    console.log(`🔌 Backend API URL: http://localhost:8000`);
    console.log('');
    console.log('Make sure the Creator Agents Platform API is running:');
    console.log('  docker-compose up postgres redis api worker');
    console.log('');
    console.log('Or run the backend locally:');
    console.log('  cd /Users/dharsankumar/Documents/GitHub/creator-agents-platform');
    console.log('  python -m app.main');
    console.log('');
    console.log('=' .repeat(60));
});

// Graceful shutdown
process.on('SIGTERM', () => {
    console.log('SIGTERM received, shutting down gracefully');
    process.exit(0);
});
