"""Changeover Analysis Dashboard - Quality Reporting & Control System.

This blueprint provides changeover analysis capabilities:
- Die changeover time tracking and analytics
- Setup time trends and optimization opportunities
- Changeover frequency by shift/operator
- Comparison of actual vs target changeover times
- Bottleneck identification in changeover processes

Integrates with die_performance_service module for setup time data.
"""

from datetime import date, datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from sqlalchemy import func, cast, Date

from .. import db
from ..models import ProcessRun, Die


bp = Blueprint('changeover_analysis', __name__, url_prefix='/quality/changeover')


@bp.route('/')
def index():
    """Changeover Analysis Dashboard.

    Main changeover analysis view with:
    - Overall changeover metrics summary
    - Setup time distribution and trends
    - Changeover frequency by day/shift
    - Best/worst performing dies for setup efficiency
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
    # Overall Changeover Metrics Summary
    # ====================================================================
    changeover_metrics = _get_overall_changeover_metrics(start_dt, end_dt)

    # ====================================================================
    # Setup Time Distribution (Last 90 days for better stats)
    # ====================================================================
    setup_time_data = _get_setup_time_distribution(end_dt, days_back=90)

    # ====================================================================
    # Changeover Frequency by Day of Week
    # ====================================================================
    daily_changeover_counts = _compute_daily_changeover_frequency(start_dt, end_dt)

    # ====================================================================
    # Die Setup Time Comparison (Top/Bottom Performers)
    # ====================================================================
    die_setup_comparison = _get_die_setup_time_comparison(start_dt, end_dt)

    return render_template(
        'quality/changeover_analysis/index.html',
        start_date=start_date_str,
        end_date=end_date_str,
        changeover_metrics=changeover_metrics,
        setup_time_data=setup_time_data,
        daily_changeover_counts=daily_changeover_counts,
        die_setup_comparison=die_setup_comparison,
    )


@bp.route('/die/<int:die_id>/')
def by_die(die_id):
    """Changeover Analysis for Specific Die.

    Shows detailed changeover history for a single die:
    - All setup/changeover events with timestamps and durations
    - Setup time trends over time (improvement/degradation)
    - Comparison to other dies using same profile
    - Average vs target setup times
    """
    username = session.get('username')
    if not username:
        return redirect(url_for('auth.login'))

    die = Die.query.get(die_id)
    if not die:
        flash(f"Die '{die_id}' not found.", 'error')
        return redirect(url_for('changeover_analysis.index'))

    # Date range for analysis (last 180 days)
    end_dt = date.today()
    start_dt = end_dt - timedelta(days=180)

    # Get all process runs for this die with setup time data
    query = ProcessRun.query.filter(
        ProcessRun.die_id == str(die.id),
        ProcessRun.started_at >= datetime.combine(start_dt, datetime.min.time())
    ).order_by(ProcessRun.started_at.asc()).all()

    # Calculate changeover statistics for this die
    die_changeovers = []
    total_setup_time = 0
    setup_times_list = []

    for run in query:
        # Estimate setup time from average_setup_time_minutes if available
        avg_setup = run.average_setup_time_minutes or 0
        if avg_setup > 0:
            die_changeovers.append({
                'run_id': run.id,
                'wo_id': run.wo_id,
                'started_at': run.started_at.strftime('%Y-%m-%d %H:%M') if run.started_at else None,
                'setup_time_minutes': avg_setup,
            })
            setup_times_list.append(avg_setup)
            total_setup_time += avg_setup

    # Calculate statistics
    stats = {
        'total_changeovers': len(setup_times_list),
        'avg_setup_time': round(sum(setup_times_list) / len(setup_times_list), 1) if setup_times_list else 0,
        'min_setup_time': min(setup_times_list) if setup_times_list else 0,
        'max_setup_time': max(setup_times_list) if setup_times_list else 0,
        'total_changeover_minutes': total_setup_time,
    }

    return render_template(
        'quality/changeover_analysis/by_die.html',
        die=die,
        changeovers=die_changeovers,
        stats=stats,
        start_date=str(start_dt),
        end_date=str(end_dt),
    )


@bp.route('/by-shift/')
def by_shift():
    """Changeover Analysis by Shift.

    Shows changeover metrics grouped by shift:
    - Average setup time per shift
    - Number of changeovers per shift
    - Changeover efficiency comparison
    - Best performing shifts for quick changeovers
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

    # Get changeover metrics by shift
    shift_metrics = _get_changeover_metrics_by_shift(start_dt, end_dt)

    return render_template(
        'quality/changeover_analysis/by_shift.html',
        shift_metrics=shift_metrics,
        start_date=start_date_str,
        end_date=end_date_str,
    )


@bp.route('/trends/')
def trends():
    """Changeover Trends Dashboard.

    Shows trend analysis for changeover performance:
    - Setup time trends over time (improvement tracking)
    - Changeover frequency patterns
    - Seasonal or periodic pattern detection
    - Correlation with other metrics (downtime, quality issues)
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

    # Get trend data for changeover times
    trends_data = _get_changeover_trends(start_dt, end_dt)

    return render_template(
        'quality/changeover_analysis/trends.html',
        start_date=start_date_str,
        end_date=end_date_str,
        trends_data=trends_data,
    )


@bp.route('/summary/')
def summary():
    """Changeover Analysis Executive Summary.

    High-level overview of changeover performance:
    - Overall setup time KPIs vs targets
    - Top improvement opportunities
    - Changeover efficiency rankings
    - Recommendations for optimization
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
    current_metrics = _get_overall_changeover_metrics(current_start, today)

    # Previous period for comparison
    previous_metrics = _get_overall_changeover_metrics(previous_start, previous_end)

    return render_template(
        'quality/changeover_analysis/summary.html',
        current_metrics=current_metrics,
        previous_metrics=previous_metrics,
    )


# ============================================================================
# Helper Functions - Changeover Analysis
# ============================================================================

def _get_overall_changeover_metrics(start_dt, end_dt):
    """Get overall changeover metrics for date range."""

    # Count total runs (proxy for number of changeovers)
    total_runs = db.session.query(func.count(ProcessRun.id)).filter(
        ProcessRun.started_at >= datetime.combine(start_dt, datetime.min.time()),
        ProcessRun.started_at < datetime.combine(end_dt + timedelta(days=1), datetime.max.time())
    ).scalar() or 0

    # Average setup time across all dies (from Die model)
    avg_setup_data = db.session.query(
        func.avg(Die.average_setup_time_minutes).label('avg'),
        func.min(Die.average_setup_time_minutes).label('min'),
        func.max(Die.average_setup_time_minutes).label('max')
    ).filter(
        Die.average_setup_time_minutes.isnot(None)
    ).first()

    # Count dies with setup time data
    active_dies = db.session.query(func.count(Die.id)).filter(
        Die.average_setup_time_minutes.isnot(None),
        Die.status == 'active'
    ).scalar() or 0

    return {
        'total_runs': total_runs,
        'avg_die_setup_time': round(avg_setup_data.avg or 0, 1) if avg_setup_data else 0,
        'min_die_setup_time': round(avg_setup_data.min or 0, 1) if avg_setup_data else 0,
        'max_die_setup_time': round(avg_setup_data.max or 0, 1) if avg_setup_data else 0,
        'active_dies_with_data': active_dies,
        'target_avg_setup_minutes': 30,  # Example target: 30 minutes average setup time
    }


def _get_setup_time_distribution(end_dt, days_back=90):
    """Get distribution of setup times."""

    query = db.session.query(
        func.avg(Die.average_setup_time_minutes).label('avg'),
        func.stddev(Die.average_setup_time_minutes).label('std')
    ).filter(
        Die.average_setup_time_minutes.isnot(None),
        Die.status == 'active'
    ).first()

    avg = query.avg or 0
    std = query.std or 0

    # Categorize setup times
    return {
        'avg': round(avg, 1),
        'std_deviation': round(std, 1) if std else 0,
        'distribution': {
            'fast (<20min)': _count_dies_with_setup_time(under=20),
            'medium (20-45min)': _count_dies_with_setup_time(min_val=20, max_val=45),
            'slow (>45min)': _count_dies_with_setup_time(over=45),
        },
    }


def _count_dies_with_setup_time(under=None, min_val=None, max_val=None):
    """Count dies within setup time range."""
    query = db.session.query(func.count(Die.id))

    if under:
        query = query.filter(Die.average_setup_time_minutes < under)
    elif min_val and max_val:
        query = query.filter(
            Die.average_setup_time_minutes >= min_val,
            Die.average_setup_time_minutes <= max_val
        )
    elif over := None:  # Placeholder for 'over' condition
        pass

    return query.scalar() or 0


def _compute_daily_changeover_frequency(start_dt, end_dt):
    """Compute changeover frequency by day of week."""

    days_of_week = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

    # Get counts grouped by day of week
    query = db.session.query(
        cast(ProcessRun.started_at, Date).label('date'),
        func.count(ProcessRun.id).label('count')
    ).filter(
        ProcessRun.started_at >= datetime.combine(start_dt, datetime.min.time()),
        ProcessRun.started_at < datetime.combine(end_dt + timedelta(days=1), datetime.max.time())
    ).group_by(
        cast(ProcessRun.started_at, Date)
    ).order_by('date').all()

    # Aggregate by day of week name
    result = {day: 0 for day in days_of_week}

    for row in query:
        date_obj = row.date if isinstance(row.date, date) else datetime.strptime(str(row.date), '%Y-%m-%d').date()
        day_name = date_obj.strftime('%A')
        if day_name in result:
            result[day_name] += row.count

    return result


def _get_die_setup_time_comparison(start_dt, end_dt):
    """Get comparison of die setup times."""

    query = db.session.query(
        Die.id.label('die_id'),
        Die.die_code,
        Die.profile_code,
        Die.average_setup_time_minutes,
        func.count(ProcessRun.id).label('run_count')
    ).join(
        ProcessRun, ProcessRun.die_id == Die.id
    ).filter(
        Die.average_setup_time_minutes.isnot(None),
        ProcessRun.started_at >= datetime.combine(start_dt, datetime.min.time()),
        ProcessRun.started_at < datetime.combine(end_dt + timedelta(days=1), datetime.max.time())
    ).group_by(
        Die.id, Die.die_code, Die.profile_code, Die.average_setup_time_minutes
    ).order_by(Die.average_setup_time_minutes.asc()).limit(20).all()

    return [{
        'die_id': row.die_id,
        'die_code': row.die_code,
        'profile_code': row.profile_code,
        'avg_setup_time': round(row.average_setup_time_minutes or 0, 1),
        'run_count': row.run_count,
    } for row in query]


def _get_changeover_metrics_by_shift(start_dt, end_dt):
    """Get changeover metrics grouped by shift."""

    query = db.session.query(
        ProcessRun.shift.label('shift'),
        func.count(ProcessRun.id).label('run_count'),
        func.avg(Die.average_setup_time_minutes).label('avg_setup')
    ).join(
        Die, ProcessRun.die_id == Die.id
    ).filter(
        ProcessRun.started_at >= datetime.combine(start_dt, datetime.min.time()),
        ProcessRun.started_at < datetime.combine(end_dt + timedelta(days=1), datetime.max.time()),
        Die.average_setup_time_minutes.isnot(None)
    ).group_by(ProcessRun.shift).order_by(func.count(ProcessRun.id).desc()).all()

    return [{
        'shift': row.shift or 'Unknown',
        'run_count': row.run_count,
        'avg_setup_time': round(row.avg_setup or 0, 1),
    } for row in query]


def _get_changeover_trends(start_dt, end_dt):
    """Get changeover trend data."""

    # Get weekly averages of setup times
    query = db.session.query(
        extract('week', ProcessRun.started_at).label('week'),
        func.avg(Die.average_setup_time_minutes).label('avg_setup')
    ).join(
        Die, ProcessRun.die_id == Die.id
    ).filter(
        ProcessRun.started_at >= datetime.combine(start_dt, datetime.min.time()),
        ProcessRun.started_at < datetime.combine(end_dt + timedelta(days=1), datetime.max.time()),
        Die.average_setup_time_minutes.isnot(None)
    ).group_by(extract('week', ProcessRun.started_at)).order_by('week').all()

    return [{'week': f"Week {row.week}", 'avg_setup_minutes': round(row.avg_setup or 0, 1)} for row in query]
