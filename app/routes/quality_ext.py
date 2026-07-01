from flask import Blueprint, render_template, request, redirect, url_for, flash
from .. import db
from ..models import DefectRecord, Capa, InspectionPlan, GoldenBoard, PpapRecord, TestResult, BurnInSession, WorkOrder
from datetime import datetime
import uuid

bp = Blueprint('quality_ext', __name__, url_prefix='/quality/ext')


@bp.route('/defects')
def defects():
    records = DefectRecord.query.order_by(DefectRecord.detected_at.desc()).limit(100).all()
    return render_template('quality/defects.html', records=records)


@bp.route('/defects/new', methods=['GET', 'POST'])
def defect_new():
    if request.method == 'POST':
        d = DefectRecord(
            id=str(uuid.uuid4()),
            unit_id=request.form['unit_id'],
            wo_id=request.form.get('wo_id') or None,
            defect_code=request.form['defect_code'],
            defect_category=request.form['defect_category'],
            description=request.form.get('description'),
            disposition=request.form.get('disposition')
        )
        db.session.add(d)
        db.session.commit()
        flash('Defect recorded.', 'success')
        return redirect(url_for('quality_ext.defects'))
    work_orders = WorkOrder.query.all()
    return render_template('quality/defect_form.html', defect=None, work_orders=work_orders)


@bp.route('/capa')
def capa_list():
    records = Capa.query.order_by(Capa.created_at.desc()).all()
    return render_template('quality/capa_list.html', records=records)


@bp.route('/capa/new', methods=['GET', 'POST'])
def capa_new():
    if request.method == 'POST':
        capa = Capa(
            id=str(uuid.uuid4()),
            capa_number=request.form['capa_number'],
            ncr_id=request.form.get('ncr_id') or None,
            type=request.form.get('type'),
            title=request.form['title'],
            problem_statement=request.form['problem_statement'],
            status='open',
            due_date=datetime.fromisoformat(request.form['due_date']).date() if request.form.get('due_date') else None,
            owner_id=request.form.get('owner_id')
        )
        db.session.add(capa)
        db.session.commit()
        flash('CAPA created.', 'success')
        return redirect(url_for('quality_ext.capa_list'))
    return render_template('quality/capa_form.html', capa=None)


@bp.route('/inspection-plans')
def inspection_plans():
    records = InspectionPlan.query.order_by(InspectionPlan.part_number).all()
    return render_template('quality/inspection_plans.html', records=records)


@bp.route('/inspection-plans/new', methods=['GET', 'POST'])
def inspection_plan_new():
    if request.method == 'POST':
        # Derive part_number/operation_name from the extrusion target so the
        # legacy columns stay populated for existing list views.
        target_type = (request.form.get('target_type') or '').upper().strip()
        target_code = (request.form.get('target_code') or '').strip()
        operation_step = (request.form.get('operation_step') or '').strip()
        part_number = target_code or (request.form.get('part_number') or '').strip() or f"{target_type or 'PLAN'}-UNSPEC"
        operation_name = operation_step or (request.form.get('operation_name') or '').strip() or target_type or 'GENERAL'

        plan = InspectionPlan(
            id=str(uuid.uuid4()),
            part_number=part_number,
            operation_name=operation_name,
            target_type=target_type or None,
            target_code=target_code or None,
            operation_step=operation_step or None,
            aql_level=request.form.get('aql_level', '2.5'),
            sample_size=int(request.form.get('sample_size') or 80),
            accept_limit=int(request.form.get('accept_limit') or 2),
            reject_limit=int(request.form.get('reject_limit') or 3),
        )
        db.session.add(plan)
        db.session.commit()
        flash('Inspection plan saved.', 'success')
        return redirect(url_for('quality_ext.inspection_plans'))

    # Build selectable master data for extrusion-domain dropdowns
    from ..models import Die, Billet, SetpointProfile

    dies = Die.query.order_by(Die.die_code.asc()).all()
    billets = Billet.query.order_by(Billet.billet_code.asc()).limit(200).all()
    profile_codes = sorted({
        d.profile_code for d in Die.query.filter(Die.profile_code.isnot(None)).all()
        if d.profile_code
    })
    process_stages = ['HLS', 'PRESSING', 'QUENCHING', 'PULLING', 'STRETCHING',
                      'FINAL_CUT', 'OVEN']
    machine_setups = sorted({
        p.process_type for p in SetpointProfile.query.all() if p.process_type
    }) or process_stages

    return render_template(
        'quality/inspection_plan_form.html',
        plan=None,
        dies=dies,
        billets=billets,
        profile_codes=profile_codes,
        process_stages=process_stages,
        machine_setups=machine_setups,
    )


@bp.route('/golden-boards')
def golden_boards():
    records = GoldenBoard.query.filter_by(is_active=True).order_by(GoldenBoard.part_number).all()
    return render_template('quality/golden_boards.html', records=records)


@bp.route('/ppap')
def ppap_list():
    records = PpapRecord.query.order_by(PpapRecord.created_at.desc()).all()
    return render_template('quality/ppap_list.html', records=records)


@bp.route('/test-results')
def test_results():
    wo_id = request.args.get('wo_id')
    q = TestResult.query.order_by(TestResult.tested_at.desc())
    if wo_id:
        q = q.filter_by(wo_id=wo_id)
    records = q.limit(100).all()
    work_orders = WorkOrder.query.all()
    return render_template('quality/test_results.html', records=records, work_orders=work_orders, selected_wo=wo_id)


@bp.route('/burn-in')
def burn_in():
    sessions = BurnInSession.query.order_by(BurnInSession.started_at.desc()).limit(50).all()
    return render_template('quality/burn_in.html', sessions=sessions)


@bp.route('/burn-in/new', methods=['GET', 'POST'])
def burn_in_new():
    if request.method == 'POST':
        session = BurnInSession(
            id=str(uuid.uuid4()),
            wo_id=request.form['wo_id'],
            chamber_id=request.form.get('chamber_id'),
            planned_hours=float(request.form['planned_hours']),
            status='queued'
        )
        db.session.add(session)
        db.session.commit()
        flash('Burn-in session queued.', 'success')
        return redirect(url_for('quality_ext.burn_in'))
    work_orders = WorkOrder.query.all()
    return render_template('quality/burn_in_form.html', session=None, work_orders=work_orders)
