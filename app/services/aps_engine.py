"""Advanced Planning System (APS) scheduling engine.

Provides finite-capacity scheduling for an aluminum extrusion plant:

  * Work-order generation from customer orders
  * Greedy deterministic scheduler that respects machine / die / billet /
    shift-calendar / maintenance / changeover constraints
  * Replanner that preserves manually-locked entries
  * Availability resolver (machines, dies, billets)
  * KPI + shortage computation

Architecture notes
------------------
* The engine is a drop-in extension of the existing
  ``app.services.scheduler.ScheduleOptimizer``. That class handles the
  simple, stateless CO->ProcessPlan path used by the legacy planning
  screen; this module owns the richer APS path with versioning, locking,
  constraint annotations, and audit events.
* All scheduled times are snapped to 30-minute boundaries (the planner's
  minimum edit slot). Durations are rounded up to the next 30 minutes.
* Determinism: given identical inputs, produce identical output. This
  matters so that replans produce predictable diffs.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, date, time
from typing import Iterable, List, Dict, Optional, Tuple, Any

from sqlalchemy.orm import Session

from .. import db
from ..models import (
    CustomerOrder,
    WorkOrder,
    ProcessPlan,
    Machine,
    Line,
    Die,
    Billet,
    ShiftCalendar,
    DowntimeEvent,
    PmSchedule,
    MaintenanceLog,
)
from ..models_routing import RoutingMaster, RoutingStepV2
from ..models_aps import (
    ApsScheduleVersion,
    ApsScheduleEntry,
    ApsConstraintLog,
    ApsScheduleEvent,
)


# ── Constants ──────────────────────────────────────────────────────────────────
SLOT_MIN = 30  # minimum edit resolution
DEFAULT_SHIFT_START = time(8, 0)    # fallback shift start (08:00)
DEFAULT_SHIFT_END = time(17, 0)     # fallback shift end   (17:00)
WORKING_DAYS = {1, 2, 3, 4, 5}      # Mon=1 .. Fri=5
SETUP_MIN_DEFAULT = 30              # default setup/changeover minutes between jobs
TRANSPORT_MIN_DEFAULT = 15          # default transport between stations on a line
CHANGE_OVER_MIN_DEFAULT = 45        # default changeover minutes between profiles/alloys
CYCLE_MIN_PER_TON = 120.0           # fallback: minutes of press time per ton of billet (when no routing)
MIN_WO_DURATION_MIN = 60            # minimum duration per WO entry (so WOs are visible on Gantt)
MAX_CASCADE_SLOTS_PER_MACHINE = 1   # max entries created per machine per WO (forces cascade to other machines if exceeded)
# Die status codes that qualify as "available for scheduling"
DIE_READY_STATUSES = {"Available", "Nitrided", "TestingPassed", "Inspected"}
# Billet statuses that qualify as "available for allocation"
BILLET_READY_STATUSES = {"AVAILABLE", "INSPECTED"}


# ── Helpers ────────────────────────────────────────────────────────────────────
def _snap30(dt: datetime) -> datetime:
    """Round datetime down to nearest 30-minute boundary."""
    minutes = dt.minute if isinstance(dt, datetime) else 0
    snapped = minutes - (minutes % 30)
    return dt.replace(minute=snapped, second=0, microsecond=0)


def _ceil30(dt: datetime) -> datetime:
    """Round datetime up to next 30-minute boundary (or keep if already aligned)."""
    snapped = _snap30(dt)
    if snapped < dt:
        return snapped + timedelta(minutes=SLOT_MIN)
    return snapped


def _new_id() -> str:
    return str(uuid.uuid4())


def _is_same_day(a: datetime, b: datetime) -> bool:
    return a.date() == b.date()


# ── Calendar helpers ───────────────────────────────────────────────────────────
class _ShiftResolver:
    """Resolves per-day working windows for a plant.

    Reads ShiftCalendar rows if available; otherwise uses the built-in
    default (Mon-Fri, 08:00-17:00).
    """
    def __init__(self, plant_id: Optional[str] = None):
        self.plant_id = plant_id
        self._windows: Dict[int, List[Tuple[time, time]]] = {}
        self._load()

    def _load(self):
        if self.plant_id:
            rows = ShiftCalendar.query.filter_by(
                plant_id=self.plant_id, is_active=True,
            ).all()
        else:
            rows = None
        if rows:
            for r in rows:
                dow = r.day_of_week if r.day_of_week is not None else None
                if dow is None:
                    continue
                self._windows.setdefault(dow, []).append((r.start_time, r.end_time))
            # Normalize
            for dow in list(self._windows.keys()):
                self._windows[dow] = sorted(self._windows[dow], key=lambda t: t[0])

    def windows_for(self, day: date) -> List[Tuple[datetime, datetime]]:
        """Return ordered list of (start, end) datetime windows for a day."""
        dow = day.isoweekday()  # Mon=1 .. Sun=7
        wins = self._windows.get(dow)
        if not wins:
            if dow in WORKING_DAYS:
                return [(
                    datetime.combine(day, DEFAULT_SHIFT_START),
                    datetime.combine(day, DEFAULT_SHIFT_END),
                )]
            return []
        return [
            (datetime.combine(day, st), datetime.combine(day, en))
            for st, en in wins
        ]


# ── Public Engine ──────────────────────────────────────────────────────────────
class ApsEngine:
    """Facade that groups all APS operations.

    Typical workflow:
      1. ``generate_work_orders(customer_order_ids)``  -- COs -> WOs
      2. ``auto_schedule(version_id=None)``            -- schedule all unscheduled WOs
      3. ``replan(version_id, preserve_locked=True)``  -- replan keeping locked entries
    """

    # ── Work-order generation from customer orders ─────────────────────────
    @classmethod
    def generate_work_orders(
        cls,
        customer_order_ids: Iterable[str],
        *,
        created_by: str = "aps",
        version_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create one WorkOrder per selected CustomerOrder.

        Rules:
          * Skip COs already converted (check for WO whose description
            contains the CO order_number, or with matching customer_order
            linkage via our customer_order_id column once WOs carry it).
          * Priority: Urgent if due_date <= +3 days, High if +7, else Medium.
          * Quantity = customer order quantity_tons (rounded up to int tons).
          * scheduled_start / scheduled_end left None — the scheduler fills them.
        """
        created: List[WorkOrder] = []
        errors: List[str] = []
        today = datetime.utcnow().date()

        for co_id in customer_order_ids:
            co = CustomerOrder.query.get(co_id)
            if co is None:
                errors.append(f"CustomerOrder {co_id} not found")
                continue
            if co.status in ("COMPLETED", "CANCELLED"):
                errors.append(f"CO {co.order_number} is {co.status} — skipped")
                continue

            # Check for existing WO linked to this CO. WOs don't have a
            # customer_order_id column, so match by description or the
            # presence of the CO's order_number in the order_number field.
            existing = (
                WorkOrder.query
                .filter(
                    (WorkOrder.order_number.like(f"%{co.order_number}%")) |
                    (WorkOrder.description.ilike(f"%{co.order_number}%"))
                )
                .first()
            )
            if existing:
                errors.append(f"WO {existing.order_number} already linked to CO {co.order_number}")
                continue

            # Priority inference
            due = co.due_date or (today + timedelta(days=14))
            days_out = max(0, (due - today).days)
            if days_out <= 3:
                priority = "Urgent"
            elif days_out <= 7:
                priority = "High"
            else:
                priority = "Medium"

            wo = WorkOrder(
                id=_new_id(),
                order_number=f"WO-APS-{co.order_number.replace('-', '')[:8]}",
                part_number=co.product_profile or "PROF-001",
                description=(
                    f"APS auto-generated from {co.order_number} "
                    f"({co.customer_name}, {co.alloy or 'n/a'}, "
                    f"{co.quantity_tons or 0}t)"
                ),
                quantity=max(1, int(round(co.quantity_tons or 1.0))),
                priority=priority,
                status="DRAFT",
                due_date=datetime.combine(due, datetime.min.time()) if isinstance(due, date) and not isinstance(due, datetime) else due,
            )
            db.session.add(wo)
            created.append(wo)

            # Mark CO in-flight
            if co.status == "DRAFT":
                co.status = "CONFIRMED"

        if created:
            db.session.flush()
            # Write an audit event for each generated WO — but only if we can
            # resolve an APS schedule version to attach it to.
            vid = version_id
            if not vid:
                active = ApsScheduleVersion.query.filter_by(
                    version_type="ACTIVE"
                ).order_by(ApsScheduleVersion.published_at.desc().nullslast()).first()
                vid = active.id if active else None
            if vid:
                for wo in created:
                    db.session.add(ApsScheduleEvent(
                        id=_new_id(),
                        version_id=vid,
                        entry_id=None,
                        event_type="WO_CREATED_FROM_CO",
                        old_values={},
                        new_values={"work_order_id": wo.id, "order_number": wo.order_number},
                        triggered_by=created_by,
                    ))

        return {
            "created": [
                {"id": wo.id, "order_number": wo.order_number, "priority": wo.priority}
                for wo in created
            ],
            "errors": errors,
        }

    # ── Availability resolver ──────────────────────────────────────────────
    @classmethod
    def available_machines(cls, at: datetime) -> List[Machine]:
        """Return machines considered 'available' at the given instant.

        A machine is available when:
          * machine.status in {Available, Running, Idle}
          * no active DowntimeEvent covering `at`
          * no overlapping PmSchedule due in the next few hours (soft check)
        """
        machines = Machine.query.filter(
            Machine.status.in_(["Available", "Running", "Idle", "available"])
        ).all()
        # Exclude machines with an active DowntimeEvent covering `at`
        down_machine_ids = {
            ev.machine_id for ev in
            DowntimeEvent.query.filter(
                DowntimeEvent.started_at <= at,
                (DowntimeEvent.ended_at.is_(None)) | (DowntimeEvent.ended_at >= at),
            ).all()
        }
        # Parse machine_id to int for comparison with Down events (stored as str)
        return [
            m for m in machines
            if str(m.id) not in down_machine_ids and m.id not in down_machine_ids
        ]

    @classmethod
    def available_dies(cls, alloy: Optional[str] = None, profile_code: Optional[str] = None) -> List[Die]:
        q = Die.query.filter(Die.status.in_(list(DIE_READY_STATUSES)))
        if alloy:
            q = q.filter((Die.alloy.is_(None)) | (Die.alloy == alloy))
        if profile_code:
            q = q.filter((Die.profile_code.is_(None)) | (Die.profile_code == profile_code))
        return q.order_by(Die.die_code.asc()).all()

    @classmethod
    def available_billets(cls, alloy: Optional[str] = None) -> List[Billet]:
        q = Billet.query.filter(Billet.status.in_(list(BILLET_READY_STATUSES)))
        if alloy:
            q = q.filter((Billet.alloy.is_(None)) | (Billet.alloy == alloy))
        return q.order_by(Billet.billet_code.asc()).all()

    # ── Maintenance / downtime overlay ─────────────────────────────────────
    @classmethod
    def machine_blocked_windows(
        cls, machine_id: int, horizon_start: datetime, horizon_end: datetime,
    ) -> List[Tuple[datetime, datetime]]:
        """Return a list of (start, end) blocked windows for a machine.

        Sources:
          * DowntimeEvent rows overlapping the horizon (active or scheduled)
          * PmSchedule rows whose due_at falls inside the horizon (treated
            as ~2h maintenance windows)
          * MaintenanceLog rows whose performed_at is recent and still
            implies downtime (duration-based) — less reliable
        """
        blocked: List[Tuple[datetime, datetime]] = []
        # DowntimeEvents
        for ev in DowntimeEvent.query.filter(
            DowntimeEvent.machine_id == str(machine_id),
            DowntimeEvent.started_at <= horizon_end,
            (DowntimeEvent.ended_at.is_(None)) | (DowntimeEvent.ended_at >= horizon_start),
        ).all():
            start = max(ev.started_at, horizon_start)
            end = min(ev.ended_at or horizon_end, horizon_end)
            blocked.append((start, end))
        # PmSchedules — treat as 2h windows starting at due_at
        for pm in PmSchedule.query.filter(
            PmSchedule.machine_id == str(machine_id),
            PmSchedule.status != "Completed",
        ).all():
            if pm.due_at is None:
                continue
            pm_start = datetime.combine(pm.due_at, DEFAULT_SHIFT_START)
            if pm_start < horizon_start:
                continue
            pm_end = pm_start + timedelta(hours=2)
            if pm_end >= horizon_start and pm_start <= horizon_end:
                blocked.append((pm_start, pm_end))
        return sorted(blocked, key=lambda b: b[0])

    # ── Core scheduler ─────────────────────────────────────────────────────
    @classmethod
    def _routing_total_minutes(cls, wo: WorkOrder) -> Optional[float]:
        """Compute total line-cycle-time (minutes) from master routing data.

        Looks up a RELEASED RoutingMaster whose product_id matches the WO's
        part_number. Sums cycle_time of all RoutingStepV2 rows in step_no
        order. Each RoutingStepV2.cycle_time is in SECONDS (schema says so);
        we aggregate into minutes. Returns None if no matching routing is
        found — callers fall back to the default flat constant.
        """
        part = wo.part_number or None
        if not part:
            return None
        routing = (
            RoutingMaster.query
            .filter_by(product_id=part, status="RELEASED")
            .order_by(RoutingMaster.revision.desc())
            .first()
        )
        if routing is None:
            return None
        steps = (
            RoutingStepV2.query
            .filter_by(routing_id=routing.id)
            .order_by(RoutingStepV2.step_no.asc())
            .all()
        )
        if not steps:
            return None
        total_seconds = 0.0
        for step in steps:
            ct = step.cycle_time
            if ct is None:
                continue
            total_seconds += float(ct)
        return total_seconds / 60.0  # seconds → minutes

    @classmethod
    def _duration_for(cls, wo: WorkOrder) -> timedelta:
        """Compute run duration for a WO.

        Priority:
          1. Sum of RoutingStepV2.cycle_time for the WO's part_number
             (master data), multiplied by WO quantity, plus per-step
             changeover + transport overheads. This models a real line
             pass where the WO traverses N stations on its assigned line.
          2. Fallback to flat CYCLE_MIN_PER_TON × quantity when no routing
             is seeded/matched for this part.

        Duration is rounded up to the next 30-minute slot and never less
        than MIN_WO_DURATION_MIN so the Gantt always shows a visible bar.
        """
        qty = max(1, int(wo.quantity or 1))
        routing_min = cls._routing_total_minutes(wo)

        if routing_min and routing_min > 0:
            # Scale by quantity (units), add per-step overheads
            n_steps = cls._count_routing_steps(wo)
            base_min = routing_min * qty
            changeover_total = max(1, n_steps) * CHANGE_OVER_MIN_DEFAULT
            transport_total  = max(0, n_steps - 1) * TRANSPORT_MIN_DEFAULT
            minutes = base_min + changeover_total + transport_total
        else:
            minutes = qty * CYCLE_MIN_PER_TON

        minutes = max(MIN_WO_DURATION_MIN, minutes)
        minutes = ((int(minutes) + SLOT_MIN - 1) // SLOT_MIN) * SLOT_MIN
        return timedelta(minutes=minutes)

    @classmethod
    def _count_routing_steps(cls, wo: WorkOrder) -> int:
        """Count routing steps for the WO's part (helper for overhead calc)."""
        part = wo.part_number or None
        if not part:
            return 0
        routing = (
            RoutingMaster.query
            .filter_by(product_id=part, status="RELEASED")
            .order_by(RoutingMaster.revision.desc())
            .first()
        )
        if routing is None:
            return 0
        return RoutingStepV2.query.filter_by(routing_id=routing.id).count()

    @classmethod
    def _machine_next_free(
        cls, machine_id: int, entries: List[ApsScheduleEntry],
    ) -> datetime:
        """Earliest time a machine is free, based on already-placed entries."""
        last_end = None
        for e in entries:
            if e.machine_id == machine_id and e.scheduled_end:
                if last_end is None or e.scheduled_end > last_end:
                    last_end = e.scheduled_end
        return last_end or datetime.utcnow()

    @classmethod
    def _find_earliest_slot(
        cls,
        wo: WorkOrder,
        machine: Machine,
        machine_entries: List[ApsScheduleEntry],
        shift_resolver: _ShiftResolver,
        blocked_windows: List[Tuple[datetime, datetime]],
        horizon_start: datetime,
        horizon_end: datetime,
    ) -> Optional[datetime]:
        """Find the earliest feasible slot start on the machine for the WO.

        Model: the job runs CONTINUOUSLY from slot_start until
        slot_start + needed, crossing shift boundaries freely. This is
        realistic for aluminum extrusion presses that typically run 24/7
        through off-shifts. Only hard conflicts (maintenance blocks and
        concurrent jobs on the same machine) block placement.

        Constraints:
          * No overlap with existing entries on this machine
          * No overlap with blocked windows (maintenance/downtime)
          * slot_end is within horizon_end
        """
        duration = cls._duration_for(wo)
        setup_min = SETUP_MIN_DEFAULT
        needed = duration + timedelta(minutes=setup_min)
        # Floor cursor at machine's next free time (or horizon start)
        cursor = max(horizon_start, cls._machine_next_free(machine.id, machine_entries))
        cursor = _ceil30(cursor)
        # Hard ceiling: planning horizon (bounded to 60 days by default for safety)
        stop = min(horizon_end, horizon_start + timedelta(days=60))

        # Try placing the run at `cursor`. If it overlaps any constraint,
        # advance cursor to just past the conflict and retry.
        max_iters = 2000
        for _ in range(max_iters):
            if cursor + needed > stop:
                return None
            slot_start = cursor
            slot_end = cursor + needed
            # Check overlap with blocked windows
            next_cursor_after_block = cursor
            for b_start, b_end in blocked_windows:
                if slot_end <= b_start or slot_start >= b_end:
                    continue
                # Overlap — advance past the block
                next_cursor_after_block = max(next_cursor_after_block, _ceil30(b_end))
            if next_cursor_after_block > cursor:
                cursor = next_cursor_after_block
                continue
            # Check overlap with already-placed entries on this machine
            next_cursor_after_entry = cursor
            for e in machine_entries:
                if e.scheduled_start is None or e.scheduled_end is None:
                    continue
                if slot_end <= e.scheduled_start or slot_start >= e.scheduled_end:
                    continue
                # Overlap — advance past this entry
                next_cursor_after_entry = max(next_cursor_after_entry, _ceil30(e.scheduled_end))
            if next_cursor_after_entry > cursor:
                cursor = next_cursor_after_entry
                continue
            return slot_start
        return None

    @classmethod
    def _find_earliest_slot_for_slice(
        cls,
        required_start: datetime,
        hours: float,
        machine: Machine,
        existing_entries: List[ApsScheduleEntry],
        blocked_windows: List[Tuple[datetime, datetime]],
        horizon_start: datetime,
        horizon_end: datetime,
    ) -> Optional[datetime]:
        """Find earliest slot >= required_start on the machine for a specific slice duration.

        Similar to _find_earliest_slot but starts from a specific time.
        """
        needed = timedelta(hours=hours)
        cursor = max(horizon_start, required_start)
        cursor = _ceil30(cursor)
        stop = min(horizon_end, horizon_start + timedelta(days=60))

        # Get existing entries on this machine
        machine_entries = [e for e in existing_entries if e.machine_id == machine.id]

        for _ in range(2000):
            if cursor + needed > stop:
                return None
            slot_start = cursor
            slot_end = cursor + needed

            # Check overlap with blocked windows
            next_cursor_after_block = cursor
            for b_start, b_end in blocked_windows:
                if not (slot_end <= b_start or slot_start >= b_end):
                    next_cursor_after_block = max(next_cursor_after_block, _ceil30(b_end))
            if next_cursor_after_block > cursor:
                cursor = next_cursor_after_block
                continue

            # Check overlap with existing entries
            next_cursor_after_entry = cursor
            for e in machine_entries:
                if e.scheduled_start is None or e.scheduled_end is None:
                    continue
                if not (slot_end <= e.scheduled_start or slot_start >= e.scheduled_end):
                    next_cursor_after_entry = max(next_cursor_after_entry, _ceil30(e.scheduled_end))
            if next_cursor_after_entry > cursor:
                cursor = next_cursor_after_entry
                continue

            return slot_start

        return None

    @classmethod
    def auto_schedule(
        cls,
        *,
        version_id: Optional[str] = None,
        horizon_days: int = 14,
        planned_by: str = "aps",
        preserve_locked: bool = True,
    ) -> Dict[str, Any]:
        """Schedule all unscheduled / non-locked work orders into the APS.

        Steps:
          1. Get or create an ACTIVE schedule version
          2. Keep locked entries in place (preserve_locked=True)
          3. Remove unlocked PLANNED entries and replace them
          4. For each WO not yet scheduled, find the first feasible slot
          5. Write ApsScheduleEntry + ApsConstraintLog + ApsScheduleEvent rows
        """
        version = cls._resolve_version(version_id)

        # Existing entries
        existing = ApsScheduleEntry.query.filter_by(version_id=version.id).all()
        existing_by_wo = {e.work_order_id: e for e in existing if e.work_order_id}

        # Locked entries: must not be moved or replaced
        locked_entries = {e.id: e for e in existing if e.is_locked}
        # Build a "keep" list: locked entries stay, everything else gets replaced
        keep_from_existing: List[ApsScheduleEntry] = []
        remove_from_existing: List[ApsScheduleEntry] = []
        for e in existing:
            if e.is_locked and preserve_locked:
                keep_from_existing.append(e)
            elif e.work_order_id is None:
                # Synthetic entry (maintenance placeholder), keep it
                keep_from_existing.append(e)
            else:
                remove_from_existing.append(e)

        # Remove unlocked entries so the scheduler can replace them
        for e in remove_from_existing:
            db.session.delete(e)
        db.session.flush()

        placed_entries = list(keep_from_existing)

        # Horizon
        horizon_start = _snap30(datetime.utcnow())
        horizon_end = horizon_start + timedelta(days=horizon_days)

        shift_resolver = _ShiftResolver(plant_id=None)

        # WOs that need scheduling: DRAFT or RELEASED, with scheduled_start=None
        # or whose existing APS entry was removed (not locked).
        candidate_wos = (
            WorkOrder.query
            .filter(WorkOrder.status.in_(["DRAFT", "RELEASED"]))
            .order_by(WorkOrder.due_date.asc().nullslast(), WorkOrder.priority.asc())
            .all()
        )
        # Filter out WOs already locked-placed
        placed_wo_ids = {e.work_order_id for e in placed_entries if e.work_order_id}
        to_schedule = [wo for wo in candidate_wos if wo.id not in placed_wo_ids]

        # Pre-fetch availability snapshots
        machines = Machine.query.order_by(Machine.name.asc()).all()
        lines = Line.query.all()
        all_dies = {d.id: d for d in Die.query.all()}
        all_billets = {b.id: b for b in Billet.query.all()}

        # Group machines by line for line-wise scheduling
        machines_by_line: Dict[int, List[Machine]] = {}
        for machine in machines:
            if machine.line_id not in machines_by_line:
                machines_by_line[machine.line_id] = []
            machines_by_line[machine.line_id].append(machine)

        created_entries: List[ApsScheduleEntry] = []
        constraint_logs: List[ApsConstraintLog] = []
        unassigned: List[Dict] = []

        # Track die assignments during the horizon (by WO placement order)
        assigned_dies: Dict[str, datetime] = {}  # die_id -> free_after timestamp
        assigned_billets: Dict[str, float] = {}  # billet_id -> allocated tons (we don't track per-billet tons, just a flag)

        for wo in to_schedule:
            reason_codes: List[str] = []
            # Parse alloy / profile hints from description
            alloy = cls._extract_alloy_from_description(wo.description)
            profile = wo.part_number or None

            # Determine candidate machines (any machine that's not Down/Maintenance)
            candidate_machines = [
                m for m in machines
                if m.status not in ("Down", "Maintenance")
            ]
            if not candidate_machines:
                reason_codes.append("NO_MACHINE_CAPACITY")
                cls._log_constraint(
                    version.id, wo.id, None,
                    reason_code="NO_MACHINE_CAPACITY",
                    message="No machines available; all in Down/Maintenance state.",
                    severity="CRITICAL",
                    logs=constraint_logs,
                )
                unassigned.append({"work_order": wo.order_number, "reasons": reason_codes})
                continue

            # Sort machines by line (to keep cascade within a line if possible)
            machines_sorted = sorted(
                candidate_machines,
                key=lambda m: (m.line_id, m.name)
            )

            # Cascade scheduling: split the work across machines
            # First, find the first available slot and machine
            best_machine = None
            best_start = None

            for m in machines_sorted:
                blocked = cls.machine_blocked_windows(m.id, horizon_start, horizon_end)
                slot_start = cls._find_earliest_slot(
                    wo, m, placed_entries + created_entries,
                    shift_resolver, blocked, horizon_start, horizon_end,
                )
                if slot_start is not None:
                    best_start = slot_start
                    best_machine = m
                    break

            if best_machine is None or best_start is None:
                reason_codes.append("NO_CAPACITY_IN_HORIZON")
                cls._log_constraint(
                    version.id, wo.id, None,
                    reason_code="NO_CAPACITY_IN_HORIZON",
                    message=(
                        f"WO {wo.order_number}: no feasible slot on any machine "
                        f"within {horizon_days}-day horizon."
                    ),
                    severity="WARNING",
                    logs=constraint_logs,
                )
                unassigned.append({"work_order": wo.order_number, "reasons": reason_codes})
                continue

            # Die assignment: look for a die matching alloy (best-effort)
            die_to_assign = cls._pick_die_for(alloy, profile, best_start, assigned_dies, all_dies)
            billet_to_assign = None
            if die_to_assign is None:
                reason_codes.append("DIE_NOT_AVAILABLE")
                cls._log_constraint(
                    version.id, wo.id, None,
                    reason_code="DIE_NOT_AVAILABLE",
                    message=(
                        f"WO {wo.order_number}: no matching die available for "
                        f"alloy={alloy or 'any'} profile={profile or 'any'}."
                    ),
                    severity="WARNING",
                    constraint_status="INFEASIBLE",
                    logs=constraint_logs,
                )

            # Billet assignment (informational)
            billet_to_assign = cls._pick_billet_for(alloy, assigned_billets, all_billets)
            if billet_to_assign is None:
                reason_codes.append("BILLET_SHORTAGE")
                cls._log_constraint(
                    version.id, wo.id, None,
                    reason_code="BILLET_SHORTAGE",
                    message=(
                        f"WO {wo.order_number}: no billet with alloy={alloy or 'any'} in stock."
                    ),
                    severity="WARNING",
                    constraint_status="INFEASIBLE",
                    logs=constraint_logs,
                )

            constraint_status = "FEASIBLE" if not reason_codes else (
                "INFEASIBLE" if any(r in reason_codes for r in (
                    "NO_CAPACITY_IN_HORIZON", "DIE_NOT_AVAILABLE",
                    "BILLET_SHORTAGE", "NO_MACHINE_CAPACITY",
                )) else "WARNING"
            )

            # Calculate total duration and split into cascade chunks
            # Each chunk is one work day (8 hours), cascaded across machines
            duration = cls._duration_for(wo)
            total_hours = duration.total_seconds() / 3600
            chunk_hours = 8.0  # one work day per entry
            num_chunks = max(1, int(total_hours / chunk_hours))

            # Create entries for each chunk, cascading across DISTINCT machines
            current_start = best_start
            machine_index = machines_sorted.index(best_machine)
            slice_count = 0
            # Track machines already used by THIS work order — each chunk MUST
            # land on a different machine. This fixes the "2 WOs same machine"
            # problem when the cascade wraps around after other machines clear.
            used_machine_ids: set = set()

            for chunk_idx in range(num_chunks):
                # Find available machine starting from current position
                # Skip any machine already used by this WO
                placed_this_chunk = False
                for attempt in range(len(machines_sorted)):
                    m_idx = (machine_index + attempt) % len(machines_sorted)
                    m = machines_sorted[m_idx]

                    # ENFORCE: never reuse a machine within the same WO's cascade
                    if m.id in used_machine_ids:
                        continue

                    blocked = cls.machine_blocked_windows(m.id, horizon_start, horizon_end)
                    slot_start = cls._find_earliest_slot_for_slice(
                        current_start, chunk_hours, m, placed_entries + created_entries,
                        blocked, horizon_start, horizon_end,
                    )

                    if slot_start is not None:
                        slice_end = slot_start + timedelta(hours=chunk_hours)
                        entry = ApsScheduleEntry(
                            id=_new_id(),
                            version_id=version.id,
                            work_order_id=wo.id,
                            machine_id=m.id,
                            die_id=die_to_assign.id if die_to_assign else None,
                            billet_id=billet_to_assign.id if billet_to_assign else None,
                            scheduled_start=slot_start,
                            scheduled_end=slice_end,
                            sequence_order=len(placed_entries) + len(created_entries) + 1,
                            is_locked=False,
                            status="PLANNED",
                            constraint_status=constraint_status,
                            constraint_reasons=list(reason_codes),
                            setup_duration_min=float(SETUP_MIN_DEFAULT) if chunk_idx == 0 else 0.0,
                            priority=wo.priority or "Medium",
                            notes=f"Slice {chunk_idx + 1}/{num_chunks} (machine {m.id}) by {planned_by}",
                        )
                        db.session.add(entry)
                        created_entries.append(entry)
                        used_machine_ids.add(m.id)
                        current_start = slice_end  # next chunk starts after this one
                        machine_index = m_idx + 1  # advance past this machine for next chunk
                        slice_count += 1
                        placed_this_chunk = True
                        break
                if not placed_this_chunk:
                    # Could not place this slice on any unused machine, stop cascading
                    reason_codes.append("PARTIAL_CASCADE")
                    cls._log_constraint(
                        version.id, wo.id, None,
                        reason_code="PARTIAL_CASCADE",
                        message=(
                            f"WO {wo.order_number}: only {slice_count}/{num_chunks} "
                            f"slices could be scheduled (no more distinct machines available in horizon)."
                        ),
                        severity="WARNING",
                        logs=constraint_logs,
                    )
                    break

                # Break early if we've placed all chunks
                if current_start >= horizon_end:
                    break

            # If num_chunks > len(machines_sorted), we're capped at distinct machines
            if num_chunks > len(machines_sorted) and slice_count < num_chunks:
                cls._log_constraint(
                    version.id, wo.id, None,
                    reason_code="MACHINE_POOL_EXHAUSTED",
                    message=(
                        f"WO {wo.order_number}: requested {num_chunks} chunks but "
                        f"only {len(machines_sorted)} machines available; scheduled {slice_count} on distinct machines."
                    ),
                    severity="WARNING",
                    logs=constraint_logs,
                )

            # mark die as occupied for all placed slices
            if die_to_assign and slice_count > 0:
                final_entry = created_entries[-1]
                assigned_dies[die_to_assign.id] = max(
                    assigned_dies.get(die_to_assign.id, best_start),
                    final_entry.scheduled_end,
                )
            if billet_to_assign:
                assigned_billets[billet_to_assign.id] = assigned_billets.get(
                    billet_to_assign.id, 0.0,
                ) + max(1.0, float(wo.quantity or 1.0))

            # If due date is at risk, log a warning
            if wo.due_date and slice_count > 0:
                last_entry = created_entries[-1]
                if last_entry.scheduled_end > wo.due_date:
                    cls._log_constraint(
                        version.id, wo.id, last_entry.id,
                        reason_code="DUE_DATE_AT_RISK",
                        message=(
                            f"WO {wo.order_number}: scheduled end "
                            f"{last_entry.scheduled_end:%Y-%m-%d} exceeds due date "
                            f"{wo.due_date:%Y-%m-%d}."
                        ),
                        severity="WARNING",
                        logs=constraint_logs,
                    )

            # Audit event
            db.session.add(ApsScheduleEvent(
                id=_new_id(),
                version_id=version.id,
                entry_id=entry.id,
                event_type="AUTO_SCHEDULED",
                old_values={},
                new_values={
                    "machine_id": entry.machine_id,
                    "scheduled_start": entry.scheduled_start.isoformat(),
                    "scheduled_end": entry.scheduled_end.isoformat(),
                    "constraint_status": entry.constraint_status,
                },
                triggered_by=planned_by,
            ))

        # Persist constraint logs
        for log in constraint_logs:
            db.session.add(log)

        # Update the version's timestamp
        version.updated_at = datetime.utcnow()
        db.session.commit()

        return {
            "version_id": version.id,
            "version_name": version.name,
            "placed": len(created_entries),
            "preserved_locked": len(keep_from_existing),
            "removed_unlocked": len(remove_from_existing),
            "unassigned": unassigned,
            "constraint_logs": len(constraint_logs),
        }

    # ── Replanner ──────────────────────────────────────────────────────────
    @classmethod
    def replan(
        cls,
        version_id: Optional[str],
        *,
        preserve_locked: bool = True,
        replanned_by: str = "aps-replan",
        horizon_days: int = 14,
    ) -> Dict[str, Any]:
        """Replan an existing schedule version.

        By default this is equivalent to auto_schedule(preserve_locked=True)
        on the active version — locked entries are kept in place, everything
        else rescheduled.
        """
        result = cls.auto_schedule(
            version_id=version_id,
            horizon_days=horizon_days,
            planned_by=replanned_by,
            preserve_locked=preserve_locked,
        )
        # Add a replan event marker for the UI to show
        version = cls._resolve_version(version_id)
        db.session.add(ApsScheduleEvent(
            id=_new_id(),
            version_id=version.id,
            entry_id=None,
            event_type="REPLAN",
            old_values={},
            new_values={
                "placed": result["placed"],
                "preserved_locked": result["preserved_locked"],
            },
            triggered_by=replanned_by,
        ))
        db.session.commit()
        return result

    # ── Manual override (move / reassign) ──────────────────────────────────
    @classmethod
    def move_entry(
        cls,
        entry_id: str,
        *,
        new_start: Optional[datetime],
        new_end: Optional[datetime],
        new_machine_id: Optional[int],
        triggered_by: str = "planner",
    ) -> Dict[str, Any]:
        """Manually move or reassign an APS entry.

        Returns the updated entry plus conflict warnings (e.g. overlap with
        existing entries, overlap with maintenance, constraint violations).
        """
        entry = ApsScheduleEntry.query.get_or_404(entry_id)
        old = {
            "machine_id": entry.machine_id,
            "scheduled_start": entry.scheduled_start.isoformat() if entry.scheduled_start else None,
            "scheduled_end": entry.scheduled_end.isoformat() if entry.scheduled_end else None,
        }
        conflicts: List[str] = []

        if new_start is not None:
            new_start = _snap30(new_start)
        if new_end is not None:
            new_end = _ceil30(new_end)

        # Enforce minimum duration
        if new_start is not None and new_end is not None:
            if new_end <= new_start:
                return {"error": "scheduled_end must be after scheduled_start", "conflicts": []}
            if (new_end - new_start).total_seconds() < SLOT_MIN * 60:
                new_end = new_start + timedelta(minutes=SLOT_MIN)

        new_machine_id = new_machine_id if new_machine_id is not None else entry.machine_id
        new_start = new_start if new_start is not None else entry.scheduled_start
        new_end = new_end if new_end is not None else entry.scheduled_end

        # Conflict checks
        horizon_start = new_start - timedelta(hours=1)
        horizon_end = new_end + timedelta(hours=1)
        # Overlap with other entries on the target machine
        overlapping = ApsScheduleEntry.query.filter(
            ApsScheduleEntry.version_id == entry.version_id,
            ApsScheduleEntry.machine_id == new_machine_id,
            ApsScheduleEntry.id != entry.id,
            ApsScheduleEntry.scheduled_start < new_end,
            ApsScheduleEntry.scheduled_end > new_start,
        ).all()
        if overlapping:
            conflicts.append(
                f"Overlaps with {len(overlapping)} other entry/entries on target machine"
            )

        # Overlap with maintenance/downtime blocks
        blocked = cls.machine_blocked_windows(
            new_machine_id, horizon_start, horizon_end,
        )
        for b_start, b_end in blocked:
            if not (new_end <= b_start or new_start >= b_end):
                conflicts.append(
                    f"Overlaps with maintenance/downtime window "
                    f"{b_start:%Y-%m-%d %H:%M}-{b_end:%H:%M} on target machine"
                )
                break

        # Write changes
        entry.machine_id = new_machine_id
        entry.scheduled_start = new_start
        entry.scheduled_end = new_end
        entry.updated_at = datetime.utcnow()
        # A manual override that changes the schedule without preserving is
        # treated as a manual override; planner may lock separately.
        db.session.add(ApsScheduleEvent(
            id=_new_id(),
            version_id=entry.version_id,
            entry_id=entry.id,
            event_type="MANUAL_OVERRIDE",
            old_values=old,
            new_values={
                "machine_id": new_machine_id,
                "scheduled_start": new_start.isoformat() if new_start else None,
                "scheduled_end": new_end.isoformat() if new_end else None,
                "conflicts": conflicts,
            },
            triggered_by=triggered_by,
        ))
        db.session.commit()
        return {
            "ok": True,
            "id": entry.id,
            "entry": entry.to_dict(rich=True),
            "conflicts": conflicts,
        }

    @classmethod
    def lock_entry(
        cls, entry_id: str, *, locked: bool = True,
        reason: Optional[str] = None, locked_by: str = "planner",
    ) -> ApsScheduleEntry:
        entry = ApsScheduleEntry.query.get_or_404(entry_id)
        old_locked = bool(entry.is_locked)
        entry.is_locked = locked
        entry.locked_by = locked_by if locked else None
        entry.locked_at = datetime.utcnow() if locked else None
        entry.lock_reason = reason if locked else None
        db.session.add(ApsScheduleEvent(
            id=_new_id(),
            version_id=entry.version_id,
            entry_id=entry.id,
            event_type="LOCKED" if locked else "UNLOCKED",
            old_values={"is_locked": old_locked},
            new_values={
                "is_locked": locked,
                "reason": reason,
                "locked_by": locked_by,
            },
            triggered_by=locked_by,
        ))
        db.session.commit()
        return entry

    # ── KPIs + summary ─────────────────────────────────────────────────────
    @classmethod
    def compute_kpis(cls, version_id: Optional[str] = None) -> Dict[str, Any]:
        version = cls._resolve_version(version_id)
        entries = ApsScheduleEntry.query.filter_by(version_id=version.id).all()
        machines = {m.id: m.name for m in Machine.query.all()}
        machine_load: Dict[int, float] = {}
        total_load_min = 0.0
        feasible = 0
        infeasible = 0
        warnings = 0
        due_at_risk = 0
        for e in entries:
            dur = e.duration_min
            machine_load[e.machine_id] = machine_load.get(e.machine_id, 0.0) + dur
            total_load_min += dur
            if e.constraint_status == "FEASIBLE":
                feasible += 1
            elif e.constraint_status == "INFEASIBLE":
                infeasible += 1
            else:
                warnings += 1
            if e.work_order and e.work_order.due_date and e.scheduled_end and e.scheduled_end > e.work_order.due_date:
                due_at_risk += 1
        total_machines = len(machines)
        horizon_hours = version.planning_horizon_days * 24
        capacity_min = total_machines * horizon_hours * 60
        utilization_pct = (total_load_min / capacity_min * 100) if capacity_min > 0 else 0.0
        # Compute per-machine stats as a list of tuples sorted by name —
        # this sidesteps Jinja dict-ordering quirks and keeps template math safe.
        per_machine_stats = [
            {
                "name": machines.get(mid, f"machine-{mid}"),
                "min": round(v, 1),
            }
            for mid, v in sorted(machine_load.items(), key=lambda kv: machines.get(kv[0], str(kv[0])))
        ]
        max_machine_load = max((s["min"] for s in per_machine_stats), default=0.0)

        return {
            "version_id": version.id,
            "version_name": version.name,
            "entries_total": len(entries),
            "feasible": feasible,
            "infeasible": infeasible,
            "warnings": warnings,
            "due_at_risk": due_at_risk,
            "total_load_min": round(total_load_min, 1),
            "capacity_min": round(capacity_min, 1),
            "utilization_pct": round(utilization_pct, 2),
            "per_machine_load_min": {
                machines.get(mid, f"machine-{mid}"): round(v, 1)
                for mid, v in machine_load.items()
            },
            "per_machine_stats": per_machine_stats,
            "max_machine_load": max_machine_load,
        }

    @classmethod
    def compute_shortages(cls, version_id: Optional[str] = None) -> Dict[str, Any]:
        version = cls._resolve_version(version_id)
        logs = ApsConstraintLog.query.filter_by(version_id=version.id).all()
        die_shortages = [l.to_dict() for l in logs if l.reason_code in ("DIE_NOT_AVAILABLE", "PROFILE_MISMATCH")]
        billet_shortages = [l.to_dict() for l in logs if l.reason_code in ("BILLET_SHORTAGE", "ALLOY_MISMATCH")]
        machine_issues = [l.to_dict() for l in logs if l.reason_code in ("MACHINE_DOWN", "MACHINE_MAINTENANCE", "NO_MACHINE_CAPACITY", "NO_CAPACITY_IN_HORIZON")]
        other = [l.to_dict() for l in logs if l.reason_code not in {
            "DIE_NOT_AVAILABLE", "PROFILE_MISMATCH", "BILLET_SHORTAGE",
            "ALLOY_MISMATCH", "MACHINE_DOWN", "MACHINE_MAINTENANCE",
            "NO_MACHINE_CAPACITY", "NO_CAPACITY_IN_HORIZON",
        }]
        return {
            "die_shortages": die_shortages,
            "billet_shortages": billet_shortages,
            "machine_issues": machine_issues,
            "other": other,
            "total": len(logs),
        }

    # ── Gantt data ─────────────────────────────────────────────────────────
    @classmethod
    def gantt_data(
        cls, version_id: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        version = cls._resolve_version(version_id)
        q = ApsScheduleEntry.query.filter_by(version_id=version.id)
        if from_date:
            q = q.filter(ApsScheduleEntry.scheduled_end > from_date)
        if to_date:
            q = q.filter(ApsScheduleEntry.scheduled_start < to_date)
        entries = q.order_by(ApsScheduleEntry.scheduled_start.asc()).all()

        # Group by machine for swimlane view
        machines = Machine.query.order_by(Machine.name.asc()).all()
        lanes: Dict[int, List[Dict]] = {m.id: [] for m in machines}
        for e in entries:
            lane = lanes.setdefault(e.machine_id or 0, [])
            lane.append(e.to_dict(rich=True))

        # Compute maintenance/downtime blocks per machine (for overlay)
        horizon_start = from_date or datetime.utcnow()
        horizon_end = to_date or (horizon_start + timedelta(days=version.planning_horizon_days))
        blocked_by_machine: Dict[int, List[Dict]] = {}
        for m in machines:
            blocks = cls.machine_blocked_windows(m.id, horizon_start, horizon_end)
            blocked_by_machine[m.id] = [
                {"start": s.isoformat(), "end": e.isoformat()} for s, e in blocks
            ]

        return {
            "version": {
                "id": version.id,
                "name": version.name,
                "version_type": version.version_type,
                "horizon_days": version.planning_horizon_days,
                "updated_at": version.updated_at.isoformat() if version.updated_at else None,
            },
            "machines": [
                {"id": m.id, "name": m.name, "status": m.status, "line_id": m.line_id}
                for m in machines
            ],
            "entries_by_machine": lanes,
            "blocked_by_machine": blocked_by_machine,
            "horizon": {
                "start": horizon_start.isoformat(),
                "end": horizon_end.isoformat(),
            },
        }

    # ── internal helpers ───────────────────────────────────────────────────
    @classmethod
    def _resolve_version(cls, version_id: Optional[str]) -> ApsScheduleVersion:
        if version_id:
            v = ApsScheduleVersion.query.get(version_id)
            if v:
                return v
        v = ApsScheduleVersion.query.filter_by(version_type="ACTIVE").order_by(
            ApsScheduleVersion.published_at.desc().nullslast()
        ).first()
        if v:
            return v
        # Create a default active version if none exists
        v = ApsScheduleVersion(
            id=_new_id(),
            name="Active Schedule",
            version_type="ACTIVE",
            planning_horizon_days=14,
            published_at=datetime.utcnow(),
            created_by="system",
        )
        db.session.add(v)
        db.session.flush()
        return v

    @classmethod
    def _extract_alloy_from_description(cls, description: Optional[str]) -> Optional[str]:
        if not description:
            return None
        description = str(description)
        for alloy in ("6061-T6", "6063-T5", "6082-T6", "7075-T6",
                      "6061", "6063", "6082", "7075"):
            if alloy in description:
                return alloy.split("-")[0]
        return None

    @classmethod
    def _pick_die_for(
        cls, alloy: Optional[str], profile: Optional[str],
        at: datetime,
        already_assigned: Dict[str, datetime],
        die_universe: Dict[str, Die],
    ) -> Optional[Die]:
        candidates = [
            d for d in die_universe.values()
            if d.status in DIE_READY_STATUSES
            and (not alloy or d.alloy is None or d.alloy == alloy)
            and (not profile or d.profile_code is None or d.profile_code == profile)
        ]
        # Pick the first die that is either free now or the earliest-free
        candidates.sort(
            key=lambda d: already_assigned.get(d.id, datetime.min)
        )
        return candidates[0] if candidates else None

    @classmethod
    def _pick_billet_for(
        cls, alloy: Optional[str],
        already_allocated: Dict[str, float],
        billet_universe: Dict[str, Billet],
    ) -> Optional[Billet]:
        candidates = [
            b for b in billet_universe.values()
            if b.status in BILLET_READY_STATUSES
            and (not alloy or b.alloy is None or b.alloy == alloy)
        ]
        if not candidates:
            return None
        return candidates[0]

    @classmethod
    def _log_constraint(
        cls, version_id, work_order_id, entry_id,
        *, reason_code, message, severity,
        constraint_status: Optional[str] = None,
        logs: List[ApsConstraintLog],
    ):
        log = ApsConstraintLog(
            id=_new_id(),
            version_id=version_id,
            work_order_id=work_order_id,
            entry_id=entry_id,
            reason_code=reason_code,
            message=message,
            severity=severity,
        )
        logs.append(log)


# Backward-compatible alias
ApsScheduler = ApsEngine
