---
 name: burn
 description: Show token usage stats and time remaining until limit
---

# Token Usage Report

Display current token usage statistics for Claude Code.

## Instructions

Run the cc-burn CLI to get token usage stats:

```bash
  npx @iam-dev/cc-burn
```

Or if installed globally:

cc-burn

Output

Shows:

- Tokens used vs limit (5-hour window)
- Burn rate (tokens/minute)
- Estimated time remaining
- Session cost
- Breakdown by input/output/cache

Options

- --statusbar - Compact single-line output
- --compact - One-line summary
- --json - Raw JSON output
- --hours <n> - Custom time window (default: 5)

Alert Levels

- Normal (< 80%): Safe to continue
- Warning (80-95%): Consider slowing down
- Critical (> 95%): Take a break or compact context

Links

- GitHub: https://github.com/iam-dev/cc-burn
- npm: https://www.npmjs.com/package/@iam-dev/cc-burn
