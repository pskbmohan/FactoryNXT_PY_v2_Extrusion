from flask import Blueprint, render_template, request
from sqlalchemy import func
from .. import db
from ..models import TraceabilityRecord, GenealogyEvent, CustomerOrder, Billet, Die, WorkOrder

bp = Blueprint("traceability", __name__)


@bp.route("/traceability", methods=["GET"])
def traceability_dashboard():
    """Extrusion traceability dashboard - shows material flow and process events."""
    entity_type = request.args.get("entity_type", "").upper()
    event_type = request.args.get("event_type", "")

    query = TraceabilityRecord.query
    if entity_type and entity_type != "ALL":
        query = query.filter(TraceabilityRecord.entity_type == entity_type)
    if event_type:
        query = query.filter(TraceabilityRecord.event_type == event_type)

    records = query.order_by(TraceabilityRecord.occurred_at.desc()).limit(100).all()

    # KPIs
    total_traces = TraceabilityRecord.query.count()

    entity_types = db.session.query(TraceabilityRecord.entity_type).distinct().all()
    entity_types = [e[0] for e in entity_types if e[0]]

    # Count per entity type for KPI cards
    raw_counts = (
        db.session.query(TraceabilityRecord.entity_type, func.count(TraceabilityRecord.id))
        .group_by(TraceabilityRecord.entity_type)
        .all()
    )
    entity_counts = {et: c for et, c in raw_counts if et}
    # Ensure all expected types have a count (0 if absent) so template is safe
    for et in ("ORDER", "PROCESS_RUN", "BILLET", "DIE", "WORK_ORDER"):
        entity_counts.setdefault(et, 0)

    # Recent events by type
    recent_inspections = TraceabilityRecord.query.filter(
        TraceabilityRecord.event_type.contains("INSPECTION")
    ).order_by(TraceabilityRecord.occurred_at.desc()).limit(5).all()

    return render_template(
        "traceability/dashboard.html",
        records=records,
        total_traces=total_traces,
        entity_types=entity_types,
        entity_counts=entity_counts,
        recent_inspections=recent_inspections,
        selected_entity_type=entity_type,
        selected_event_type=event_type,
    )


class _EventView:
    """Uniform wrapper so the material template can iterate over both
    TraceabilityRecord and GenealogyEvent objects with a consistent
    attribute interface (entity_type, entity_id, machine_name, result).
    """
    __slots__ = ("_obj", "_kind")

    def __init__(self, obj, kind):
        object.__setattr__(self, "_obj", obj)
        object.__setattr__(self, "_kind", kind)

    def __getattr__(self, name):
        obj = self._obj
        kind = self._kind
        if name == "entity_type":
            if kind == "trace":
                return obj.entity_type
            # GenealogyEvent — infer entity type from the event stage
            ev = (obj.event_type or "").upper()
            if "DIE" in ev or "NITRID" in ev:
                return "DIE"
            if "BILLET" in ev:
                return "BILLET"
            return "ORDER"
        if name == "entity_id":
            if kind == "trace":
                return obj.entity_id
            return getattr(obj, "part_number", None) or getattr(obj, "lot_number", None) or str(obj.id)
        if name == "machine_name":
            return getattr(obj, "machine_id", None) or None
        if name == "result":
            data = getattr(obj, "data", None)
            if isinstance(data, dict):
                return data.get("status", "")
            return ""
        return getattr(obj, name)


@bp.route("/traceability/material", methods=["GET"])
def material_traceability():
    """Material traceability - billet and die tracking."""
    part = request.args.get("part")
    lot = request.args.get("lot")

    # Query both traceability records and genealogy events
    raw_events = []

    # Traceability records for materials
    query = TraceabilityRecord.query.filter(
        TraceabilityRecord.entity_type.in_(["BILLET", "DIE", "ORDER", "PROCESS_RUN"])
    )
    if part:
        query = query.filter(TraceabilityRecord.entity_id.contains(part))
    if lot:
        query = query.filter(TraceabilityRecord.data.contains(f'"{lot}"'))

    for rec in query.order_by(TraceabilityRecord.occurred_at.desc()).limit(100).all():
        raw_events.append(_EventView(rec, "trace"))

    # Genealogy events
    gen_query = GenealogyEvent.query
    if part:
        gen_query = gen_query.filter(GenealogyEvent.part_number == part)
    if lot:
        gen_query = gen_query.filter(GenealogyEvent.lot_number == lot)

    for ev in gen_query.order_by(GenealogyEvent.occurred_at.desc()).limit(100).all():
        raw_events.append(_EventView(ev, "genealogy"))

    # Sort by occurred_at descending
    raw_events.sort(key=lambda e: e.occurred_at or __import__("datetime").datetime.min, reverse=True)

    return render_template(
        "traceability/material.html",
        events=raw_events[:200],
        part=part or "",
        lot=lot or "",
    )


@bp.route("/traceability/genealogy", methods=["GET"])
def genealogy_view():
    """Process genealogy - track work orders and process runs."""
    order_number = request.args.get("order_number")
    wo = None
    process_events = []
    genealogy_events = []

    if order_number:
        # Find work order
        wo = WorkOrder.query.filter_by(order_number=order_number).first()
        if wo:
            # Get traceability records for this WO
            process_events = TraceabilityRecord.query.filter(
                (TraceabilityRecord.entity_type == "WORK_ORDER") &
                (TraceabilityRecord.entity_id == wo.id)
            ).order_by(TraceabilityRecord.occurred_at.asc()).all()

            # Get genealogy events
            genealogy_events = GenealogyEvent.query.filter_by(
                work_order_id=wo.id
            ).order_by(GenealogyEvent.occurred_at.asc()).all()

    return render_template(
        "traceability/genealogy.html",
        work_order=wo,
        process_events=process_events,
        genealogy_events=genealogy_events,
        order_number=order_number or "",
    )
