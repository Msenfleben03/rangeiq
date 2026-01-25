Start a new day planning session.

## Step 0: Check if daily file exists

1. Get today's date: `date +%Y-%m-%d`
2. Check if `YYYY-MM-DD.md` exists in current working directory
3. **If daily file exists**: Skip to **Casual Check-in Mode** (see bottom of this file)
4. **If daily file does NOT exist**: Continue with full planning flow below

---

## Step 1: Determine if Monday (first day of week)

If Monday, do weekly review FIRST before daily planning (go to Step 1a).
Otherwise, skip to Step 2 (Daily Planning).

### Step 1a: Weekly Review (Mondays only)

1. **Read ALL tracking files**: daily files from last week, backlog.md, roadmap.md, and any referenced docs
2. **Summarize last week**:
   - What was completed
   - What carried forward
   - Key learnings/notes
3. **Ask user for any additions** - things done but not captured
4. **Discuss strategic framing** - what's the focus for coming week/period? Don't assume - ask.

---

## Step 2: Daily Planning (Full Flow)

### Phase 1: Calendar (get user confirmation FIRST)

1. **Fetch calendar (if icalBuddy is available)**
   - Run `date` to get current time
   - Run `icalBuddy -ic "Work" eventsToday` (or whatever calendar name user specifies)
   - Present calendar **contextualized against current time**: mark meetings as "already passed" or "upcoming"
   - Ask: "Any meetings to ignore?" and "Any time adjustments?"
   - **STOP HERE and wait for user response before continuing**

2. **After user confirms calendar (or if skipped)**
   - Summarize: busy/light day, estimated focus time
   - Then proceed to Phase 2

### Phase 2: Context & Task Review

3. **Read context files silently**
   - Recent daily files (last 3 days)
   - backlog.md, roadmap.md
   - Any referenced docs

4. **Present carryover & ask sync questions**
   - Show incomplete tasks from recent daily files
   - **Flag recurring deferrals**: If a task has carried forward 3+ days, propose intervention:
     - Timebox: "30 min first thing tomorrow"
     - Break down: "What's the smallest piece?"
     - Pair with reward: "Do this, then the fun task"
   - Ask: "What's your focus for today?"

### Phase 3: Task Selection

5. **Present consolidated task view** - carryover + backlog items
6. **Collect NEW tasks**
7. **Side project check** - "Any ideas pulling at you?"
8. **Confirm priority order**
9. **Procrastination check** - flag boring tasks and suggest strategies

### Phase 4: Documentation

10. **Create daily file** with numbered task list, deferred section, notes
11. **Update backlog.md and roadmap.md**
12. **Update previous day's file** with task statuses

---

## Casual Check-in Mode (when daily file already exists)

1. **Read context silently** - today's file, recent dailies, backlog, roadmap
2. **Present quick task view** - 2-3 easy wins, flag deferred 3+ days
3. **Listen and update** - user picks task, update files
4. **Keep it lightweight** - no rigid structure, focus on reducing friction
