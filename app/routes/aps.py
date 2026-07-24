"""APS routes

Two blueprints:
  aps          – page views (/aps/cockpit, /aps/scheduler)
                 + scheduler JSON API (/aps/api/*)
  aps_resource – JSON REST API (/aps/resource/mappings, …)

bp is aliased to aps_resource_bp for backwards-compat with __init__.py.
"""
from datetime import datetime, timedelta
import traceback

from flask import Blueprint, jsonify, request, render_template
from app import db
from app.models_aps import (
    MachineResourceMapping,
    WorkOrderResource,
    ApsScheduleVersion,
    ApsScheduleEntry,
)
from app.models import Machine, Die, WorkOrder
from app.services.wo_probability import calculate_wo_probability
from app.services.bom_service import is_press_machine
from app.services.aps_engine import ApsEngine

# ── Page blueprint ────────────────────────────────────────────────────────────
aps_page_bp = Blueprint('aps', __name__, url_prefix='/aps')


# ── Helpers ───────────────────────────────────────────────────────────────────

def _version_horizon(version):
    """Return (horizon_start, horizon_end) datetimes for a version."""
    start = version.created_at or datetime.utcnow()
    days  = version.planning_horizon_days or 7
    return start, start + timedelta(days=days)


def _active_machines():
    """Return active *press* machines, defensively handling the missing
    `is_active` column.

    Scheduling is press-only: the press is the actual bottleneck resource,
    other station types (HLS, Quench, Puller, Stretch, Oven) are downstream
    steps of the same run, not separate schedulable capacity. See
    is_press_machine() in app/services/bom_service.py.

    Falls back (in order):
      1. filter_by(is_active=True)
      2. filter by status in common 'active' values
      3. ALL machines if nothing else works
    Each tier is then filtered down to press machines only.
    """
    try:
        machines = Machine.query.filter_by(is_active=True).all()
        if machines:
            return [m for m in machines if is_press_machine(m)]
    except Exception:
        pass
    try:
        machines = Machine.query.filter(
            Machine.status.in_(["Running", "Available", "Idle", "Active"])
        ).all()
        if machines:
            return [m for m in machines if is_press_machine(m)]
    except Exception:
        pass
    return [m for m in Machine.query.order_by(Machine.name).all() if is_press_machine(m)]


def _safe_entries_for_version(version):
    """Return schedule entries for a version; swallow errors and return []."""
    if not version:
        return []
    try:
        return ApsScheduleEntry.query.filter_by(version_id=version.id).all()
    except Exception:
        return []


def _entry_to_dict(e):
    """Serialise an ApsScheduleEntry to a JSON-safe dict.

    All relationship accesses are null-guarded so that a single entry
    with a missing FK (machine, die, work_order) does not raise an
    AttributeError and crash the entire api_gantt response.
    """
    try:
        wo = e.work_order  # may be None if FK is dangling

        # scheduled_start / scheduled_end should never be None, but guard
        # defensively so strftime doesn't blow up.
        s_start = e.scheduled_start
        s_end   = e.scheduled_end
        if s_start is None or s_end is None:
            # Skip malformed entry gracefully
            return None

        duration_min = int((s_end - s_start).total_seconds() / 60)

        return {
            'id': str(e.id),
            'machine_id': e.machine_id,
            'machine_name': e.machine.name if e.machine else 'Unassigned',
            # WorkOrder has no `work_order_number` — use `order_number`
            # (falling back gracefully via getattr so a missing field never
            # raises AttributeError inside this try block).
            'work_order_number': getattr(wo, 'order_number', None) or getattr(wo, 'work_order_number', None),
            'part_number': wo.part_number if wo else None,
            'product_profile': getattr(wo, 'product_profile', None) if wo else None,
            'customer_name': getattr(wo, 'customer_name', None) if wo else None,
            'customer_order_number': getattr(wo, 'customer_order_number', None) if wo else None,
            'scheduled_start': s_start.strftime('%Y-%m-%dT%H:%M:%S'),
            'scheduled_end':   s_end.strftime('%Y-%m-%dT%H:%M:%S'),
            'duration_min': duration_min,
            'priority': e.priority,
            'status': e.status,
            'constraint_status': e.constraint_status or 'FEASIBLE',
            'constraint_reasons': e.constraint_reasons or [],
            'is_locked': e.is_locked,
            'locked_by': e.locked_by,
            'die_code': e.die.die_code if e.die else None,
            'billet_code': None,
            'setup_duration_min': e.setup_duration_min or 0,
        }
    except Exception:
        # Log the bad entry and return None so callers can skip it.
        # This prevents one corrupt row from making the whole Gantt fail.
        traceback.print_exc()
        return None


def _build_cockpit_context():
    """Build the full context dict required by aps/cockpit.html."""
    version  = ApsEngine._resolve_version(None)
    entries  = _safe_entries_for_version(version)
    machines = _active_machines()

    # ── KPIs ──────────────────────────────────────────────────────────────
    total_load   = sum(int((e.scheduled_end - e.scheduled_start).total_seconds() / 60) for e in entries)
    machine_count = len(machines) or 1
    days          = (version.planning_horizon_days or 7) if version else 7
    capacity_min  = days * 24 * 60 * machine_count
    utilization   = round(total_load / capacity_min * 100, 1) if capacity_min else 0

    feasible   = sum(1 for e in entries if (e.constraint_status or 'FEASIBLE') == 'FEASIBLE')
    infeasible = sum(1 for e in entries if (e.constraint_status or '') == 'INFEASIBLE')
    due_at_risk = infeasible

    # Per-machine load
    load_by_machine = {}
    for e in entries:
        mid = e.machine_id
        load_by_machine[mid] = load_by_machine.get(mid, 0) + int(
            (e.scheduled_end - e.scheduled_start).total_seconds() / 60
        )
    per_machine_stats = []
    for m in machines:
        per_machine_stats.append({'name': m.name, 'min': load_by_machine.get(m.id, 0)})
    max_machine_load = max((s['min'] for s in per_machine_stats), default=0)

    kpis = {
        'entries_total':     len(entries),
        'utilization_pct':   utilization,
        'feasible':          feasible,
        'infeasible':        infeasible,
        'due_at_risk':       due_at_risk,
        'per_machine_stats': per_machine_stats,
        'max_machine_load':  max_machine_load,
    }

    # ── Shortages (collected from INFEASIBLE entries) ──────────────────────
    die_shortages     = []
    machine_issues    = []
    billet_shortages  = []
    other_constraints = []
    at_risk_machines  = []

    for e in entries:
        if (e.constraint_status or 'FEASIBLE') != 'FEASIBLE':
            reasons = e.constraint_reasons or []
            for r in (reasons if isinstance(reasons, list) else [str(reasons)]):
                item = {'reason_code': 'CONSTRAINT', 'message': str(r), 'severity': 'WARNING'}
                if 'die' in str(r).lower():
                    item['reason_code'] = 'DIE_SHORTAGE'
                    die_shortages.append(item)
                elif 'billet' in str(r).lower():
                    item['reason_code'] = 'BILLET_SHORTAGE'
                    billet_shortages.append(item)
                elif 'machine' in str(r).lower() or 'overlap' in str(r).lower():
                    item['reason_code'] = 'MACHINE_CONFLICT'
                    item['severity']    = 'CRITICAL'
                    machine_issues.append(item)
                    machine_name = e.machine.name if e.machine else str(e.machine_id)
                    if machine_name not in at_risk_machines:
                        at_risk_machines.append(machine_name)
                else:
                    other_constraints.append(item)

    shortages = {
        'total':            len(die_shortages) + len(billet_shortages) + len(machine_issues) + len(other_constraints),
        'die_shortages':    die_shortages,
        'billet_shortages': billet_shortages,
        'machine_issues':   machine_issues,
        'other':            other_constraints,
    }

    # ── Unscheduled work orders ────────────────────────────────────────────
    scheduled_wo_ids  = {e.work_order_id for e in entries}
    open_wos          = WorkOrder.query.filter(WorkOrder.status.in_(['RELEASED', 'PLANNED'])).all()
    unscheduled_count = sum(1 for wo in open_wos if wo.id not in scheduled_wo_ids)

    # ── Recent constraint logs (reuse entries with constraint info) ────────
    recent_logs = [
        type('Log', (), {
            'created_at':  e.updated_at if hasattr(e, 'updated_at') and e.updated_at else e.scheduled_start,
            'reason_code': e.constraint_status or 'FEASIBLE',
            'severity':    'CRITICAL' if e.constraint_status == 'INFEASIBLE' else 'INFO',
        })()
        for e in sorted(entries, key=lambda x: x.scheduled_start, reverse=True)
        if (e.constraint_status or 'FEASIBLE') != 'FEASIBLE'
    ][:10]

    return {
        'version':           version,
        'kpis':              kpis,
        'shortages':         shortages,
        'unscheduled_count': unscheduled_count,
        'at_risk_machines':  at_risk_machines,
        'recent_logs':       recent_logs,
    }


# ── Page routes ───────────────────────────────────────────────────────────────

@aps_page_bp.route('/cockpit')
def cockpit():
    """APS cockpit dashboard."""
    ctx = _build_cockpit_context()
    return render_template('aps/cockpit.html', **ctx)


@aps_page_bp.route('/scheduler')
def scheduler():
    """APS Gantt / scheduler view."""
    return render_template('aps/scheduler.html')


@aps_page_bp.route('/wo-probability')
def wo_probability_page():
    """WO On-Time Probability dashboard."""
    return render_template('aps/wo_probability.html')


# ── Scheduler JSON API ────────────────────────────────────────────────────────

@aps_page_bp.route('/api/gantt', methods=['GET'])
def api_gantt():
    """Return current schedule version data for the Gantt chart."""
    try:
        version = ApsEngine._resolve_version(None)
        now     = datetime.utcnow()

        horizon_start, horizon_end = _version_horizon(version)
        machines = _active_machines()
        entries  = _safe_entries_for_version(version)

        entries_by_machine = {}
        for e in entries:
            d = _entry_to_dict(e)
            if d is None:          # skip malformed / serialisation-failed entries
                continue
            mid = str(e.machine_id)
            entries_by_machine.setdefault(mid, []).append(d)

        return jsonify({
            'version': {
                'id':           version.id,
                'name':         version.name,
                'version_type': version.version_type,
            },
            'machines': [
                {'id': m.id, 'name': m.name, 'status': getattr(m, 'status', 'Unknown')}
                for m in machines
            ],
            'entries_by_machine':  entries_by_machine,
            'blocked_by_machine':  {},
            'horizon': {
                'start': horizon_start.strftime('%Y-%m-%dT%H:%M:%S'),
                'end':   horizon_end.strftime('%Y-%m-%dT%H:%M:%S'),
            },
        })
    except Exception as exc:
        traceback.print_exc()
        return jsonify({'error': str(exc)}), 500


@aps_page_bp.route('/api/kpis', methods=['GET'])
def api_kpis():
    """Return high-level KPI metrics for the current schedule."""
    try:
        version = ApsScheduleVersion.query.order_by(ApsScheduleVersion.created_at.desc()).first()
        if not version:
            return jsonify({'utilization_pct': 0, 'total_load_min': 0, 'capacity_min': 0, 'due_at_risk': 0})

        entries       = _safe_entries_for_version(version)
        total_load    = sum(int((e.scheduled_end - e.scheduled_start).total_seconds() / 60) for e in entries)
        machine_count = len(_active_machines()) or 1
        days          = version.planning_horizon_days or 7
        capacity_min  = days * 24 * 60 * machine_count
        utilization   = round(total_load / capacity_min * 100, 1) if capacity_min else 0
        due_at_risk   = sum(1 for e in entries if getattr(e, 'constraint_status', None) == 'INFEASIBLE')

        return jsonify({
            'utilization_pct': utilization,
            'total_load_min':  total_load,
            'capacity_min':    capacity_min,
            'due_at_risk':     due_at_risk,
        })
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


@aps_page_bp.route('/api/auto-schedule', methods=['POST'])
def api_auto_schedule():
    """Run finite-capacity auto-scheduling and create a new schedule version."""
    try:
        open_wos = WorkOrder.query.filter(WorkOrder.status.in_(['RELEASED', 'PLANNED'])).all()
        machines = _active_machines()

        if not machines:
            return jsonify({'ok': False, 'error': 'No active machines configured'}), 400

        version = ApsScheduleVersion(
            name=f'Auto-{datetime.utcnow().strftime("%Y%m%d-%H%M")}',
            version_type='DRAFT',
            planning_horizon_days=7,
        )
        db.session.add(version)
        db.session.flush()

        placed           = 0
        unassigned       = []
        cursor_by_machine = {m.id: datetime.utcnow() for m in machines}

        for wo in open_wos:
            mapping = MachineResourceMapping.query.filter_by(
                part_number=wo.part_number, active=True
            ).first()
            if not mapping:
                # No resource mapping: assign to least-loaded active machine
                # (previously this skipped the WO — that's why nothing got scheduled
                # when MachineResourceMapping table was empty).
                machine = min(machines, key=lambda m: cursor_by_machine.get(m.id, datetime.utcnow()))
                cycle_min = 60       # default 60 min per unit
                setup_min = 15
                qty       = getattr(wo, 'quantity', 1) or 1
                duration_min = setup_min + cycle_min * qty
                start = cursor_by_machine.get(machine.id, datetime.utcnow())
                end   = start + timedelta(minutes=duration_min)
                entry = ApsScheduleEntry(
                    version_id=version.id,
                    work_order_id=wo.id,
                    machine_id=machine.id,
                    scheduled_start=start,
                    scheduled_end=end,
                    status='PLANNED',
                    constraint_status='FEASIBLE',
                    priority=getattr(wo, 'priority', 'medium'),
                    setup_duration_min=setup_min,
                )
                db.session.add(entry)
                cursor_by_machine[machine.id] = end + timedelta(minutes=30)
                placed += 1
                continue

            machine    = next((m for m in machines if m.id == mapping.machine_id), machines[0])
            cycle_min  = int((mapping.cycle_time_sec or 3600) / 60)
            setup_min  = int((mapping.setup_time_sec or 0) / 60)
            changeover_min = int((mapping.changeover_time_sec or 0) / 60)
            qty        = getattr(wo, 'quantity', 1) or 1
            duration_min = setup_min + cycle_min * qty
            start = cursor_by_machine[machine.id]
            end   = start + timedelta(minutes=duration_min)

            entry = ApsScheduleEntry(
                version_id=version.id,
                work_order_id=wo.id,
                machine_id=machine.id,
                scheduled_start=start,
                scheduled_end=end,
                status='PLANNED',
                constraint_status='FEASIBLE',
                priority=getattr(wo, 'priority', 'medium'),
                setup_duration_min=setup_min,
            )
            db.session.add(entry)
            # Use wo.order_number — work_order_number does NOT exist on WorkOrder
            cursor_by_machine[machine.id] = end + timedelta(minutes=changeover_min)
            placed += 1

        db.session.commit()
        return jsonify({'ok': True, 'placed': placed, 'unassigned': unassigned, 'version_id': version.id})
    except Exception as exc:
        db.session.rollback()
        return jsonify({'ok': False, 'error': str(exc)}), 500


@aps_page_bp.route('/api/replan', methods=['POST'])
def api_replan():
    """Replan: preserve locked entries, reschedule the rest."""
    try:
        data            = request.json or {}
        preserve_locked = data.get('preserve_locked', True)

        version = ApsEngine._resolve_version(None)
        locked_entries = []
        if preserve_locked:
            locked_entries = ApsScheduleEntry.query.filter_by(
                version_id=version.id, is_locked=True
            ).all()

        new_version = ApsScheduleVersion(
            name=f'Replan-{datetime.utcnow().strftime("%Y%m%d-%H%M")}',
            version_type='DRAFT',
            planning_horizon_days=7,
        )
        db.session.add(new_version)
        db.session.flush()

        preserved_locked  = 0
        cursor_by_machine = {}

        for le in locked_entries:
            new_entry = ApsScheduleEntry(
                version_id=new_version.id,
                work_order_id=le.work_order_id,
                machine_id=le.machine_id,
                die_id=le.die_id,
                scheduled_start=le.scheduled_start,
                scheduled_end=le.scheduled_end,
                status=le.status,
                constraint_status=le.constraint_status,
                priority=le.priority,
                is_locked=True,
                locked_by=le.locked_by,
                setup_duration_min=le.setup_duration_min,
            )
            db.session.add(new_entry)
            prev = cursor_by_machine.get(le.machine_id)
            if prev is None or le.scheduled_end > prev:
                cursor_by_machine[le.machine_id] = le.scheduled_end
            preserved_locked += 1

        machines = _active_machines()
        for m in machines:
            if m.id not in cursor_by_machine:
                cursor_by_machine[m.id] = datetime.utcnow()

        open_wos      = WorkOrder.query.filter(WorkOrder.status.in_(['RELEASED', 'PLANNED'])).all()
        locked_wo_ids = {le.work_order_id for le in locked_entries}
        placed        = 0

        for wo in open_wos:
            if wo.id in locked_wo_ids:
                continue
            mapping = MachineResourceMapping.query.filter_by(
                part_number=wo.part_number, active=True
            ).first()
            if mapping:
                machine = next((m for m in machines if m.id == mapping.machine_id), machines[0] if machines else None)
                if not machine:
                    continue
                cycle_min    = int((mapping.cycle_time_sec or 3600) / 60)
                setup_min    = int((mapping.setup_time_sec or 0) / 60)
                changeover_min = int((mapping.changeover_time_sec or 0) / 60)
            else:
                # No mapping — assign to least-loaded machine (don't skip the WO)
                machine = min(machines, key=lambda m: cursor_by_machine.get(m.id, datetime.utcnow())) if machines else None
                if not machine:
                    continue
                cycle_min = 60
                setup_min = 15
                changeover_min = 30
            qty          = getattr(wo, 'quantity', 1) or 1
            duration_min = setup_min + cycle_min * qty
            start = cursor_by_machine[machine.id]
            end   = start + timedelta(minutes=duration_min)
            entry = ApsScheduleEntry(
                version_id=new_version.id,
                work_order_id=wo.id,
                machine_id=machine.id,
                scheduled_start=start,
                scheduled_end=end,
                status='PLANNED',
                constraint_status='FEASIBLE',
                priority=getattr(wo, 'priority', 'medium'),
                setup_duration_min=setup_min,
            )
            db.session.add(entry)
            cursor_by_machine[machine.id] = end + timedelta(minutes=changeover_min)
            placed += 1

        db.session.commit()
        return jsonify({'ok': True, 'placed': placed, 'preserved_locked': preserved_locked, 'version_id': new_version.id})
    except Exception as exc:
        db.session.rollback()
        return jsonify({'ok': False, 'error': str(exc)}), 500


@aps_page_bp.route('/api/entry/<entry_id>/move', methods=['POST'])
def api_move_entry(entry_id):
    """Move a schedule entry to a new time slot / machine."""
    entry = ApsScheduleEntry.query.get_or_404(entry_id)
    if entry.is_locked:
        return jsonify({'ok': False, 'error': 'Entry is locked'}), 400

    data = request.json or {}
    try:
        if 'scheduled_start' in data:
            entry.scheduled_start = datetime.strptime(data['scheduled_start'], '%Y-%m-%d %H:%M:%S')
        if 'scheduled_end' in data:
            entry.scheduled_end   = datetime.strptime(data['scheduled_end'],   '%Y-%m-%d %H:%M:%S')
        if 'machine_id' in data:
            entry.machine_id = data['machine_id']
    except ValueError as exc:
        return jsonify({'ok': False, 'error': str(exc)}), 400

    overlapping = ApsScheduleEntry.query.filter(
        ApsScheduleEntry.machine_id   == entry.machine_id,
        ApsScheduleEntry.id           != entry.id,
        ApsScheduleEntry.scheduled_start < entry.scheduled_end,
        ApsScheduleEntry.scheduled_end   > entry.scheduled_start,
        ApsScheduleEntry.version_id   == entry.version_id,
    ).all()
    conflicts = [
        f'Overlaps with WO {o.work_order_id} ({o.scheduled_start}\u2013{o.scheduled_end})'
        for o in overlapping
    ]
    entry.constraint_status  = 'INFEASIBLE' if conflicts else 'FEASIBLE'
    entry.constraint_reasons = conflicts
    db.session.commit()
    return jsonify({'ok': True, 'conflicts': conflicts})


@aps_page_bp.route('/api/entry/<entry_id>/lock', methods=['POST'])
def api_lock_entry(entry_id):
    """Lock or unlock a schedule entry."""
    entry     = ApsScheduleEntry.query.get_or_404(entry_id)
    data      = request.json or {}
    entry.is_locked  = data.get('locked', True)
    entry.locked_by  = data.get('reason', 'Planner') if entry.is_locked else None
    entry.locked_at  = datetime.utcnow() if entry.is_locked else None
    db.session.commit()
    return jsonify({'ok': True, 'is_locked': entry.is_locked})


@aps_page_bp.route('/api/entry/<entry_id>/release', methods=['POST'])
def api_release_entry(entry_id):
    """Release a schedule entry to the shop floor (dispatch)."""
    entry        = ApsScheduleEntry.query.get_or_404(entry_id)
    data         = request.json or {}
    entry.status = data.get('status', 'DISPATCHED')
    db.session.commit()
    return jsonify({'ok': True, 'status': entry.status})


# ── New APS endpoints (schedule score, publish, auto-schedule-v2, unscheduled) ─

@aps_page_bp.route('/api/schedule-score', methods=['GET'])
def api_schedule_score():
    """Calculate a Schedule Score (0-100) for the current version."""
    try:
        version = ApsScheduleVersion.query.order_by(
            ApsScheduleVersion.created_at.desc()
        ).first()
        if not version:
            return jsonify({"score": 0, "components": {}})

        entries = ApsScheduleEntry.query.filter_by(version_id=version.id).all()
        total = len(entries) or 1
        feasible = sum(
            1 for e in entries if (e.constraint_status or "FEASIBLE") == "FEASIBLE"
        )
        total_load = sum(
            int((e.scheduled_end - e.scheduled_start).total_seconds() / 60)
            for e in entries
        )
        # Press-only: capacity is measured against press machines only, since
        # that's the only resource type entries are ever scheduled on.
        machine_count = len(_active_machines()) or 1
        days = version.planning_horizon_days or 7
        capacity_min = days * 24 * 60 * machine_count
        utilization = total_load / capacity_min if capacity_min else 0

        on_time = 0
        for e in entries:
            wo = e.work_order
            if wo and hasattr(wo, "due_date") and wo.due_date and e.scheduled_end:
                due_dt = (
                    datetime.combine(wo.due_date, datetime.max.time())
                    if hasattr(wo.due_date, "year") and not hasattr(wo.due_date, "hour")
                    else wo.due_date
                )
                if e.scheduled_end <= due_dt:
                    on_time += 1
            else:
                on_time += 1

        score = (
            0.40 * (feasible / total)
            + 0.30 * min(utilization / 0.85, 1.0)
            + 0.30 * (on_time / total)
        ) * 100

        return jsonify({
            "score": round(score, 1),
            "components": {
                "feasibility_pct": round((feasible / total) * 100, 1),
                "utilization_pct": round(utilization * 100, 1),
                "on_time_pct": round((on_time / total) * 100, 1),
            },
            "version_id": version.id,
            "version_name": version.name,
        })
    except Exception as exc:
        traceback.print_exc()
        return jsonify({"error": str(exc)}), 500


@aps_page_bp.route('/api/publish', methods=['POST'])
def api_publish():
    """Publish the current DRAFT schedule version to the shop floor."""
    try:
        data = request.json or {}
        version_id = data.get("version_id")

        if version_id:
            version = ApsScheduleVersion.query.get_or_404(version_id)
        else:
            version = ApsScheduleVersion.query.order_by(
                ApsScheduleVersion.created_at.desc()
            ).first()

        if not version:
            return jsonify({"ok": False, "error": "No schedule version found"}), 404

        if version.version_type == "PUBLISHED":
            return jsonify({"ok": False, "error": "Version is already published"}), 400

        version.version_type = "PUBLISHED"

        entries = ApsScheduleEntry.query.filter_by(
            version_id=version.id, status="PLANNED"
        ).all()
        dispatched = 0
        for entry in entries:
            if (entry.constraint_status or "FEASIBLE") == "FEASIBLE":
                entry.status = "DISPATCHED"
                wo = entry.work_order
                if wo and wo.status in ("RELEASED", "PLANNED"):
                    wo.status = "SCHEDULED"
                    wo.scheduled_start = entry.scheduled_start
                    wo.scheduled_end = entry.scheduled_end
                dispatched += 1

        db.session.commit()
        return jsonify({
            "ok": True,
            "version_id": version.id,
            "version_name": version.name,
            "dispatched_entries": dispatched,
        })
    except Exception as exc:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(exc)}), 500


@aps_page_bp.route('/api/auto-schedule-v2', methods=['POST'])
def api_auto_schedule_v2():
    """Run scheduling with algorithm selection (FIFO / DUE_DATE / OEE_OPTIMISED)."""
    try:
        data = request.json or {}
        horizon = int(data.get("horizon_days", 7))
        algorithm = data.get("algorithm", "DUE_DATE").upper()

        open_wos = WorkOrder.query.filter(
            WorkOrder.status.in_(["RELEASED", "PLANNED"])
        ).all()
        # Press-only: see is_press_machine() in app/services/bom_service.py.
        machines = [m for m in Machine.query.filter_by(is_active=True).all() if is_press_machine(m)]

        if not machines:
            return jsonify({"ok": False, "error": "No active press machines configured"}), 400

        if algorithm == "DUE_DATE":
            open_wos = sorted(
                open_wos,
                key=lambda w: (w.due_date or datetime(2099, 12, 31)),
            )
        elif algorithm == "OEE_OPTIMISED":
            from collections import defaultdict
            by_part = defaultdict(list)
            for wo in open_wos:
                by_part[wo.part_number or "UNKNOWN"].append(wo)
            sorted_parts = sorted(
                by_part.keys(),
                key=lambda p: min(
                    (w.due_date or datetime(2099, 12, 31)) for w in by_part[p]
                ),
            )
            open_wos = [wo for p in sorted_parts for wo in by_part[p]]
        # else FIFO: keep original order

        version = ApsScheduleVersion(
            name=f"{algorithm}-{datetime.utcnow().strftime('%Y%m%d-%H%M')}",
            version_type="DRAFT",
            planning_horizon_days=horizon,
        )
        db.session.add(version)
        db.session.flush()

        placed = 0
        unassigned = []
        cursor_by_machine = {m.id: datetime.utcnow() for m in machines}

        for wo in open_wos:
            mapping = MachineResourceMapping.query.filter_by(
                part_number=wo.part_number, active=True
            ).first()

            if mapping:
                machine = next(
                    (m for m in machines if m.id == mapping.machine_id),
                    machines[0],
                )
                cycle_min = int((mapping.cycle_time_sec or 3600) / 60)
                setup_min = int((mapping.setup_time_sec or 0) / 60)
                changeover_min = int((mapping.changeover_time_sec or 0) / 60)
            else:
                machine = min(machines, key=lambda m: cursor_by_machine[m.id])
                cycle_min = 60
                setup_min = 15
                changeover_min = 30

            qty = getattr(wo, "quantity", 1) or 1
            duration_min = setup_min + cycle_min * qty
            start = cursor_by_machine[machine.id]

            horizon_end = datetime.utcnow() + timedelta(days=horizon)
            if start + timedelta(minutes=duration_min) > horizon_end:
                unassigned.append(wo.order_number)
                continue

            end = start + timedelta(minutes=duration_min)
            entry = ApsScheduleEntry(
                version_id=version.id,
                work_order_id=wo.id,
                machine_id=machine.id,
                scheduled_start=start,
                scheduled_end=end,
                status="PLANNED",
                constraint_status="FEASIBLE",
                priority=getattr(wo, "priority", "medium"),
                setup_duration_min=setup_min,
            )
            db.session.add(entry)
            cursor_by_machine[machine.id] = end + timedelta(minutes=changeover_min)
            placed += 1

        db.session.commit()
        return jsonify({
            "ok": True,
            "placed": placed,
            "unassigned": unassigned,
            "version_id": version.id,
            "algorithm": algorithm,
            "horizon_days": horizon,
        })
    except Exception as exc:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(exc)}), 500


@aps_page_bp.route('/api/unscheduled-wos', methods=['GET'])
def api_unscheduled_wos():
    """Return WOs that are RELEASED or PLANNED but NOT in the current schedule."""
    try:
        version = ApsScheduleVersion.query.order_by(
            ApsScheduleVersion.created_at.desc()
        ).first()
        scheduled_wo_ids = set()
        if version:
            entries = ApsScheduleEntry.query.filter_by(version_id=version.id).all()
            scheduled_wo_ids = {e.work_order_id for e in entries}

        open_wos = WorkOrder.query.filter(
            WorkOrder.status.in_(["RELEASED", "PLANNED"])
        ).all()

        result = []
        for wo in open_wos:
            if wo.id not in scheduled_wo_ids:
                result.append({
                    "id": str(wo.id),
                    "work_order_number": wo.order_number,
                    "part_number": wo.part_number,
                    "quantity": getattr(wo, "quantity", 0),
                    "due_date": wo.due_date.strftime("%Y-%m-%d")
                    if wo.due_date else None,
                    "priority": getattr(wo, "priority", "medium"),
                })

        return jsonify({"ok": True, "count": len(result), "work_orders": result})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@aps_page_bp.route('/api/wo-probability', methods=['GET'])
def api_wo_probability():
    """On-time delivery probability for every active (RELEASED/RUNNING) WO."""
    try:
        now = datetime.utcnow()
        work_orders = WorkOrder.query.filter(
            WorkOrder.status.in_(["RELEASED", "RUNNING"])
        ).all()

        results = [calculate_wo_probability(wo, now=now) for wo in work_orders]
        results.sort(key=lambda r: r["probability_pct"])

        for r in results:
            if r["projected_completion"] is not None:
                r["projected_completion"] = r["projected_completion"].strftime("%Y-%m-%dT%H:%M:%S")

        summary = {
            "total": len(results),
            "critical": sum(1 for r in results if r["status"] == "critical"),
            "at_risk": sum(1 for r in results if r["status"] == "at_risk"),
            "on_track": sum(1 for r in results if r["status"] == "on_track"),
            "ahead": sum(1 for r in results if r["status"] == "ahead"),
        }

        return jsonify({
            "as_of": now.strftime("%Y-%m-%dT%H:%M:%S"),
            "work_orders": results,
            "summary": summary,
        })
    except Exception as exc:
        traceback.print_exc()
        return jsonify({"error": str(exc)}), 500


# ── Resource JSON API blueprint ───────────────────────────────────────────────
aps_resource_bp = Blueprint('aps_resource', __name__, url_prefix='/aps/resource')

# Alias for backwards-compat with __init__.py: ``from .routes.aps import bp``
bp = aps_resource_bp


@aps_resource_bp.route('/mappings', methods=['GET'])
def list_mappings():
    mappings = MachineResourceMapping.query.all()
    return jsonify([{
        'id': m.id, 'part_number': m.part_number, 'machine_id': m.machine_id,
        'die_id': m.die_id, 'consumable_ids': m.consumable_ids,
        'cycle_time_sec': m.cycle_time_sec, 'changeover_time_sec': m.changeover_time_sec,
        'setup_time_sec': m.setup_time_sec, 'transport_time_sec': m.transport_time_sec,
    } for m in mappings])


@aps_resource_bp.route('/mappings', methods=['POST'])
def create_mapping():
    data    = request.json
    mapping = MachineResourceMapping(
        part_number=data['part_number'], machine_id=data['machine_id'],
        die_id=data.get('die_id'), consumable_ids=data.get('consumable_ids', []),
        cycle_time_sec=data['cycle_time_sec'],
        changeover_time_sec=data.get('changeover_time_sec', 1800),
        setup_time_sec=data.get('setup_time_sec', 900),
        transport_time_sec=data.get('transport_time_sec', 300),
    )
    db.session.add(mapping)
    db.session.commit()
    return jsonify({'id': mapping.id, 'status': 'created'}), 201


@aps_resource_bp.route('/mappings/<int:mapping_id>', methods=['PUT'])
def update_mapping(mapping_id):
    mapping = MachineResourceMapping.query.get_or_404(mapping_id)
    data    = request.json
    mapping.part_number         = data.get('part_number',         mapping.part_number)
    mapping.machine_id          = data.get('machine_id',          mapping.machine_id)
    mapping.die_id              = data.get('die_id',              mapping.die_id)
    mapping.consumable_ids      = data.get('consumable_ids',      mapping.consumable_ids)
    mapping.cycle_time_sec      = data.get('cycle_time_sec',      mapping.cycle_time_sec)
    mapping.changeover_time_sec = data.get('changeover_time_sec', mapping.changeover_time_sec)
    mapping.setup_time_sec      = data.get('setup_time_sec',      mapping.setup_time_sec)
    mapping.transport_time_sec  = data.get('transport_time_sec',  mapping.transport_time_sec)
    db.session.commit()
    return jsonify({'status': 'updated'})


@aps_resource_bp.route('/mappings/<int:mapping_id>', methods=['DELETE'])
def delete_mapping(mapping_id):
    mapping = MachineResourceMapping.query.get_or_404(mapping_id)
    db.session.delete(mapping)
    db.session.commit()
    return jsonify({'status': 'deleted'})


@aps_resource_bp.route('/mappings/part/<part_number>', methods=['GET'])
def get_mappings_by_part(part_number):
    mappings = MachineResourceMapping.query.filter_by(part_number=part_number).all()
    return jsonify([{
        'id': m.id, 'part_number': m.part_number,
        'machine_id': m.machine_id,
        'machine_name': Machine.query.get(m.machine_id).name if m.machine_id else None,
        'die_id': m.die_id,
        'die_code': Die.query.get(m.die_id).die_code if m.die_id else None,
        'consumable_ids': m.consumable_ids, 'cycle_time_sec': m.cycle_time_sec,
        'changeover_time_sec': m.changeover_time_sec, 'setup_time_sec': m.setup_time_sec,
        'transport_time_sec': m.transport_time_sec,
    } for m in mappings])


@aps_resource_bp.route('/mappings/machine/<int:machine_id>', methods=['GET'])
def get_mappings_by_machine(machine_id):
    mappings = MachineResourceMapping.query.filter_by(machine_id=machine_id).all()
    return jsonify([{
        'id': m.id, 'part_number': m.part_number, 'die_id': m.die_id,
        'consumable_ids': m.consumable_ids, 'cycle_time_sec': m.cycle_time_sec,
    } for m in mappings])
