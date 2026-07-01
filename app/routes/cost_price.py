from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from .. import db
from ..models import CostPriceConfig
import uuid

bp = Blueprint("cost_price", __name__)


@bp.route("/cost-price")
def list_configs():
    configs = CostPriceConfig.query.order_by(CostPriceConfig.updated_at.desc()).all()
    return render_template("cost_price/list.html", configs=configs)


@bp.route("/cost-price/new", methods=["GET", "POST"])
def create_config():
    if request.method == "POST":
        part_number = request.form.get("part_number")
        if not part_number:
            flash("Part Number is required.", "error")
            return redirect(url_for("cost_price.create_config"))

        raw_material_cost_per_kg = float(request.form.get("raw_material_cost_per_kg") or 0)
        material_weight_kg = float(request.form.get("material_weight_kg") or 0)
        machine_rate_per_hour = float(request.form.get("machine_rate_per_hour") or 0)
        cycle_time_hours = float(request.form.get("cycle_time_hours") or 0)
        labor_rate_per_hour = float(request.form.get("labor_rate_per_hour") or 0)
        labor_hours = float(request.form.get("labor_hours") or 0)
        energy_kwh = float(request.form.get("energy_kwh") or 0)
        energy_rate_per_kwh = float(request.form.get("energy_rate_per_kwh") or 0)
        overhead_percent = float(request.form.get("overhead_percent") or 10)
        margin_percent = float(request.form.get("margin_percent") or 15)

        material_cost = raw_material_cost_per_kg * material_weight_kg
        machine_cost = machine_rate_per_hour * cycle_time_hours
        labor_cost = labor_rate_per_hour * labor_hours
        energy_cost = energy_kwh * energy_rate_per_kwh
        subtotal = material_cost + machine_cost + labor_cost + energy_cost
        calculated_cost = subtotal * (1 + overhead_percent / 100)
        break_even_price = calculated_cost * (1 + margin_percent / 100)

        config = CostPriceConfig(
            id=str(uuid.uuid4()),
            part_number=part_number,
            revision=request.form.get("revision") or "A",
            raw_material_cost_per_kg=raw_material_cost_per_kg,
            material_weight_kg=material_weight_kg,
            machine_rate_per_hour=machine_rate_per_hour,
            cycle_time_hours=cycle_time_hours,
            labor_rate_per_hour=labor_rate_per_hour,
            labor_hours=labor_hours,
            energy_kwh=energy_kwh,
            energy_rate_per_kwh=energy_rate_per_kwh,
            overhead_percent=overhead_percent,
            margin_percent=margin_percent,
            calculated_cost=round(calculated_cost, 2),
            break_even_price=round(break_even_price, 2),
            currency=request.form.get("currency") or "USD",
        )
        db.session.add(config)
        db.session.commit()
        flash("Cost price configuration created.", "success")
        return redirect(url_for("cost_price.detail", id=config.id))

    return render_template("cost_price/form.html", config=None)


@bp.route("/cost-price/<id>")
def detail(id):
    config = CostPriceConfig.query.get_or_404(id)
    return render_template("cost_price/detail.html", config=config)


@bp.route("/cost-price/<id>/edit", methods=["GET", "POST"])
def update_config(id):
    config = CostPriceConfig.query.get_or_404(id)
    if request.method == "POST":
        config.part_number = request.form.get("part_number") or config.part_number
        config.revision = request.form.get("revision") or "A"
        config.raw_material_cost_per_kg = float(request.form.get("raw_material_cost_per_kg") or 0)
        config.material_weight_kg = float(request.form.get("material_weight_kg") or 0)
        config.machine_rate_per_hour = float(request.form.get("machine_rate_per_hour") or 0)
        config.cycle_time_hours = float(request.form.get("cycle_time_hours") or 0)
        config.labor_rate_per_hour = float(request.form.get("labor_rate_per_hour") or 0)
        config.labor_hours = float(request.form.get("labor_hours") or 0)
        config.energy_kwh = float(request.form.get("energy_kwh") or 0)
        config.energy_rate_per_kwh = float(request.form.get("energy_rate_per_kwh") or 0)
        config.overhead_percent = float(request.form.get("overhead_percent") or 10)
        config.margin_percent = float(request.form.get("margin_percent") or 15)
        config.currency = request.form.get("currency") or "USD"

        material_cost = config.raw_material_cost_per_kg * config.material_weight_kg
        machine_cost = config.machine_rate_per_hour * config.cycle_time_hours
        labor_cost = config.labor_rate_per_hour * config.labor_hours
        energy_cost = config.energy_kwh * config.energy_rate_per_kwh
        subtotal = material_cost + machine_cost + labor_cost + energy_cost
        config.calculated_cost = round(subtotal * (1 + config.overhead_percent / 100), 2)
        config.break_even_price = round(config.calculated_cost * (1 + config.margin_percent / 100), 2)

        db.session.commit()
        flash("Cost price configuration updated.", "success")
        return redirect(url_for("cost_price.detail", id=config.id))

    return render_template("cost_price/form.html", config=config)


@bp.route("/cost-price/<id>/delete", methods=["POST"])
def delete_config(id):
    config = CostPriceConfig.query.get_or_404(id)
    db.session.delete(config)
    db.session.commit()
    flash("Cost price configuration deleted.", "success")
    return redirect(url_for("cost_price.list_configs"))


@bp.route("/api/cost-price/<id>/breakdown")
def breakdown_json(id):
    config = CostPriceConfig.query.get_or_404(id)
    material = config.raw_material_cost_per_kg * config.material_weight_kg
    machine = config.machine_rate_per_hour * config.cycle_time_hours
    labor = config.labor_rate_per_hour * config.labor_hours
    energy = config.energy_kwh * config.energy_rate_per_kwh
    subtotal = material + machine + labor + energy
    overhead = subtotal * config.overhead_percent / 100
    margin = (subtotal + overhead) * config.margin_percent / 100

    return jsonify({
        "part_number": config.part_number,
        "breakdown": {
            "material": round(material, 2),
            "machine": round(machine, 2),
            "labor": round(labor, 2),
            "energy": round(energy, 2),
            "overhead": round(overhead, 2),
            "margin": round(margin, 2),
        },
        "calculated_cost": config.calculated_cost,
        "break_even_price": config.break_even_price,
    })
