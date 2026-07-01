from flask import Blueprint, render_template, request, redirect, url_for, flash
from .. import db
from ..models import PcbPanel, PcbBoard, UnitHistory, WorkOrder
from datetime import datetime
import uuid

bp = Blueprint('pcb', __name__, url_prefix='/pcb')


@bp.route('/')
def index():
    panels = PcbPanel.query.order_by(PcbPanel.created_at.desc()).limit(50).all()
    return render_template('pcb/index.html', panels=panels)


@bp.route('/panels/<panel_id>')
def panel_detail(panel_id):
    panel = PcbPanel.query.get_or_404(panel_id)
    return render_template('pcb/panel_detail.html', panel=panel)


@bp.route('/panels/new', methods=['GET', 'POST'])
def panel_new():
    if request.method == 'POST':
        panel = PcbPanel(
            id=str(uuid.uuid4()),
            wo_id=request.form['wo_id'],
            panel_serial=request.form['panel_serial'],
            board_count=int(request.form.get('board_count') or 4),
            status='In-Assembly'
        )
        db.session.add(panel)
        db.session.commit()
        flash('Panel created.', 'success')
        return redirect(url_for('pcb.index'))
    work_orders = WorkOrder.query.filter(WorkOrder.status == 'Released').all()
    return render_template('pcb/panel_form.html', panel=None, work_orders=work_orders)


@bp.route('/boards')
def boards():
    wo_id = request.args.get('wo_id')
    q = PcbBoard.query.order_by(PcbBoard.created_at.desc())
    if wo_id:
        q = q.filter_by(wo_id=wo_id)
    boards = q.limit(100).all()
    work_orders = WorkOrder.query.all()
    return render_template('pcb/boards.html', boards=boards, work_orders=work_orders, selected_wo=wo_id)


@bp.route('/boards/<board_id>')
def board_detail(board_id):
    board = PcbBoard.query.get_or_404(board_id)
    history = UnitHistory.query.filter_by(board_id=board_id).order_by(UnitHistory.created_at.asc()).all()
    return render_template('pcb/board_detail.html', board=board, history=history)


@bp.route('/boards/<board_id>/history/add', methods=['POST'])
def history_add(board_id):
    PcbBoard.query.get_or_404(board_id)
    entry = UnitHistory(
        id=str(uuid.uuid4()),
        board_id=board_id,
        operation_name=request.form['operation_name'],
        status=request.form['status'],
        machine_id=request.form.get('machine_id')
    )
    db.session.add(entry)
    db.session.commit()
    flash('History entry added.', 'success')
    return redirect(url_for('pcb.board_detail', board_id=board_id))
