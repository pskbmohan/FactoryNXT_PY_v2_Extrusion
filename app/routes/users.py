from flask import Blueprint, render_template, request, redirect, url_for, flash
from .. import db
from ..models import Plant, Role, UserProfile, OperatorCertification, AuditLog, ElectronicSignature
from datetime import datetime
import uuid

bp = Blueprint('users', __name__, url_prefix='/users')


@bp.route('/')
def index():
    profiles = UserProfile.query.filter_by(is_active=True).order_by(UserProfile.full_name).all()
    return render_template('users/index.html', profiles=profiles)


@bp.route('/new', methods=['GET', 'POST'])
def new():
    if request.method == 'POST':
        profile = UserProfile(
            id=str(uuid.uuid4()),
            plant_id=request.form.get('plant_id') or None,
            role_id=request.form.get('role_id') or None,
            full_name=request.form['full_name'],
            employee_id=request.form['employee_id'],
            role=request.form['role'],
            is_active=True
        )
        db.session.add(profile)
        db.session.commit()
        flash('User profile created.', 'success')
        return redirect(url_for('users.index'))
    plants = Plant.query.all()
    roles = Role.query.all()
    return render_template('users/form.html', profile=None, plants=plants, roles=roles)


@bp.route('/certifications')
def certifications():
    records = OperatorCertification.query.filter_by(is_active=True).order_by(OperatorCertification.expiry_date).all()
    return render_template('users/certifications.html', records=records)


@bp.route('/certifications/new', methods=['GET', 'POST'])
def certification_new():
    if request.method == 'POST':
        cert = OperatorCertification(
            id=str(uuid.uuid4()),
            user_id=request.form['user_id'],
            operation_code=request.form['operation_code'],
            certification_level=request.form['certification_level'],
            certified_at=datetime.fromisoformat(request.form['certified_at']),
            expiry_date=datetime.fromisoformat(request.form['expiry_date']).date() if request.form.get('expiry_date') else None,
            certified_by=request.form.get('certified_by'),
            is_active=True
        )
        db.session.add(cert)
        db.session.commit()
        flash('Certification saved.', 'success')
        return redirect(url_for('users.certifications'))
    profiles = UserProfile.query.filter_by(is_active=True).all()
    return render_template('users/certification_form.html', cert=None, profiles=profiles)


@bp.route('/audit-log')
def audit_log():
    records = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(200).all()
    return render_template('users/audit_log.html', records=records)


@bp.route('/plants')
def plants():
    records = Plant.query.order_by(Plant.name).all()
    return render_template('users/plants.html', records=records)


@bp.route('/plants/new', methods=['GET', 'POST'])
def plant_new():
    if request.method == 'POST':
        plant = Plant(
            id=str(uuid.uuid4()),
            code=request.form['code'],
            name=request.form['name'],
            timezone=request.form.get('timezone', 'UTC')
        )
        db.session.add(plant)
        db.session.commit()
        flash('Plant created.', 'success')
        return redirect(url_for('users.plants'))
    return render_template('users/plant_form.html', plant=None)


@bp.route('/roles')
def roles():
    records = Role.query.order_by(Role.display_name).all()
    return render_template('users/roles.html', records=records)
