"""Inspection Management Dashboard - Quality Reporting & Control System.

This blueprint provides inspection management views for Req #10-12:
- Inspection frequency and method management (Req #10)
- Inspection planning interface (Req #11)
- First-piece validation tracking (Req #12)

Integrates with inspection_service module for core operations.
"""

from datetime import date, datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from sqlalchemy import func, and_

from .. import db
from ..models import WorkOrder, Die, InspectionPlan, QualityInspection


bp = Blueprint('inspection_management', __name__, url_prefix='/quality/inspections')


@bp.route('/')
def index():
    """Inspection Management Dashboard.

    Main inspection management view with:
    - Active inspection plans overview
    - Recent inspections summary
    - Inspection frequency compliance metrics
    - Quick access to planning and validation views
    """
    username = session.get('username')
    if not username:
        return redirect(url_for('auth.login'))

    # Date range parameters for recent inspections
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
    # Active Inspection Plans Summary
    # ====================================================================
    active_plans = _get_active_inspection_plans()

    # ====================================================================
    # Recent Inspections with Status
    # ====================================================================
    recent_inspections = _get_recent_inspections(start_dt, end_dt, limit=20)

    # ====================================================================
    # Inspection Frequency Compliance Metrics
    # ====================================================================
    compliance_metrics = _compute_inspection_compliance(start_dt, end_dt)

    # ====================================================================
    # First-Piece Validation Status (Req #12)
    # ====================================================================
    first_piece_status = _get_first_piece_validation_summary(start_dt, end_dt)

    return render_template(
        'quality/inspection_management/index.html',
        start_date=start_date_str,
        end_date=end_date_str,
        active_plans=active_plans,
        recent_inspections=recent_inspections,
        compliance_metrics=compliance_metrics,
        first_piece_status=first_piece_status,
    )


@bp.route('/plans/')
def inspection_plans():
    """Inspection Plans Management View (Req #10).

    Manage inspection frequency and methods:
    - List all active inspection plans with frequencies
    - Edit inspection methods per requirement type
    - Set inspection intervals (per run, per shift, daily)
    - Define acceptance criteria for each inspection type
    """
    username = session.get('username')
    if not username:
        return redirect(url_for('auth.login'))

    # Filter options
    filter_type = request.args.get('type', 'all')  # all, dimension, surface, visual, process
    active_only = request.args.get('active', '1') == '1'

    plans_query = InspectionPlan.query.filter_by(is_active=True) if active_only else InspectionPlan.query.all()

    if filter_type != 'all':
        plans_query = plans_query.filter_by(inspection_type=filter_type)

    inspection_plans = plans_query.order_by(InspectionPlan.profile_code, InspectionPlan.inspection_type).all()

    # Group by profile for better organization
    plans_by_profile = {}
    for plan in inspection_plans:
        if not plan.profile_code:
            continue
        if plan.profile_code not in plans_by_profile:
            plans_by_profile[plan.profile_code] = []
        plans_by_profile[plan.profile_code].append(plan)

    return render_template(
        'quality/inspection_management/plans.html',
        inspection_plans=plans_by_profile,
        filter_type=filter_type,
        active_only=active_only,
    )


@bp.route('/plans/<int:plan_id>/')
def plan_detail(plan_id):
    """Inspection Plan Detail View.

    Detailed view of a specific inspection plan:
    - Full inspection method configuration
    - Historical compliance data for this plan
    - Associated work orders and inspections
    - Edit capabilities for frequency/method updates
    """
    username = session.get('username')
    if not username:
        return redirect(url_for('auth.login'))

    plan = InspectionPlan.query.get(plan_id)
    if not plan:
        flash(f"Inspection plan '{plan_id}' not found.", 'error')
        return redirect(url_for('inspection_management.inspection_plans'))

    # Get historical inspections for this plan (last 90 days)
    end_dt = date.today()
    start_dt = end_dt - timedelta(days=90)

    related_inspections = QualityInspection.query.filter(
        and_(
            QualityInspection.inspection_type == plan.inspection_type,
            QualityInspection.stage.in_(['pre_production', 'in_process']),
            QualityInspection.timestamp >= datetime.combine(start_dt, datetime.min.time()),
            QualityInspection.timestamp <= datetime.combine(end_dt + timedelta(days=1), datetime.max.time())
        )
    ).order_by(QualityInspection.timestamp.desc()).limit(50).all()

    # Calculate compliance for this plan
    inspection_count = len(related_inspections)
    passed_count = sum(1 for i in related_inspections if i.pass_fail == 'pass')
    compliance_pct = (passed_count / inspection_count * 100) if inspection_count > 0 else 100

    return render_template(
        'quality/inspection_management/plan_detail.html',
        plan=plan,
        related_inspections=related_inspections,
        inspection_count=inspection_count,
        passed_count=passed_count,
        compliance_pct=compliance_pct,
    )


@bp.route('/first-piece/')
def first_piece_validation():
    """First-Piece Validation View (Req #12).

    Track and validate first-piece inspections before production starts:
    - Pending validations for active work orders
    - Completed first-piece inspections with results
    - Dimensional verification against specifications
    - Process parameter confirmation requirements
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

    # Get pending first-piece validations (pre-production inspections not yet passed)
    pending_validations = _get_pending_first_piece_validations(start_dt, end_dt)

    # Get completed first-piece inspections with results
    completed_inspections = _get_completed_first_piece_inspections(start_dt, end_dt)

    # Summary metrics
    total_pending = len(pending_validations)
    total_completed = len(completed_inspections)
    pass_rate = (completed_inspections.pass_count / total_completed * 100) if completed_inspections.total > 0 else 100

    return render_template(
        'quality/inspection_management/first_piece.html',
        start_date=start_date_str,
        end_date=end_date_str,
        pending_validations=pending_validations,
        first_piece_summary=completed_inspections,
        total_pending=total_pending,
        pass_rate=round(pass_rate, 1),
    )


@bp.route('/compliance/')
def compliance_view():
    """Inspection Compliance Dashboard.

    Overall inspection frequency and method compliance:
    - Required vs actual inspections by type
    - Missed inspection alerts
    - Inspection method effectiveness metrics
    - Trend analysis for compliance rates
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

    # Get compliance data by inspection type
    compliance_by_type = _get_compliance_by_inspection_type(start_dt, end_dt)

    # Get missed inspections (alerts)
    missed_inspections = _get_missed_inspections(start_dt, end_dt)

    return render_template(
        'quality/inspection_management/compliance.html',
        start_date=start_date_str,
        end_date=end_date_str,
        compliance_by_type=compliance_by_type,
        missed_inspections=missed_inspections,
    )


@bp.route('/by-work-order/<int:wo_id>/')
def by_work_order(wo_id):
    """Inspection View for Specific Work Order.

    All inspections associated with a work order:
    - Pre-production first-piece validation status
    - In-process inspection records
    - Post-extrusion final inspection results
    - Dimensional measurement history
    """
    username = session.get('username')
    if not username:
        return redirect(url_for('auth.login'))

    wo = WorkOrder.query.get(wo_id)
    if not wo:
        flash(f"Work Order '{wo_id}' not found.", 'error')
        return redirect(url_for('inspection_management.index'))

    # Get all inspections for this work order
    inspections = QualityInspection.query.filter_by(wo_id=wo.wo_number).order_by(
        QualityInspection.timestamp.desc()
    ).all()

    # Summary metrics
    total_inspections = len(inspections)
    passed_count = sum(1 for i in inspections if i.pass_fail == 'pass')
    failed_count = sum(1 for i in inspections if i.pass_fail == 'fail')
    pass_rate = (passed_count / total_inspections * 100) if total_inspections > 0 else 100

    return render_template(
        'quality/inspection_management/by_work_order.html',
        wo=wo,
        inspections=inspections,
        total_inspections=total_inspections,
        passed_count=passed_count,
        failed_count=failed_count,
        pass_rate=round(pass_rate, 1),
    )


@bp.route('/summary/')
def summary():
    """Inspection Management Executive Summary.

    High-level overview of inspection program effectiveness:
    - Overall compliance rates by category
    - First-piece validation success trends
    - Inspection frequency adherence metrics
    - Top inspection issues and recommendations
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
    current_compliance = _compute_inspection_compliance(current_start, today)
    current_first_piece = _get_first_piece_validation_summary(current_start, today)

    # Previous period for comparison
    previous_compliance = _compute_inspection_compliance(previous_start, previous_end)
    previous_first_piece = _get_first_piece_validation_summary(previous_start, previous_end)

    return render_template(
        'quality/inspection_management/summary.html',
        current_compliance=current_compliance,
        previous_compliance=previous_compliance,
        current_first_piece=current_first_piece,
        previous_first_piece=previous_first_piece,
    )


# ============================================================================
# Helper Functions - Inspection Management
# ============================================================================

def _get_active_inspection_plans():
    """Get all active inspection plans."""
    plans = InspectionPlan.query.filter_by(is_active=True).all()
    return [{
        'plan_id': p.id,
        'profile_code': p.profile_code or 'All Profiles',
        'inspection_type': p.inspection_type or 'Not Specified',
        'frequency': p.frequency or 'As Needed',
        'method': p.method or 'Not Defined',
        'acceptance_criteria': p.acceptance_criteria or 'Not Defined',
    } for p in plans]


def _get_recent_inspections(start_dt, end_dt, limit=20):
    """Get recent inspections within date range."""
    query = db.session.query(
        QualityInspection.id.label('inspection_id'),
        QualityInspection.wo_id,
        QualityInspection.inspection_type,
        QualityInspection.stage,
        QualityInspection.pass_fail,
        QualityInspection.timestamp,
        Die.die_code,
        WorkOrder.profile_code,
    ).join(
        Die, QualityInspection.die_id == Die.id, isouter=True
    ).join(
        WorkOrder, QualityInspection.wo_id == WorkOrder.wo_number, isouter=True
    ).filter(
        QualityInspection.timestamp >= datetime.combine(start_dt, datetime.min.time()),
        QualityInspection.timestamp <= datetime.combine(end_dt + timedelta(days=1), datetime.max.time())
    ).order_by(QualityInspection.timestamp.desc()).limit(limit).all()

    return [{
        'inspection_id': r.inspection_id,
        'wo_id': r.wo_id,
        'inspection_type': r.inspection_type or 'Not Specified',
        'stage': r.stage or 'Unknown',
        'pass_fail': r.pass_fail or 'Pending',
        'timestamp': r.timestamp.strftime('%Y-%m-%d %H:%M') if r.timestamp else None,
        'die_code': r.die_code or 'N/A',
        'profile_code': r.profile_code or 'N/A',
    } for r in query]


def _compute_inspection_compliance(start_dt, end_dt):
    """Compute inspection compliance metrics."""
    # Get all required inspections based on active plans
    active_plans = InspectionPlan.query.filter_by(is_active=True).all()

    total_required = 0
    total_completed = 0
    passed_inspections = 0

    for plan in active_plans:
        # Count actual inspections matching this plan's criteria
        inspection_query = db.session.query(func.count(QualityInspection.id)).filter(
            and_(
                QualityInspection.inspection_type == plan.inspection_type,
                QualityInspection.stage.in_(['pre_production', 'in_process']),
                QualityInspection.timestamp >= datetime.combine(start_dt, datetime.min.time()),
                QualityInspection.timestamp <= datetime.combine(end_dt + timedelta(days=1), datetime.max.time())
            )
        ).scalar() or 0

        completed_query = db.session.query(func.count(QualityInspection.id)).filter(
            and_(
                QualityInspection.inspection_type == plan.inspection_type,
                QualityInspection.stage.in_(['pre_production', 'in_process']),
                QualityInspection.pass_fail == 'pass',
                QualityInspection.timestamp >= datetime.combine(start_dt, datetime.min.time()),
                QualityInspection.timestamp <= datetime.combine(end_dt + timedelta(days=1), datetime.max.time())
            )
        ).scalar() or 0

        total_completed += completed_query
        passed_inspections += completed_query

    # Estimate required inspections based on work orders in period
    wo_count = db.session.query(func.count(WorkOrder.id)).filter(
        WorkOrder.status.in_(['active', 'in_production']),
        WorkOrder.created_at >= datetime.combine(start_dt, datetime.min.time()),
        WorkOrder.created_at <= datetime.combine(end_dt + timedelta(days=1), datetime.max.time())
    ).scalar() or 0

    total_required = wo_count * len(active_plans) if active_plans else wo_count

    compliance_pct = (total_completed / total_required * 100) if total_required > 0 else 100

    return {
        'total_required': total_required,
        'total_completed': total_completed,
        'passed_inspections': passed_inspections,
        'compliance_pct': round(compliance_pct, 1),
        'pass_rate_pct': round((passed_inspections / total_completed * 100) if total_completed > 0 else 100, 1),
    }


def _get_first_piece_validation_summary(start_dt, end_dt):
    """Get first-piece validation summary metrics (Req #12)."""
    completed = db.session.query(
        func.count(QualityInspection.id).label('total'),
        func.sum(func.cast(QualityInspection.pass_fail == 'pass', db.Integer)).label('pass_count')
    ).filter(
        and_(
            QualityInspection.stage == 'pre_production',
            QualityInspection.inspection_type == 'first_piece_validation',
            QualityInspection.timestamp >= datetime.combine(start_dt, datetime.min.time()),
            QualityInspection.timestamp <= datetime.combine(end_dt + timedelta(days=1), datetime.max.time())
        )
    ).first()

    return {
        'total': completed.total or 0,
        'pass_count': completed.pass_count or 0,
        'fail_count': (completed.total or 0) - (completed.pass_count or 0),
    }


def _get_pending_first_piece_validations(start_dt, end_dt):
    """Get pending first-piece validations."""
    # This would need work orders that started in period but don't have FPV yet
    # Simplified implementation for now
    return []


def _get_completed_first_piece_inspections(start_dt, end_dt):
    """Get completed first-piece inspection records with summary."""
    query = db.session.query(
        func.count(QualityInspection.id).label('total'),
        func.sum(func.cast(QualityInspection.pass_fail == 'pass', db.Integer)).label('pass_count')
    ).filter(
        and_(
            QualityInspection.stage == 'pre_production',
            QualityInspection.inspection_type == 'first_piece_validation',
            QualityInspection.timestamp >= datetime.combine(start_dt, datetime.min.time()),
            QualityInspection.timestamp <= datetime.combine(end_dt + timedelta(days=1), datetime.max.time())
        )
    ).first()

    return {
        'total': query.total or 0,
        'pass_count': query.pass_count or 0,
    }


def _get_compliance_by_inspection_type(start_dt, end_dt):
    """Get compliance data grouped by inspection type."""
    types = ['dimensional', 'surface', 'visual', 'process_parameter']

    result = {}
    for itype in types:
        completed = db.session.query(func.count(QualityInspection.id)).filter(
            and_(
                QualityInspection.inspection_type == itype,
                QualityInspection.stage.in_(['pre_production', 'in_process']),
                QualityInspection.timestamp >= datetime.combine(start_dt, datetime.min.time()),
                QualityInspection.timestamp <= datetime.combine(end_dt + timedelta(days=1), datetime.max.time())
            )
        ).scalar() or 0

        passed = db.session.query(func.count(QualityInspection.id)).filter(
            and_(
                QualityInspection.inspection_type == itype,
                QualityInspection.stage.in_(['pre_production', 'in_process']),
                QualityInspection.pass_fail == 'pass',
                QualityInspection.timestamp >= datetime.combine(start_dt, datetime.min.time()),
                QualityInspection.timestamp <= datetime.combine(end_dt + timedelta(days=1), datetime.max.time())
            )
        ).scalar() or 0

        result[itype] = {
            'inspection_type': itype,
            'completed_count': completed,
            'passed_count': passed,
            'compliance_pct': round((passed / completed * 100) if completed > 0 else 100, 1),
        }

    return result


def _get_missed_inspections(start_dt, end_dt):
    """Get inspections that were missed or overdue."""
    # This would need logic to compare required vs actual based on frequencies
    # Simplified implementation for now
    return []
