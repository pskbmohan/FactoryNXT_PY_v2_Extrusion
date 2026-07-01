from flask import Blueprint, render_template, request, redirect, url_for, flash
from .. import db
from ..models import GenealogyEvent, RepairRecord, PcbBoard, WorkOrder
from datetime import datetime
import uuid

bp = Blueprint('genealogy', __name__, url_prefix='/genealogy')


def _json_field_like(column, key, value):
    """Return a filter expression matching JSON `column` containing key=value.

    Works on PostgreSQL (JSON/JSONB) and SQLite by casting the JSON column
    to text and doing a substring match on the serialised fragment. The
    JSON fragment is produced by the seed script without whitespace after
    the colon, so this matches reliably.
    """
    return db.cast(column, db.Text).contains(f'"{key}": "{value}"')


@bp.route('/')
def index():
    return render_template('genealogy/index.html')


@bp.route('/search')
def search():
    serial = request.args.get('serial', '').strip()
    billet_code = request.args.get('billet_code', '').strip()
    die_code = request.args.get('die_code', '').strip()
    order_number = request.args.get('order_number', '').strip()
    alloy = request.args.get('alloy', '').strip()

    board = None
    events = []
    repairs = []
    extrusion_unit = None  # dict summarising a non-PCB searched unit

    # --- Extrusion-oriented search paths ---
    if billet_code:
        events = GenealogyEvent.query.filter(
            _json_field_like(GenealogyEvent.data, 'billet', billet_code)
        ).order_by(GenealogyEvent.occurred_at.asc()).all()
        if events:
            first_data = events[0].data or {}
            extrusion_unit = {
                'identifier': billet_code,
                'label': 'Billet Code',
                'alloy': first_data.get('alloy', '-'),
                'die_code': first_data.get('die_code', '-'),
                'order_number': first_data.get('order_number', '-'),
            }
    elif die_code:
        events = GenealogyEvent.query.filter(
            _json_field_like(GenealogyEvent.data, 'die_code', die_code)
        ).order_by(GenealogyEvent.occurred_at.asc()).all()
        if events:
            first_data = events[0].data or {}
            extrusion_unit = {
                'identifier': die_code,
                'label': 'Die Code',
                'alloy': first_data.get('alloy', '-'),
                'billet': first_data.get('billet', '-'),
                'order_number': first_data.get('order_number', '-'),
            }
    elif order_number:
        events = GenealogyEvent.query.filter(
            _json_field_like(GenealogyEvent.data, 'order_number', order_number)
        ).order_by(GenealogyEvent.occurred_at.asc()).all()
        if events:
            first_data = events[0].data or {}
            extrusion_unit = {
                'identifier': order_number,
                'label': 'Work Order',
                'alloy': first_data.get('alloy', '-'),
                'die_code': first_data.get('die_code', '-'),
                'billet': first_data.get('billet', '-'),
            }
    elif alloy:
        events = GenealogyEvent.query.filter(
            _json_field_like(GenealogyEvent.data, 'alloy', alloy)
        ).order_by(GenealogyEvent.occurred_at.asc()).all()
        if events:
            first_data = events[0].data or {}
            extrusion_unit = {
                'identifier': alloy,
                'label': 'Alloy',
                'die_code': first_data.get('die_code', '-'),
                'billet': first_data.get('billet', '-'),
                'order_number': first_data.get('order_number', '-'),
            }
    elif serial:
        # Legacy PCB board serial search (kept for back-compat)
        board = PcbBoard.query.filter_by(serial_number=serial).first()
        if board:
            events = GenealogyEvent.query.filter_by(board_id=board.id).order_by(GenealogyEvent.occurred_at.asc()).all()
            repairs = RepairRecord.query.filter_by(board_id=board.id).order_by(RepairRecord.repaired_at.asc()).all()

    return render_template(
        'genealogy/search.html',
        serial=serial,
        billet_code=billet_code,
        die_code=die_code,
        order_number=order_number,
        alloy=alloy,
        board=board,
        events=events,
        repairs=repairs,
        extrusion_unit=extrusion_unit,
        has_search=any([serial, billet_code, die_code, order_number, alloy]),
    )


@bp.route('/events')
def events():
    board_id = request.args.get('board_id')
    q = GenealogyEvent.query.order_by(GenealogyEvent.occurred_at.desc())
    if board_id:
        q = q.filter_by(board_id=board_id)
    events = q.limit(100).all()
    return render_template('genealogy/events.html', events=events)


@bp.route('/repairs')
def repairs():
    records = RepairRecord.query.order_by(RepairRecord.repaired_at.desc()).limit(100).all()
    return render_template('genealogy/repairs.html', records=records)


@bp.route('/repairs/new', methods=['GET', 'POST'])
def repair_new():
    if request.method == 'POST':
        repair = RepairRecord(
            id=str(uuid.uuid4()),
            board_id=request.form['board_id'],
            wo_id=request.form['wo_id'],
            ncr_id=request.form.get('ncr_id') or None,
            reference_designator=request.form['reference_designator'],
            removed_part_number=request.form['removed_part_number'],
            removed_lot=request.form.get('removed_lot'),
            installed_part_number=request.form['installed_part_number'],
            installed_lot=request.form.get('installed_lot'),
            reason_code=request.form['reason_code'],
            operator_id=request.form['operator_id']
        )
        db.session.add(repair)
        db.session.commit()
        flash('Repair record saved.', 'success')
        return redirect(url_for('genealogy.repairs'))
    boards = PcbBoard.query.all()
    work_orders = WorkOrder.query.all()
    return render_template('genealogy/repair_form.html', repair=None, boards=boards, work_orders=work_orders)
