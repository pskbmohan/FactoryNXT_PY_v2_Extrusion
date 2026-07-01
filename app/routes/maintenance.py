from flask import Blueprint, render_template, request, redirect, url_for, flash
from .. import db
from ..models import PmSchedule, MaintenanceLog, CalibrationRecord, Stencil
from datetime import datetime
import uuid

bp = Blueprint('maintenance', __name__, url_prefix='/maintenance')


@bp.route('/')
def index():
    due_pm = PmSchedule.query.order_by(PmSchedule.due_at).limit(20).all()
    recent_logs = MaintenanceLog.query.order_by(MaintenanceLog.performed_at.desc()).limit(20).all()
    return render_template('maintenance/index.html', due_pm=due_pm, recent_logs=recent_logs)


@bp.route('/pm')
def pm_list():
    records = PmSchedule.query.order_by(PmSchedule.due_at).all()
    return render_template('maintenance/pm_list.html', records=records)


@bp.route('/pm/new', methods=['GET', 'POST'])
def pm_new():
    if request.method == 'POST':
        pm = PmSchedule(
            id=str(uuid.uuid4()),
            machine_id=request.form['machine_id'],
            task_name=request.form['task_name'],
            frequency_days=int(request.form.get('frequency_days') or 0) or None,
            due_at=datetime.fromisoformat(request.form['due_at']).date() if request.form.get('due_at') else None,
            assigned_engineer=request.form.get('assigned_engineer'),
            status=request.form.get('status', 'Pending')
        )
        db.session.add(pm)
        db.session.commit()
        flash('PM Schedule created.', 'success')
        return redirect(url_for('maintenance.pm_list'))
    return render_template('maintenance/pm_form.html', pm=None)


@bp.route('/logs')
def logs():
    records = MaintenanceLog.query.order_by(MaintenanceLog.performed_at.desc()).limit(100).all()
    return render_template('maintenance/logs.html', records=records)


@bp.route('/logs/new', methods=['GET', 'POST'])
def log_new():
    if request.method == 'POST':
        log = MaintenanceLog(
            id=str(uuid.uuid4()),
            machine_id=request.form['machine_id'],
            log_type=request.form['log_type'],
            description=request.form['description'],
            action_taken=request.form.get('action_taken'),
            downtime_minutes=int(request.form.get('downtime_minutes') or 0) or None,
            technician_id=request.form.get('technician_id'),
            performed_at=datetime.fromisoformat(request.form['performed_at'])
        )
        db.session.add(log)
        db.session.commit()
        flash('Maintenance log saved.', 'success')
        return redirect(url_for('maintenance.logs'))
    return render_template('maintenance/log_form.html', log=None)


@bp.route('/calibration')
def calibration():
    records = CalibrationRecord.query.order_by(CalibrationRecord.next_due_at).all()
    return render_template('maintenance/calibration.html', records=records)


@bp.route('/calibration/new', methods=['GET', 'POST'])
def calibration_new():
    if request.method == 'POST':
        rec = CalibrationRecord(
            id=str(uuid.uuid4()),
            machine_id=request.form['machine_id'],
            result=request.form.get('result'),
            certificate_number=request.form.get('certificate_number'),
            performed_by=request.form.get('performed_by'),
            performed_at=datetime.fromisoformat(request.form['performed_at']),
            next_due_at=datetime.fromisoformat(request.form['next_due_at'])
        )
        db.session.add(rec)
        db.session.commit()
        flash('Calibration record saved.', 'success')
        return redirect(url_for('maintenance.calibration'))
    return render_template('maintenance/calibration_form.html', record=None)


@bp.route('/stencils')
def stencils():
    records = Stencil.query.order_by(Stencil.stencil_code).all()
    return render_template('maintenance/stencils.html', records=records)


@bp.route('/stencils/new', methods=['GET', 'POST'])
def stencil_new():
    if request.method == 'POST':
        s = Stencil(
            id=str(uuid.uuid4()),
            stencil_code=request.form['stencil_code'],
            part_number=request.form['part_number'],
            manufacturer=request.form.get('manufacturer'),
            print_count_limit=int(request.form.get('print_count_limit') or 0) or None,
            clean_cycle_interval=int(request.form.get('clean_cycle_interval') or 10),
            status=request.form.get('status', 'active')
        )
        db.session.add(s)
        db.session.commit()
        flash('Stencil created.', 'success')
        return redirect(url_for('maintenance.stencils'))
    return render_template('maintenance/stencil_form.html', stencil=None)
