#!/bin/bash

# AI Onboarding Agent Demo Script
# This script demonstrates how to use the AI onboarding agent

echo "🚀 AI-Powered Developer Onboarding Agent Demo"
echo "=============================================="
echo

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install dependencies if needed
if [ ! -f "venv/pyvenv.cfg" ] || [ "requirements.txt" -nt "venv/pyvenv.cfg" ]; then
    echo "📥 Installing dependencies..."
    pip install -r requirements.txt
fi

# Check configuration
echo "🔍 Checking configuration..."
if [ ! -f ".env" ]; then
    echo "❌ Error: .env file not found!"
    echo "Please copy .env.example to .env and configure your settings."
    echo "Required variables:"
    echo "  - GITHUB_TOKEN"
    echo "  - GITHUB_USERNAME"
    echo "  - OPENROUTER_API_KEY"
    exit 1
fi

# Run tests
echo "🧪 Running tests..."
python src/test_agent.py
if [ $? -ne 0 ]; then
    echo "❌ Tests failed!"
    exit 1
fi

echo
echo "✅ All tests passed! Agent is ready."
echo

# Example usage (dry run)
echo "🎯 Example Usage (Dry Run):"
echo "python src/test_integration.py"
echo

# Example usage (production - requires real configuration)
echo "🎯 Example Usage (Production):"
echo "python src/agent.py \"I need to deploy my new NodeJS service called inventory-api\""
echo

echo "📋 Available natural language patterns:"
echo "  - \"I need to deploy my new NodeJS service called [name]\""
echo "  - \"Create a React app called [name]\""
echo "  - \"Build a backend service named [name]\""
echo "  - \"Deploy a simple web app called [name]\""
echo

echo "🔗 More information:"
echo "  - README.md for detailed documentation"
echo "  - templates/ for available stack templates"
echo "  - src/agent.py for implementation details"
echo

echo "✨ Demo completed! The AI onboarding agent is ready to use."