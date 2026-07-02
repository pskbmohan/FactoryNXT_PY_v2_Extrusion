from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from .config import Config

db = SQLAlchemy()
migrate = Migrate()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)

    from .routes.dashboard import bp as dashboard_bp
    from .routes.auth import bp as auth_bp
    from .routes.api import bp as api_bp
    from .routes.work_orders import bp as work_orders_bp
    from .routes.ncr import bp as ncr_bp
    from .routes.bom import bp as bom_bp
    from .routes.routing import bp as routing_bp
    from .routes.routing_builder import bp as routing_builder_bp
    from .routes.quality_ext import bp as quality_bp
    from .routes.machines import bp as machines_bp
    from .routes.inventory import bp as inventory_bp
    from .routes.production import bp as production_bp
    from .routes.traceability import bp as traceability_bp
    from .routes.admin import bp as admin_bp
    from .routes.smt_materials import bp as smt_materials_bp
    from .routes.operations import bp as operations_bp
    from .routes.scheduling import bp as scheduling_bp
    from .routes.kitting import bp as kitting_bp
    from .routes.oee import bp as oee_bp
    from .routes.pcb import bp as pcb_bp
    from .routes.maintenance import bp as maintenance_bp
    from .routes.genealogy import bp as genealogy_bp
    from .routes.stations import bp as stations_bp
    from .routes.integrations import bp as integrations_bp
    from .routes.planning import bp as planning_bp
    from .routes.tool_shop import bp as tool_shop_bp
    from .routes.process_line import bp as process_line_bp
    from .routes.kpi_alerts import bp as kpi_alerts_bp
    # aps_page_bp  → Blueprint('aps', ...)       → url_for('aps.cockpit') etc.
    # aps_bp (bp)  → Blueprint('aps_resource')   → JSON API under /aps/resource/
    from .routes.aps import bp as aps_bp
    from .routes.aps import aps_page_bp

    # ── Extrusion add-on modules (cost price, dies, furnace, etc.) ──────
    from .routes.cost_price import bp as cost_price_bp
    from .routes.material_receipt import bp as material_receipt_bp
    from .routes.dies import bp as dies_mgmt_bp
    from .routes.coating_schedule import bp as coating_schedule_bp
    from .routes.containers import bp as containers_bp
    from .routes.furnace import bp as furnace_bp
    from .routes.finishing import bp as finishing_bp
    from .routes.logistics import bp as logistics_bp
    from .routes.docs import docs_bp

    # Import APS models so their tables are created by db.create_all()
    # and registered with SQLAlchemy's metadata.
    from . import models_aps  # noqa: F401

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(work_orders_bp)
    app.register_blueprint(ncr_bp)
    app.register_blueprint(bom_bp)
    app.register_blueprint(routing_bp)
    app.register_blueprint(routing_builder_bp)
    app.register_blueprint(quality_bp)
    app.register_blueprint(machines_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(production_bp)
    app.register_blueprint(traceability_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(smt_materials_bp)
    app.register_blueprint(operations_bp)
    app.register_blueprint(scheduling_bp)
    app.register_blueprint(kitting_bp)
    app.register_blueprint(oee_bp)
    app.register_blueprint(pcb_bp)
    app.register_blueprint(maintenance_bp)
    app.register_blueprint(genealogy_bp)
    app.register_blueprint(stations_bp)
    app.register_blueprint(integrations_bp)
    app.register_blueprint(planning_bp)
    app.register_blueprint(tool_shop_bp)
    app.register_blueprint(process_line_bp)
    app.register_blueprint(kpi_alerts_bp)
    app.register_blueprint(aps_page_bp)   # page views  → 'aps.cockpit', 'aps.scheduler'
    app.register_blueprint(aps_bp)        # JSON API    → 'aps_resource.list_mappings' etc.

    # ── Extrusion add-on modules ──────────────────────────────────────
    app.register_blueprint(cost_price_bp)
    app.register_blueprint(material_receipt_bp)
    app.register_blueprint(dies_mgmt_bp)
    app.register_blueprint(coating_schedule_bp)
    app.register_blueprint(containers_bp)
    app.register_blueprint(furnace_bp)
    app.register_blueprint(finishing_bp)
    app.register_blueprint(logistics_bp)
    app.register_blueprint(docs_bp)

    # ── Flask CLI: seed-planning ──────────────────────────────────────────
    @app.cli.command("seed-planning")
    def seed_planning_command():
        """Seed Machines, WOs, ProcessPlans, MachineResourceMappings and APS data."""
        import os
        import sys
        _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if _root not in sys.path:
            sys.path.insert(0, _root)
        from seed_planning_aps import seed
        seed()

    # Auto-seed demo data so every screen has content on first run.
    # Runs only once the DB is up; silent on error.
    try:
        with app.app_context():
            db.create_all()

            # Schema validation: check critical columns exist before seeding
            # This prevents crashes when migrations haven't run yet
            from sqlalchemy import inspect
            inspector = inspect(db.engine)

            # Check if inspection_plans table has the required extrusion columns
            if 'inspection_plans' in inspector.get_table_names():
                columns = [col['name'] for col in inspector.get_columns('inspection_plans')]
                required_columns = ['target_type', 'target_code', 'operation_step']
                schema_ready = all(col in columns for col in required_columns)
            else:
                schema_ready = False

            if not schema_ready:
                import logging
                logging.getLogger(__name__).warning(
                    "Schema not ready for seeding - required columns missing. "
                    "Run 'flask db upgrade' to apply migrations."
                )
                return app

            import os, sys
            _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if _root not in sys.path:
                sys.path.insert(0, _root)
            from scripts import seed_data  # noqa: WPS433
            seed_plant_master_data = seed_data.seed_plant_master_data
            seed_plant_master_data()
            seed_data.seed_material_grades()
            seed_data.seed_customer_orders()
            seed_data.seed_dies_and_workflow()
            seed_data.seed_inspection_plans()
            seed_data.seed_billets()
            seed_data.seed_setpoint_profiles()
            seed_data.seed_process_runs_and_records()
            seed_data.seed_plc_signal_mappings()
            seed_data.seed_integration_jobs()
            seed_data.seed_alert_rules()
            seed_data.seed_alerts()
            seed_data.seed_kpi_records()
            seed_data.seed_admin_master()
            seed_data.seed_work_orders_and_traceability()
            seed_data.seed_oee_and_downtime()
            seed_data.seed_process_plans_and_schedule()
            seed_data.seed_audit_trail()
            seed_data.seed_extrusion_traceability()
            seed_data.seed_aps_data()
            # Extrusion modules seed data
            seed_data.seed_die_lifecycle_extended()
            seed_data.seed_material_receipt_module()
            seed_data.seed_coating_schedule_module()
            seed_data.seed_containers_module()
            seed_data.seed_furnace_module()
            seed_data.seed_finishing_module()
            seed_data.seed_logistics_module()
            seed_data.seed_cost_price_module()
            db.session.commit()
    except Exception as exc:  # pragma: no cover - startup seed best-effort
        try:
            db.session.rollback()
        except Exception:
            pass
        import logging
        logging.getLogger(__name__).warning("Auto-seed skipped: %s", exc)

    return app
