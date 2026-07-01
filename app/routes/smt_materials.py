from flask import Blueprint, render_template, request, redirect, url_for, flash
from .. import db
from ..models import SolderPasteLot, GoldenBoard, PpapRecord, WorkOrder
from datetime import datetime
import uuid

bp = Blueprint("smt_materials", __name__)


# ─── Solder Paste Lots ────────────────────────────────────────────────────────

@bp.route("/solder-paste")
def solder_paste_list():
    lots = SolderPasteLot.query.order_by(SolderPasteLot.created_at.desc()).all()
    return render_template("smt_materials/solder_paste_list.html", lots=lots)


@bp.route("/solder-paste/new", methods=["GET", "POST"])
def solder_paste_new():
    if request.method == "POST":
        lot = SolderPasteLot(
            id=str(uuid.uuid4()),
            lot_number=request.form["lot_number"],
            manufacturer=request.form["manufacturer"],
            part_number=request.form["part_number"],
            quantity_g=float(request.form["quantity_g"]),
            expiry_date=datetime.strptime(request.form["expiry_date"], "%Y-%m-%d").date(),
            floor_life_hours=float(request.form.get("floor_life_hours", 8)),
            status="sealed",
        )
        db.session.add(lot)
        db.session.commit()
        flash("Solder paste lot created.", "success")
        return redirect(url_for("smt_materials.solder_paste_list"))
    return render_template("smt_materials/solder_paste_form.html", lot=None)


@bp.route("/solder-paste/<lot_id>/open", methods=["POST"])
def solder_paste_open(lot_id):
    lot = SolderPasteLot.query.get_or_404(lot_id)
    if lot.status == "sealed":
        lot.status = "open"
        lot.opened_at = datetime.utcnow()
        from datetime import timedelta
        lot.must_discard_by = lot.opened_at + timedelta(hours=lot.floor_life_hours)
        db.session.commit()
        flash(f"Lot {lot.lot_number} marked as opened.", "success")
    return redirect(url_for("smt_materials.solder_paste_list"))


@bp.route("/solder-paste/<lot_id>/discard", methods=["POST"])
def solder_paste_discard(lot_id):
    lot = SolderPasteLot.query.get_or_404(lot_id)
    lot.status = "discarded"
    db.session.commit()
    flash(f"Lot {lot.lot_number} discarded.", "warning")
    return redirect(url_for("smt_materials.solder_paste_list"))


# ─── Golden Boards ────────────────────────────────────────────────────────────

@bp.route("/golden-boards")
def golden_board_list():
    boards = GoldenBoard.query.order_by(GoldenBoard.created_at.desc()).all()
    return render_template("smt_materials/golden_board_list.html", boards=boards)


@bp.route("/golden-boards/new", methods=["GET", "POST"])
def golden_board_new():
    if request.method == "POST":
        board = GoldenBoard(
            id=str(uuid.uuid4()),
            part_number=request.form["part_number"],
            serial_number=request.form["serial_number"],
            machine_id=request.form.get("machine_id") or None,
            limit_file_path=request.form.get("limit_file_path") or None,
            is_active=True,
        )
        db.session.add(board)
        db.session.commit()
        flash("Golden board registered.", "success")
        return redirect(url_for("smt_materials.golden_board_list"))
    return render_template("smt_materials/golden_board_form.html", board=None)


@bp.route("/golden-boards/<board_id>/deactivate", methods=["POST"])
def golden_board_deactivate(board_id):
    board = GoldenBoard.query.get_or_404(board_id)
    board.is_active = False
    db.session.commit()
    flash(f"Golden board {board.serial_number} deactivated.", "warning")
    return redirect(url_for("smt_materials.golden_board_list"))


# ─── PPAP Records ─────────────────────────────────────────────────────────────

@bp.route("/ppap")
def ppap_list():
    records = (
        PpapRecord.query
        .outerjoin(WorkOrder, PpapRecord.wo_id == WorkOrder.id)
        .add_entity(WorkOrder)
        .order_by(PpapRecord.created_at.desc())
        .all()
    )
    return render_template("smt_materials/ppap_list.html", records=records)


@bp.route("/ppap/new", methods=["GET", "POST"])
def ppap_new():
    work_orders = WorkOrder.query.order_by(WorkOrder.order_number).all()
    if request.method == "POST":
        record = PpapRecord(
            id=str(uuid.uuid4()),
            part_number=request.form["part_number"],
            wo_id=request.form.get("wo_id") or None,
            level=int(request.form["level"]),
            status="in_progress",
        )
        db.session.add(record)
        db.session.commit()
        flash("PPAP record created.", "success")
        return redirect(url_for("smt_materials.ppap_list"))
    return render_template("smt_materials/ppap_form.html", record=None, work_orders=work_orders)


@bp.route("/ppap/<record_id>/approve", methods=["POST"])
def ppap_approve(record_id):
    record = PpapRecord.query.get_or_404(record_id)
    record.status = "approved"
    record.approved_at = datetime.utcnow()
    db.session.commit()
    flash(f"PPAP record for {record.part_number} approved.", "success")
    return redirect(url_for("smt_materials.ppap_list"))


@bp.route("/ppap/<record_id>/reject", methods=["POST"])
def ppap_reject(record_id):
    record = PpapRecord.query.get_or_404(record_id)
    record.status = "rejected"
    db.session.commit()
    flash(f"PPAP record for {record.part_number} rejected.", "danger")
    return redirect(url_for("smt_materials.ppap_list"))
