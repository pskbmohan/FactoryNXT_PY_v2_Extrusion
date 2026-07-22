"""Master Data page routes - serves HTML pages for master data management.

All page-render URLs live here under /master-data/* so the JSON API
at /api/master/* (in master_data_bom.py) stays a clean JSON surface.
"""

from flask import Blueprint, render_template

bp = Blueprint("master_data_pages", __name__, url_prefix="/master-data")


# ───────────────── BOM-driven master data ────────────────────────────────────

@bp.route("/customers")
def customers_page():
    """Render Customers master data page."""
    return render_template("master_data_bom/customers.html")


@bp.route("/part-numbers")
def part_numbers_page():
    """Render Part Numbers master data page."""
    return render_template("master_data_bom/part_numbers.html")


@bp.route("/boms")
def boms_page():
    """Render BOM management page."""
    return render_template("master_data_bom/boms.html")


@bp.route("/customer-part-map")
def customer_part_map_page():
    """Render Customer-Part Mapping page."""
    return render_template("master_data_bom/customer_part_map.html")


# ───────────────── Catalog / reference master data ──────────────────────────

@bp.route("/coating-colors")
def coating_colors_page():
    """Render Coating Colors master data page."""
    return render_template("master_data_bom/coating_colors.html")


@bp.route("/raw-material-types")
def raw_material_types_page():
    """Render Raw Material Types master data page."""
    return render_template("master_data_bom/raw_material_types.html")


@bp.route("/alloy-compositions")
def alloy_compositions_page():
    """Render Alloy Compositions master data page."""
    return render_template("master_data_bom/alloy_compositions.html")


@bp.route("/finishing-process-types")
def finishing_process_types_page():
    """Render Finishing Process Types master data page."""
    return render_template("master_data_bom/finishing_process_types.html")


@bp.route("/packaging-specs")
def packaging_specs_page():
    """Render Packaging Specs master data page."""
    return render_template("master_data_bom/packaging_specs.html")


@bp.route("/defect-codes")
def defect_codes_page():
    """Render Defect Codes master data page."""
    return render_template("master_data_bom/defect_codes.html")


@bp.route("/quality-parameters")
def quality_parameters_page():
    """Render Quality Parameters (setpoint profiles) master data page."""
    return render_template("master_data_bom/quality_parameters.html")
