const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const morgan = require('morgan');
require('dotenv').config();

const app = express();
const PORT = process.env.PORT || 8080;

// Middleware
app.use(helmet());
app.use(cors());
app.use(morgan('combined'));
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Health check endpoint
app.get('/health', (req, res) => {
  res.status(200).json({
    status: 'healthy',
    app: '{{appName}}',
    version: '1.0.0',
    timestamp: new Date().toISOString()
  });
});

// Welcome endpoint
app.get('/', (req, res) => {
  res.status(200).json({
    message: 'Welcome to {{appName}}!',
    description: '{{description}}',
    version: '1.0.0',
    endpoints: [
      'GET /health - Health check',
      'GET / - Welcome message',
      'GET /api/info - App information'
    ]
  });
});

// API info endpoint
app.get('/api/info', (req, res) => {
  res.status(200).json({
    app: '{{appName}}',
    description: '{{description}}',
    version: '1.0.0',
    environment: process.env.NODE_ENV || 'development',
    port: PORT,
    repository: '{{repositoryUrl}}'
  });
});

// 404 handler
app.use('*', (req, res) => {
  res.status(404).json({
    error: 'Not Found',
    message: `Route ${req.originalUrl} not found`
  });
});

// Error handler
app.use((err, req, res, next) => {
  console.error('Error:', err);
  res.status(err.status || 500).json({
    error: 'Internal Server Error',
    message: process.env.NODE_ENV === 'development' ? err.message : 'Something went wrong'
  });
});

// Start server
if (require.main === module) {
  app.listen(PORT, '0.0.0.0', () => {
    console.log(`🚀 {{appName}} server running on port ${PORT}`);
    console.log(`📍 Health check: http://localhost:${PORT}/health`);
    console.log(`📍 Welcome: http://localhost:${PORT}/`);
  });
}

module.exports = app;