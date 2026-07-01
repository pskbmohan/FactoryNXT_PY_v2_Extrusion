"""APS routes

Two blueprints:
  aps          – page views (/aps/cockpit, /aps/scheduler)
                 + scheduler JSON API (/aps/api/*)
  aps_resource – JSON REST API (/aps/resource/mappings, …)

bp is aliased to aps_resource_bp for backwards-compat with __init__.py.
"""
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request, render_template
from app import db
from app.models_aps import (
    MachineResourceMapping,
    WorkOrderResource,
    ApsScheduleVersion,
    ApsScheduleEntry,
)
from app.models import Machine, Die, WorkOrder

# ── Page blueprint ────────────────────────────────────────────────────────────
aps_page_bp = Blueprint('aps', __name__, url_prefix='/aps')


# ── Helpers ───────────────────────────────────────────────────────────────────

def _version_horizon(version):
    """Return (horizon_start, horizon_end) datetimes for a version."""
    start = version.created_at or datetime.utcnow()
    days  = version.planning_horizon_days or 7
    return start, start + timedelta(days=days)


def _entry_to_dict(e):
    """Serialise an ApsScheduleEntry to a JSON-safe dict."""
    wo = e.work_order
    return {
        'id': str(e.id),
        'machine_id': e.machine_id,
        'machine_name': e.machine.name if e.machine else 'Unassigned',
        'work_order_number': wo.work_order_number if wo else None,
        'part_number': wo.part_number if wo else None,
        'product_profile': getattr(wo, 'product_profile', None) if wo else None,
        'customer_name': getattr(wo, 'customer_name', None) if wo else None,
        'customer_order_number': getattr(wo, 'customer_order_number', None) if wo else None,
        'scheduled_start': e.scheduled_start.strftime('%Y-%m-%dT%H:%M:%S'),
        'scheduled_end':   e.scheduled_end.strftime('%Y-%m-%dT%H:%M:%S'),
        'duration_min': int((e.scheduled_end - e.scheduled_start).total_seconds() / 60),
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


def _build_cockpit_context():
    """Build the full context dict required by aps/cockpit.html."""
    version  = ApsScheduleVersion.query.order_by(ApsScheduleVersion.created_at.desc()).first()
    entries  = ApsScheduleEntry.query.filter_by(version_id=version.id).all() if version else []
    machines = Machine.query.filter_by(is_active=True).all()

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


# ── Scheduler JSON API ────────────────────────────────────────────────────────

@aps_page_bp.route('/api/gantt', methods=['GET'])
def api_gantt():
    """Return current schedule version data for the Gantt chart."""
    try:
        version = ApsScheduleVersion.query.order_by(ApsScheduleVersion.created_at.desc()).first()
        now     = datetime.utcnow()

        if not version:
            return jsonify({
                'version':           None,
                'machines':          [],
                'entries_by_machine': {},
                'blocked_by_machine': {},
                'horizon': {
                    'start': now.strftime('%Y-%m-%dT%H:%M:%S'),
                    'end':   (now + timedelta(days=7)).strftime('%Y-%m-%dT%H:%M:%S'),
                },
            })

        horizon_start, horizon_end = _version_horizon(version)
        machines = Machine.query.filter_by(is_active=True).all()
        entries  = ApsScheduleEntry.query.filter_by(version_id=version.id).all()

        entries_by_machine = {}
        for e in entries:
            mid = str(e.machine_id)
            entries_by_machine.setdefault(mid, []).append(_entry_to_dict(e))

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
        return jsonify({'error': str(exc)}), 500


@aps_page_bp.route('/api/kpis', methods=['GET'])
def api_kpis():
    """Return high-level KPI metrics for the current schedule."""
    try:
        version = ApsScheduleVersion.query.order_by(ApsScheduleVersion.created_at.desc()).first()
        if not version:
            return jsonify({'utilization_pct': 0, 'total_load_min': 0, 'capacity_min': 0, 'due_at_risk': 0})

        entries       = ApsScheduleEntry.query.filter_by(version_id=version.id).all()
        total_load    = sum(int((e.scheduled_end - e.scheduled_start).total_seconds() / 60) for e in entries)
        machine_count = Machine.query.filter_by(is_active=True).count() or 1
        days          = version.planning_horizon_days or 7
        capacity_min  = days * 24 * 60 * machine_count
        utilization   = round(total_load / capacity_min * 100, 1) if capacity_min else 0
        due_at_risk   = sum(1 for e in entries if e.constraint_status == 'INFEASIBLE')

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
        machines = Machine.query.filter_by(is_active=True).all()

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
                unassigned.append(wo.work_order_number)
                continue

            machine    = next((m for m in machines if m.id == mapping.machine_id), machines[0])
            cycle_min  = int((mapping.cycle_time_sec or 3600) / 60)
            qty        = getattr(wo, 'quantity', 1) or 1
            duration_min = cycle_min * qty
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
                setup_duration_min=int((mapping.setup_time_sec or 0) / 60),
            )
            db.session.add(entry)
            cursor_by_machine[machine.id] = end
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

        version = ApsScheduleVersion.query.order_by(ApsScheduleVersion.created_at.desc()).first()
        locked_entries = []
        if version and preserve_locked:
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

        machines = Machine.query.filter_by(is_active=True).all()
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
            if not mapping:
                continue
            machine = next((m for m in machines if m.id == mapping.machine_id), machines[0] if machines else None)
            if not machine:
                continue
            cycle_min    = int((mapping.cycle_time_sec or 3600) / 60)
            qty          = getattr(wo, 'quantity', 1) or 1
            duration_min = cycle_min * qty
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
                setup_duration_min=int((mapping.setup_time_sec or 0) / 60),
            )
            db.session.add(entry)
            cursor_by_machine[machine.id] = end
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
        f'Overlaps with WO {o.work_order_id} ({o.scheduled_start}–{o.scheduled_end})'
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
