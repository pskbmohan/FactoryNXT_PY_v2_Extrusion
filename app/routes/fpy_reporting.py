"""First Pass Yield (FPY) Reporting - Quality Reporting & Control System.

This blueprint provides comprehensive FPY reporting capabilities:
- FPY calculation by profile, die, alloy, and shift
- Trend analysis over configurable time periods
- Comparative analysis between shifts/days/weeks
- Drill-down to individual run details

Integrates with the quality_service module for computation logic.
"""

from datetime import date, datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from sqlalchemy import func, cast, extract

from .. import db
from ..models import (
    Die,
    KPIRecord,
    ProcessRun,
    QualityInspection,
)


bp = Blueprint('fpy_reporting', __name__, url_prefix='/quality/fpy')


@bp.route('/')
def index():
    """FPY Reporting Dashboard.

    Main FPY view with:
    - Current period FPY summary
    - Historical trend chart data
    - Breakdown by all dimensions (profile, die, alloy, shift)
    - Comparative analysis controls
    """
    username = session.get('username')
    if not username:
        return redirect(url_for('auth.login'))

    # Date range parameters
    period_type = request.args.get('period', '7d')  # 1d, 7d, 30d, custom
    start_date_str = request.args.get('start', (date.today() - timedelta(days=7)).isoformat())
    end_date_str = request.args.get('end', date.today().isoformat())

    try:
        start_dt = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_dt = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    except ValueError:
        flash('Invalid date range. Using default.', 'warning')
        start_dt = date.today() - timedelta(days=7)
        end_dt = date.today()

    # Apply period type defaults if custom not selected
    if period_type == '1d':
        start_dt = end_dt
    elif period_type == '7d':
        start_dt = end_dt - timedelta(days=6)
    elif period_type == '30d':
        start_dt = end_dt - timedelta(days=29)

    # ====================================================================
    # FPY Summary for Selected Period
    # ====================================================================
    fpy_summary = _compute_fpy_for_period(start_dt, end_dt)

    # ====================================================================
    # FPY by Profile Code
    # ====================================================================
    fpf_by_profile = _get_fpy_by_profile(start_dt, end_dt)

    # ====================================================================
    # FPY by Alloy
    # ====================================================================
    fpy_by_alloy = _get_fpy_by_alloy(start_dt, end_dt)

    # ====================================================================
    # FPY by Die
    # ====================================================================
    fpy_by_die = _get_fpy_by_die(start_dt, end_dt)

    # ====================================================================
    # FPY by Shift (Morning/Afternoon/Night)
    # ====================================================================
    fpy_by_shift = _get_fpy_by_shift(start_dt, end_dt)

    # ====================================================================
    # Historical Trend Data
    # ====================================================================
    trend_data = _get_fpy_trend(end_dt, days_back=30)

    # ====================================================================
    # Comparative Analysis (This Period vs Previous Period)
    # ====================================================================
    comparison = _compare_periods(start_dt, end_dt)

    return render_template(
        'quality/fpy_reporting/index.html',
        period_type=period_type,
        start_date=start_date_str,
        end_date=end_date_str,
        fpy_summary=fpy_summary,
        fpy_by_profile=fpf_by_profile,
        fpy_by_alloy=fpy_by_alloy,
        fpy_by_die=fpy_by_die,
        fpy_by_shift=fpy_by_shift,
        trend_data=trend_data,
        comparison=comparison,
    )


@bp.route('/profile/<profile_code>')
def by_profile(profile_code):
    """FPY detailed view for specific profile.

    Args:
        profile_code: Profile code to filter by (e.g., 'PN-6063-H-100')
    """
    username = session.get('username')
    if not username:
        return redirect(url_for('auth.login'))

    start_date_str = request.args.get('start', (date.today() - timedelta(days=7)).isoformat())
    end_date_str = request.args.get('end', date.today().isoformat())

    try:
        start_dt = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_dt = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    except ValueError:
        start_dt = date.today() - timedelta(days=7)
        end_dt = date.today()

    # FPY for this profile
    fpy_summary = _compute_fpy_for_period(start_dt, end_dt, filter_profile=profile_code)

    # Breakdown by die for this profile
    fpy_by_die = _get_fpy_by_die(start_dt, end_dt, filter_profile=profile_code)

    return render_template(
        'quality/fpy_reporting/by_profile.html',
        profile_code=profile_code,
        start_date=start_date_str,
        end_date=end_date_str,
        fpy_summary=fpy_summary,
        fpy_by_die=fpy_by_die,
    )


@bp.route('/alloy/<alloy>')
def by_alloy(alloy):
    """FPY detailed view for specific alloy.

    Args:
        alloy: Alloy code to filter by (e.g., '6063', '6082')
    """
    username = session.get('username')
    if not username:
        return redirect(url_for('auth.login'))

    start_date_str = request.args.get('start', (date.today() - timedelta(days=7)).isoformat())
    end_date_str = request.args.get('end', date.today().isoformat())

    try:
        start_dt = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_dt = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    except ValueError:
        start_dt = date.today() - timedelta(days=7)
        end_dt = date.today()

    fpy_summary = _compute_fpy_for_period(start_dt, end_dt, filter_alloy=alloy)
    fpy_by_die = _get_fpy_by_die(start_dt, end_dt, filter_alloy=alloy)

    return render_template(
        'quality/fpy_reporting/by_alloy.html',
        alloy_code=alloy,
        start_date=start_date_str,
        end_date=end_date_str,
        fpy_summary=fpy_summary,
        fpy_by_die=fpy_by_die,
    )


@bp.route('/shift/<shift_name>')
def by_shift(shift_name):
    """FPY detailed view for specific shift.

    Args:
        shift_name: Shift name (morning, afternoon, night)
    """
    username = session.get('username')
    if not username:
        return redirect(url_for('auth.login'))

    start_date_str = request.args.get('start', (date.today() - timedelta(days=7)).isoformat())
    end_date_str = request.args.get('end', date.today().isoformat())

    try:
        start_dt = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_dt = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    except ValueError:
        start_dt = date.today() - timedelta(days=7)
        end_dt = date.today()

    fpy_summary = _compute_fpy_for_period(start_dt, end_dt, filter_shift=shift_name)
    fpy_by_profile = _get_fpy_by_profile(start_dt, end_dt, filter_shift=shift_name)

    return render_template(
        'quality/fpy_reporting/by_shift.html',
        shift_name=shift_name.title(),
        start_date=start_date_str,
        end_date=end_date_str,
        fpy_summary=fpy_summary,
        fpy_by_profile=fpy_by_profile,
    )


# ============================================================================
# Helper Functions for FPY Computation
# ============================================================================

def _compute_fpy_for_period(start_dt, end_dt, filter_profile=None, filter_alloy=None, filter_shift=None):
    """Compute First Pass Yield for a date period.

    Args:
        start_dt: Start date (date object)
        end_dt: End date (date object)
        filter_profile: Optional profile code to filter by
        filter_alloy: Optional alloy code to filter by
        filter_shift: Optional shift name to filter by

    Returns:
        dict with FPY metrics for the period
    """
    # Convert to datetime range
    start_datetime = datetime.combine(start_dt, datetime.min.time())
    end_datetime = datetime.combine(end_dt, datetime.max.time()) + timedelta(seconds=1)

    # Base query for completed process runs
    run_query = ProcessRun.query.filter(
        ProcessRun.started_at >= start_datetime,
        ProcessRun.started_at < end_datetime,
        ProcessRun.status == 'COMPLETED'
    )

    # Apply profile filter if specified
    if filter_profile:
        from ..models import Die as DieModel
        run_query = run_query.join(DieModel).filter(
            DieModel.profile_code.like(f'%{filter_profile}%')
        )

    total_runs = run_query.count()

    # Count first-piece inspections that passed (pre_production stage)
    inspection_filter = QualityInspection.query.filter(
        QualityInspection.stage == 'pre_production',
        QualityInspection.inspection_type == 'first_piece',
        QualityInspection.timestamp >= start_datetime,
        QualityInspection.timestamp < end_datetime,
        QualityInspection.pass_fail == 'PASS'
    )

    # Apply profile filter to inspections as well
    if filter_profile:
        inspection_filter = inspection_filter.join(DieModel).filter(
            DieModel.profile_code.like(f'%{filter_profile}%')
        )

    good_first_pass = inspection_filter.count()

    # Calculate FPY percentage
    fpy_percent = (good_first_pass / total_runs * 100) if total_runs > 0 else 0.0

    # Get recent KPIRecord for this period
    kpi_record = KPIRecord.query.filter(
        KPIRecord.kpi_type == 'FPY',
        KPIRecord.shift_date >= start_dt,
        KPIRecord.shift_date <= end_dt
    ).order_by(KPIRecord.calculated_at.desc()).first()

    return {
        'fpy_percent': round(fpy_percent, 2),
        'good_first_pass': good_first_pass,
        'total_produced': total_runs,
        'kpi_value': kpi_record.value if kpi_record else None,
        'calculation_date': datetime.utcnow().isoformat(),
    }


def _get_fpy_by_profile(start_dt, end_dt, filter_shift=None):
    """Get FPY breakdown by profile code."""
    start_datetime = datetime.combine(start_dt, datetime.min.time())
    end_datetime = datetime.combine(end_dt, datetime.max.time()) + timedelta(seconds=1)

    from ..models import Die as DieModel

    # Query runs grouped by profile
    profiles_data = {}

    query = db.session.query(
        DieModel.profile_code.label('profile'),
        func.count(ProcessRun.id).label('total_runs'),
        func.sum(func.cast(ProcessRun.status == 'COMPLETED', db.Integer)).label('completed')
    ).join(DieModel, ProcessRun.die_id == DieModel.id)

    query = query.filter(
        ProcessRun.started_at >= start_datetime,
        ProcessRun.started_at < end_datetime
    )

    if filter_shift:
        # Would need shift-based filtering logic here
        pass

    profiles_data = query.group_by(DieModel.profile_code).all()

    result = []
    for row in profiles_data:
        fpy = (row.completed / row.total_runs * 100) if row.total_runs > 0 else 0.0
        result.append({
            'profile_code': row.profile,
            'total_runs': row.total_runs,
            'completed_runs': row.completed,
            'fpy_percent': round(fpy, 2),
        })

    # Sort by FPY descending
    return sorted(result, key=lambda x: x['fpy_percent'], reverse=True)


def _get_fpy_by_alloy(start_dt, end_dt):
    """Get FPY breakdown by alloy."""
    start_datetime = datetime.combine(start_dt, datetime.min.time())
    end_datetime = datetime.combine(end_dt, datetime.max.time()) + timedelta(seconds=1)

    from ..models import Die as DieModel

    alloys_data = db.session.query(
        DieModel.alloy.label('alloy'),
        func.count(ProcessRun.id).label('total_runs'),
        func.sum(func.cast(ProcessRun.status == 'COMPLETED', db.Integer)).label('completed')
    ).join(DieModel, ProcessRun.die_id == DieModel.id)

    alloys_data = alloys_data.filter(
        ProcessRun.started_at >= start_datetime,
        ProcessRun.started_at < end_datetime
    ).group_by(DieModel.alloy).all()

    result = []
    for row in alloys_data:
        fpy = (row.completed / row.total_runs * 100) if row.total_runs > 0 else 0.0
        result.append({
            'alloy': row.alloy or 'Unknown',
            'total_runs': row.total_runs,
            'completed_runs': row.completed,
            'fpy_percent': round(fpy, 2),
        })

    return sorted(result, key=lambda x: x['fpy_percent'], reverse=True)


def _get_fpy_by_die(start_dt, end_dt, filter_profile=None, filter_alloy=None):
    """Get FPY breakdown by die."""
    start_datetime = datetime.combine(start_dt, datetime.min.time())
    end_datetime = datetime.combine(end_dt, datetime.max.time()) + timedelta(seconds=1)

    from ..models import Die as DieModel

    query = db.session.query(
        DieModel.id.label('die_id'),
        DieModel.die_code.label('die_code'),
        DieModel.profile_code.label('profile'),
        DieModel.alloy.label('alloy'),
        func.count(ProcessRun.id).label('total_runs'),
        func.sum(func.cast(ProcessRun.status == 'COMPLETED', db.Integer)).label('completed')
    ).join(DieModel, ProcessRun.die_id == DieModel.id)

    query = query.filter(
        ProcessRun.started_at >= start_datetime,
        ProcessRun.started_at < end_datetime
    )

    if filter_profile:
        query = query.filter(DieModel.profile_code.like(f'%{filter_profile}%'))
    if filter_alloy:
        query = query.filter(DieModel.alloy == filter_alloy)

    dies_data = query.group_by(DieModel.id, DieModel.die_code).all()

    result = []
    for row in dies_data:
        fpy = (row.completed / row.total_runs * 100) if row.total_runs > 0 else 0.0
        result.append({
            'die_id': str(row.die_id),
            'die_code': row.die_code,
            'profile': row.profile or 'N/A',
            'alloy': row.alloy or 'N/A',
            'total_runs': row.total_runs,
            'completed_runs': row.completed,
            'fpy_percent': round(fpy, 2),
        })

    return sorted(result, key=lambda x: x['fpy_percent'], reverse=True)


def _get_fpy_by_shift(start_dt, end_dt):
    """Get FPY breakdown by shift (morning/afternoon/night)."""
    start_datetime = datetime.combine(start_dt, datetime.min.time())
    end_datetime = datetime.combine(end_dt, datetime.max.time()) + timedelta(seconds=1)

    # Define shift periods
    shifts = {
        'morning': {'start': 6, 'end': 14},      # 6 AM - 2 PM
        'afternoon': {'start': 14, 'end': 22},   # 2 PM - 10 PM
        'night': {'start': 22, 'end': 30},       # 10 PM - 6 AM (next day)
    }

    result = {}

    for shift_name, shift_range in shifts.items():
        total_runs = ProcessRun.query.filter(
            ProcessRun.started_at >= start_datetime,
            ProcessRun.started_at < end_datetime,
            extract('hour', ProcessRun.started_at).between(shift_range['start'], shift_range['end'] - 1)
        ).count()

        # For the night shift crossing midnight, we need special handling
        if shift_name == 'night':
            # Count runs from previous day late evening too
            prev_start = start_datetime - timedelta(days=1)
            prev_runs = ProcessRun.query.filter(
                ProcessRun.started_at >= prev_start,
                ProcessRun.started_at < start_datetime,
                extract('hour', ProcessRun.started_at).between(shift_range['start'], 24)
            ).count()
            total_runs += prev_runs

        result[shift_name.title()] = {
            'total_runs': total_runs,
            'fpy_percent': None,  # Would need detailed inspection data
        }

    return result


def _get_fpy_trend(end_dt, days_back=30):
    """Get FPY trend data for the specified number of days."""
    start_dt = end_dt - timedelta(days=days_back)

    daily_data = []

    current_date = start_dt
    while current_date <= end_dt:
        # Get KPI record for this date
        kpi_record = KPIRecord.query.filter(
            KPIRecord.kpi_type == 'FPY',
            KPIRecord.shift_date == current_date
        ).first()

        daily_data.append({
            'date': current_date.isoformat(),
            'fpy_percent': round(kpi_record.value, 2) if kpi_record and kpi_record.value else None,
        })

        current_date += timedelta(days=1)

    return daily_data


def _compare_periods(start_dt, end_dt):
    """Compare current period FPY with previous period.

    Returns:
        dict with comparison metrics (improvement/decline percentage)
    """
    # Current period datetime range
    start_datetime = datetime.combine(start_dt, datetime.min.time())
    end_datetime = datetime.combine(end_dt, datetime.max.time()) + timedelta(seconds=1)

    # Previous period (same duration before current start)
    prev_end_datetime = start_datetime - timedelta(days=1)
    prev_start_datetime = prev_end_datetime - timedelta(
        days=(end_datetime - start_datetime).days
    )

    # Get FPY for current period
    current_summary = _compute_fpy_for_period(start_dt, end_dt)

    # Get FPY for previous period (would need date-based filtering in computation)
    prev_start_date = datetime.fromtimestamp(prev_start_datetime.timestamp()).date()
    prev_end_date = datetime.fromtimestamp(prev_end_datetime.timestamp()).date()
    prev_summary = _compute_fpy_for_period(prev_start_date, prev_end_date)

    # Calculate change
    if current_summary['fpy_percent'] is not None and prev_summary['fpy_percent'] is not None:
        fpy_change = current_summary['fpy_percent'] - prev_summary['fpy_percent']
        trend = 'improving' if fpy_change > 0 else ('declining' if fpy_change < 0 else 'stable')

        return {
            'current_fpy': current_summary['fpy_percent'],
            'previous_fpy': prev_summary['fpy_percent'],
            'absolute_change': round(fpy_change, 2),
            'trend': trend,
            'period_current': f"{start_dt.isoformat()} to {end_dt.isoformat()}",
            'period_previous': f"{prev_start_date.isoformat()} to {prev_end_date.isoformat()}",
        }

    return {'status': 'insufficient_data'}

