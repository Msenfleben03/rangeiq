# Voicemode Quick Reference

> **⚠️ IMPORTANT REMINDER:** For WSL local models, you must enable virtualization in BIOS first!
> See `VOICEMODE_SETUP.md` → "BIOS Configuration Required for WSL" section for details.

## 🚀 Quick Start

### 1. Set API Key (One-time)

```bash
# Option A: Project .env file
echo "OPENAI_API_KEY=sk-your-key-here" >> .env

# Option B: Global environment
voice-mode config set OPENAI_API_KEY sk-your-key-here

# Option C: System environment (PowerShell)
[System.Environment]::SetEnvironmentVariable('OPENAI_API_KEY', 'sk-your-key-here', 'User')
```

### 2. Restart Terminal

```bash
# Activate FFmpeg in PATH
exit
# Open new terminal
cd C:\Users\msenf\sports-betting
```

### 3. Test Voice

```bash
voice-mode converse
```

---

## 📋 Common Commands

### Status & Info

```bash
voice-mode status                    # Show all service status
voice-mode --version                 # Show version
voice-mode config list               # List all config options
claude mcp list                      # Verify MCP connection
```

### Voice Conversation

```bash
voice-mode converse                  # Start voice conversation
voice-mode converse --voice alloy    # Use specific voice
voice-mode transcribe audio.wav      # Transcribe audio file
```

### History & Logs

```bash
voice-mode history                   # Search conversation history
voice-mode exchanges                 # View recent exchanges
voice-mode exchanges --limit 50      # Show last 50 exchanges
```

### Configuration

```bash
voice-mode config get OPENAI_API_KEY           # Check API key status
voice-mode config set VOICEMODE_SAVE_ALL true  # Save all audio
voice-mode config edit                         # Edit config file directly
```

---

## 🎯 Sports Betting Shortcuts

### Daily Workflow

```bash
# Morning routine
voice-mode converse
> "Show today's NCAAB games with highest CLV"
> "What's my current bankroll?"
> "Any high-EV bets available?"

# Bet logging
> "Log bet: Duke -7.5 at -110, stake $150, DraftKings"
> "Show my open bets"

# Evening review
> "How did my bets perform today?"
> "Show this week's ROI"
```

### Voice Commands for Betting

```bash
# Data queries
"Show last 10 games for Duke"
"What's the Elo rating for UNC?"
"Compare closing lines vs model predictions"

# Backtesting
"Run backtest on 2024 season"
"Show ROI by conference"
"What's my CLV percentage?"

# Bankroll management
"Current bankroll status"
"Kelly sizing for next bet"
"Show bet distribution across books"
```

---

## ⚙️ Configuration Presets

### Maximum Audio Logging (Betting)

```bash
voice-mode config set VOICEMODE_SAVE_ALL true
voice-mode config set VOICEMODE_SAVE_AUDIO true
voice-mode config set VOICEMODE_SAVE_TRANSCRIPTIONS true
voice-mode config set VOICEMODE_AUDIO_FEEDBACK true
```

### Privacy-Focused (Minimal Logging)

```bash
voice-mode config set VOICEMODE_SAVE_ALL false
voice-mode config set VOICEMODE_SAVE_AUDIO false
voice-mode config set VOICEMODE_SAVE_TRANSCRIPTIONS false
```

### Local-First (When WSL configured)

```bash
voice-mode config set VOICEMODE_PREFER_LOCAL true
voice-mode config set VOICEMODE_ALWAYS_TRY_LOCAL true
voice-mode config set VOICEMODE_AUTO_START_KOKORO true
```

---

## 🛠️ Troubleshooting One-Liners

### FFmpeg Not Found

```bash
# Check if installed
where ffmpeg.exe

# If not found, add to PATH temporarily
$env:PATH += ";C:\Users\msenf\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.0.1-full_build\bin"

# Verify
ffmpeg -version
```

### MCP Connection Issues

```bash
# Check status
claude mcp list

# View logs
cat ~/AppData/Local/claude-cli-nodejs/Cache/C--Users-msenf-sports-betting/mcp-logs-plugin-voicemode-voicemode/*.jsonl | tail -50

# Restart Claude Code
exit
# Reopen terminal
```

### OpenAI API Not Working

```bash
# Check status
voice-mode status | grep "api_key_set"

# Verify environment
echo $env:OPENAI_API_KEY  # PowerShell
echo $OPENAI_API_KEY      # Bash

# Reconfigure
voice-mode config set OPENAI_API_KEY sk-your-key-here
```

---

## 📍 Key File Locations

```
C:\Users\msenf\.voicemode\
├── voicemode.env              # Main configuration
├── audio\                      # Recorded conversations
│   └── YYYY\MM\               # Organized by date
├── exchanges\                  # Conversation logs
└── history\                    # Searchable history

C:\Users\msenf\sports-betting\
├── .env                        # Project API keys
└── docs\
    ├── VOICEMODE_SETUP.md             # Full setup guide
    └── VOICEMODE_QUICK_REFERENCE.md   # This file
```

---

## 🎤 Available Voices (OpenAI)

| Voice | Characteristics | Best For |
|-------|----------------|----------|
| `alloy` | Neutral, clear | Default, data reading |
| `echo` | Male, authoritative | Reports, summaries |
| `fable` | British, expressive | Storytelling |
| `onyx` | Deep, male | Alerts, confirmations |
| `nova` | Female, friendly | Conversations |
| `shimmer` | Warm, empathetic | Extended dialogs |

**Set preferred voice:**

```bash
voice-mode config set VOICEMODE_VOICES alloy,nova
```

---

## 💰 Cost Tracking (OpenAI API)

### Real-time Usage Check

```bash
# View usage at: https://platform.openai.com/usage

# Estimate costs:
# TTS: $0.015 per 1000 characters
# STT: $0.006 per minute
```

### Budget Alerts

```bash
# Set budget limit on OpenAI dashboard
# Get email alerts at 75%, 90%, 100% usage
```

---

## 🔗 Quick Links

- **Full Setup Guide:** `docs/VOICEMODE_SETUP.md`
- **Voicemode Docs:** https://voice-mode.readthedocs.io/
- **OpenAI API Keys:** https://platform.openai.com/api-keys
- **OpenAI Pricing:** https://openai.com/api/pricing/
- **Check MCP Status:** `claude mcp list`

---

## 📞 Getting Help

```bash
# Command help
voice-mode --help
voice-mode converse --help
voice-mode config --help

# Service status
voice-mode status

# View recent logs
voice-mode exchanges --limit 10

# Check MCP connection
claude mcp list
```

---

**Quick Access:** Keep this file pinned for daily reference!
**Last Updated:** January 24, 2026
