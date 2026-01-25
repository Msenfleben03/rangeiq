# Voicemode Setup Guide - Windows Installation

## Installation Status: ✅ Complete with Limitations

**Date:** January 24, 2026
**Platform:** Windows 10/11
**Voicemode Version:** 8.0.2

---

## ✅ What Was Successfully Installed

| Component | Status | Details |
|-----------|--------|---------|
| **Visual Studio Build Tools** | ✅ Installed | C++ compiler for native packages |
| **Windows SDK 10.0.22621** | ✅ Installed | Required header files |
| **voicemode MCP server** | ✅ Working | Fully functional MCP integration |
| **FFmpeg 8.0.1** | ✅ Installed | Audio conversion (requires terminal restart) |
| **Git** | ✅ Available | Version control for models |

### MCP Server Status

```bash
claude mcp list
```

```
✅ plugin:voicemode:voicemode - Connected
✅ plugin:context7:context7 - Connected
✅ plugin:voice-hooks - Connected
✅ chroma - Connected
✅ github - Connected
```

**All 5 MCP servers operational!**

---

## ⚠️ Windows Platform Limitations

### Local Service Management Not Supported

The voicemode local service installation (`voice-mode service install`) **does not work on Windows** due to:

- Unix-specific code dependencies (`os.uname()`, `fcntl` module)
- Service management designed for Linux/macOS systemd/launchd

**Error encountered:**

```
❌ Whisper installation failed: module 'os' has no attribute 'uname'
```

### What This Means

- ✅ **MCP server works** - Voice features available via MCP protocol
- ❌ **Automated local services don't work** - Can't auto-install Whisper/Kokoro
- ✅ **Cloud services work** - OpenAI API fully supported

---

## 🔧 BIOS Configuration Required for WSL (Action Required)

### ⚠️ **REMINDER: Enable Virtualization in BIOS/UEFI**

**Current Status:**

- ✅ CPU supports virtualization (Intel VT-x / AMD-V)
- ✅ WSL 2 is installed
- ✅ Virtual Machine Platform enabled
- ❌ **Virtualization NOT enabled in BIOS firmware** ← **YOU NEED TO FIX THIS**

**Why This Matters:**
WSL 2 requires hardware virtualization to be enabled in your computer's BIOS/UEFI settings. Without this, you cannot use WSL for local voice models.

### How to Enable Virtualization

**When you next restart your computer, follow these steps:**

1. **Restart your computer**

2. **Enter BIOS/UEFI settings** during boot by pressing:
   - **Dell**: F2 or F12
   - **HP**: F10 or Esc
   - **Lenovo**: F1 or F2
   - **ASUS**: F2 or Delete
   - **MSI**: Delete
   - **Other brands**: Try F2, F10, Delete, or Esc

3. **Find the virtualization setting** (look in these menus):
   - Advanced → CPU Configuration
   - Advanced → Processor Options
   - Security tab
   - System Configuration

4. **Enable the setting** (name varies by manufacturer):
   - **Intel CPUs**: "Intel VT-x", "Intel Virtualization Technology", or "VT-x"
   - **AMD CPUs**: "AMD-V" or "SVM Mode"
   - Change from "Disabled" to "Enabled"

5. **Save and Exit**:
   - Usually press F10 to save
   - Confirm when prompted
   - Computer will restart

6. **After reboot**, come back to this guide and continue with WSL installation

### Verification After BIOS Change

After enabling virtualization and rebooting, run this command to verify:

```powershell
powershell -Command "Get-ComputerInfo -Property HyperVRequirementVirtualizationFirmwareEnabled"
```

**Expected output:**

```
HyperVRequirementVirtualizationFirmwareEnabled
----------------------------------------------
                                         True
```

If it shows `True`, you're ready to continue with WSL installation!

---

## 🎯 Recommended Setup Options

### Option 1: OpenAI API (Recommended - Easiest)

**Pros:**

- ✅ No additional setup required
- ✅ High-quality voice synthesis (OpenAI TTS-HD)
- ✅ Excellent transcription accuracy (Whisper API)
- ✅ Works immediately after API key configuration

**Cons:**

- 💰 Costs ~$0.015 per 1000 characters (TTS)
- 💰 Costs ~$0.006 per minute (STT)
- 🌐 Requires internet connection

**Setup:**

1. **Get OpenAI API Key:**
   - Go to https://platform.openai.com/api-keys
   - Create new API key

2. **Configure voicemode:**

Edit `C:\Users\msenf\.voicemode\voicemode.env`:

```bash
OPENAI_API_KEY=sk-your-key-here
```

Or set system environment variable:

```powershell
[System.Environment]::SetEnvironmentVariable('OPENAI_API_KEY', 'sk-your-key-here', 'User')
```

3. **Test:**

```bash
voice-mode status
# Should show OpenAI as "configured"

voice-mode converse
# Start voice conversation
```

**For your sports betting project:**
Add to `.env`:

```bash
OPENAI_API_KEY=sk-your-key-here
```

---

### Option 2: Windows Subsystem for Linux (WSL) ⚠️ **REQUIRES BIOS CONFIGURATION**

**Current Status:** ⏸️ **BLOCKED - Virtualization not enabled in BIOS**

**Pros:**

- ✅ Full local model support (Whisper + Kokoro)
- ✅ No API costs
- ✅ Complete privacy (runs locally)
- ✅ True Unix environment

**Cons:**

- ⚙️ Requires WSL setup
- 💾 Additional disk space (~5-10 GB for models)
- 🔧 More complex configuration
- 🔧 **Requires enabling virtualization in BIOS** (see section above)

**⚠️ IMPORTANT:** Before proceeding with WSL installation, you **MUST** enable virtualization in your BIOS/UEFI settings. See the "BIOS Configuration Required for WSL" section above.

**Setup Steps (After Enabling BIOS Virtualization):**

1. **Install WSL:**

```powershell
wsl --install -d Ubuntu-24.04
```

2. **Install voicemode in WSL:**

```bash
# Inside WSL terminal
curl -LsSf https://astral.sh/uv/install.sh | sh
uvx voice-mode deps --yes
uvx voice-mode service install whisper
uvx voice-mode service install kokoro
```

3. **Start services:**

```bash
voice-mode service start whisper
voice-mode service start kokoro
```

4. **Configure voicemode to use WSL services:**

```bash
# In Windows, edit C:\Users\msenf\.voicemode\voicemode.env
VOICEMODE_STT_BASE_URLS=http://localhost:2022
VOICEMODE_TTS_BASE_URLS=http://localhost:8880
VOICEMODE_PREFER_LOCAL=true
```

**For sports betting project:**
You can run voicemode entirely in WSL and access it from Windows Claude Code.

---

### Option 3: Manual Local Setup (Advanced)

**For advanced users** who want local models without WSL:

1. **Whisper.cpp (C++ implementation):**
   - Download: https://github.com/ggerganov/whisper.cpp
   - Build for Windows
   - Run as HTTP server on port 2022

2. **Kokoro-TTS:**
   - Install separately with Python
   - Configure as HTTP service
   - Point voicemode to local endpoints

This option requires significant manual configuration and is not officially supported.

---

## 📦 FFmpeg Configuration

### Current Status

FFmpeg is installed but **not yet in PATH** (requires terminal restart).

**Installation location:**

```
C:\Users\msenf\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.0.1-full_build\bin\
```

### Activate FFmpeg

**Option A: Restart terminal** (Recommended)

- Close and reopen your terminal
- FFmpeg will be automatically in PATH

**Option B: Temporary PATH update**

```powershell
$env:PATH += ";C:\Users\msenf\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.0.1-full_build\bin"
```

**Verify:**

```bash
ffmpeg -version
# Should show: ffmpeg version 8.0.1
```

---

## 🎤 Using Voicemode with Claude Code

### Available Commands

```bash
# Check status
voice-mode status

# Start voice conversation
voice-mode converse

# Transcribe audio file
voice-mode transcribe audio.wav

# View conversation history
voice-mode history

# View recent exchanges
voice-mode exchanges

# Check configuration
voice-mode config list

# Set configuration
voice-mode config set VOICEMODE_SAVE_ALL true
```

### Voice Conversation Workflow

1. **Start conversation:**

```bash
voice-mode converse
```

2. **Speak naturally** - voicemode will:
   - Record your voice
   - Transcribe with STT (OpenAI or local Whisper)
   - Send to Claude
   - Synthesize response with TTS
   - Play audio response

3. **Session management:**
   - All conversations saved to `~/.voicemode/audio/`
   - Transcripts stored for review
   - History searchable with `voice-mode history`

---

## 🏀 Sports Betting Project Integration

### Use Cases for Voicemode

1. **Hands-free data exploration:**

   ```
   "Show me NCAAB games with highest CLV today"
   "What's the current bankroll status?"
   ```

2. **Voice-controlled backtesting:**

   ```
   "Run backtest on 2024 NCAAB season with Elo model"
   "Show ROI breakdown by conference"
   ```

3. **Verbal bet logging:**

   ```
   "Log bet: Duke -7.5 at -110, $150 stake, DraftKings"
   "What were my picks yesterday?"
   ```

4. **Audio reports:**
   - Generate weekly performance summaries
   - Listen to model predictions while reviewing odds
   - Voice alerts for high-EV opportunities

### Configuration for Betting Workflow

Add to `C:\Users\msenf\sports-betting\.env`:

```bash
# Voice settings
VOICEMODE_SAVE_ALL=true                    # Keep all audio logs
VOICEMODE_SAVE_TRANSCRIPTIONS=true        # Save bet confirmations
VOICEMODE_AUDIO_FEEDBACK=true             # Hear confirmations
VOICEMODE_VOICES=alloy,af_sky             # Preferred voices

# OpenAI API (if using cloud)
OPENAI_API_KEY=sk-your-key-here
```

---

## 🔧 Troubleshooting

### "Couldn't find ffmpeg" Warning

**Solution:** Restart terminal to load new PATH.

### "No module named 'fcntl'" Error

**Status:** Expected on Windows. This is a Unix-specific module. Core functionality still works.

### MCP Connection Failed

**Check:**

```bash
claude mcp list
# Should show voicemode as Connected

# If failed, check logs:
cat ~/AppData/Local/claude-cli-nodejs/Cache/C--Users-msenf-sports-betting/mcp-logs-plugin-voicemode-voicemode/*.jsonl
```

### OpenAI API Not Working

**Verify:**

```bash
voice-mode status
# Check "api_key_set": true under openai providers
```

**Fix:**

```bash
# Ensure API key is set
echo $env:OPENAI_API_KEY  # PowerShell
# or
echo $OPENAI_API_KEY      # Bash

# If empty, set it:
voice-mode config set OPENAI_API_KEY sk-your-key-here
```

---

## 📊 Cost Estimates (OpenAI API)

### Typical Usage Patterns

| Activity | Duration | Cost |
|----------|----------|------|
| 5-minute voice conversation | 5 min | ~$0.10 |
| 10 voice bets logged | ~2 min | ~$0.04 |
| Daily model review (voice) | 10 min | ~$0.20 |
| Weekly backtesting discussion | 15 min | ~$0.30 |

**Monthly estimate for moderate use:** ~$15-30

**Cost savings with local models (WSL):** $0/month (free)

---

## 🎯 Next Steps

### Immediate Actions Available Now

**Option A: Quick Start with OpenAI API (Recommended)**

1. ✅ **Restart terminal** to activate FFmpeg
2. ✅ **Set OpenAI API key** for immediate voice functionality
3. ✅ **Test voice conversation:** `voice-mode converse`

**Option B: Enable WSL for Free Local Models (Requires Restart)**

1. ⏸️ **Enable virtualization in BIOS** (see "BIOS Configuration Required" section above)
2. ⏸️ After BIOS change, reboot and verify virtualization is enabled
3. ⏸️ Install Ubuntu 24.04 in WSL
4. ⏸️ Install local Whisper and Kokoro services

### Future Enhancements (After Voice Setup Complete)

1. Integrate voice commands into betting workflow
2. Create voice-activated daily report script
3. Configure voice shortcuts for bet logging

---

## 📚 Additional Resources

- **Voicemode Documentation:** https://voice-mode.readthedocs.io/
- **Voicemode GitHub:** https://github.com/mbailey/voicemode
- **OpenAI Pricing:** https://openai.com/api/pricing/
- **Whisper.cpp:** https://github.com/ggerganov/whisper.cpp
- **WSL Installation:** https://learn.microsoft.com/en-us/windows/wsl/install

---

## 🔐 Security Notes

### API Key Safety

- ✅ Store API keys in `.env` files (gitignored)
- ✅ Never commit API keys to version control
- ✅ Use environment variables for production
- ❌ Don't hardcode keys in scripts

### Audio Privacy

- 🔒 All audio saved locally by default (`~/.voicemode/audio/`)
- 🔒 OpenAI API processes audio but doesn't store long-term
- 🔒 Local models (WSL) = complete privacy, zero cloud transmission

---

**Last Updated:** January 24, 2026
**Maintained by:** Claude Code Session
**Project:** Sports Betting Model Development
