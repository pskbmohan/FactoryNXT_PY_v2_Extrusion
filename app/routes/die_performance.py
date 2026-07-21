"""Die Performance Dashboard - Quality Reporting & Control System.

This blueprint provides die performance analytics:
- Die life remaining tracking (cycles and percentage)
- Setup time metrics (total and average per die)
- Failure history with severity classification
- Productivity scores based on runs and lifecycle status
- Breakdown by profile, alloy, and current status

Integrates with die_performance_service module.
"""

from datetime import date, datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from sqlalchemy import func

from .. import db
from ..models import Die, ProcessRun
from ..services.die_performance_service import DiePerformanceService


bp = Blueprint('die_performance', __name__, url_prefix='/quality/die-perf')


@bp.route('/')
def index():
    """Die Performance Dashboard.

    Main die performance view with:
    - Overall die fleet status summary
    - Life remaining metrics for all dies
    - Productivity scores by die
    - Status breakdown (active, maintenance, retired, etc.)
    - Alloy and profile distribution
    """
    username = session.get('username')
    if not username:
        return redirect(url_for('auth.login'))

    # Date range parameters for productivity metrics
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
    # Overall Die Fleet Summary
    # ====================================================================
    lifecycle_summary = DiePerformanceService.get_die_lifecycle_summary()

    # ====================================================================
    # Die Life Remaining Calculation for All Dies
    # ====================================================================
    life_remaining_data = DiePerformanceService.calculate_all_dies_life_remaining()

    # ====================================================================
    # Die Productivity Metrics (Last N Days)
    # ====================================================================
    productivity_data = DiePerformanceService.compute_die_productivity(
        start_date=start_dt,
        end_date=end_dt
    )

    # ====================================================================
    # Failure History (Last 90 Days)
    # ====================================================================
    failure_history = DiePerformanceService.get_failure_history(days_back=90)

    return render_template(
        'quality/die_performance/index.html',
        start_date=start_date_str,
        end_date=end_date_str,
        lifecycle_summary=lifecycle_summary,
        life_remaining_data=life_remaining_data,
        productivity_data=productivity_data,
        failure_history=failure_history,
    )


@bp.route('/<die_id>/')
def by_die(die_id):
    """Detailed Die Performance View.

    Shows comprehensive metrics for a single die:
    - Current life remaining (cycles and percentage)
    - Detailed productivity history
    - Complete failure log
    - Setup time analysis
    - Associated process runs
    """
    username = session.get('username')
    if not username:
        return redirect(url_for('auth.login'))

    die = Die.query.get(die_id)
    if not die:
        flash(f"Die '{die_id}' not found.", 'error')
        return redirect(url_for('die_performance.index'))

    # Get life remaining for this specific die
    life_remaining = DiePerformanceService.calculate_die_life_remaining(die_id)

    # Get productivity for this die (last 90 days default)
    start_date_str = request.args.get('start', (date.today() - timedelta(days=90)).isoformat())
    end_date_str = request.args.get('end', date.today().isoformat())

    try:
        start_dt = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_dt = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    except ValueError:
        flash('Invalid date range. Using default.', 'warning')
        start_dt = date.today() - timedelta(days=90)
        end_dt = date.today()

    productivity_data = DiePerformanceService.compute_die_productivity(
        die_id=die_id,
        start_date=start_dt,
        end_date=end_dt
    )

    # Get failure history for this specific die
    failure_history = DiePerformanceService.get_failure_history(die_id=die_id, days_back=90)

    # Get process runs for this die (last 12 months)
    one_year_ago = date.today() - timedelta(days=365)
    process_runs_query = db.session.query(ProcessRun).filter(
        ProcessRun.die_id == str(die.id),
        ProcessRun.started_at >= datetime.combine(one_year_ago, datetime.min.time())
    ).order_by(ProcessRun.started_at.desc()).limit(100).all()

    return render_template(
        'quality/die_performance/by_die.html',
        die=die,
        life_remaining=life_remaining,
        productivity_data=productivity_data,
        failure_history=failure_history,
        process_runs=process_runs,
        start_date=start_date_str,
        end_date=end_date_str,
    )


@bp.route('/<die_id>/failures/')
def die_failures(die_id):
    """Die Failure Analysis View.

    Focused view on failure history for a specific die:
    - All recorded failures with timestamps
    - Severity distribution
    - Common failure patterns
    - Impact on production (downtime estimation)
    """
    username = session.get('username')
    if not username:
        return redirect(url_for('auth.login'))

    die = Die.query.get(die_id)
    if not die:
        flash(f"Die '{die_id}' not found.", 'error')
        return redirect(url_for('die_performance.index'))

    # Get failure history for this specific die (last 180 days)
    days_back = int(request.args.get('days', 180))
    failure_history = DiePerformanceService.get_failure_history(die_id=die_id, days_back=days_back)

    # Calculate severity breakdown
    severity_counts = {'minor': 0, 'moderate': 0, 'major': 0, 'critical': 0}
    for failure in failure_history.get('failures', []):
        # Severity is stored in die.last_failure_reason context
        # This would need additional tracking for accurate counts
        pass

    return render_template(
        'quality/die_performance/failures.html',
        die=die,
        failure_history=failure_history,
        severity_counts=severity_counts,
        days_back=days_back,
    )


@bp.route('/by-profile/')
def by_profile():
    """Die Performance by Profile View.

    Aggregated metrics grouped by profile code:
    - Average life remaining per profile
    - Productivity scores by profile
    - Failure frequency by profile
    - Best/worst performing dies per profile
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

    # Get all dies and group by profile
    dies = Die.query.all()
    profile_summary = {}

    for die in dies:
        if not die.profile_code:
            continue

        if die.profile_code not in profile_summary:
            profile_summary[die.profile_code] = {
                'profile_code': die.profile_code,
                'total_dies': 0,
                'avg_life_remaining_pct': 0.0,
                'total_runs_in_period': 0,
                'avg_productivity_score': 0.0,
                'dies_list': []
            }

        # Calculate life remaining for this die
        life_data = DiePerformanceService.calculate_die_life_remaining(die.id)
        percent_remaining = life_data.get('percent_remaining') or 0.0

        # Get productivity metrics
        prod_data = DiePerformanceService.compute_die_productivity(
            die_id=die.id,
            start_date=start_dt,
            end_date=end_dt
        )

        profile_summary[die.profile_code]['total_dies'] += 1
        profile_summary[die.profile_code]['avg_life_remaining_pct'] += percent_remaining
        profile_summary[die.profile_code]['total_runs_in_period'] += \
            prod_data.get('by_die', {}).get(die.id, {}).get('total_runs_in_period', 0)

        # Add die to list
        profile_summary[die.profile_code]['dies_list'].append({
            'die_id': str(die.id),
            'die_code': die.die_code,
            'alloy': die.alloy,
            'life_remaining_pct': percent_remaining,
            'productivity_score': prod_data.get('by_die', {}).get(die.id, {}).get('productivity_score', 0.0)
        })

    # Calculate averages and sort by total runs (descending)
    for profile in profile_summary.values():
        if profile['total_dies'] > 0:
            profile['avg_life_remaining_pct'] /= profile['total_dies']
            profile['dies_list'].sort(key=lambda x: x['productivity_score'], reverse=True)

    return render_template(
        'quality/die_performance/by_profile.html',
        profile_summary=profile_summary,
        start_date=start_date_str,
        end_date=end_date_str,
    )


@bp.route('/by-alloy/')
def by_alloy():
    """Die Performance by Alloy View.

    Aggregated metrics grouped by alloy type:
    - Average life remaining per alloy
    - Productivity scores by alloy
    - Failure frequency by alloy
    - Die count and utilization by alloy
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

    # Get all dies and group by alloy
    dies = Die.query.all()
    alloy_summary = {}

    for die in dies:
        if not die.alloy:
            continue

        if die.alloy not in alloy_summary:
            alloy_summary[die.alloy] = {
                'alloy': die.alloy,
                'total_dies': 0,
                'avg_life_remaining_pct': 0.0,
                'total_runs_in_period': 0,
                'dies_list': []
            }

        # Calculate life remaining for this die
        life_data = DiePerformanceService.calculate_die_life_remaining(die.id)
        percent_remaining = life_data.get('percent_remaining') or 0.0

        # Get productivity metrics
        prod_data = DiePerformanceService.compute_die_productivity(
            die_id=die.id,
            start_date=start_dt,
            end_date=end_dt
        )

        alloy_summary[die.alloy]['total_dies'] += 1
        alloy_summary[die.alloy]['avg_life_remaining_pct'] += percent_remaining
        alloy_summary[die.alloy]['total_runs_in_period'] += \
            prod_data.get('by_die', {}).get(die.id, {}).get('total_runs_in_period', 0)

        # Add die to list
        alloy_summary[die.alloy]['dies_list'].append({
            'die_id': str(die.id),
            'die_code': die.die_code,
            'profile_code': die.profile_code,
            'life_remaining_pct': percent_remaining,
            'productivity_score': prod_data.get('by_die', {}).get(die.id, {}).get('productivity_score', 0.0)
        })

    # Calculate averages and sort by total runs (descending)
    for alloy in alloy_summary.values():
        if alloy['total_dies'] > 0:
            alloy['avg_life_remaining_pct'] /= alloy['total_dies']
            alloy['dies_list'].sort(key=lambda x: x['productivity_score'], reverse=True)

    return render_template(
        'quality/die_performance/by_alloy.html',
        alloy_summary=alloy_summary,
        start_date=start_date_str,
        end_date=end_date_str,
    )


@bp.route('/by-status/')
def by_status():
    """Die Performance by Status View.

    Aggregated metrics grouped by die status:
    - Active dies count and average life
    - Dies in maintenance with expected return dates
    - Retired dies summary
    - Testing pending status tracking
    """
    username = session.get('username')
    if not username:
        return redirect(url_for('auth.login'))

    # Get all dies and group by status
    dies = Die.query.all()
    status_summary = {}

    for die in dies:
        status = die.status or 'Unknown'
        if status not in status_summary:
            status_summary[status] = {
                'status': status,
                'total_dies': 0,
                'avg_life_remaining_pct': 0.0,
                'dies_list': []
            }

        # Calculate life remaining for this die
        life_data = DiePerformanceService.calculate_die_life_remaining(die.id)
        percent_remaining = life_data.get('percent_remaining') or 0.0

        status_summary[status]['total_dies'] += 1
        status_summary[status]['avg_life_remaining_pct'] += percent_remaining

        # Add die to list
        status_summary[status]['dies_list'].append({
            'die_id': str(die.id),
            'die_code': die.die_code,
            'profile_code': die.profile_code,
            'alloy': die.alloy,
            'life_remaining_pct': percent_remaining,
            'last_failure_reason': die.last_failure_reason or 'None',
        })

    # Calculate averages and sort dies by life remaining (descending)
    for status in status_summary.values():
        if status['total_dies'] > 0:
            status['avg_life_remaining_pct'] /= status['total_dies']
            status['dies_list'].sort(key=lambda x: x['life_remaining_pct'], reverse=True)

    return render_template(
        'quality/die_performance/by_status.html',
        status_summary=status_summary,
    )


@bp.route('/summary/')
def summary():
    """Die Performance Summary Report.

    High-level executive summary of die fleet performance:
    - Total dies in fleet with breakdown by key metrics
    - Fleet-wide average life remaining
    - Overall productivity score
    - Top performing and underperforming dies
    - Critical alerts (dies near end of life)
    """
    username = session.get('username')
    if not username:
        return redirect(url_for('auth.login'))

    # Get comprehensive summary data
    lifecycle_summary = DiePerformanceService.get_die_lifecycle_summary()
    life_remaining_data = DiePerformanceService.calculate_all_dies_life_remaining()

    dies = Die.query.all()

    # Identify critical dies (less than 20% remaining)
    critical_dies = []
    warning_dies = []
    good_condition_dies = []

    for die in dies:
        life_data = DiePerformanceService.calculate_die_life_remaining(die.id)
        percent_remaining = life_data.get('percent_remaining', 0) or 100.0

        if percent_remaining < 20:
            critical_dies.append({
                'die_id': str(die.id),
                'die_code': die.die_code,
                'profile_code': die.profile_code,
                'percent_remaining': round(percent_remaining, 1)
            })
        elif percent_remaining < 50:
            warning_dies.append({
                'die_id': str(die.id),
                'die_code': die.die_code,
                'profile_code': die.profile_code,
                'percent_remaining': round(percent_remaining, 1)
            })
        else:
            good_condition_dies.append({
                'die_id': str(die.id),
                'die_code': die.die_code,
                'profile_code': die.profile_code,
                'percent_remaining': round(percent_remaining, 1)
            })

    # Sort each group by percent remaining (ascending for critical/warning, descending for good)
    critical_dies.sort(key=lambda x: x['percent_remaining'])
    warning_dies.sort(key=lambda x: x['percent_remaining'])
    good_condition_dies.sort(key=lambda x: x['percent_remaining'], reverse=True)

    return render_template(
        'quality/die_performance/summary.html',
        lifecycle_summary=lifecycle_summary,
        life_remaining_data=life_remaining_data,
        critical_dies=critical_dies,
        warning_dies=warning_dies,
        good_condition_dies=good_condition_dies,
    )
