# Sports Betting Model Development

A systematic approach to building profitable sports betting projection models using quantitative methods and disciplined bankroll management.

## 🎯 Project Goal

Achieve positive ROI through **Closing Line Value (CLV)** capture across NCAA Basketball, MLB, NFL, and NCAA Football markets, starting with zero capital outlay for data and tools.

## 📊 Core Philosophy

> **CLV > Win Rate**: A bettor who consistently beats closing lines will profit long-term, even through losing streaks.

This project prioritizes:

- **CLV tracking** as the primary success metric
- **Walk-forward validation** to prevent overfitting
- **Conservative bankroll management** (Quarter Kelly, 3% max bet)
- **Market inefficiency targeting** (player props, small conferences)

## 🚀 Quick Start

### Step 1: Install Prerequisites

Before running the setup script, install these dependencies:

```powershell
# 1. Install Miniconda (Python environment manager)
#    Download from: https://docs.conda.io/en/latest/miniconda.html
#    Choose: Miniconda3 Windows 64-bit
#    Run installer, check "Add to PATH" option

# 2. Install SQLite (database)
#    Download from: https://www.sqlite.org/download.html
#    Choose: sqlite-tools-win-x64-*.zip
#    Extract to C:\sqlite and add to PATH:
#    - Search "Environment Variables" in Windows
#    - Edit PATH, add: C:\sqlite

# 3. Install Node.js (optional, for claude-flow)
#    Download from: https://nodejs.org/
#    Choose: LTS version, run installer

# 4. Install Git (includes Git Bash)
#    Download from: https://git-scm.com/download/win
#    Run installer with default options

# Verify installations (open new terminal after installing):
conda --version      # Should show: conda 23.x.x or higher
sqlite3 --version    # Should show: 3.x.x
node --version       # Should show: v18.x.x or higher (optional)
git --version        # Should show: git version 2.x.x
```

### Step 2: Download and Extract Project

```bash
# Option A: If you have the zip file
unzip sports-betting.zip
cd sports-betting

# Option B: If cloning from git
git clone https://github.com/yourusername/sports-betting.git
cd sports-betting
```

### Step 3: Run Automated Setup

```bash
# Open Git Bash (recommended) or PowerShell
# Navigate to project folder
cd sports-betting

# Run setup script
bash scripts/setup_environment.sh
```

This script will:

- ✅ Create conda environment `sports_betting` with Python 3.11
- ✅ Install all Python dependencies from `requirements.txt`
- ✅ Create project directory structure
- ✅ Copy `.env.example` to `.env`
- ✅ Initialize SQLite database with schema
- ✅ Set up pre-commit hooks

### Step 4: Configure API Keys

```powershell
# Edit .env file with your API keys
# Option 1: Notepad
notepad .env

# Option 2: VS Code (if already open)
# Just click on .env in the Explorer panel
```

**Required API Keys:**
| Key | Where to Get | Cost |
|-----|--------------|------|
| `ODDS_API_KEY` | https://the-odds-api.com/ | Free (500 req/month) |
| `CFBD_API_KEY` | https://collegefootballdata.com/ | Free |

### Step 5: Verify Installation

```bash
# Activate the environment
conda activate sports_betting

# Run tests
make test

# Or manually verify:
python -c "import pandas; import numpy; import sklearn; print('Core packages OK')"
python -c "from sportsipy.ncaab.teams import Teams; print('sportsipy OK')"
```

### Step 6: Initialize Claude-Flow (Optional)

```bash
# Only if you have Node.js installed and want AI-assisted development
npx claude-flow@alpha init
npx claude-flow@alpha memory init --reasoningbank
```

### Troubleshooting

| Issue | Solution |
|-------|----------|
| `conda: command not found` | Close and reopen terminal; ensure Miniconda added to PATH during install |
| `sqlite3: command not found` | Verify C:\sqlite is in PATH; restart terminal |
| `bash: command not found` | Use Git Bash instead of PowerShell/CMD |
| Script fails in PowerShell | Use Git Bash (installed with Git) |
| pip install fails | Try `pip install --upgrade pip` first |
| Node.js commands fail | Try Git Bash; PowerShell may have execution policy issues |

---

## 💻 VS Code Setup

This project includes pre-configured VS Code settings for optimal development experience.

### Opening the Project

```bash
# Open in VS Code from terminal
code sports-betting

# Or: File > Open Folder > select sports-betting
```

### Installing Recommended Extensions

When you first open the project, VS Code will prompt to install recommended extensions. Click **Install All**, or manually install via:

1. Open Extensions panel (`Ctrl+Shift+X` / `Cmd+Shift+X`)
2. Type `@recommended` in the search bar
3. Click **Install Workspace Recommendations**

**Essential Extensions:**
| Extension | Purpose |
|-----------|---------|
| Python | IntelliSense, debugging, formatting |
| Pylance | Fast type checking |
| Jupyter | Notebook support |
| Black Formatter | Auto-format on save |
| Ruff | Fast linting |
| SQLite Viewer | Browse betting.db |
| Rainbow CSV | Readable CSV files |
| GitLens | Git history & blame |

### Selecting the Python Interpreter

1. Open Command Palette (`Ctrl+Shift+P`)
2. Type: `Python: Select Interpreter`
3. Choose: `sports_betting (conda)`

If not visible, click **Enter interpreter path** and browse to:
`C:\Users\<your-username>\miniconda3\envs\sports_betting\python.exe`

### Using the Integrated Terminal

```bash
# Open terminal: Ctrl+` (backtick) or View > Terminal

# Activate conda environment (usually automatic)
conda activate sports_betting

# Run tests
make test

# Run daily pipeline
make run-daily
```

### Running & Debugging

**Quick Run (no debugging):**

- Open any Python file
- Press `Ctrl+F5` (Run Without Debugging)

**With Debugging:**

- Press `F5` or use Run > Start Debugging
- Choose a configuration from the dropdown:
  - `Python: Current File` - Run active file
  - `Pytest: All Tests` - Run full test suite
  - `Pytest: Current File` - Run tests in active file
  - `Daily Run: Refresh & Predict` - Run daily pipeline

**Breakpoints:**

- Click in the gutter (left of line numbers) to set breakpoints
- Use the Debug panel to inspect variables

### Viewing the Database

1. Install SQLite Viewer extension (included in recommendations)
2. Open `data/betting.db` in the Explorer panel
3. Click tables to browse data

Or use the terminal:

```bash
make db-shell
# Then: .tables, SELECT * FROM teams LIMIT 10;
```

### Jupyter Notebooks

1. Open any `.ipynb` file in `notebooks/`
2. Select kernel: `sports_betting (Python 3.11)`
3. Run cells with `Shift+Enter`

**Creating new notebooks:**

- Command Palette > `Create: New Jupyter Notebook`
- Save in `notebooks/exploration/` or `notebooks/analysis/`

### Code Formatting

Formatting is automatic on save. To manually format:

- Press `Shift+Alt+F`
- Or: Command Palette > `Format Document`

### Useful Keyboard Shortcuts

| Action | Shortcut |
|--------|----------|
| Command Palette | `Ctrl+Shift+P` |
| Quick Open File | `Ctrl+P` |
| Search in Files | `Ctrl+Shift+F` |
| Toggle Terminal | `` Ctrl+` `` |
| Go to Definition | `F12` |
| Peek Definition | `Alt+F12` |
| Run Without Debug | `Ctrl+F5` |
| Start Debugging | `F5` |
| Toggle Sidebar | `Ctrl+B` |
| Format Document | `Shift+Alt+F` |

### VS Code Settings Included

The `.vscode/` folder contains:

| File | Purpose |
|------|---------|
| `settings.json` | Workspace settings (formatting, linting, paths) |
| `extensions.json` | Recommended extensions list |
| `launch.json` | Debug configurations for tests and pipelines |

These are committed to the repository so all developers have consistent settings.

---

## 📁 Project Structure

```
sports_betting/
├── CLAUDE.md              # AI context (Claude Code reads this)
├── CLAUDE-FLOW.md         # Multi-agent orchestration config
├── README.md              # This file
├── requirements.txt       # Python dependencies
├── .env                   # API keys (gitignored)
│
├── .vscode/               # VS Code configuration (shared)
│   ├── settings.json      # Workspace settings
│   ├── launch.json        # Debug configurations
│   └── extensions.json    # Recommended extensions
│
├── config/                # Configuration
│   └── constants.py       # Thresholds, parameters
│
├── data/                  # Data storage
│   ├── raw/               # Unprocessed downloads
│   ├── processed/         # Feature-engineered data
│   └── betting.db         # SQLite database
│
├── models/                # Prediction models
├── features/              # Feature engineering
├── betting/               # Bet sizing, CLV tracking
├── tracking/              # Database interface, logging
├── backtesting/           # Walk-forward validation
├── pipelines/             # Daily automation
├── notebooks/             # Exploration & analysis
├── tests/                 # Unit tests
├── scripts/               # Utility scripts
│
└── docs/                  # Documentation
    ├── DATA_DICTIONARY.md # Field definitions
    ├── DATA_SOURCES.md    # API documentation
    ├── DECISIONS.md       # Architecture decisions
    ├── RUNBOOK.md         # Operations procedures
    └── SESSION_HANDOFF.md # Session continuity
```

## 🏈 Supported Sports

| Sport | Status | Primary Model | Data Source |
|-------|--------|---------------|-------------|
| NCAAB | 🔄 In Progress | Elo ratings | sportsipy |
| MLB | ⏳ Planned | Pitcher-based | pybaseball |
| NFL | 📋 Future | EPA-based | nfl-data-py |
| NCAAF | 📋 Future | Returning production | cfbd |

## 🔮 Prediction Markets (New)

Diversifying into political/economic prediction markets based on Tetlock's Superforecasting methodology.

| Platform | Use Case | Status |
|----------|----------|--------|
| **Kalshi** | Primary trading (CFTC-regulated) | 📋 Account setup |
| **Polymarket** | Data source, US launch Mar 2026 | ✅ Fetcher built |
| **PredictIt** | Accuracy benchmark only | 📋 Future |

### Why Prediction Markets?

- **Higher CLV potential**: 3-10% vs 1-3% in sports
- **Different inefficiencies**: Political/economic vs athletic
- **Uncorrelated returns**: Portfolio diversification
- **Less competition**: 2-3 year window before institutional saturation

### Key Resources

- `pipelines/polymarket_fetcher.py` - Market data fetching
- `tracking/forecasting_db.py` - Belief revision tracking
- `docs/SUPERFORECASTING_RESEARCH_SYNTHESIS.md` - Tetlock methodology
- `docs/PREDICTION_MARKETS_INTEGRATION_GUIDE.md` - Technical guide

## 💰 Bankroll Management

| Parameter | Value |
|-----------|-------|
| Starting Bankroll | $5,000 |
| Active Capital | $4,000 |
| Reserve (untouched) | $1,000 |
| Default Bet Sizing | Quarter Kelly |
| Maximum Bet | 3% ($150) |
| Daily Exposure Limit | 10% ($500) |

### Risk Limits

| Trigger | Threshold | Action |
|---------|-----------|--------|
| Weekly Loss | 15% | Reduce sizing 50% |
| Monthly Loss | 25% | Full stop, review |

## 📈 Development Phases

| Phase | Weeks | Focus | Target |
|-------|-------|-------|--------|
| 1-2 | Jan 24 - Feb 6 | NCAAB Elo foundation | Working model |
| 3-4 | Feb 7 - Feb 20 | Paper betting + MLB | 50+ paper bets |
| 5-6 | Feb 21 - Mar 6 | March Madness prep | Tournament model |
| 7-8 | Mar 7 - Mar 20 | Live testing | Small stakes |
| 9-10 | Mar 21 - Apr 3 | MLB deployment | Full operation |

## 🧪 Key Metrics

| Metric | Target | Why It Matters |
|--------|--------|----------------|
| **CLV** | > 1% | Primary indicator of edge |
| Closing Line Beat % | > 55% | Consistency measure |
| ROI | > 2% | Profitability (secondary) |
| Sample Size | > 500 bets | Statistical significance |

## 📚 Documentation

- **[DECISIONS.md](docs/DECISIONS.md)** - Why we made each architectural choice
- **[RUNBOOK.md](docs/RUNBOOK.md)** - Daily/weekly/monthly operations
- **[DATA_DICTIONARY.md](docs/DATA_DICTIONARY.md)** - Field definitions
- **[DATA_SOURCES.md](docs/DATA_SOURCES.md)** - API details and rate limits

## 🛠 Development with Claude

This project is designed for AI-assisted development using Claude Code and claude-flow:

```bash
# Start new model with SPARC methodology
npx claude-flow@alpha sparc tdd "NCAAB Elo model"

# Use swarm for complex tasks
npx claude-flow@alpha swarm "Backtest NCAAB Elo 2020-2025" --agents 4

# Query stored patterns
npx claude-flow@alpha memory query "data leakage" --namespace betting/patterns
```

## ⚠️ Disclaimers

### Financial Risk

Sports betting involves substantial risk of loss. This project is for educational purposes. Never bet more than you can afford to lose.

### Not Financial Advice

Nothing in this project constitutes financial or betting advice. Past performance does not guarantee future results.

### Legal Compliance

Ensure sports betting is legal in your jurisdiction. This project was developed in Wisconsin, USA where sports betting is legal.

### Responsible Gambling

If you or someone you know has a gambling problem, call 1-800-522-4700 (National Council on Problem Gambling).

## 📄 License

This project is for personal use. If you find it helpful, consider contributing improvements back.

## 🤝 Contributing

This is a personal project, but suggestions are welcome. Please open an issue to discuss before submitting PRs.

---

**Remember: CLV > Win Rate. Track everything. Stay disciplined.**
