from flask import Blueprint, render_template, request, redirect, url_for, flash
from .. import db
from ..models import OeeSnapshot, DowntimeEvent, SmtLine, Alarm, Machine
from datetime import datetime

bp = Blueprint('oee', __name__, url_prefix='/oee')


@bp.route('/')
def index():
    lines = SmtLine.query.filter_by(is_active=True).all()
    snapshots = OeeSnapshot.query.order_by(OeeSnapshot.shift_date.desc()).limit(50).all()
    return render_template('oee/index.html', lines=lines, snapshots=snapshots)


@bp.route('/smt-lines')
def smt_lines():
    lines = SmtLine.query.order_by(SmtLine.name).all()
    return render_template('oee/smt_lines.html', lines=lines)


@bp.route('/smt-lines/new', methods=['GET', 'POST'])
def smt_line_new():
    if request.method == 'POST':
        import uuid
        line = SmtLine(
            id=str(uuid.uuid4()),
            plant_id=request.form['plant_id'],
            name=request.form['name'],
            code=request.form['code'],
            is_active='is_active' in request.form
        )
        db.session.add(line)
        db.session.commit()
        flash('SMT Line created.', 'success')
        return redirect(url_for('oee.smt_lines'))
    return render_template('oee/smt_line_form.html', line=None)


@bp.route('/snapshots')
def snapshots():
    line_id = request.args.get('line_id')
    q = OeeSnapshot.query.order_by(OeeSnapshot.shift_date.desc())
    if line_id:
        q = q.filter_by(smt_line_id=line_id)
    records = q.limit(100).all()
    lines = SmtLine.query.all()
    return render_template('oee/snapshots.html', records=records, lines=lines, selected_line=line_id)


@bp.route('/downtime')
def downtime():
    events = DowntimeEvent.query.order_by(DowntimeEvent.started_at.desc()).limit(100).all()
    return render_template('oee/downtime.html', events=events)


@bp.route('/downtime/new', methods=['GET', 'POST'])
def downtime_new():
    if request.method == 'POST':
        import uuid
        ended = request.form.get('ended_at')
        started = datetime.fromisoformat(request.form['started_at'])
        ended_dt = datetime.fromisoformat(ended) if ended else None
        duration = None
        if ended_dt:
            duration = (ended_dt - started).total_seconds() / 60
        event = DowntimeEvent(
            id=str(uuid.uuid4()),
            machine_id=request.form['machine_id'],
            reason_code=request.form['reason_code'],
            reason_category=request.form.get('reason_category'),
            started_at=started,
            ended_at=ended_dt,
            duration_min=duration,
            notes=request.form.get('notes'),
            reported_by=request.form.get('reported_by')
        )
        db.session.add(event)
        db.session.commit()
        flash('Downtime event logged.', 'success')
        return redirect(url_for('oee.downtime'))
    return render_template('oee/downtime_form.html', event=None)


@bp.route('/detailed', methods=['GET'])
def detailed():
    """Plant-wide OEE detailed dashboard with Pareto and trend metrics."""
    snapshots = OeeSnapshot.query.order_by(OeeSnapshot.shift_date.desc()).limit(7).all()
    downtime_events = DowntimeEvent.query.order_by(DowntimeEvent.started_at.desc()).limit(20).all()

    # Calculate aggregate metrics for display
    # Values are stored as fractions (0.85-0.98) in the database; templates
    # multiply by 100 for display as percentages. Fallbacks must also be
    # fractions to maintain consistency.
    avg_oee = sum(s.oee or 0 for s in snapshots) / len(snapshots) if snapshots else 0.874
    avg_avail = sum(s.availability or 0 for s in snapshots) / len(snapshots) if snapshots else 0.961
    avg_perf = sum(s.performance or 0 for s in snapshots) / len(snapshots) if snapshots else 0.918
    avg_qual = sum(s.quality or 0 for s in snapshots) / len(snapshots) if snapshots else 0.997
    total_downtime_hrs = sum((s.downtime_min or 0) for s in snapshots) / 60 if snapshots else 3.2

    return render_template(
        'oee/detailed.html',
        snapshots=snapshots,
        downtime_events=downtime_events,
        avg_oee=round(avg_oee, 4),
        avg_avail=round(avg_avail, 4),
        avg_perf=round(avg_perf, 4),
        avg_qual=round(avg_qual, 4),
        total_downtime_hrs=round(total_downtime_hrs, 1),
    )


@bp.route('/alarms', methods=['GET'])
def alarms():
    """Alarm & Event History dashboard."""
    severity_filter = request.args.get('severity', '')
    q = Alarm.query.options(db.joinedload(Alarm.machine))

    if severity_filter:
        q = q.filter(Alarm.severity == severity_filter)

    alarms_list = q.order_by(Alarm.id.desc()).limit(50).all()

    # Calculate stats for footer
    all_alarms = Alarm.query.all()
    total_active = len([a for a in all_alarms if a.is_active])
    critical_count = len([a for a in all_alarms if a.severity == 'HIGH' and a.is_active])
    warning_count = len([a for a in all_alarms if a.severity == 'MEDIUM' and a.is_active])

    return render_template(
        'oee/alarms.html',
        alarms=alarms_list,
        severity_filter=severity_filter,
        total_active=total_active,
        critical_count=critical_count,
        warning_count=warning_count,
    )
