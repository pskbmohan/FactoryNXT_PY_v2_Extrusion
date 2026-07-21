"""Quality Metrics Dashboard - Quality Reporting & Control System.

This blueprint provides comprehensive quality metrics analytics:
- Parts Per Million (PPM) defect rate with category breakdowns
- Surface defects analysis and trending
- Bend-per-meter measurements for profile quality
- Defect rate trends over time
- Performance by shift, operator, alloy, profile
- Comparison to target KPIs

Integrates with quality_service module.
"""

from datetime import date, datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from sqlalchemy import func, cast, Date
import statistics

from .. import db
from ..models import WorkOrder, ProcessRun, KPIRecord, DefectCode, QualityInspection


bp = Blueprint('quality_metrics', __name__, url_prefix='/quality/metrics')

# Make timedelta available in templates
@bp.app_template_global()
def get_timedelta(days=0):
    """Make timedelta available in Jinja2 templates."""
    return lambda days=days: timedelta(days)


@bp.route('/')
def index():
    """Quality Metrics Dashboard.

    Main quality metrics view with:
    - Overall PPM rate and trending
    - Surface defects summary
    - Bend-per-meter statistics
    - KPI performance vs targets
    - Breakdown by multiple dimensions
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
    # PPM Analysis
    # ====================================================================
    ppm_data = _compute_ppm_metrics(start_dt, end_dt)

    # ====================================================================
    # Surface Defects Analysis
    # ====================================================================
    surface_defects_data = _analyze_surface_defects(start_dt, end_dt)

    # ====================================================================
    # Bend Per Meter Statistics
    # ====================================================================
    bend_per_meter_data = _compute_bend_per_meter_stats(start_dt, end_dt)

    # ====================================================================
    # Quality KPI Trends (Last 30 days)
    # ====================================================================
    quality_trends = _get_quality_kpi_trends(end_dt, days_back=30)

    # ====================================================================
    # Performance by Shift
    # ====================================================================
    metrics_by_shift = _compute_metrics_by_dimension(start_dt, end_dt, 'shift')

    # ====================================================================
    # Performance by Operator
    # ====================================================================
    top_operators = _get_top_performing_operators(start_dt, end_dt)

    return render_template(
        'quality/metrics/index.html',
        start_date=start_date_str,
        end_date=end_date_str,
        ppm_data=ppm_data,
        surface_defects_data=surface_defects_data,
        bend_per_meter_data=bend_per_meter_data,
        quality_trends=quality_trends,
        metrics_by_shift=metrics_by_shift,
        top_operators=top_operators,
    )


@bp.route('/by-profile/')
def by_profile():
    """Quality Metrics by Profile View.

    Aggregated metrics grouped by profile code:
    - PPM rate per profile
    - Surface defect frequency
    - Bend-per-meter variation
    - Best/worst performing profiles
    - Target vs actual comparison
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

    # Get profile-level quality metrics
    profile_metrics = _compute_metrics_by_profile(start_dt, end_dt)

    return render_template(
        'quality/metrics/by_profile.html',
        profile_metrics=profile_metrics,
        start_date=start_date_str,
        end_date=end_date_str,
    )


@bp.route('/by-alloy/')
def by_alloy():
    """Quality Metrics by Alloy View.

    Aggregated metrics grouped by alloy type:
    - PPM rate per alloy
    - Surface defect patterns by alloy
    - Bend-per-meter characteristics
    - Quality consistency analysis
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

    # Get alloy-level quality metrics
    alloy_metrics = _compute_metrics_by_alloy(start_dt, end_dt)

    return render_template(
        'quality/metrics/by_alloy.html',
        alloy_metrics=alloy_metrics,
        start_date=start_date_str,
        end_date=end_date_str,
    )


@bp.route('/by-shift/')
def by_shift():
    """Quality Metrics by Shift View.

    Aggregated metrics grouped by shift:
    - PPM rate per shift
    - Surface defect frequency by shift
    - Bend-per-meter consistency
    - Shift comparison analysis
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

    # Get shift-level quality metrics
    shift_metrics = _compute_metrics_by_dimension(start_dt, end_dt, 'shift')

    return render_template(
        'quality/metrics/by_shift.html',
        shift_metrics=shift_metrics,
        start_date=start_date_str,
        end_date=end_date_str,
    )


@bp.route('/defect-analysis/')
def defect_analysis():
    """Defect Analysis Dashboard.

    Deep dive into defect patterns:
    - Defect code frequency analysis
    - Category-based breakdown (surface, functional, aesthetic, dimensional)
    - Severity distribution
    - Temporal trends in defects
    - Pareto analysis of top defects
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

    # Get defect analysis data
    defect_summary = _get_defect_analysis(start_dt, end_dt)

    return render_template(
        'quality/metrics/defect_analysis.html',
        defect_summary=defect_summary,
        start_date=start_date_str,
        end_date=end_date_str,
    )


@bp.route('/summary/')
def summary():
    """Quality Metrics Executive Summary.

    High-level overview of quality performance:
    - Overall PPM rate and trend direction
    - Surface defects status
    - Bend-per-meter compliance
    - Quality KPI vs targets
    - Critical issues requiring attention
    - Period-over-period comparison
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
    current_ppm = _compute_overall_ppm(current_start, today)
    current_surface = _analyze_surface_defects(current_start, today)
    current_bend = _compute_bend_per_meter_stats(current_start, today)

    # Previous period metrics for comparison
    previous_ppm = _compute_overall_ppm(previous_start, previous_end)
    previous_surface = _analyze_surface_defects(previous_start, previous_end)
    previous_bend = _compute_bend_per_meter_stats(previous_start, previous_end)

    return render_template(
        'quality/metrics/summary.html',
        current_ppm=current_ppm,
        current_surface=current_surface,
        current_bend=current_bend,
        previous_ppm=previous_ppm,
        previous_surface=previous_surface,
        previous_bend=previous_bend,
    )


# ============================================================================
# Helper Functions - PPM Analysis
# ============================================================================

def _compute_ppm_metrics(start_dt, end_dt):
    """Compute Parts Per Million defect rate metrics."""

    # Get total parts produced in period
    total_parts_query = db.session.query(
        func.sum(ProcessRun.expected_output).label('total_parts')
    ).filter(
        ProcessRun.started_at >= datetime.combine(start_dt, datetime.min.time()),
        ProcessRun.started_at < datetime.combine(end_dt + timedelta(days=1), datetime.max.time())
    )
    total_parts = total_parts_query.scalar() or 0

    # Get defect count from quality inspections and scrap records
    defect_count_query = db.session.query(
        func.count(QualityInspection.id).label('defects')
    ).filter(
        QualityInspection.inspection_type == 'post_extrusion',
        QualityInspection.pass_fail == False,  # Failed inspections indicate defects
        QualityInspection.timestamp >= datetime.combine(start_dt, datetime.min.time()),
        QualityInspection.timestamp < datetime.combine(end_dt + timedelta(days=1), datetime.max.time())
    )
    defect_count = defect_count_query.scalar() or 0

    # Calculate PPM
    ppm_rate = (defect_count / total_parts * 1_000_000) if total_parts > 0 else 0

    # Get defects by category breakdown
    query = db.session.query(
        DefectCode.category,
        func.count(QualityInspection.id).label('count')
    ).join(DefectCode, QualityInspection.defect_code == DefectCode.code).filter(
        QualityInspection.inspection_type == 'post_extrusion',
        QualityInspection.pass_fail == False,
        QualityInspection.timestamp >= datetime.combine(start_dt, datetime.min.time()),
        QualityInspection.timestamp < datetime.combine(end_dt + timedelta(days=1), datetime.max.time())
    ).group_by(DefectCode.category).order_by(func.count(QualityInspection.id).desc()).all()

    defects_by_category = {}
    for row in query:
        category = row.category or 'Unknown'
        defects_by_category[category] = {
            'category': category,
            'defect_count': row.count,
            'ppm_contribution': round((row.count / total_parts * 1_000_000), 2) if total_parts > 0 else 0,
        }

    # Get top defect codes (Pareto analysis)
    top_defects_query = db.session.query(
        DefectCode.code,
        DefectCode.name,
        func.count(QualityInspection.id).label('count')
    ).join(DefectCode, QualityInspection.defect_code == DefectCode.code).filter(
        QualityInspection.inspection_type == 'post_extrusion',
        QualityInspection.pass_fail == False,
        QualityInspection.timestamp >= datetime.combine(start_dt, datetime.min.time()),
        QualityInspection.timestamp < datetime.combine(end_dt + timedelta(days=1), datetime.max.time())
    ).group_by(DefectCode.code, DefectCode.name).order_by(func.count(QualityInspection.id).desc()).limit(10).all()

    top_defects = [{
        'code': row.code,
        'name': row.name,
        'count': row.count,
        'ppm_impact': round((row.count / total_parts * 1_000_000), 2) if total_parts > 0 else 0,
    } for row in top_defects_query]

    return {
        'total_parts_produced': total_parts,
        'total_defects': defect_count,
        'ppm_rate': round(ppm_rate, 2),
        'defects_by_category': defects_by_category,
        'top_defects': top_defects,
        'target_ppm': 50000,  # Example target: 50K PPM (95% yield)
    }


def _compute_overall_ppm(start_dt, end_dt):
    """Compute overall PPM for a date range."""
    total_parts_query = db.session.query(
        func.sum(ProcessRun.expected_output).label('total_parts')
    ).filter(
        ProcessRun.started_at >= datetime.combine(start_dt, datetime.min.time()),
        ProcessRun.started_at < datetime.combine(end_dt + timedelta(days=1), datetime.max.time())
    )
    total_parts = total_parts_query.scalar() or 0

    defect_count_query = db.session.query(
        func.count(QualityInspection.id).label('defects')
    ).filter(
        QualityInspection.inspection_type == 'post_extrusion',
        QualityInspection.pass_fail == False,
        QualityInspection.timestamp >= datetime.combine(start_dt, datetime.min.time()),
        QualityInspection.timestamp < datetime.combine(end_dt + timedelta(days=1), datetime.max.time())
    )
    defect_count = defect_count_query.scalar() or 0

    ppm_rate = (defect_count / total_parts * 1_000_000) if total_parts > 0 else 0

    return {
        'total_parts': total_parts,
        'defects': defect_count,
        'ppm_rate': round(ppm_rate, 2),
    }


# ============================================================================
# Helper Functions - Surface Defects Analysis
# ============================================================================

def _analyze_surface_defects(start_dt, end_dt):
    """Analyze surface defects by category and trend."""

    # Get all defect codes in surface category
    surface_codes = db.session.query(DefectCode.code).filter(
        DefectCode.category == 'surface',
        DefectCode.is_active == True
    ).all()
    surface_code_list = [code[0] for code in surface_codes]

    # Count surface defects
    if not surface_code_list:
        return {
            'total_surface_defects': 0,
            'surface_ppm': 0,
            'by_defect_type': {},
            'severity_breakdown': {'minor': 0, 'moderate': 0, 'major': 0},
        }

    surface_query = db.session.query(
        QualityInspection.defect_code,
        DefectCode.name,
        DefectCode.severity,
        func.count(QualityInspection.id).label('count')
    ).join(DefectCode, QualityInspection.defect_code == DefectCode.code).filter(
        QualityInspection.inspection_type == 'post_extrusion',
        QualityInspection.pass_fail == False,
        QualityInspection.timestamp >= datetime.combine(start_dt, datetime.min.time()),
        QualityInspection.timestamp < datetime.combine(end_dt + timedelta(days=1), datetime.max.time())
    ).group_by(
        QualityInspection.defect_code, DefectCode.name, DefectCode.severity
    ).order_by(func.count(QualityInspection.id).desc()).all()

    by_defect_type = {}
    severity_breakdown = {'minor': 0, 'moderate': 0, 'major': 0}

    for row in surface_query:
        defect_code = row.defect_code
        severity = row.severity or 'minor'
        if severity not in severity_breakdown:
            severity = 'minor'

        by_defect_type[defect_code] = {
            'name': row.name,
            'count': row.count,
            'severity': severity,
        }
        severity_breakdown[severity] += 1

    # Calculate surface PPM contribution
    total_parts_query = db.session.query(
        func.sum(ProcessRun.expected_output).label('total_parts')
    ).filter(
        ProcessRun.started_at >= datetime.combine(start_dt, datetime.min.time()),
        ProcessRun.started_at < datetime.combine(end_dt + timedelta(days=1), datetime.max.time())
    )
    total_parts = total_parts_query.scalar() or 0

    total_surface_defects = sum(d['count'] for d in by_defect_type.values())
    surface_ppm = (total_surface_defects / total_parts * 1_000_000) if total_parts > 0 else 0

    return {
        'total_surface_defects': total_surface_defects,
        'surface_ppm': round(surface_ppm, 2),
        'by_defect_type': by_defect_type,
        'severity_breakdown': severity_breakdown,
        'target_surface_ppm': 30000,  # Example target for surface defects
    }


# ============================================================================
# Helper Functions - Bend Per Meter Statistics
# ============================================================================

def _compute_bend_per_meter_stats(start_dt, end_dt):
    """Compute bend-per-meter quality metrics."""

    # Get dimension measurements from quality inspections (bend/straightness data)
    query = db.session.query(
        QualityInspection.id,
        QualityInspection.measured_values,
        WorkOrder.profile_code,
        Die.die_code,
        WorkOrder.alloy,
        ProcessRun.started_at
    ).join(ProcessRun, QualityInspection.wo_id == ProcessRun.wo_id).outerjoin(
        Die, ProcessRun.die_id == Die.id
    ).filter(
        QualityInspection.timestamp >= datetime.combine(start_dt, datetime.min.time()),
        QualityInspection.timestamp < datetime.combine(end_dt + timedelta(days=1), datetime.max.time())
    )

    measurements = query.all()

    # Extract bend-per-meter values from measured_values JSON
    bend_values = []
    by_profile = {}
    by_alloy = {}

    for inspection in measurements:
        if not inspection.measured_values or 'bend_per_meter' not in inspection.measured_values:
            continue

        try:
            value = float(inspection.measured_values['bend_per_meter'])
            bend_values.append(value)

            # Group by profile
            profile = inspection.profile_code or 'Unknown'
            if profile not in by_profile:
                by_profile[profile] = []
            by_profile[profile].append(value)

            # Group by alloy
            alloy = inspection.alloy or 'Unknown'
            if alloy not in by_alloy:
                by_alloy[alloy] = []
            by_alloy[alloy].append(value)

        except (ValueError, TypeError):
            continue

    if not bend_values:
        return {
            'total_measurements': 0,
            'avg_bend_per_meter': 0.0,
            'min_bend_per_meter': 0.0,
            'max_bend_per_meter': 0.0,
            'std_deviation': 0.0,
            'by_profile': {},
            'by_alloy': {},
        }

    # Calculate statistics
    avg_bend = statistics.mean(bend_values)
    min_bend = min(bend_values)
    max_bend = max(bend_values)
    std_dev = statistics.stdev(bend_values) if len(bend_values) > 1 else 0.0

    # Calculate per-profile averages
    profile_stats = {}
    for profile, values in by_profile.items():
        profile_stats[profile] = {
            'avg_bend_per_meter': round(statistics.mean(values), 4),
            'measurement_count': len(values),
            'min': min(values),
            'max': max(values),
        }

    # Calculate per-alloy averages
    alloy_stats = {}
    for alloy, values in by_alloy.items():
        alloy_stats[alloy] = {
            'avg_bend_per_meter': round(statistics.mean(values), 4),
            'measurement_count': len(values),
            'min': min(values),
            'max': max(values),
        }

    return {
        'total_measurements': len(bend_values),
        'avg_bend_per_meter': round(avg_bend, 4),
        'min_bend_per_meter': round(min_bend, 4),
        'max_bend_per_meter': round(max_bend, 4),
        'std_deviation': round(std_dev, 4),
        'by_profile': profile_stats,
        'by_alloy': alloy_stats,
        'target_avg_bend_per_meter': 0.5,  # Example target value
    }


# ============================================================================
# Helper Functions - Trends and Comparisons
# ============================================================================

def _get_quality_kpi_trends(end_dt, days_back=30):
    """Get daily quality KPI trends."""
    start_dt = end_dt - timedelta(days=days_back)

    # Get daily PPM trend
    query = db.session.query(
        cast(ProcessRun.started_at, Date).label('date'),
        func.sum(ProcessRun.expected_output).label('parts_produced'),
        func.count(QualityInspection.id).label('defects')
    ).join(
        QualityInspection, ProcessRun.wo_id == QualityInspection.wo_id
    ).filter(
        ProcessRun.started_at >= datetime.combine(start_dt, datetime.min.time()),
        ProcessRun.started_at < datetime.combine(end_dt + timedelta(days=1), datetime.max.time()),
        QualityInspection.inspection_type == 'post_extrusion',
        QualityInspection.pass_fail == False
    ).group_by(
        cast(ProcessRun.started_at, Date)
    ).order_by('date').all()

    trends = []
    for row in query:
        ppm = (row.defects / row.parts_produced * 1_000_000) if row.parts_produced > 0 else 0
        trends.append({
            'date': str(row.date),
            'parts_produced': row.parts_produced,
            'defects': row.defects,
            'ppm_rate': round(ppm, 2),
        })

    return trends


def _compute_metrics_by_dimension(start_dt, end_dt, dimension):
    """Compute metrics grouped by specified dimension."""
    if dimension == 'shift':
        # Get shift data from work orders or process runs
        query = db.session.query(
            ProcessRun.shift,
            func.sum(ProcessRun.expected_output).label('parts_produced'),
            func.count(QualityInspection.id).label('defects')
        ).join(
            QualityInspection, ProcessRun.wo_id == QualityInspection.wo_id
        ).filter(
            ProcessRun.started_at >= datetime.combine(start_dt, datetime.min.time()),
            ProcessRun.started_at < datetime.combine(end_dt + timedelta(days=1), datetime.max.time()),
            QualityInspection.inspection_type == 'post_extrusion',
            QualityInspection.pass_fail == False
        ).group_by(ProcessRun.shift).order_by(func.sum(ProcessRun.expected_output).desc()).all()

        result = {}
        for row in query:
            shift = row.shift or 'Unknown'
            ppm = (row.defects / row.parts_produced * 1_000_000) if row.parts_produced > 0 else 0
            result[shift] = {
                'shift': shift,
                'parts_produced': row.parts_produced,
                'defects': row.defects,
                'ppm_rate': round(ppm, 2),
            }
        return result

    elif dimension == 'operator':
        query = db.session.query(
            ProcessRun.operator_id,
            func.sum(ProcessRun.expected_output).label('parts_produced'),
            func.count(QualityInspection.id).label('defects')
        ).join(
            QualityInspection, ProcessRun.wo_id == QualityInspection.wo_id
        ).filter(
            ProcessRun.started_at >= datetime.combine(start_dt, datetime.min.time()),
            ProcessRun.started_at < datetime.combine(end_dt + timedelta(days=1), datetime.max.time()),
            QualityInspection.inspection_type == 'post_extrusion',
            QualityInspection.pass_fail == False
        ).group_by(ProcessRun.operator_id).order_by(func.sum(ProcessRun.expected_output).desc()).all()

        result = {}
        for row in query:
            operator = f"Operator {row.operator_id}" if row.operator_id else 'Unknown'
            ppm = (row.defects / row.parts_produced * 1_000_000) if row.parts_produced > 0 else 0
            result[operator] = {
                'operator': operator,
                'parts_produced': row.parts_produced,
                'defects': row.defects,
                'ppm_rate': round(ppm, 2),
            }
        return result

    return {}


def _get_top_performing_operators(start_dt, end_dt):
    """Get top performing operators by quality metrics."""
    query = db.session.query(
        ProcessRun.operator_id,
        func.sum(ProcessRun.expected_output).label('parts_produced'),
        func.count(QualityInspection.id).label('defects')
    ).join(
        QualityInspection, ProcessRun.wo_id == QualityInspection.wo_id
    ).filter(
        ProcessRun.started_at >= datetime.combine(start_dt, datetime.min.time()),
        ProcessRun.started_at < datetime.combine(end_dt + timedelta(days=1), datetime.max.time()),
        QualityInspection.inspection_type == 'post_extrusion',
        QualityInspection.pass_fail == False
    ).group_by(ProcessRun.operator_id).order_by(
        (func.sum(ProcessRun.expected_output) - func.count(QualityInspection.id)) /
        func.sum(ProcessRun.expected_output).desc()
    ).limit(10).all()

    operators = []
    for row in query:
        operator_id = f"Operator {row.operator_id}" if row.operator_id else 'Unknown'
        ppm = (row.defects / row.parts_produced * 1_000_000) if row.parts_produced > 0 else 0
        operators.append({
            'operator': operator_id,
            'parts_produced': row.parts_produced,
            'defects': row.defects,
            'ppm_rate': round(ppm, 2),
            'yield_pct': round((row.parts_produced - row.defects) / row.parts_produced * 100, 2) if row.parts_produced > 0 else 0,
        })

    return operators


def _compute_metrics_by_profile(start_dt, end_dt):
    """Compute quality metrics grouped by profile."""
    query = db.session.query(
        WorkOrder.profile_code,
        func.sum(ProcessRun.expected_output).label('parts_produced'),
        func.count(QualityInspection.id).label('defects')
    ).join(ProcessRun, WorkOrder.wo_id == ProcessRun.wo_id).join(
        QualityInspection, ProcessRun.wo_id == QualityInspection.wo_id
    ).filter(
        ProcessRun.started_at >= datetime.combine(start_dt, datetime.min.time()),
        ProcessRun.started_at < datetime.combine(end_dt + timedelta(days=1), datetime.max.time()),
        QualityInspection.inspection_type == 'post_extrusion',
        QualityInspection.pass_fail == False
    ).group_by(WorkOrder.profile_code).order_by(func.sum(ProcessRun.expected_output).desc()).all()

    result = {}
    for row in query:
        profile = row.profile_code or 'Unknown'
        ppm = (row.defects / row.parts_produced * 1_000_000) if row.parts_produced > 0 else 0
        result[profile] = {
            'profile': profile,
            'parts_produced': row.parts_produced,
            'defects': row.defects,
            'ppm_rate': round(ppm, 2),
            'yield_pct': round((row.parts_produced - row.defects) / row.parts_produced * 100, 2) if row.parts_produced > 0 else 0,
        }

    return result


def _compute_metrics_by_alloy(start_dt, end_dt):
    """Compute quality metrics grouped by alloy."""
    query = db.session.query(
        WorkOrder.alloy,
        func.sum(ProcessRun.expected_output).label('parts_produced'),
        func.count(QualityInspection.id).label('defects')
    ).join(ProcessRun, WorkOrder.wo_id == ProcessRun.wo_id).join(
        QualityInspection, ProcessRun.wo_id == QualityInspection.wo_id
    ).filter(
        ProcessRun.started_at >= datetime.combine(start_dt, datetime.min.time()),
        ProcessRun.started_at < datetime.combine(end_dt + timedelta(days=1), datetime.max.time()),
        QualityInspection.inspection_type == 'post_extrusion',
        QualityInspection.pass_fail == False
    ).group_by(WorkOrder.alloy).order_by(func.sum(ProcessRun.expected_output).desc()).all()

    result = {}
    for row in query:
        alloy = row.alloy or 'Unknown'
        ppm = (row.defects / row.parts_produced * 1_000_000) if row.parts_produced > 0 else 0
        result[alloy] = {
            'alloy': alloy,
            'parts_produced': row.parts_produced,
            'defects': row.defects,
            'ppm_rate': round(ppm, 2),
            'yield_pct': round((row.parts_produced - row.defects) / row.parts_produced * 100, 2) if row.parts_produced > 0 else 0,
        }

    return result


def _get_defect_analysis(start_dt, end_dt):
    """Get comprehensive defect analysis data."""

    # Get all defects with category and severity breakdowns
    query = db.session.query(
        DefectCode.code,
        DefectCode.name,
        DefectCode.category,
        DefectCode.severity,
        func.count(QualityInspection.id).label('count')
    ).join(
        QualityInspection, QualityInspection.defect_code == DefectCode.code
    ).filter(
        QualityInspection.inspection_type == 'post_extrusion',
        QualityInspection.pass_fail == False,
        QualityInspection.timestamp >= datetime.combine(start_dt, datetime.min.time()),
        QualityInspection.timestamp < datetime.combine(end_dt + timedelta(days=1), datetime.max.time())
    ).group_by(
        DefectCode.code, DefectCode.name, DefectCode.category, DefectCode.severity
    ).order_by(func.count(QualityInspection.id).desc()).all()

    by_category = {}
    severity_totals = {'minor': 0, 'moderate': 0, 'major': 0, 'critical': 0}

    for row in query:
        category = row.category or 'Unknown'
        if category not in by_category:
            by_category[category] = {
                'category': category,
                'total_defects': 0,
                'defect_codes': {},
            }

        severity = row.severity or 'minor'
        if severity not in severity_totals:
            severity = 'minor'

        by_category[category]['total_defects'] += row.count
        by_category[category]['defect_codes'][row.code] = {
            'name': row.name,
            'count': row.count,
            'severity': severity,
        }
        severity_totals[severity] += row.count

    return {
        'by_category': by_category,
        'severity_totals': severity_totals,
        'total_defects': sum(c['total_defects'] for c in by_category.values()),
    }
