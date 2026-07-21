"""Alarm & Downtime Dashboard - Quality Reporting & Control System.

This blueprint provides alarm and downtime analytics:
- Machine alarm tracking with duration metrics
- Alarm categorization (mechanical, electrical, hydraulic, thermal, safety)
- Severity analysis (info, warning, critical)
- Recurring alarm detection
- Breakdown by machine, category, severity
- Trend analysis for continuous improvement

Integrates with AlarmBreakdownLog model.
"""

from datetime import date, datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from sqlalchemy import func, extract

from .. import db
from ..models import AlarmBreakdownLog


bp = Blueprint('alarm_downtime', __name__, url_prefix='/quality/alarm-downtime')


@bp.route('/')
def index():
    """Alarm & Downtime Dashboard.

    Main alarm view with:
    - Total alarms and downtime summary
    - Alarms by category (Pareto chart data)
    - Top recurring alarms
    - Breakdown by machine, severity
    - Duration analysis
    """
    username = session.get('username')
    if not username:
        return redirect(url_for('auth.login'))

    # Date range parameters
    start_date_str = request.args.get('start', (date.today() - timedelta(days=30)).isoformat())
    end_date_str = request.args.get('end', date.today().isoformat())

    try:
        start_dt = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_dt = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    except ValueError:
        flash('Invalid date range. Using default.', 'warning')
        start_dt = date.today() - timedelta(days=30)
        end_dt = date.today()

    # ====================================================================
    # Overall Alarm Metrics
    # ====================================================================
    alarm_metrics = _get_overall_alarm_metrics(start_dt, end_dt)

    # ====================================================================
    # Alarms by Category (Pareto Analysis)
    # ====================================================================
    alarms_by_category = _compute_alarms_by_category(start_dt, end_dt)

    # ====================================================================
    # Top Recurring Alarms
    # ====================================================================
    recurring_alarms = _get_recurring_alarms(start_dt, end_dt, n=10)

    # ====================================================================
    # Alarms by Severity
    # ====================================================================
    alarms_by_severity = _compute_alarms_by_dimension(start_dt, end_dt, 'severity')

    # ====================================================================
    # Alarms by Machine
    # ====================================================================
    alarms_by_machine = _compute_alarms_by_dimension(start_dt, end_dt, 'machine')

    # ====================================================================
    # Downtime Trends (Last 30 days)
    # ====================================================================
    downtime_trends = _get_downtime_trend(end_dt, days_back=30)

    return render_template(
        'quality/alarm_downtime/index.html',
        start_date=start_date_str,
        end_date=end_date_str,
        alarm_metrics=alarm_metrics,
        alarms_by_category=alarms_by_category,
        recurring_alarms=recurring_alarms,
        alarms_by_severity=alarms_by_severity,
        alarms_by_machine=alarms_by_machine,
        downtime_trends=downtime_trends,
    )


@bp.route('/<alarm_id>/')
def detail(alarm_id):
    """Detailed Alarm View.

    Shows complete details for a specific alarm:
    - Full alarm information
    - Resolution notes and resolver info
    - Related alarms (same machine/timeframe)
    - Historical context for this alarm code
    """
    username = session.get('username')
    if not username:
        return redirect(url_for('auth.login'))

    alarm = AlarmBreakdownLog.query.get(alarm_id)
    if not alarm:
        flash(f"Alarm '{alarm_id}' not found.", 'error')
        return redirect(url_for('alarm_downtime.index'))

    # Get related alarms for same machine in similar timeframe (7 days before/after)
    week_before = alarm.started_at - timedelta(days=7) if alarm.started_at else None
    week_after = alarm.ended_at + timedelta(days=7) if alarm.ended_at else None

    related_query = AlarmBreakdownLog.query.filter(
        AlarmBreakdownLog.machine_id == alarm.machine_id,
        AlarmBreakdownLog.alarm_code == alarm.alarm_code
    )

    if week_before and week_after:
        related_query = related_query.filter(
            AlarmBreakdownLog.started_at >= datetime.combine(week_before, datetime.min.time()),
            AlarmBreakdownLog.started_at <= datetime.combine(week_after, datetime.max.time())
        )

    related_alarms = related_query.order_by(AlarmBreakdownLog.started_at.desc()).limit(20).all()

    return render_template(
        'quality/alarm_downtime/detail.html',
        alarm=alarm,
        related_alarms=related_alarms,
    )


@bp.route('/recurring/')
def recurring():
    """Recurring Alarms Dashboard.

    Focused view on alarms that repeat:
    - List of all recurring alarm codes
    - Frequency analysis (how often each occurs)
    - Total downtime from recurring issues
    - Patterns and trends
    """
    username = session.get('username')
    if not username:
        return redirect(url_for('auth.login'))

    # Date range parameters
    start_date_str = request.args.get('start', (date.today() - timedelta(days=90)).isoformat())
    end_date_str = request.args.get('end', date.today().isoformat())

    try:
        start_dt = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_dt = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    except ValueError:
        flash('Invalid date range. Using default.', 'warning')
        start_dt = date.today() - timedelta(days=90)
        end_dt = date.today()

    # Get recurring alarms with counts
    query = db.session.query(
        AlarmBreakdownLog.alarm_code,
        AlarmBreakdownLog.alarm_name,
        AlarmBreakdownLog.machine_id,
        func.count(AlarmBreakdownLog.id).label('occurrence_count'),
        func.sum(AlarmBreakdownLog.duration_min or 0).label('total_downtime')
    ).filter(
        AlarmBreakdownLog.is_recurring == True,
        AlarmBreakdownLog.started_at >= datetime.combine(start_dt, datetime.min.time()),
        AlarmBreakdownLog.started_at < datetime.combine(end_dt + timedelta(days=1), datetime.max.time())
    ).group_by(
        AlarmBreakdownLog.alarm_code,
        AlarmBreakdownLog.alarm_name,
        AlarmBreakdownLog.machine_id
    ).order_by(func.count(AlarmBreakdownLog.id).desc()).all()

    recurring_summary = []
    for row in query:
        recurring_summary.append({
            'alarm_code': row.alarm_code,
            'alarm_name': row.alarm_name,
            'machine_id': row.machine_id,
            'occurrence_count': row.occurrence_count,
            'total_downtime_minutes': round(row.total_downtime or 0, 1),
        })

    return render_template(
        'quality/alarm_downtime/recurring.html',
        recurring_summary=recurring_summary,
        start_date=start_date_str,
        end_date=end_date_str,
    )


@bp.route('/by-category/')
def by_category():
    """Alarm Analysis by Category View.

    Aggregated metrics grouped by alarm category:
    - Count per category (mechanical, electrical, hydraulic, thermal, safety)
    - Total downtime per category
    - Average duration per category
    - Severity distribution within each category
    """
    username = session.get('username')
    if not username:
        return redirect(url_for('auth.login'))

    # Date range parameters
    start_date_str = request.args.get('start', (date.today() - timedelta(days=90)).isoformat())
    end_date_str = request.args.get('end', date.today().isoformat())

    try:
        start_dt = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_dt = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    except ValueError:
        flash('Invalid date range. Using default.', 'warning')
        start_dt = date.today() - timedelta(days=90)
        end_dt = date.today()

    # Get all alarms and group by category
    query = db.session.query(AlarmBreakdownLog).filter(
        AlarmBreakdownLog.started_at >= datetime.combine(start_dt, datetime.min.time()),
        AlarmBreakdownLog.started_at < datetime.combine(end_dt + timedelta(days=1), datetime.max.time())
    ).all()

    category_summary = {}
    for alarm in query:
        category = alarm.category or 'Unknown'
        if category not in category_summary:
            category_summary[category] = {
                'category': category,
                'total_alarms': 0,
                'total_downtime_minutes': 0.0,
                'avg_duration_minutes': 0.0,
                'severity_counts': {'info': 0, 'warning': 0, 'critical': 0},
            }

        category_summary[category]['total_alarms'] += 1
        category_summary[category]['total_downtime_minutes'] += (alarm.duration_min or 0)
        severity = alarm.severity or 'warning'
        if severity in category_summary[category]['severity_counts']:
            category_summary[category]['severity_counts'][severity] += 1

    # Calculate averages and sort by total alarms (descending)
    for cat in category_summary.values():
        if cat['total_alarms'] > 0:
            cat['avg_duration_minutes'] = round(cat['total_downtime_minutes'] / cat['total_alarms'], 1)

    return render_template(
        'quality/alarm_downtime/by_category.html',
        category_summary=category_summary,
        start_date=start_date_str,
        end_date=end_date_str,
    )


@bp.route('/by-machine/')
def by_machine():
    """Alarm Analysis by Machine View.

    Aggregated metrics grouped by machine:
    - Alarm count per machine
    - Total downtime per machine
    - Most frequent alarm codes per machine
    - Category breakdown per machine
    """
    username = session.get('username')
    if not username:
        return redirect(url_for('auth.login'))

    # Date range parameters
    start_date_str = request.args.get('start', (date.today() - timedelta(days=90)).isoformat())
    end_date_str = request.args.get('end', date.today().isoformat())

    try:
        start_dt = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_dt = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    except ValueError:
        flash('Invalid date range. Using default.', 'warning')
        start_dt = date.today() - timedelta(days=90)
        end_dt = date.today()

    # Get all alarms and group by machine
    query = db.session.query(AlarmBreakdownLog).filter(
        AlarmBreakdownLog.started_at >= datetime.combine(start_dt, datetime.min.time()),
        AlarmBreakdownLog.started_at < datetime.combine(end_dt + timedelta(days=1), datetime.max.time())
    ).all()

    machine_summary = {}
    for alarm in query:
        machine_id = alarm.machine_id or 'Unknown'
        if machine_id not in machine_summary:
            machine_summary[machine_id] = {
                'machine_id': machine_id,
                'total_alarms': 0,
                'total_downtime_minutes': 0.0,
                'avg_duration_minutes': 0.0,
                'alarm_codes': {},
            }

        machine_summary[machine_id]['total_alarms'] += 1
        machine_summary[machine_id]['total_downtime_minutes'] += (alarm.duration_min or 0)

        # Track alarm codes
        code = alarm.alarm_code or 'Unknown'
        if code not in machine_summary[machine_id]['alarm_codes']:
            machine_summary[machine_id]['alarm_codes'][code] = {
                'name': alarm.alarm_name,
                'count': 0,
                'total_duration': 0.0,
            }
        machine_summary[machine_id]['alarm_codes'][code]['count'] += 1
        machine_summary[machine_id]['alarm_codes'][code]['total_duration'] += (alarm.duration_min or 0)

    # Calculate averages and sort by total alarms (descending)
    for machine in machine_summary.values():
        if machine['total_alarms'] > 0:
            machine['avg_duration_minutes'] = round(machine['total_downtime_minutes'] / machine['total_alarms'], 1)

    return render_template(
        'quality/alarm_downtime/by_machine.html',
        machine_summary=machine_summary,
        start_date=start_date_str,
        end_date=end_date_str,
    )


@bp.route('/summary/')
def summary():
    """Alarm & Downtime Executive Summary.

    High-level overview of alarm and downtime status:
    - Total alarms with breakdown by severity
    - Total downtime minutes in period
    - Critical issues requiring attention
    - Top problem areas (category, machine)
    - Trend indicators vs previous period
    """
    username = session.get('username')
    if not username:
        return redirect(url_for('auth.login'))

    # Get current and previous period for comparison
    today = date.today()
    current_start = today - timedelta(days=30)
    previous_start = today - timedelta(days=60)
    previous_end = today - timedelta(days=30)

    # Current period metrics
    current_metrics = _get_overall_alarm_metrics(current_start, today)

    # Previous period metrics for comparison
    previous_metrics = _get_overall_alarm_metrics(previous_start, previous_end)

    return render_template(
        'quality/alarm_downtime/summary.html',
        current_metrics=current_metrics,
        previous_metrics=previous_metrics,
    )


# ============================================================================
# Helper Functions
# ============================================================================

def _get_overall_alarm_metrics(start_dt, end_dt):
    """Compute overall alarm metrics for date range."""
    query = AlarmBreakdownLog.query.filter(
        AlarmBreakdownLog.started_at >= datetime.combine(start_dt, datetime.min.time()),
        AlarmBreakdownLog.started_at < datetime.combine(end_dt + timedelta(days=1), datetime.max.time())
    )

    total_alarms = query.count()
    resolved_alarms = query.filter(AlarmBreakdownLog.ended_at.isnot(None)).count()
    unresolved_alarms = query.filter(AlarmBreakdownLog.ended_at.is_(None)).count()

    total_downtime = db.session.query(func.sum(AlarmBreakdownLog.duration_min or 0)).filter(
        AlarmBreakdownLog.started_at >= datetime.combine(start_dt, datetime.min.time()),
        AlarmBreakdownLog.started_at < datetime.combine(end_dt + timedelta(days=1), datetime.max.time())
    ).scalar() or 0

    recurring_count = query.filter(AlarmBreakdownLog.is_recurring == True).count()

    # Severity breakdown
    severity_counts = {}
    for alarm in query.all():
        sev = alarm.severity or 'warning'
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    return {
        'total_alarms': total_alarms,
        'resolved_alarms': resolved_alarms,
        'unresolved_alarms': unresolved_alarms,
        'total_downtime_minutes': round(total_downtime or 0, 1),
        'recurring_count': recurring_count,
        'severity_breakdown': severity_counts,
    }


def _compute_alarms_by_category(start_dt, end_dt):
    """Compute alarms grouped by category."""
    query = db.session.query(
        AlarmBreakdownLog.category,
        func.count(AlarmBreakdownLog.id).label('count'),
        func.sum(AlarmBreakdownLog.duration_min or 0).label('total_downtime')
    ).filter(
        AlarmBreakdownLog.started_at >= datetime.combine(start_dt, datetime.min.time()),
        AlarmBreakdownLog.started_at < datetime.combine(end_dt + timedelta(days=1), datetime.max.time())
    ).group_by(AlarmBreakdownLog.category).order_by(func.count(AlarmBreakdownLog.id).desc()).all()

    result = {}
    for row in query:
        category = row.category or 'Unknown'
        result[category] = {
            'category': category,
            'count': row.count,
            'total_downtime_minutes': round(row.total_downtime or 0, 1),
        }

    return result


def _get_recurring_alarms(start_dt, end_dt, n=10):
    """Get top N recurring alarms."""
    query = db.session.query(
        AlarmBreakdownLog.alarm_code,
        AlarmBreakdownLog.alarm_name,
        func.count(AlarmBreakdownLog.id).label('occurrence_count'),
        func.sum(AlarmBreakdownLog.duration_min or 0).label('total_downtime')
    ).filter(
        AlarmBreakdownLog.is_recurring == True,
        AlarmBreakdownLog.started_at >= datetime.combine(start_dt, datetime.min.time()),
        AlarmBreakdownLog.started_at < datetime.combine(end_dt + timedelta(days=1), datetime.max.time())
    ).group_by(
        AlarmBreakdownLog.alarm_code,
        AlarmBreakdownLog.alarm_name
    ).order_by(func.count(AlarmBreakdownLog.id).desc()).limit(n).all()

    return [{
        'alarm_code': row.alarm_code,
        'alarm_name': row.alarm_name,
        'occurrence_count': row.occurrence_count,
        'total_downtime_minutes': round(row.total_downtime or 0, 1),
    } for row in query]


def _compute_alarms_by_dimension(start_dt, end_dt, dimension):
    """Compute alarms grouped by specified dimension (severity, machine, etc.)."""
    if dimension == 'severity':
        column = AlarmBreakdownLog.severity
    elif dimension == 'machine':
        column = AlarmBreakdownLog.machine_id
    else:
        return {}

    query = db.session.query(
        column.label('dimension'),
        func.count(AlarmBreakdownLog.id).label('count')
    ).filter(
        AlarmBreakdownLog.started_at >= datetime.combine(start_dt, datetime.min.time()),
        AlarmBreakdownLog.started_at < datetime.combine(end_dt + timedelta(days=1), datetime.max.time())
    ).group_by(column).order_by(func.count(AlarmBreakdownLog.id).desc()).all()

    return {row.dimension: row.count for row in query}


def _get_downtime_trend(end_dt, days_back=30):
    """Get daily downtime trend."""
    start_dt = end_dt - timedelta(days=days_back)

    query = db.session.query(
        extract('date', AlarmBreakdownLog.started_at).label('date'),
        func.sum(AlarmBreakdownLog.duration_min or 0).label('downtime')
    ).filter(
        AlarmBreakdownLog.started_at >= datetime.combine(start_dt, datetime.min.time()),
        AlarmBreakdownLog.started_at < datetime.combine(end_dt + timedelta(days=1), datetime.max.time())
    ).group_by(extract('date', AlarmBreakdownLog.started_at)).order_by('date').all()

    return [{'date': str(row.date), 'downtime_minutes': round(row.downtime or 0, 1)} for row in query]
