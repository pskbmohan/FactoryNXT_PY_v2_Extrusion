from flask import Blueprint, render_template, request, redirect, url_for, flash
from .. import db
from ..models import ProductionSchedule, ShiftCalendar, SmtLine, WorkOrder
from datetime import datetime
import uuid

bp = Blueprint('scheduling', __name__, url_prefix='/scheduling')


@bp.route('/')
def index():
    schedule = ProductionSchedule.query.order_by(ProductionSchedule.scheduled_start).limit(50).all()
    return render_template('scheduling/index.html', schedule=schedule)


@bp.route('/new', methods=['GET', 'POST'])
def new():
    if request.method == 'POST':
        entry = ProductionSchedule(
            id=str(uuid.uuid4()),
            plant_id=request.form['plant_id'],
            wo_id=request.form['wo_id'],
            smt_line_id=request.form.get('smt_line_id') or None,
            scheduled_start=datetime.fromisoformat(request.form['scheduled_start']),
            scheduled_end=datetime.fromisoformat(request.form['scheduled_end']),
            sequence_order=int(request.form.get('sequence_order') or 0) or None,
            is_locked='is_locked' in request.form
        )
        db.session.add(entry)
        db.session.commit()
        flash('Schedule entry created.', 'success')
        return redirect(url_for('scheduling.index'))
    work_orders = WorkOrder.query.filter(WorkOrder.status.in_(['Released', 'Draft'])).all()
    lines = SmtLine.query.filter_by(is_active=True).all()
    return render_template('scheduling/form.html', entry=None, work_orders=work_orders, lines=lines)


@bp.route('/shifts')
def shifts():
    records = ShiftCalendar.query.order_by(ShiftCalendar.day_of_week, ShiftCalendar.start_time).all()
    return render_template('scheduling/shifts.html', records=records)


@bp.route('/shifts/new', methods=['GET', 'POST'])
def shift_new():
    if request.method == 'POST':
        from datetime import time as dtime
        st = request.form['start_time'].split(':')
        et = request.form['end_time'].split(':')
        shift = ShiftCalendar(
            id=str(uuid.uuid4()),
            plant_id=request.form['plant_id'],
            shift_name=request.form['shift_name'],
            day_of_week=int(request.form.get('day_of_week') or 0),
            start_time=dtime(int(st[0]), int(st[1])),
            end_time=dtime(int(et[0]), int(et[1])),
            is_active='is_active' in request.form
        )
        db.session.add(shift)
        db.session.commit()
        flash('Shift created.', 'success')
        return redirect(url_for('scheduling.shifts'))
    return render_template('scheduling/shift_form.html', shift=None)
