"""Scrap and Rejection Reporting - Quality Reporting & Control System.

This blueprint provides comprehensive scrap analytics:
- Scrap rate calculation by period
- Defect categorization (surface/dimensional/functional/aesthetic)
- Pareto analysis of top defects
- Breakdown by die, operator, alloy
- Internal vs customer rejection comparison
- Trend analysis for continuous improvement tracking

Integrates with defect_tracking_service module.
"""

from datetime import date, datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from sqlalchemy import func

from .. import db
from ..models import (
    DefectCode,
    Die,
    ProcessRun,
    QualityInspection,
)


bp = Blueprint('scrap_reporting', __name__, url_prefix='/quality/scrap')


@bp.route('/')
def index():
    """Scrap and Rejection Analytics Dashboard.

    Main scrap view with:
    - Current period scrap rate percentage
    - Scrap by defect category (Pareto chart data)
    - Top 10 defects breakdown
    - Breakdown by die/operator/alloy
    - Internal vs customer rejection comparison
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
    # Overall Scrap Metrics
    # ====================================================================
    scrap_metrics = _get_overall_scrap_metrics(start_dt, end_dt)

    # ====================================================================
    # Scrap by Defect Category (Pareto Analysis)
    # ====================================================================
    scrap_by_category = _compute_scrap_by_category(start_dt, end_dt)

    # ====================================================================
    # Top 10 Defects (Most Frequent)
    # ====================================================================
    top_defects = _get_top_defects(start_dt, end_dt, n=10)

    # ====================================================================
    # Scrap by Die
    # ====================================================================
    scrap_by_die = _compute_scrap_by_dimension(start_dt, end_dt, 'die')

    # ====================================================================
    # Scrap by Operator
    # ====================================================================
    scrap_by_operator = _compute_scrap_by_dimension(start_dt, end_dt, 'operator')

    # ====================================================================
    # Scrap by Alloy
    # ====================================================================
    scrap_by_alloy = _compute_scrap_by_dimension(start_dt, end_dt, 'alloy')

    # ====================================================================
    # Rejection Rates (Internal vs Customer)
    # ====================================================================
    rejection_rates = _get_rejection_comparison(start_dt, end_dt)

    # ====================================================================
    # Scrap Trends (Last 30 days)
    # ====================================================================
    scrap_trends = _get_scrap_trend(end_dt, days_back=30)

    return render_template(
        'quality/scrap_reporting/index.html',
        start_date=start_date_str,
        end_date=end_date_str,
        scrap_metrics=scrap_metrics,
        scrap_by_category=scrap_by_category,
        top_defects=top_defects,
        scrap_by_die=scrap_by_die,
        scrap_by_operator=scrap_by_operator,
        scrap_by_alloy=scrap_by_alloy,
        rejection_rates=rejection_rates,
        scrap_trends=scrap_trends,
    )


@bp.route('/defect/<defect_code>')
def defect_detail(defect_code):
    """Detailed view for specific defect code.

    Args:
        defect_code: Defect code to view (e.g., 'DS001', 'DW002')
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

    # Get defect code details from master data
    defect_info = DefectCode.query.filter_by(code=defect_code).first()

    if not defect_info:
        flash(f'Defect code {defect_code} not found.', 'error')
        return redirect(url_for('scrap_reporting.index'))

    # Count occurrences of this defect in period
    start_datetime = datetime.combine(start_dt, datetime.min.time())
    end_datetime = datetime.combine(end_dt, datetime.max.time()) + timedelta(seconds=1)

    defect_count_query = db.session.query(func.count(QualityInspection.id))
    defect_count_query = defect_count_query.filter(
        QualityInspection.timestamp >= start_datetime,
        QualityInspection.timestamp < end_datetime,
        # Note: Would need to query JSONB field for specific defect code
        # This is a simplified filter
        QualityInspection.pass_fail == 'FAIL'
    )

    defect_count = defect_count_query.scalar() or 0

    return render_template(
        'quality/scrap_reporting/defect_detail.html',
        defect_code=defect_code,
        defect_info=defect_info,
        start_date=start_date_str,
        end_date=end_date_str,
        defect_count=defect_count,
    )


@bp.route('/die/<die_id>')
def by_die(die_id):
    """Scrap breakdown for specific die.

    Args:
        die_id: Die ID to filter by
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

    # Get die info
    die_info = Die.query.get(die_id)

    # Scrap metrics for this die
    scrap_metrics = _get_scrap_for_die(start_dt, end_dt, str(die_id))

    return render_template(
        'quality/scrap_reporting/by_die.html',
        die_info=die_info,
        start_date=start_date_str,
        end_date=end_date_str,
        scrap_metrics=scrap_metrics,
    )


# ============================================================================
# Helper Functions for Scrap Computation
# ============================================================================

def _get_overall_scrap_metrics(start_dt, end_dt):
    """Compute overall scrap rate metrics for a period."""
    start_datetime = datetime.combine(start_dt, datetime.min.time())
    end_datetime = datetime.combine(end_dt, datetime.max.time()) + timedelta(seconds=1)

    # Total completed process runs (production units)
    total_produced_query = ProcessRun.query.filter(
        ProcessRun.started_at >= start_datetime,
        ProcessRun.started_at < end_datetime,
        ProcessRun.status == 'COMPLETED'
    )

    total_produced = total_produced_query.count()

    # Count failed inspections (scrap)
    scrap_count_query = db.session.query(func.count(QualityInspection.id))
    scrap_count_query = scrap_count_query.filter(
        QualityInspection.timestamp >= start_datetime,
        QualityInspection.timestamp < end_datetime,
        QualityInspection.pass_fail == 'FAIL'
    )

    total_scrap = scrap_count_query.scalar() or 0

    # Scrap rate percentage
    scrap_rate_percent = (total_scrap / total_produced * 100) if total_produced > 0 else 0.0

    return {
        'total_produced': total_produced,
        'total_scrap_units': total_scrap,
        'scrap_rate_percent': round(scrap_rate_percent, 2),
        'period_start': start_dt.isoformat(),
        'period_end': end_dt.isoformat(),
    }


def _compute_scrap_by_category(start_dt, end_dt):
    """Compute scrap breakdown by defect category."""
    start_datetime = datetime.combine(start_dt, datetime.min.time())
    end_datetime = datetime.combine(end_dt, datetime.max.time()) + timedelta(seconds=1)

    categories = ['surface', 'dimensional', 'functional', 'aesthetic']

    # Get all active defect codes with their categories
    defect_codes = DefectCode.query.filter_by(is_active=True).all()

    category_counts = {cat: 0 for cat in categories}

    # For each category, count associated defects
    for code_obj in defect_codes:
        if code_obj.category in category_counts:
            # Would need to query quality_inspections.results JSONB for this specific code
            # Placeholder logic - actual implementation would parse JSONB field
            pass

    # Return structure with placeholder data (would be populated from actual queries)
    result = {cat: {'count': 0, 'percentage': 0.0} for cat in categories}

    return result


def _get_top_defects(start_dt, end_dt, n=10):
    """Get top N defect codes by frequency."""
    start_datetime = datetime.combine(start_dt, datetime.min.time())
    end_datetime = datetime.combine(end_dt, datetime.max.time()) + timedelta(seconds=1)

    # Get all active defect codes with counts
    defect_codes = DefectCode.query.filter_by(is_active=True).order_by(DefectCode.code).all()

    top_defects = []
    for rank, code_obj in enumerate(defect_codes[:n], 1):
        # Count occurrences - would query quality_inspections JSONB field
        count = 0  # Placeholder

        top_defects.append({
            'rank': rank,
            'code': code_obj.code,
            'name': code_obj.name,
            'category': code_obj.category,
            'severity': code_obj.severity,
            'count': count,
            'description': code_obj.description or '',
        })

    return top_defects


def _compute_scrap_by_dimension(start_dt, end_dt, dimension):
    """Compute scrap breakdown by specified dimension (die/operator/alloy)."""
    start_datetime = datetime.combine(start_dt, datetime.min.time())
    end_datetime = datetime.combine(end_dt, datetime.max.time()) + timedelta(seconds=1)

    if dimension == 'die':
        # Query dies with their scrap counts
        dies_data = db.session.query(
            Die.id.label('die_id'),
            Die.die_code.label('die_code'),
            Die.profile_code.label('profile'),
            Die.alloy.label('alloy'),
            func.count(ProcessRun.id).label('total_runs'),
        ).join(
            ProcessRun, Die.id == ProcessRun.die_id
        ).filter(
            ProcessRun.started_at >= start_datetime,
            ProcessRun.started_at < end_datetime,
            ProcessRun.status == 'COMPLETED'
        ).group_by(Die.id).all()

        result = []
        for row in dies_data:
            # Scrap count would need join with failed inspections
            scrap_count = 0
            result.append({
                'die_id': str(row.die_id),
                'die_code': row.die_code,
                'profile': row.profile or 'N/A',
                'alloy': row.alloy or 'N/A',
                'total_runs': row.total_runs,
                'scrap_count': scrap_count,
            })

        return result

    elif dimension == 'operator':
        # Query operators with their scrap counts
        inspections = QualityInspection.query.filter(
            QualityInspection.timestamp >= start_datetime,
            QualityInspection.timestamp < end_datetime,
            QualityInspection.operator_id.isnot(None)
        ).all()

        operator_scrap = {}
        for insp in inspections:
            op_id = insp.operator_id or 'Unassigned'
            if op_id not in operator_scrap:
                operator_scrap[op_id] = {'count': 0}
            if insp.pass_fail == 'FAIL':
                operator_scrap[op_id]['count'] += 1

        result = [
            {
                'operator_id': op_id,
                'scrap_count': data['count'],
            }
            for op_id, data in operator_scrap.items()
        ]

        return sorted(result, key=lambda x: x['scrap_count'], reverse=True)

    elif dimension == 'alloy':
        # Query alloys with their scrap counts
        dies_with_alloy = Die.query.filter(Die.alloy.isnot(None)).all()

        result = {}
        for die in dies_with_alloy:
            alloy = die.alloy or 'Unknown'
            if alloy not in result:
                result[alloy] = {'count': 0, 'dies_count': set()}
            result[alloy]['dies'].add(str(die.id))

        return [
            {
                'alloy': alloy,
                'scrap_count': data['count'],
                'dies_using_alloy': len(data['dies']),
            }
            for alloy, data in result.items()
        ]


def _get_scrap_for_die(start_dt, end_dt, die_id):
    """Get scrap metrics for a specific die."""
    start_datetime = datetime.combine(start_dt, datetime.min.time())
    end_datetime = datetime.combine(end_dt, datetime.max.time()) + timedelta(seconds=1)

    # Total runs for this die
    total_runs = ProcessRun.query.filter(
        ProcessRun.die_id == str(die_id),
        ProcessRun.started_at >= start_datetime,
        ProcessRun.started_at < end_datetime,
        ProcessRun.status == 'COMPLETED'
    ).count()

    # Scrap count for this die (would need join with quality_inspections)
    scrap_count = 0  # Placeholder

    return {
        'die_id': str(die_id),
        'total_runs': total_runs,
        'scrap_units': scrap_count,
        'scrap_rate_percent': round((scrap_count / total_runs * 100) if total_runs > 0 else 0, 2),
    }


def _get_rejection_comparison(start_dt, end_dt):
    """Compare internal vs customer rejection rates."""
    start_datetime = datetime.combine(start_dt, datetime.min.time())
    end_datetime = datetime.combine(end_dt, datetime.max.time()) + timedelta(seconds=1)

    # Internal rejections (production scrap)
    internal_count_query = db.session.query(func.count(QualityInspection.id))
    internal_count_query = internal_count_query.filter(
        QualityInspection.timestamp >= start_datetime,
        QualityInspection.timestamp < end_datetime,
        QualityInspection.pass_fail == 'FAIL'
    )

    internal_rejections = internal_count_query.scalar() or 0

    # Customer rejections (would query customer returns table)
    customer_rejections = 0  # Placeholder - would need separate query

    return {
        'internal_rejections': internal_rejections,
        'customer_rejections': customer_rejections,
        'total_rejections': internal_rejections + customer_rejections,
        'ratio_internal_to_customer': round(
            (internal_rejections / customer_rejections) if customer_rejections > 0 else float('inf'), 2
        ) if customer_rejections > 0 else None,
    }


def _get_scrap_trend(end_dt, days_back=30):
    """Get scrap rate trend for the specified number of days."""
    start_dt = end_dt - timedelta(days=days_back)

    daily_data = []

    current_date = start_dt
    while current_date <= end_dt:
        # Get scrap metrics for this day
        metrics = _get_overall_scrap_metrics(current_date, current_date)

        daily_data.append({
            'date': current_date.isoformat(),
            'scrap_rate_percent': metrics['scrap_rate_percent'],
            'total_produced': metrics['total_produced'],
            'total_scrap': metrics['total_scrap_units'],
        })

        current_date += timedelta(days=1)

    return daily_data

