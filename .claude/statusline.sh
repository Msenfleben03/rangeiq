#!/bin/bash
# Sports Betting Project Status Line
# Shows bankroll, model performance, CLV tracking, Claude Flow metrics, and development status

# Read Claude Code JSON input from stdin (if available)
CLAUDE_INPUT=$(cat 2>/dev/null || echo "{}")

# Get project directory from Claude Code input or use current directory
PROJECT_DIR=$(echo "$CLAUDE_INPUT" | jq -r '.workspace.project_dir // ""' 2>/dev/null)
if [ -z "$PROJECT_DIR" ] || [ "$PROJECT_DIR" = "null" ]; then
  PROJECT_DIR="C:/Users/msenf/sports-betting"
fi

# File paths relative to project directory
BETTING_DB="${PROJECT_DIR}/data/betting.db"
BANKROLL_LOG="${PROJECT_DIR}/tracking/bankroll.json"
MODEL_METRICS="${PROJECT_DIR}/.claude/metrics/model-performance.json"

# Claude Flow paths
FLOW_CONFIG="${PROJECT_DIR}/.claude-flow/config.yaml"
FLOW_DATA="${PROJECT_DIR}/.claude-flow/data"
FLOW_STATE="${PROJECT_DIR}/.claude-flow/state.json"

# ANSI Color Codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[0;37m'
BOLD='\033[1m'
DIM='\033[2m'
RESET='\033[0m'

# Bright colors
BRIGHT_RED='\033[1;31m'
BRIGHT_GREEN='\033[1;32m'
BRIGHT_YELLOW='\033[1;33m'
BRIGHT_BLUE='\033[1;34m'
BRIGHT_PURPLE='\033[1;35m'
BRIGHT_CYAN='\033[1;36m'

# Sports Betting Project Settings
STARTING_BANKROLL=5000
TARGET_ROI=0.05  # 5% monthly target

# Default values for betting metrics
CURRENT_BANKROLL="--"
DAILY_PNL="--"
AVG_CLV="--"
ACTIVE_BETS=0
BETS_PLACED=0
WIN_RATE="--"
ROI="--"

# Default values for Claude Flow metrics
FLOW_ENABLED=false
SWARM_ACTIVE=false
ACTIVE_AGENTS=0
MEMORY_ITEMS=0
FLOW_TOPOLOGY="--"

# Get current git branch
GIT_BRANCH=""
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  GIT_BRANCH=$(git branch --show-current 2>/dev/null || echo "master")
fi

# Get model name from Claude Code input
MODEL_NAME=""
if [ "$CLAUDE_INPUT" != "{}" ]; then
  MODEL_NAME=$(echo "$CLAUDE_INPUT" | jq -r '.model.display_name // ""' 2>/dev/null)
fi

# Query betting database for current stats (if database exists)
if [ -f "$BETTING_DB" ] && command -v sqlite3 &>/dev/null; then
  # Get most recent bankroll entry
  LATEST_BALANCE=$(sqlite3 "$BETTING_DB" "SELECT ending_balance FROM bankroll_log ORDER BY date DESC LIMIT 1" 2>/dev/null || echo "")
  if [ -n "$LATEST_BALANCE" ]; then
    CURRENT_BANKROLL=$(printf "%.0f" "$LATEST_BALANCE")
  fi

  # Get today's P&L
  TODAY=$(date +%Y-%m-%d)
  DAILY_PNL=$(sqlite3 "$BETTING_DB" "SELECT COALESCE(SUM(profit_loss), 0) FROM bets WHERE DATE(game_date) = '$TODAY' AND result IS NOT NULL" 2>/dev/null || echo "0")
  DAILY_PNL=$(printf "%.0f" "$DAILY_PNL" 2>/dev/null || echo "0")

  # Get average CLV (last 100 bets)
  AVG_CLV=$(sqlite3 "$BETTING_DB" "SELECT COALESCE(AVG(clv), 0) FROM (SELECT clv FROM bets WHERE clv IS NOT NULL ORDER BY created_at DESC LIMIT 100)" 2>/dev/null || echo "0")
  AVG_CLV=$(printf "%.2f" "$AVG_CLV" 2>/dev/null || echo "0.00")

  # Count active bets (pending results)
  ACTIVE_BETS=$(sqlite3 "$BETTING_DB" "SELECT COUNT(*) FROM bets WHERE result IS NULL" 2>/dev/null || echo "0")

  # Total bets placed
  BETS_PLACED=$(sqlite3 "$BETTING_DB" "SELECT COUNT(*) FROM bets" 2>/dev/null || echo "0")

  # Win rate
  WINS=$(sqlite3 "$BETTING_DB" "SELECT COUNT(*) FROM bets WHERE result = 'W'" 2>/dev/null || echo "0")
  if [ "$BETS_PLACED" -gt 0 ]; then
    WIN_RATE=$(awk "BEGIN {printf \"%.1f\", ($WINS / $BETS_PLACED) * 100}")
  fi

  # ROI calculation
  TOTAL_STAKE=$(sqlite3 "$BETTING_DB" "SELECT COALESCE(SUM(stake), 0) FROM bets WHERE result IS NOT NULL" 2>/dev/null || echo "0")
  TOTAL_PROFIT=$(sqlite3 "$BETTING_DB" "SELECT COALESCE(SUM(profit_loss), 0) FROM bets WHERE result IS NOT NULL" 2>/dev/null || echo "0")
  if [ "$(echo "$TOTAL_STAKE > 0" | bc 2>/dev/null)" = "1" ]; then
    ROI=$(awk "BEGIN {printf \"%.1f\", ($TOTAL_PROFIT / $TOTAL_STAKE) * 100}")
  fi
elif [ -f "$BANKROLL_LOG" ]; then
  # Fallback to JSON log file
  CURRENT_BANKROLL=$(jq -r '.current_balance // 5000' "$BANKROLL_LOG" 2>/dev/null || echo "5000")
  DAILY_PNL=$(jq -r '.today_pnl // 0' "$BANKROLL_LOG" 2>/dev/null || echo "0")
  AVG_CLV=$(jq -r '.avg_clv // 0' "$BANKROLL_LOG" 2>/dev/null | xargs printf "%.2f")
  ACTIVE_BETS=$(jq -r '.active_bets // 0' "$BANKROLL_LOG" 2>/dev/null || echo "0")
fi

# Query Claude Flow metrics
if [ -f "$FLOW_CONFIG" ]; then
  FLOW_ENABLED=true

  # Get topology from config
  if command -v yq &>/dev/null; then
    FLOW_TOPOLOGY=$(yq eval '.swarm.topology // "hierarchical"' "$FLOW_CONFIG" 2>/dev/null || echo "hierarchical")
  elif command -v grep &>/dev/null; then
    FLOW_TOPOLOGY=$(grep "topology:" "$FLOW_CONFIG" 2>/dev/null | head -n1 | sed 's/.*topology: *\(.*\)/\1/' || echo "hierarchical")
  fi

  # Count memory items (check for memory database or files)
  if [ -d "$FLOW_DATA" ]; then
    MEMORY_ITEMS=$(find "$FLOW_DATA" -type f 2>/dev/null | wc -l | tr -d ' ')
  fi

  # Check for active swarm state
  if [ -f "$FLOW_STATE" ]; then
    SWARM_ACTIVE=$(jq -r '.swarm.active // false' "$FLOW_STATE" 2>/dev/null || echo "false")
    ACTIVE_AGENTS=$(jq -r '.swarm.agents | length // 0' "$FLOW_STATE" 2>/dev/null || echo "0")
  fi
fi

# Calculate bankroll change
BANKROLL_CHANGE=0
if [ "$CURRENT_BANKROLL" != "--" ]; then
  BANKROLL_CHANGE=$((CURRENT_BANKROLL - STARTING_BANKROLL))
fi

# Color bankroll based on performance
BANKROLL_COLOR="${BRIGHT_GREEN}"
if [ "$BANKROLL_CHANGE" -lt 0 ]; then
  BANKROLL_COLOR="${BRIGHT_RED}"
elif [ "$BANKROLL_CHANGE" -eq 0 ]; then
  BANKROLL_COLOR="${YELLOW}"
fi

# Color P&L
PNL_COLOR="${DIM}"
if [ "$DAILY_PNL" != "--" ] && [ "$(echo "$DAILY_PNL > 0" | bc 2>/dev/null)" = "1" ]; then
  PNL_COLOR="${BRIGHT_GREEN}"
elif [ "$DAILY_PNL" != "--" ] && [ "$(echo "$DAILY_PNL < 0" | bc 2>/dev/null)" = "1" ]; then
  PNL_COLOR="${BRIGHT_RED}"
fi

# Color CLV (positive is good)
CLV_COLOR="${DIM}"
if [ "$AVG_CLV" != "--" ] && [ "$(echo "$AVG_CLV > 0.01" | bc 2>/dev/null)" = "1" ]; then
  CLV_COLOR="${BRIGHT_GREEN}"
elif [ "$AVG_CLV" != "--" ] && [ "$(echo "$AVG_CLV < -0.01" | bc 2>/dev/null)" = "1" ]; then
  CLV_COLOR="${BRIGHT_RED}"
fi

# Color ROI
ROI_COLOR="${DIM}"
if [ "$ROI" != "--" ] && [ "$(echo "$ROI > 0" | bc 2>/dev/null)" = "1" ]; then
  ROI_COLOR="${BRIGHT_GREEN}"
elif [ "$ROI" != "--" ] && [ "$(echo "$ROI < 0" | bc 2>/dev/null)" = "1" ]; then
  ROI_COLOR="${BRIGHT_RED}"
fi

# Get context window usage from Claude Code input
CONTEXT_PCT=0
CONTEXT_COLOR="${DIM}"
if [ "$CLAUDE_INPUT" != "{}" ]; then
  CONTEXT_REMAINING=$(echo "$CLAUDE_INPUT" | jq '.context_window.remaining_percentage // null' 2>/dev/null)

  if [ "$CONTEXT_REMAINING" != "null" ] && [ -n "$CONTEXT_REMAINING" ]; then
    CONTEXT_PCT=$((100 - CONTEXT_REMAINING))
  fi

  # Color based on usage
  if [ "$CONTEXT_PCT" -lt 50 ]; then
    CONTEXT_COLOR="${BRIGHT_GREEN}"
  elif [ "$CONTEXT_PCT" -lt 75 ]; then
    CONTEXT_COLOR="${BRIGHT_YELLOW}"
  else
    CONTEXT_COLOR="${BRIGHT_RED}"
  fi
fi

# Check development phase based on project structure
DEV_PHASE="Setup"
PHASE_COLOR="${YELLOW}"
if [ -f "${PROJECT_DIR}/models/elo.py" ]; then
  DEV_PHASE="Building"
  PHASE_COLOR="${BRIGHT_CYAN}"
fi
if [ "$BETS_PLACED" -gt 0 ] && [ "$BETS_PLACED" -lt 50 ]; then
  DEV_PHASE="Testing"
  PHASE_COLOR="${BRIGHT_YELLOW}"
fi
if [ "$BETS_PLACED" -gt 50 ]; then
  DEV_PHASE="Live"
  PHASE_COLOR="${BRIGHT_GREEN}"
fi

# Color Flow topology
FLOW_COLOR="${DIM}"
if [ "$SWARM_ACTIVE" = "true" ]; then
  FLOW_COLOR="${BRIGHT_CYAN}"
elif [ "$FLOW_ENABLED" = "true" ]; then
  FLOW_COLOR="${CYAN}"
fi

# Build output
OUTPUT=""

# Header: Sports Betting Project
OUTPUT="${BOLD}${BRIGHT_PURPLE}Sports Betting${RESET}"
if [ -n "$MODEL_NAME" ]; then
  OUTPUT="${OUTPUT}  ${DIM}│${RESET}  ${PURPLE}${MODEL_NAME}${RESET}"
fi
if [ -n "$GIT_BRANCH" ]; then
  OUTPUT="${OUTPUT}  ${DIM}│${RESET}  ${BRIGHT_BLUE}${GIT_BRANCH}${RESET}"
fi
OUTPUT="${OUTPUT}  ${DIM}│${RESET}  ${PHASE_COLOR}${DEV_PHASE}${RESET}"

# Bankroll Line
if [ "$BANKROLL_CHANGE" -ge 0 ]; then
  CHANGE_SIGN="+"
else
  CHANGE_SIGN=""
fi
OUTPUT="${OUTPUT}  ${DIM}│${RESET}  ${BANKROLL_COLOR}\$${CURRENT_BANKROLL}${RESET} ${DIM}(${CHANGE_SIGN}${BANKROLL_CHANGE})${RESET}"

# Stats Line: Daily P&L | CLV | Active Bets | ROI
OUTPUT="${OUTPUT}  ${DIM}│${RESET}  ${PNL_COLOR}Today: \$${DAILY_PNL}${RESET}"
OUTPUT="${OUTPUT}  ${DIM}│${RESET}  ${CLV_COLOR}CLV: ${AVG_CLV}%${RESET}"
if [ "$ACTIVE_BETS" -gt 0 ]; then
  OUTPUT="${OUTPUT}  ${DIM}│${RESET}  ${BRIGHT_CYAN}Active: ${ACTIVE_BETS}${RESET}"
fi
if [ "$ROI" != "--" ]; then
  OUTPUT="${OUTPUT}  ${DIM}│${RESET}  ${ROI_COLOR}ROI: ${ROI}%${RESET}"
fi
if [ "$CONTEXT_PCT" -gt 0 ]; then
  OUTPUT="${OUTPUT}  ${DIM}│${RESET}  ${CONTEXT_COLOR}Context: ${CONTEXT_PCT}%${RESET}"
fi

# Claude Flow metrics (only show if enabled)
if [ "$FLOW_ENABLED" = "true" ]; then
  OUTPUT="${OUTPUT}  ${DIM}│${RESET}  ${FLOW_COLOR}Flow: ${FLOW_TOPOLOGY}${RESET}"

  if [ "$SWARM_ACTIVE" = "true" ] && [ "$ACTIVE_AGENTS" -gt 0 ]; then
    OUTPUT="${OUTPUT} ${BRIGHT_CYAN}(${ACTIVE_AGENTS} agents)${RESET}"
  fi

  if [ "$MEMORY_ITEMS" -gt 0 ]; then
    OUTPUT="${OUTPUT}  ${DIM}│${RESET}  ${PURPLE}Memory: ${MEMORY_ITEMS}${RESET}"
  fi
fi

printf "%b" "$OUTPUT"
