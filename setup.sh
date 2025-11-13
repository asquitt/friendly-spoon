#!/bin/bash
# Setup script for LLM Feature Store
# This script sets up the development environment

set -e  # Exit on error

echo "================================"
echo "LLM Feature Store - Setup"
echo "================================"
echo ""

# Check for required tools
echo "📋 Checking prerequisites..."

command -v python3 >/dev/null 2>&1 || { echo "❌ Python 3 is required but not installed."; exit 1; }
command -v docker >/dev/null 2>&1 || { echo "❌ Docker is required but not installed."; exit 1; }
command -v docker-compose >/dev/null 2>&1 || { echo "❌ Docker Compose is required but not installed."; exit 1; }

echo "✅ All prerequisites found!"
echo ""

# Create virtual environment
echo "🐍 Creating Python virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✅ Virtual environment created!"
else
    echo "✅ Virtual environment already exists!"
fi
echo ""

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "📦 Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt

echo "✅ Dependencies installed!"
echo ""

# Create .env file
if [ ! -f ".env" ]; then
    echo "⚙️  Creating .env file..."
    cp .env.example .env
    echo "✅ .env file created! Edit it to customize your configuration."
else
    echo "✅ .env file already exists!"
fi
echo ""

# Create data directory
echo "📁 Creating data directories..."
mkdir -p data
mkdir -p logs
mkdir -p notebooks
echo "✅ Directories created!"
echo ""

# Start Docker services
echo "🐳 Starting Docker services..."
echo "   This may take a few minutes on first run..."
docker-compose up -d

echo ""
echo "⏳ Waiting for services to be healthy..."
sleep 10

# Check services
echo ""
echo "🔍 Checking service health..."

# Check Redis
if docker-compose exec -T redis redis-cli ping > /dev/null 2>&1; then
    echo "✅ Redis is healthy"
else
    echo "⚠️  Redis may not be ready yet"
fi

# Check Kafka (simplified check)
if docker-compose ps kafka | grep -q "Up"; then
    echo "✅ Kafka is running"
else
    echo "⚠️  Kafka may not be ready yet"
fi

# Check MinIO
if curl -s http://localhost:9000/minio/health/live > /dev/null 2>&1; then
    echo "✅ MinIO is healthy"
else
    echo "⚠️  MinIO may not be ready yet"
fi

echo ""
echo "================================"
echo "🎉 Setup Complete!"
echo "================================"
echo ""
echo "Next steps:"
echo ""
echo "1. 📝 Review and edit .env file (if needed)"
echo "   nano .env"
echo ""
echo "2. 🚀 Run the example:"
echo "   python examples/simple_usage.py"
echo ""
echo "3. 🌐 Access the UIs:"
echo "   • Kafka UI:      http://localhost:8080"
echo "   • Redis UI:      http://localhost:8081"
echo "   • Temporal UI:   http://localhost:8082"
echo "   • OpenFaaS:      http://localhost:8083"
echo "   • Prometheus:    http://localhost:9090"
echo "   • Grafana:       http://localhost:3000 (admin/admin)"
echo "   • MinIO Console: http://localhost:9001 (minioadmin/minioadmin)"
echo "   • Jupyter:       http://localhost:8888"
echo ""
echo "4. 📚 Read the documentation:"
echo "   • README.md"
echo "   • docs/COST_OPTIMIZATION.md"
echo "   • docs/ARCHITECTURE.md"
echo ""
echo "💰 Current setup cost: $0/month (all local!)"
echo ""
echo "To stop services:"
echo "   docker-compose down"
echo ""
echo "To remove all data:"
echo "   docker-compose down -v"
echo ""
echo "Happy feature storing! 🎉"
