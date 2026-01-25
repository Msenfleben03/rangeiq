# Voice Integration Setup

## Overview

Your sports-betting project has **two complementary voice solutions** configured:

| Solution | Purpose | Claude Speaks? | Interrupts Mid-Task? |
|----------|---------|----------------|----------------------|
| **mcp-voice-hooks** | Browser-based voice input | Optional | ✅ Yes |
| **VoiceMode MCP** | Full bidirectional conversation | ✅ Yes | No |

**Recommended workflow:** Use mcp-voice-hooks for iterative coding sessions where you need to interrupt. Use VoiceMode for hands-free conversations when walking/cooking/thinking.

---

## Part 1: mcp-voice-hooks (Already Configured)

### Settings Summary

| Parameter | Value | Description |
|-----------|-------|-------------|
| Port | `5111` | Browser interface at `localhost:5111` |
| Auto-open browser | `true` | Opens voice interface on Claude Code start |
| Deliver before tools | `true` | Enables mid-task interruption |

### Usage

1. Start Claude Code in the project:

   ```powershell
   cd C:\Users\msenf\sports-betting
   claude
   ```

2. Browser auto-opens to `http://localhost:5111`

3. **Push-to-talk:** Hold spacebar or click microphone button

### Mid-Task Interruption Examples

| Say this... | While doing this... |
|-------------|---------------------|
| "Change sharpe threshold to 1.5" | Running backtest |
| "Stop, use Poisson instead" | Model parameter tuning |
| "Actually, filter to NFL props only" | Data pipeline |

---

## Part 2: VoiceMode MCP (Requires One-Time Setup)

VoiceMode enables Claude to **speak responses back to you** - true bidirectional voice conversation.

### One-Time Installation

Run these commands once in your Claude Code session:

```
# Step 1: Install dependencies (local speech services)
/voicemode:install
```

This installs:

- **Whisper.cpp** — Local speech-to-text (no cloud API needed)
- **Kokoro** — Local text-to-speech with multiple voices

### Starting a Voice Conversation

```
/voicemode:converse
```

Or use the slash command:

```
/converse
```

### Voice Conversation Features

- **Natural turn-taking** — Automatic silence detection
- **Works offline** — Local speech services (no API keys required)
- **Low latency** — Fast enough for real conversation
- **Privacy** — Audio processed locally by default

### Optional: OpenAI API Fallback

If local services have issues, set OpenAI as fallback:

```powershell
$env:OPENAI_API_KEY = "your-openai-key"
```

Or add to your `.env` file in the project root.

---

## Configuration File

Location: `C:\Users\msenf\sports-betting\.claude\settings.local.json`

```json
{
  "extraKnownMarketplaces": {
    "mcp-voice-hooks-marketplace": {
      "source": {
        "source": "git",
        "url": "https://github.com/johnmatthewtennant/mcp-voice-hooks.git"
      }
    },
    "mbailey-plugins": {
      "source": {
        "source": "git",
        "url": "https://github.com/mbailey/plugins.git"
      }
    }
  },
  "enabledPlugins": {
    "plugin-dev@claude-plugins-official": true,
    "mcp-voice-hooks-plugin@mcp-voice-hooks-marketplace": true,
    "voicemode@mbailey-plugins": true
  },
  "env": {
    "MCP_VOICE_HOOKS_PORT": "5111",
    "MCP_VOICE_HOOKS_AUTO_OPEN_BROWSER": "true",
    "MCP_VOICE_HOOKS_AUTO_DELIVER_VOICE_INPUT_BEFORE_TOOLS": "true"
  }
}
```

---

## When to Use Which Solution

### Use mcp-voice-hooks when

- Running long backtests that may need adjustment
- Iterating on model parameters
- You want to type AND voice input simultaneously
- Need to interrupt/redirect mid-task

### Use VoiceMode when

- Walking to a meeting
- Cooking while debugging
- Eyes tired, need a screen break
- Hands busy (holding coffee, dog, etc.)
- Want Claude to speak responses back

---

## Windows-Specific Notes

### WSL2 Audio (if using WSL)

If running in WSL2, PulseAudio is required for microphone access:

```bash
sudo apt install pulseaudio pulseaudio-utils
```

### PowerShell Environment Variables

Set for current session:

```powershell
$env:OPENAI_API_KEY = "your-key"
```

Set permanently:

```powershell
[Environment]::SetEnvironmentVariable("OPENAI_API_KEY", "your-key", "User")
```

---

## Troubleshooting

### mcp-voice-hooks Issues

| Problem | Solution |
|---------|----------|
| Voice not recognized | Grant microphone permissions in browser |
| Port conflict | Change `MCP_VOICE_HOOKS_PORT` in settings |
| Hooks not triggering | Restart Claude Code after config changes |

### VoiceMode Issues

| Problem | Solution |
|---------|----------|
| No audio output | Check system audio settings |
| Microphone not detected | Verify terminal/app has mic permissions |
| Slow speech recognition | Install local Whisper: `/voicemode:install` |

### Debug Audio

Save audio files for troubleshooting:

```powershell
$env:VOICEMODE_SAVE_AUDIO = "true"
# Files saved to ~/.voicemode/audio/YYYY/MM/
```

---

## Slash Commands Reference

### VoiceMode Commands

| Command | Description |
|---------|-------------|
| `/voicemode:install` | Install dependencies (Whisper, Kokoro) |
| `/voicemode:converse` | Start voice conversation |
| `/converse` | Shorthand for voice conversation |

### Plugin Management

```bash
# List installed plugins
claude plugins list

# Check VoiceMode status
claude plugins info voicemode@mbailey-plugins
```

---

## Uninstall

### Remove mcp-voice-hooks only

```json
"mcp-voice-hooks-plugin@mcp-voice-hooks-marketplace": false
```

### Remove VoiceMode only

```json
"voicemode@mbailey-plugins": false
```

### Remove both

Delete the entire `enabledPlugins` section and `extraKnownMarketplaces` entries.
