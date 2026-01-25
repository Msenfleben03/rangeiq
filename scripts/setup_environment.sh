#!/bin/bash
# Sports Betting Model Development - Environment Setup Script
# Run: bash scripts/setup_environment.sh

set -e  # Exit on any error

echo "=========================================="
echo "Sports Betting Model Development Setup"
echo "=========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if conda is installed
if ! command -v conda &> /dev/null; then
    echo -e "${RED}Error: conda is not installed.${NC}"
    echo "Please install Miniconda or Anaconda first:"
    echo "  https://docs.conda.io/en/latest/miniconda.html"
    exit 1
fi

echo -e "${GREEN}✓ conda found${NC}"

# Environment name
ENV_NAME="sports_betting"
PYTHON_VERSION="3.11"

# Check if environment already exists
if conda env list | grep -q "^${ENV_NAME} "; then
    echo -e "${YELLOW}Environment '${ENV_NAME}' already exists.${NC}"
    read -p "Do you want to remove and recreate it? (y/N): " confirm
    if [[ $confirm == [yY] ]]; then
        echo "Removing existing environment..."
        conda env remove -n $ENV_NAME -y
    else
        echo "Activating existing environment..."
        eval "$(conda shell.bash hook)"
        conda activate $ENV_NAME
        echo -e "${GREEN}✓ Environment activated${NC}"
        exit 0
    fi
fi

# Create conda environment
echo ""
echo "Creating conda environment: $ENV_NAME (Python $PYTHON_VERSION)"
conda create -n $ENV_NAME python=$PYTHON_VERSION -y

# Activate environment
eval "$(conda shell.bash hook)"
conda activate $ENV_NAME
echo -e "${GREEN}✓ Environment created and activated${NC}"

# Upgrade pip
echo ""
echo "Upgrading pip..."
pip install --upgrade pip

# Install requirements
echo ""
echo "Installing Python dependencies..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
    echo -e "${GREEN}✓ Dependencies installed${NC}"
else
    echo -e "${YELLOW}Warning: requirements.txt not found. Skipping dependency installation.${NC}"
fi

# Create directory structure
echo ""
echo "Creating project directories..."
mkdir -p data/raw/ncaab
mkdir -p data/raw/mlb
mkdir -p data/raw/nfl
mkdir -p data/raw/ncaaf
mkdir -p data/processed
mkdir -p data/odds
mkdir -p data/external
mkdir -p models/saved
mkdir -p models/sport_specific/ncaab
mkdir -p models/sport_specific/mlb
mkdir -p features/sport_specific
mkdir -p betting
mkdir -p tracking
mkdir -p backtesting
mkdir -p pipelines
mkdir -p notebooks/exploration
mkdir -p notebooks/modeling
mkdir -p notebooks/analysis
mkdir -p tests
mkdir -p logs
mkdir -p reports/daily
mkdir -p reports/weekly
mkdir -p reports/monthly
mkdir -p reports/incidents
mkdir -p backups
echo -e "${GREEN}✓ Directories created${NC}"

# Setup .env file
echo ""
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo -e "${YELLOW}Created .env from .env.example${NC}"
        echo "Please edit .env to add your API keys."
    else
        echo -e "${YELLOW}Warning: .env.example not found. Creating empty .env${NC}"
        touch .env
    fi
else
    echo -e "${GREEN}✓ .env already exists${NC}"
fi

# Initialize database
echo ""
if [ -f "scripts/init_database.sql" ]; then
    echo "Initializing SQLite database..."
    mkdir -p data
    sqlite3 data/betting.db < scripts/init_database.sql
    echo -e "${GREEN}✓ Database initialized at data/betting.db${NC}"
else
    echo -e "${YELLOW}Warning: scripts/init_database.sql not found. Skipping database setup.${NC}"
fi

# Install pre-commit hooks (optional)
echo ""
if [ -f ".pre-commit-config.yaml" ]; then
    echo "Setting up pre-commit hooks..."
    pip install pre-commit
    pre-commit install
    echo -e "${GREEN}✓ Pre-commit hooks installed${NC}"
fi

# Check for Node.js (needed for claude-flow)
echo ""
if command -v node &> /dev/null; then
    NODE_VERSION=$(node -v)
    echo -e "${GREEN}✓ Node.js found: $NODE_VERSION${NC}"

    # Test claude-flow availability
    if npx claude-flow@alpha --version &> /dev/null; then
        echo -e "${GREEN}✓ claude-flow available${NC}"
    else
        echo -e "${YELLOW}Note: claude-flow not yet initialized. Run 'npx claude-flow@alpha init' to set up.${NC}"
    fi
else
    echo -e "${YELLOW}Warning: Node.js not found. claude-flow features will not be available.${NC}"
    echo "Install Node.js from: https://nodejs.org/"
fi

# Verify critical packages
echo ""
echo "Verifying critical package imports..."
python -c "import pandas; print(f'  pandas: {pandas.__version__}')" 2>/dev/null || echo -e "${RED}  pandas: FAILED${NC}"
python -c "import numpy; print(f'  numpy: {numpy.__version__}')" 2>/dev/null || echo -e "${RED}  numpy: FAILED${NC}"
python -c "import sklearn; print(f'  scikit-learn: {sklearn.__version__}')" 2>/dev/null || echo -e "${RED}  scikit-learn: FAILED${NC}"
python -c "import sportsipy; print('  sportsipy: OK')" 2>/dev/null || echo -e "${YELLOW}  sportsipy: Not installed (optional)${NC}"
python -c "import pybaseball; print('  pybaseball: OK')" 2>/dev/null || echo -e "${YELLOW}  pybaseball: Not installed (optional)${NC}"

# Summary
echo ""
echo "=========================================="
echo -e "${GREEN}Setup Complete!${NC}"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Edit .env to add your API keys"
echo "  2. Activate environment: conda activate $ENV_NAME"
echo "  3. Initialize claude-flow: npx claude-flow@alpha init"
echo "  4. Run a test: python -c \"from sportsipy.ncaab.teams import Teams; print('OK')\""
echo ""
echo "Project structure created at: $(pwd)"
echo ""
