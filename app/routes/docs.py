from flask import Blueprint, render_template, abort

docs_bp = Blueprint('docs', __name__, url_prefix='/docs')

DOCS_PAGES = {
    'index':             ('FactoryNXT Docs Home',          'docs/index.html'),
    'dashboard':         ('Dashboard & KPIs',              'docs/dashboard.html'),
    'work-orders':       ('Work Orders',                   'docs/work_orders.html'),
    'planning':          ('Production Planning',           'docs/planning.html'),
    'aps':               ('APS — Advanced Scheduling',     'docs/aps.html'),
    'operations':        ('Operations & Shop Floor',       'docs/operations.html'),
    'process-line':      ('Process Line',                  'docs/process_line.html'),
    'routing-builder':   ('Routing Builder',               'docs/routing_builder.html'),
    'production':        ('Production Tracking',           'docs/production.html'),
    'dies':              ('Die Management',                'docs/dies.html'),
    'tool-shop':         ('Tool Shop',                     'docs/tool_shop.html'),
    'furnace':           ('Furnace & Heat Treatment',      'docs/furnace.html'),
    'finishing':         ('Finishing & Stretching',        'docs/finishing.html'),
    'coating-schedule':  ('Coating Schedule',              'docs/coating_schedule.html'),
    'quality':           ('Quality & NCR',                 'docs/quality.html'),
    'oee':               ('OEE — Machine Efficiency',      'docs/oee.html'),
    'kpi-alerts':        ('KPI Alerts & Notifications',    'docs/kpi_alerts.html'),
    'material-receipt':  ('Material Receipt',              'docs/material_receipt.html'),
    'inventory':         ('Inventory',                     'docs/inventory.html'),
    'bom':               ('Bill of Materials (BOM)',       'docs/bom.html'),
    'cost-price':        ('Cost & Price Config',           'docs/cost_price.html'),
    'containers':        ('Container Management',          'docs/containers.html'),
    'traceability':      ('Traceability & Genealogy',      'docs/traceability.html'),
    'genealogy':         ('Part Genealogy',                'docs/genealogy.html'),
    'logistics':         ('Logistics & Shipments',         'docs/logistics.html'),
    'kitting':           ('Kitting',                       'docs/kitting.html'),
    'packaging':         ('Packaging',                     'docs/packaging.html'),
    'maintenance':       ('Maintenance',                   'docs/maintenance.html'),
    'stations':          ('Stations & Workcentres',        'docs/stations.html'),
    'machines':          ('Machines',                      'docs/machines.html'),
    'integrations':      ('Integrations & API',            'docs/integrations.html'),
    'admin':             ('Admin & Users',                 'docs/admin.html'),
}

@docs_bp.route('/')
@docs_bp.route('/index')
def docs_index():
    return render_template('docs/index.html', pages=DOCS_PAGES, current='index')

@docs_bp.route('/<slug>')
def docs_page(slug):
    if slug not in DOCS_PAGES:
        abort(404)
    title, template = DOCS_PAGES[slug]
    return render_template(template, pages=DOCS_PAGES, current=slug, title=title)
