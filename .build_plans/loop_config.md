# Quality Feature Implementation Loop Configuration

## Overview
This loop implements the Quality Reporting & Control System feature session by session, following the build plan at [quality-buildplan.md](../quality-buildplan.md).

---

## Session Execution Pattern

Each iteration will:
1. Read `.build_plans/session_tracker.md` to determine current phase/status
2. Identify next task based on priority order (P0 → P1 → P2 → P3+)
3. Execute the work for that session
4. Update the tracker with completion status
5. Log progress and identify next steps

---

## Current State Detection Logic

Before starting each session, check:

### 1. Check if Phase 1 migrations exist
```bash
ls -la /home/mohan/FactoryNXT_PY_v2_Extrusion/migrations/versions/ | grep quality
```

### 2. Check if services were created
```bash
ls -la /home/mohan/FactoryNXT_PY_v2_Extrusion/app/services/*quality*.py 2>/dev/null || echo "No quality services yet"
```

### 3. Check if routes were created
```bash
ls -la /home/mohan/FactoryNXT_PY_v2_Extrusion/app/routes/*quality*.py 2>/dev/null || echo "No quality routes yet"
```

---

## Phase Priority Order

**P0 (Critical):** Session S1-S4 → Database schema + basic services + core dashboards  
**P1 (High):** Session S5-S8 → Scrap reporting, die performance, alarm monitoring, metrics dashboard  
**P2 (Medium):** Session S9-S12 → Parameter traceability, changeover analysis, inspection management, traceability viewer  
**P3+ (Enhancement):** Session S13-S16 → SPC charts, maintenance linkage, foundry/testing checks, inline integration

---

## Session Template

Each session should:
1. **Read tracker:** `/home/mohan/FactoryNXT_PY_v2_Extrusion/.build_plans/session_tracker.md`
2. **Identify current task** based on "Status" field in tracker
3. **Execute work** following the build plan specifications
4. **Update tracker** with completion status and next session goals

---

## Progress Logging Format

After each session, add to `session_tracker.md`:

```markdown
### Session [SN] - [Phase Name]
**Date:** YYYY-MM-DD  
**Status:** COMPLETED/IN PROGRESS/BLOCKED  
**Completed:**
- [x] Task 1
- [x] Task 2
...

**Issues encountered:** (if any)
**Next session focus:** [...]
```

---

## Loop Trigger Commands

### Manual trigger to continue:
```bash
# Run this command each time you want the loop to proceed
/cron-resume quality-feature-implement
```

### Schedule recurring execution:
The loop is configured to run every 30 minutes via cron job.

To check current scheduled jobs:
```bash
# Check active cron jobs (if using system cron)
crontab -l | grep quality

# Or view internal scheduler if available
ls .claude/scheduled_tasks.json
```

---

## Blocker Resolution

If a session is BLOCKED, document the blocker and resolution needed:

```markdown
**Blocker:** [Description of what's preventing progress]
**Resolution required:** [What needs to happen to unblock]
**Impact on timeline:** [How this affects subsequent sessions]
```

---

## Success Criteria per Session

### Phase 1 (Database Schema):
- Migration file created and syntactically valid
- All tables defined with correct column types
- Foreign keys properly specified
- Indexes added for performance-critical columns
- Seed data included for default values

### Phase 2-3 (Services & Routes):
- Service classes follow existing patterns (KPIEngine)
- Flask blueprints use established route conventions
- Templates extend base layout consistently
- Error handling follows project standards

### Phase 4+ (Integration Features):
- PLC integration tested with simulated data first
- All integrations have fallback/error paths documented
- Security considerations addressed for external systems

---

## Documentation Updates Required Per Session

After completing each phase, update:
1. `session_tracker.md` - Mark completion, log issues
2. `quality-buildplan.md` - If any plan adjustments needed
3. `CHANGELOG.md` - Document major changes if applicable
