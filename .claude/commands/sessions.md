---
name: sessions
description: Smart session memory - save, search, and resume Claude Code sessions
author: IaM <DEV>
version: 1.0.0
---

# Sessions - Never Lose Context Again

Automatically saves your Claude Code sessions with AI-powered summaries. Pick up exactly where you left off - even months later.

## Commands

- `/sessions` - Show last session summary for current project
- `/sessions:search <query>` - Search across all saved sessions
- `/sessions:resume [id]` - Resume session with full context
- `/sessions:list` - Browse all saved sessions
- `/sessions:export` - Export session to markdown or JSON.
- `/sessions:settings` - Configure retention (7d/30d/1y/forever)

## Features

- 🔄 **Auto-save** - Sessions saved automatically on exit
- 🧠 **AI Summaries** - What you worked on, tasks done, next steps
- 📅 **Extended Retention** - Keep 1 year+ (vs Claude's 30 days)
- 🔍 **Full-text Search** - Find sessions by keywords, files, tasks
- ▶️ **Smart Resume** - Restore complete context instantly

## Usage

After any session, run `/sessions` to see what was saved:

```
📍 LAST SESSION: Yesterday 3:42 PM (47 min)
🎯 Refactoring auth system - extracted TokenService
✅ Completed: 3 tasks | ⏳ Pending: 2 tasks
💡 Next: Update middleware imports
```

Then `/sessions:resume` to continue exactly where you left off.

## Links

- GitHub: https://github.com/iam-dev/cc-sessions
- npm: https://www.npmjs.com/package/@iam-dev/cc-sessions
