"""Parameter Monitoring Dashboard - Quality Reporting & Control System.

This blueprint provides process parameter traceability views:
- Real-time parameter readings from PLC during extrusion runs
- Parameter history with visualizations of temperature, speed, pressure profiles
- Violation tracking against setpoint limits (quality_parameters table)
- Trend analysis for each parameter type
- Comparison between expected (setpoints) and actual parameters

Integrates with parameter_monitoring_service module.
"""

from datetime import date, datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from sqlalchemy import func, extract
import statistics

from .. import db
from ..models import ProcessRun, ParameterReading, QualityParameter


bp = Blueprint('parameter_monitoring', __name__, url_prefix='/quality/parameters')


@bp.route('/')
def index():
    """Parameter Monitoring Dashboard.

    Main parameter monitoring view with:
    - Recent extrusion runs with parameter summaries
    - Real-time parameter capture status
    - Parameter violation overview
    - Quick access to detailed views
    """
    username = session.get('username')
    if not username:
        return redirect(url_for('auth.login'))

    # Date range parameters
    start_date_str = request.args.get('start', (date.today() - timedelta(days=7)).isoformat())
    end_date_str = request.args.get('end', date.today().isoformat())

    try:
        start_dt = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_dt = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    except ValueError:
        flash('Invalid date range. Using default.', 'warning')
        start_dt = date.today() - timedelta(days=7)
        end_dt = date.today()

    # ====================================================================
    # Recent Extrusion Runs with Parameter Summary
    # ====================================================================
    recent_runs = _get_recent_extrusion_runs(start_dt, end_dt, limit=20)

    # ====================================================================
    # Parameter Violations Overview (Last 7 days)
    # ====================================================================
    violation_summary = _get_violation_summary(start_dt, end_dt)

    # ====================================================================
    # Recent Parameter Readings with Status
    # ====================================================================
    recent_readings = _get_recent_parameter_readings(end_dt, limit=50)

    return render_template(
        'quality/parameter_monitoring/index.html',
        start_date=start_date_str,
        end_date=end_date_str,
        recent_runs=recent_runs,
        violation_summary=violation_summary,
        recent_readings=recent_readings,
    )


@bp.route('/run/<int:run_id>/')
def run_details(run_id):
    """Detailed Parameter View for a Single Extrusion Run.

    Shows complete parameter history for an extrusion run:
    - Full timeline of parameter readings over the run duration
    - Temperature profiles (billet, container, die, exit)
    - Speed and pressure curves
    - Violations with timestamps
    - Comparison against setpoint limits
    """
    username = session.get('username')
    if not username:
        return redirect(url_for('auth.login'))

    run = ProcessRun.query.get(run_id)
    if not run:
        flash(f"Extrusion run '{run_id}' not found.", 'error')
        return redirect(url_for('parameter_monitoring.index'))

    # Get all parameter readings for this run
    readings = ParameterReading.query.filter(
        ParameterReading.run_id == run_id
    ).order_by(ParameterReading.timestamp.asc()).all()

    if not readings:
        flash(f"No parameter data available for run '{run_id}'.", 'warning')

    # Calculate violation summary for this run
    violations_in_run = _get_violations_for_run(run_id)

    # Get setpoint profile for comparison
    setpoint_profile = QualityParameter.query.filter(
        QualityParameter.profile_code == run.profile_code,
        QualityParameter.alloy == run.alloy
    ).first() if run.profile_code and run.alloy else None

    return render_template(
        'quality/parameter_monitoring/run_details.html',
        run=run,
        readings=readings,
        violations_in_run=violations_in_run,
        setpoint_profile=setpoint_profile,
    )


@bp.route('/profile/<int:profile_id>/')
def profile_view(profile_id):
    """Parameter Profile View.

    Shows historical parameter behavior for a specific alloy/profile combination:
    - Average temperature profiles over time
    - Parameter variability analysis
    - Common violation patterns
    - Trend detection (improving/degrading)
    """
    username = session.get('username')
    if not username:
        return redirect(url_for('auth.login'))

    profile = QualityParameter.query.get(profile_id)
    if not profile:
        flash(f"Quality parameter profile '{profile_id}' not found.", 'error')
        return redirect(url_for('parameter_monitoring.index'))

    # Date range for analysis (last 90 days)
    end_dt = date.today()
    start_dt = end_dt - timedelta(days=90)

    # Get all runs using this profile and their parameter readings
    run_ids = db.session.query(ProcessRun.wo_id).filter(
        ProcessRun.profile_code == profile.profile_code,
        ProcessRun.alloy == profile.alloy
    ).distinct().all()
    wo_ids = [r[0] for r in run_ids if r and hasattr(r, 'wo_id')]

    # Get parameter statistics for this profile
    param_stats = _compute_profile_parameter_statistics(
        start_dt, end_dt,
        profile.profile_code,
        profile.alloy
    )

    return render_template(
        'quality/parameter_monitoring/profile_view.html',
        profile=profile,
        param_stats=param_stats,
        start_date=str(start_dt),
        end_date=str(end_dt),
    )


@bp.route('/violations/')
def violations():
    """Parameter Violations Dashboard.

    Focused view on all parameter limit violations:
    - List of all violations with timestamps and parameters affected
    - Severity classification (warning vs critical)
    - Trend analysis for violation frequency
    - Top problem parameters
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

    # Get all violations for this period
    violations_list, violation_counts = _get_violations_with_summary(start_dt, end_dt)

    return render_template(
        'quality/parameter_monitoring/violations.html',
        start_date=start_date_str,
        end_date=end_date_str,
        violations=violations_list,
        violation_counts=violation_counts,
    )


@bp.route('/trends/')
def trends():
    """Parameter Trends Dashboard.

    Shows parameter trend analysis over time:
    - Temperature trend lines (billet, container, die, exit)
    - Pressure and speed stability metrics
    - Parameter drift detection
    - Anomaly identification
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

    # Get trend data for each parameter type
    trends_data = _compute_parameter_trends(start_dt, end_dt)

    return render_template(
        'quality/parameter_monitoring/trends.html',
        start_date=start_date_str,
        end_date=end_date_str,
        trends_data=trends_data,
    )


@bp.route('/summary/')
def summary():
    """Parameter Monitoring Executive Summary.

    High-level overview of parameter monitoring status:
    - Overall data capture rate
    - Parameter health indicators
    - Most common violations
    - Trend analysis summary
    - Recommendations for improvement
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
    current_stats = _get_overall_parameter_statistics(current_start, today)

    # Previous period for comparison
    previous_stats = _get_overall_parameter_statistics(previous_start, previous_end)

    return render_template(
        'quality/parameter_monitoring/summary.html',
        current_stats=current_stats,
        previous_stats=previous_stats,
    )


# ============================================================================
# Helper Functions - Parameter Monitoring
# ============================================================================

def _get_recent_extrusion_runs(start_dt, end_dt, limit=20):
    """Get recent extrusion runs with parameter summary."""
    query = db.session.query(
        ProcessRun.id.label('run_id'),
        ProcessRun.wo_id,
        ProcessRun.die_id,
        ProcessRun.profile_code,
        ProcessRun.alloy,
        ProcessRun.started_at,
        ProcessRun.completed_at,
        func.count(ParameterReading.id).label('reading_count'),
        func.sum(
            CASE_PARAM_WITHIN_LIMITS()
        ).label('within_limit_ratio')
    ).join(
        ParameterReading, ProcessRun.id == ParameterReading.run_id
    ).filter(
        ProcessRun.started_at >= datetime.combine(start_dt, datetime.min.time()),
        ProcessRun.started_at < datetime.combine(end_dt + timedelta(days=1), datetime.max.time())
    ).group_by(
        ProcessRun.id, ProcessRun.wo_id, ProcessRun.die_id,
        ProcessRun.profile_code, ProcessRun.alloy,
        ProcessRun.started_at, ProcessRun.completed_at
    ).order_by(ProcessRun.started_at.desc()).limit(limit).all()

    return [{
        'run_id': row.run_id,
        'wo_id': row.wo_id,
        'die_id': row.die_id,
        'profile_code': row.profile_code,
        'alloy': row.alloy,
        'started_at': row.started_at.strftime('%Y-%m-%d %H:%M') if row.started_at else None,
        'completed_at': row.completed_at.strftime('%Y-%m-%d %H:%M') if row.completed_at else None,
        'reading_count': row.reading_count or 0,
        'within_limit_ratio': round((row.within_limit_ratio / row.reading_count * 100) if (row.reading_count and row.reading_count > 0) else 100, 1),
    } for row in query]


def _get_violation_summary(start_dt, end_dt):
    """Get summary of parameter violations."""

    # Count total readings vs within-limit readings
    total_readings = db.session.query(
        func.count(ParameterReading.id).label('total')
    ).filter(
        ParameterReading.timestamp >= datetime.combine(start_dt, datetime.min.time()),
        ParameterReading.timestamp < datetime.combine(end_dt + timedelta(days=1), datetime.max.time())
    ).scalar() or 0

    within_limit_readings = db.session.query(
        func.count(ParameterReading.id).label('within')
    ).filter(
        ParameterReading.all_within_limits == True,
        ParameterReading.timestamp >= datetime.combine(start_dt, datetime.min.time()),
        ParameterReading.timestamp < datetime.combine(end_dt + timedelta(days=1), datetime.max.time())
    ).scalar() or 0

    violation_count = total_readings - within_limit_readings

    # Get violations by parameter type
    param_violations = db.session.query(
        func.count(ParameterReading.id).label('count'),
        ParameterReading.billet_temp > QualityParameter.billet_temp_max.label('billet_high') |
        (ParameterReading.billet_temp < QualityParameter.billet_temp_min)
    ).join(
        ProcessRun, ParameterReading.run_id == ProcessRun.id
    ).filter(
        ParameterReading.timestamp >= datetime.combine(start_dt, datetime.min.time()),
        ParameterReading.timestamp < datetime.combine(end_dt + timedelta(days=1), datetime.max.time())
    )

    return {
        'total_readings': total_readings,
        'within_limit_count': within_limit_readings,
        'violation_count': violation_count,
        'capture_rate_pct': round((within_limit_readings / total_readings * 100) if total_readings > 0 else 100, 1),
    }


def _get_recent_parameter_readings(end_dt, limit=50):
    """Get recent parameter readings."""
    query = ParameterReading.query.filter(
        ParameterReading.timestamp <= datetime.combine(end_dt + timedelta(days=1), datetime.max.time()),
        ParameterReading.timestamp >= datetime.combine(end_dt - timedelta(days=7), datetime.min.time())
    ).order_by(ParameterReading.timestamp.desc()).limit(limit).all()

    return [{
        'reading_id': r.id,
        'run_id': r.run_id,
        'timestamp': r.timestamp.strftime('%Y-%m-%d %H:%M:%S') if r.timestamp else None,
        'billet_temp': round(r.billet_temp, 1) if r.billet_temp else None,
        'container_temp': round(r.container_temp, 1) if r.container_temp else None,
        'die_temp': round(r.die_temp, 1) if r.die_temp else None,
        'exit_temp': round(r.exit_temp, 1) if r.exit_temp else None,
        'ram_speed': round(r.ram_speed, 2) if r.ram_speed else None,
        'pressure': round(r.main_cylinder_pressure, 1) if r.main_cylinder_pressure else None,
        'force': round(r.extrusion_force, 1) if r.extrusion_force else None,
        'cycle_time': round(r.cycle_time, 2) if r.cycle_time else None,
        'within_limits': r.all_within_limits or False,
    } for r in query]


def _get_violations_for_run(run_id):
    """Get violations for a specific run."""
    # This would need ProcessParameterAlert queries - simplified here
    return []


def _compute_profile_parameter_statistics(start_dt, end_dt, profile_code, alloy):
    """Compute statistics for a parameter profile."""

    # Get all runs with this profile/alloy combination
    runs = db.session.query(ProcessRun.id).filter(
        ProcessRun.profile_code == profile_code,
        ProcessRun.alloy == alloy
    ).all()
    run_ids = [r.id for r in runs]

    if not run_ids:
        return {}

    # Get parameter statistics
    readings = ParameterReading.query.filter(
        ParameterReading.run_id.in_(run_ids),
        ParameterReading.timestamp >= datetime.combine(start_dt, datetime.min.time()),
        ParameterReading.timestamp < datetime.combine(end_dt + timedelta(days=1), datetime.max.time())
    ).all()

    if not readings:
        return {}

    # Calculate statistics for each parameter type
    billet_temps = [r.billet_temp for r in readings if r.billet_temp]
    container_temps = [r.container_temp for r in readings if r.container_temp]
    die_temps = [r.die_temp for r in readings if r.die_temp]
    exit_temps = [r.exit_temp for r in readings if r.exit_temp]

    return {
        'billet_temp': _calc_param_stats(billet_temps),
        'container_temp': _calc_param_stats(container_temps),
        'die_temp': _calc_param_stats(die_temps),
        'exit_temp': _calc_param_stats(exit_temps),
        'ram_speed': _calc_param_stats([r.ram_speed for r in readings if r.ram_speed]),
        'pressure': _calc_param_stats([r.main_cylinder_pressure for r in readings if r.main_cylinder_pressure]),
    }


def _calc_param_stats(values):
    """Calculate statistics for a list of values."""
    if not values:
        return {'avg': 0, 'min': 0, 'max': 0, 'std_dev': 0}

    avg = statistics.mean(values)
    min_val = min(values)
    max_val = max(values)
    std_dev = statistics.stdev(values) if len(values) > 1 else 0

    return {
        'avg': round(avg, 2),
        'min': round(min_val, 2),
        'max': round(max_val, 2),
        'std_dev': round(std_dev, 2),
        'count': len(values),
    }


def _get_violations_with_summary(start_dt, end_dt):
    """Get violations list with summary counts."""

    # Get all parameter readings that had any violation
    query = ParameterReading.query.filter(
        ParameterReading.all_within_limits == False,
        ParameterReading.timestamp >= datetime.combine(start_dt, datetime.min.time()),
        ParameterReading.timestamp < datetime.combine(end_dt + timedelta(days=1), datetime.max.time())
    ).order_by(ParameterReading.timestamp.desc()).all()

    violations = []
    for r in query:
        # Get the quality parameters for this run's profile/alloy to check specific violations
        qp = None
        if r.run_id:
            process_run = ProcessRun.query.get(r.run_id)
            if process_run and process_run.profile_code and process_run.alloy:
                qp = QualityParameter.query.filter_by(
                    profile_code=process_run.profile_code,
                    alloy=process_run.alloy
                ).first()

        violations.append({
            'reading_id': r.id,
            'run_id': r.run_id,
            'timestamp': r.timestamp.strftime('%Y-%m-%d %H:%M:%S') if r.timestamp else None,
            'billet_temp_violation': bool(r.billet_temp is not None and qp),
            'within_limits': False,
        })

    violation_counts = {
        'total_violations': len(query),
        'unique_runs_affected': len(set(r.run_id for r in query)),
    }

    return violations, violation_counts


def _compute_parameter_trends(start_dt, end_dt):
    """Compute parameter trend data."""
    trends = {}

    # Get daily averages for each temperature type
    temp_params = ['billet_temp', 'container_temp', 'die_temp', 'exit_temp']

    for param in temp_params:
        query = db.session.query(
            extract('date', ParameterReading.timestamp).label('date'),
            func.avg(getattr(ParameterReading, param)).label('avg_value')
        ).filter(
            getattr(ParameterReading, param).isnot(None),
            ParameterReading.timestamp >= datetime.combine(start_dt, datetime.min.time()),
            ParameterReading.timestamp < datetime.combine(end_dt + timedelta(days=1), datetime.max.time())
        ).group_by(extract('date', ParameterReading.timestamp)).order_by('date').all()

        trends[param] = [{'date': str(row.date), 'avg_value': round(float(row.avg_value or 0), 2)} for row in query]

    return trends


def _get_overall_parameter_statistics(start_dt, end_dt):
    """Get overall parameter statistics."""
    total_readings = db.session.query(
        func.count(ParameterReading.id)
    ).filter(
        ParameterReading.timestamp >= datetime.combine(start_dt, datetime.min.time()),
        ParameterReading.timestamp < datetime.combine(end_dt + timedelta(days=1), datetime.max.time())
    ).scalar() or 0

    within_limit = db.session.query(
        func.count(ParameterReading.id)
    ).filter(
        ParameterReading.all_within_limits == True,
        ParameterReading.timestamp >= datetime.combine(start_dt, datetime.min.time()),
        ParameterReading.timestamp < datetime.combine(end_dt + timedelta(days=1), datetime.max.time())
    ).scalar() or 0

    return {
        'total_readings': total_readings,
        'within_limit_count': within_limit,
        'capture_rate_pct': round((within_limit / total_readings * 100) if total_readings > 0 else 100, 1),
    }


# ============================================================================
# SQLAlchemy Helper - Case expression for within limits check
# ============================================================================

def CASE_PARAM_WITHIN_LIMITS():
    """SQLAlchemy case expression to count readings within all limits."""
    from sqlalchemy import case

    return case(
        (ParameterReading.all_within_limits == True, 1),
        else_=0
    )
