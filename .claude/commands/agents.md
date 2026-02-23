# /agents -- Agent Roster Manager

Manage the specialized agents defined in `.claude/agents/`.

## Usage

```bash
/agents                    # List all agents with descriptions
/agents list               # Same as above
/agents show <name>        # Show full agent definition
/agents add <name>         # Create a new agent interactively
/agents remove <name>      # Remove an agent definition
/agents search <keyword>   # Find agents by keyword
```

## Instructions

When the user invokes `/agents`, follow these steps:

### Default / `list`

1. Read all `.md` files in `.claude/agents/` directory.
2. For each file, extract the agent name (filename without `.md`) and the first line or description.
3. Display a formatted table:

| # | Agent | Description |
|---|-------|-------------|
| 1 | sql-pro | ... |
| 2 | data-scientist | ... |

4. Show total count and remind user they can use `/agents show <name>` for details.

### `show <name>`

1. Read `.claude/agents/<name>.md`.
2. Display the full content to the user.

### `add <name>`

1. Ask the user for: description, use cases, and which tools the agent needs.
2. Create `.claude/agents/<name>.md` with the agent definition.
3. Confirm creation.

### `search <keyword>`

1. Grep all files in `.claude/agents/` for the keyword (case-insensitive).
2. Show matching agents with relevant context.

### `remove <name>`

1. Confirm with the user before deleting.
2. Delete `.claude/agents/<name>.md`.

## Important

- This command manages the **agent roster** (`.claude/agents/*.md` files).
- To generate or update **AGENTS.md** project documentation, use `/agents:agents` instead.
