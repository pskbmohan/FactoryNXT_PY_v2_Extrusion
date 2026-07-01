from flask import Blueprint, render_template, request, redirect, url_for, flash
from .. import db
from ..models import Kit, FeederReel, SolderPasteLot, WorkOrder
from datetime import datetime
import uuid

bp = Blueprint('kitting', __name__, url_prefix='/kitting')


@bp.route('/')
def index():
    kits = Kit.query.order_by(Kit.created_at.desc()).limit(50).all()
    return render_template('kitting/index.html', kits=kits)


@bp.route('/kits/<kit_id>')
def kit_detail(kit_id):
    kit = Kit.query.get_or_404(kit_id)
    return render_template('kitting/kit_detail.html', kit=kit)


@bp.route('/kits/new', methods=['GET', 'POST'])
def kit_new():
    if request.method == 'POST':
        kit = Kit(
            id=str(uuid.uuid4()),
            wo_id=request.form['wo_id'],
            status='pending'
        )
        db.session.add(kit)
        db.session.commit()
        flash('Kit created.', 'success')
        return redirect(url_for('kitting.index'))
    work_orders = WorkOrder.query.filter(WorkOrder.status.in_(['Released'])).all()
    return render_template('kitting/kit_form.html', kit=None, work_orders=work_orders)


@bp.route('/feeder-reels')
def feeder_reels():
    reels = FeederReel.query.order_by(FeederReel.created_at.desc()).limit(100).all()
    return render_template('kitting/feeder_reels.html', reels=reels)


@bp.route('/feeder-reels/new', methods=['GET', 'POST'])
def reel_new():
    if request.method == 'POST':
        qty = int(request.form['quantity_initial'])
        reel = FeederReel(
            id=str(uuid.uuid4()),
            reel_id=request.form['reel_id'],
            part_number=request.form['part_number'],
            quantity_initial=qty,
            quantity_remaining=qty,
            feeder_slot=request.form.get('feeder_slot'),
            machine_id=request.form.get('machine_id'),
            wo_id=request.form.get('wo_id') or None
        )
        db.session.add(reel)
        db.session.commit()
        flash('Feeder reel registered.', 'success')
        return redirect(url_for('kitting.feeder_reels'))
    work_orders = WorkOrder.query.all()
    return render_template('kitting/reel_form.html', reel=None, work_orders=work_orders)


@bp.route('/solder-paste')
def solder_paste():
    lots = SolderPasteLot.query.order_by(SolderPasteLot.created_at.desc()).all()
    return render_template('kitting/solder_paste.html', lots=lots)


@bp.route('/solder-paste/new', methods=['GET', 'POST'])
def paste_new():
    if request.method == 'POST':
        from datetime import date
        lot = SolderPasteLot(
            id=str(uuid.uuid4()),
            lot_number=request.form['lot_number'],
            manufacturer=request.form['manufacturer'],
            part_number=request.form['part_number'],
            quantity_g=float(request.form['quantity_g']),
            expiry_date=datetime.fromisoformat(request.form['expiry_date']).date(),
            floor_life_hours=float(request.form.get('floor_life_hours') or 8),
            status='sealed'
        )
        db.session.add(lot)
        db.session.commit()
        flash('Solder paste lot registered.', 'success')
        return redirect(url_for('kitting.solder_paste'))
    return render_template('kitting/paste_form.html', lot=None)
