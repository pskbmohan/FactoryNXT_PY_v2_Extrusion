"""Inspection Service - Unified inspection handling and MTC generation.

This service handles:
- Creating unified inspection records across all quality stages
- Validating first-piece inspections before production starts
- Generating Material Test Certificates (MTC/MTR) for customer delivery

Integrates with the quality_inspections table, test_events table, and existing
BilletInspection/DieInspection models.
"""

from datetime import datetime, date, timedelta
from jinja2 import Template
import uuid

from .. import db
from ..models import (
    AlloyComposition,
    Billet,
    Die,
    QualityInspection,
    TestEvent,
    WorkOrder,
)


class InspectionService:
    """Handle unified quality inspections and MTC generation."""

    # ------------------------------------------------------------------
    # Unified Inspection Creation
    # ------------------------------------------------------------------
    @classmethod
    def create_inspection(cls, inspection_data):
        """Create a new unified quality inspection record.

        Args:
            inspection_data: Dict with keys:
                - inspection_type: 'dimensional', 'visual', 'process_parameter', 'first_piece'
                - stage: 'pre_production', 'in_process', 'post_extrusion'
                - wo_id: WorkOrder ID (optional)
                - billet_id: Billet ID (optional)
                - die_id: Die ID (optional)
                - run_id: ProcessRun ID (optional)
                - operator_id: Operator who performed inspection
                - inspector_name: Name of inspector
                - results: Dict with inspection-specific result data
                - pass_fail: 'PASS', 'FAIL', or 'PENDING'
                - measured_values: Dict of dimension measurements
                - notes: Optional text notes

        Returns:
            dict with created inspection ID and summary info
        """
        # Validate required fields
        if not inspection_data.get('inspection_type'):
            return {
                "success": False,
                "error": "inspection_type is required",
            }
        if not inspection_data.get('stage'):
            return {
                "success": False,
                "error": "stage is required",
            }

        # Create the inspection record
        inspection = QualityInspection(
            id=str(uuid.uuid4()),
            inspection_type=inspection_data['inspection_type'],
            stage=inspection_data['stage'],
            wo_id=inspection_data.get('wo_id'),
            billet_id=inspection_data.get('billet_id'),
            die_id=inspection_data.get('die_id'),
            run_id=inspection_data.get('run_id'),
            operator_id=inspection_data.get('operator_id'),
            inspector_name=inspection_data.get('inspector_name'),
            timestamp=datetime.utcnow(),
            results=inspection_data.get('results', {}),
            pass_fail=inspection_data.get('pass_fail', 'PENDING'),
            measured_values=inspection_data.get('measured_values', {}),
            notes=inspection_data.get('notes'),
        )

        db.session.add(inspection)
        db.session.flush()  # Get ID before commit for return value

        return {
            "success": True,
            "inspection_id": str(inspection.id),
            "inspection_type": inspection.inspection_type,
            "stage": inspection.stage,
            "pass_fail": inspection.pass_fail,
            "timestamp": inspection.timestamp.isoformat(),
        }

    @classmethod
    def get_inspection(cls, inspection_id):
        """Get a specific inspection by ID.

        Args:
            inspection_id: UUID string of the inspection to retrieve

        Returns:
            dict with full inspection details or None if not found
        """
        inspection = QualityInspection.query.get(inspection_id)
        if not inspection:
            return None

        die_info = None
        if inspection.die_id:
            die = Die.query.get(inspection.die_id)
            if die:
                die_info = {
                    "die_code": die.die_code,
                    "profile_code": die.profile_code,
                    "alloy": die.alloy,
                }

        return {
            "id": str(inspection.id),
            "inspection_type": inspection.inspection_type,
            "stage": inspection.stage,
            "wo_id": inspection.wo_id,
            "billet_id": inspection.billet_id,
            "die_id": str(inspection.die_id) if inspection.die_id else None,
            "die_info": die_info,
            "operator_id": inspection.operator_id,
            "inspector_name": inspection.inspector_name,
            "timestamp": inspection.timestamp.isoformat(),
            "results": inspection.results or {},
            "pass_fail": inspection.pass_fail,
            "measured_values": inspection.measured_values or {},
            "notes": inspection.notes,
            "erp_posted": inspection.erp_posted,
            "erp_posted_at": inspection.erp_posted_at.isoformat() if inspection.erp_posted_at else None,
        }

    @classmethod
    def query_inspections(cls, filters=None):
        """Query inspections with optional filters.

        Args:
            filters: Dict of filter options:
                - wo_id: Filter by WorkOrder ID
                - die_id: Filter by Die ID
                - inspection_type: Filter by type
                - stage: Filter by stage
                - pass_fail: Filter by PASS/FAIL status
                - date_from: Start date for timestamp range
                - date_to: End date for timestamp range

        Returns:
            list of inspection summary dicts
        """
        query = QualityInspection.query

        if filters:
            if filters.get('wo_id'):
                query = query.filter_by(wo_id=filters['wo_id'])
            if filters.get('die_id'):
                query = query.filter_by(die_id=filters['die_id'])
            if filters.get('inspection_type'):
                query = query.filter_by(inspection_type=filters['inspection_type'])
            if filters.get('stage'):
                query = query.filter_by(stage=filters['stage'])
            if filters.get('pass_fail'):
                query = query.filter_by(pass_fail=filters['pass_fail'])
            if filters.get('date_from'):
                date_from = datetime.strptime(filters['date_from'], '%Y-%m-%d')
                query = query.filter(QualityInspection.timestamp >= date_from)
            if filters.get('date_to'):
                date_to = datetime.strptime(filters['date_to'], '%Y-%m-%d') + timedelta(days=1)
                query = query.filter(QualityInspection.timestamp < date_to)

        inspections = query.order_by(QualityInspection.timestamp.desc()).all()

        return [{
            "id": str(i.id),
            "inspection_type": i.inspection_type,
            "stage": i.stage,
            "wo_id": i.wo_id,
            "die_id": str(i.die_id) if i.die_id else None,
            "timestamp": i.timestamp.isoformat(),
            "pass_fail": i.pass_fail,
        } for i in inspections]

    # ------------------------------------------------------------------
    # First-Piece Validation
    # ------------------------------------------------------------------
    @classmethod
    def validate_first_piece(cls, inspection_data):
        """Validate first-piece dimensions before production starts.

        This is a pre-production check that must pass before extrusion begins.
        Measures critical dimensions and compares against setpoint tolerances.

        Args:
            inspection_data: Dict with:
                - wo_id: WorkOrder ID for the run
                - die_id: Die being used
                - dimension_measurements: Dict of measured values vs target
                    e.g., {"OD": {"target": 50.0, "measured": 49.8}}
                - inspector_name: Name of inspector performing validation

        Returns:
            dict with validation result and pass/fail decision
        """
        wo_id = inspection_data.get('wo_id')
        die_id = inspection_data.get('die_id')
        dimension_measurements = inspection_data.get('dimension_measurements', {})
        inspector_name = inspection_data.get('inspector_name')

        # Create the first-piece inspection record
        validation_result = cls._evaluate_dimensions(dimension_measurements)

        pass_fail = 'PASS' if validation_result['all_passed'] else 'FAIL'

        inspection = QualityInspection(
            id=str(uuid.uuid4()),
            inspection_type='first_piece',
            stage='pre_production',
            wo_id=wo_id,
            die_id=die_id,
            inspector_name=inspector_name,
            timestamp=datetime.utcnow(),
            results={
                "dimension_validation": validation_result,
                "measurements": dimension_measurements,
            },
            pass_fail=pass_fail,
            measured_values=dimension_measurements,
        )

        db.session.add(inspection)
        db.session.commit()

        return {
            "success": True,
            "inspection_id": str(inspection.id),
            "validation_result": validation_result,
            "passed": pass_fail == 'PASS',
            "can_proceed": pass_fail == 'PASS',
        }

    @classmethod
    def _evaluate_dimensions(cls, dimension_measurements):
        """Evaluate if measured dimensions are within tolerance.

        Args:
            dimension_measurements: Dict of {"dimension_name": {"target": X, "measured": Y}}

        Returns:
            dict with evaluation results for each dimension
        """
        # Default tolerances (should be configurable per profile)
        default_tolerance_pct = 0.5  # 0.5% tolerance

        results = {}
        all_passed = True

        for dim_name, measurement in dimension_measurements.items():
            target = measurement.get('target')
            measured = measurement.get('measured')

            if target is None or measured is None:
                results[dim_name] = {
                    "status": "invalid_data",
                    "passed": False,
                    "deviation_pct": None,
                }
                all_passed = False
                continue

            deviation = abs(measured - target)
            tolerance = abs(target * default_tolerance_pct / 100) if target != 0 else 0.5
            deviation_pct = (deviation / abs(target) * 100) if target != 0 else 0

            passed = deviation <= tolerance

            results[dim_name] = {
                "target": target,
                "measured": measured,
                "deviation": round(deviation, 3),
                "tolerance": round(tolerance, 3),
                "deviation_pct": round(deviation_pct, 2),
                "passed": passed,
            }

            if not passed:
                all_passed = False

        return {
            "dimensions_evaluated": len(dimension_measurements),
            "all_passed": all_passed,
            "dimension_results": results,
        }

    # ------------------------------------------------------------------
    # Material Test Certificate (MTC/MTR) Generation
    # ------------------------------------------------------------------
    @classmethod
    def generate_mtc_report(cls, wo_id):
        """Generate a complete Material Test Certificate for a work order.

        The MTC includes:
        - Order and batch information
        - Chemical composition from AlloyComposition table
        - Mechanical test results (hardness, UTS) from test_events
        - Dimensional verification data
        - Inspector signatures and dates

        Args:
            wo_id: WorkOrder ID to generate certificate for

        Returns:
            dict with MTC data ready for PDF generation or HTML display
        """
        work_order = WorkOrder.query.get(wo_id)
        if not work_order:
            return {
                "success": False,
                "error": f"WorkOrder '{wo_id}' not found",
            }

        # Gather chemical composition data
        alloy_composition_data = []
        if hasattr(work_order, 'alloy') and work_order.alloy:
            compositions = AlloyComposition.query.filter_by(
                alloy_code=work_order.alloy
            ).all()

            for comp in compositions:
                spec_max_val = getattr(comp, 'spec_max', None)
                alloy_composition_data.append({
                    "element": comp.element,
                    "value_percent": comp.value_percent,
                    "spec_min": comp.spec_min,
                    "spec_max": spec_max_val,
                })

        # Gather mechanical test results
        test_results = TestEvent.query.filter_by(wo_id=wo_id).all()
        mechanical_tests = []
        for test in test_results:
            mechanical_tests.append({
                "test_type": test.test_type,
                "result_value": test.result_value,
                "acceptance_limit": test.acceptance_limit,
                "passed": test.passed,
                "tested_at": test.tested_at.isoformat(),
                "tester_name": test.tester_name,
            })

        # Gather dimensional inspection data from quality_inspections
        dimensional_data = []
        inspections = QualityInspection.query.filter_by(
            wo_id=wo_id,
            stage='post_extrusion'
        ).all()

        for insp in inspections:
            if insp.measured_values:
                dimensional_data.append({
                    "dimension_type": insp.inspection_type,
                    "measured_values": insp.measured_values,
                    "timestamp": insp.timestamp.isoformat(),
                })

        # Build MTC data structure
        mtc_data = {
            "certificate_number": f"MTC-{wo_id[:8]}-{datetime.utcnow().strftime('%Y%m%d')}",
            "work_order_id": wo_id,
            "order_date": work_order.order_date.isoformat() if hasattr(work_order, 'order_date') else None,
            "batch_number": getattr(work_order, 'batch_number', f"BATCH-{wo_id[:8]}"),
            "heat_number": getattr(work_order, 'heat_number', None),
            "material_grade": work_order.alloy or "Unknown",
            "profile_code": getattr(work_order, 'profile_code', None),
            "die_code": getattr(work_order, 'die_type_id', None),

            # Chemical composition section
            "chemical_composition": alloy_composition_data,

            # Mechanical properties section
            "mechanical_tests": mechanical_tests,

            # Dimensional verification section
            "dimensional_verification": dimensional_data,

            # Certification statement
            "certification_statement": (
                f"This certifies that the material described above has been tested and "
                f"meets the requirements of specification {getattr(work_order, 'specification', 'N/A')}."
            ),

            "generated_at": datetime.utcnow().isoformat(),
        }

        return {
            "success": True,
            "mtc_data": mtc_data,
            "ready_for_pdf": True,
        }

    @classmethod
    def get_mtc_template(cls):
        """Return HTML template for MTC generation.

        Returns:
            Jinja2 Template object ready for rendering with MTC data
        """
        template_str = """
<!DOCTYPE html>
<html>
<head>
    <title>Material Test Certificate - {{ certificate_number }}</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        .header { text-align: center; border-bottom: 2px solid #333; padding-bottom: 10px; margin-bottom: 20px; }
        .section { margin: 20px 0; }
        .section-title { font-weight: bold; background: #f5f5f5; padding: 8px; border-left: 4px solid #333; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background: #f5f5f5; }
        .pass { color: green; font-weight: bold; }
        .fail { color: red; font-weight: bold; }
        .signature { margin-top: 40px; display: flex; justify-content: space-between; }
        .sig-line { border-top: 1px solid #333; width: 200px; text-align: center; padding-top: 5px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>MATERIAL TEST CERTIFICATE</h1>
        <p>Certificate No: {{ certificate_number }}</p>
        <p>Generated: {{ generated_at[:10] }}</p>
    </div>

    <div class="section">
        <div class="section-title">Order Information</div>
        <table>
            <tr><th>Work Order ID</th><td>{{ work_order_id }}</td></tr>
            <tr><th>Batch Number</th><td>{{ batch_number }}</td></tr>
            {% if heat_number %}<tr><th>Heat Number</th><td>{{ heat_number }}</td></tr>{% endif %}
            <tr><th>Material Grade</th><td>{{ material_grade }}</td></tr>
            <tr><th>Profile Code</th><td>{{ profile_code or 'N/A' }}</td></tr>
        </table>
    </div>

    {% if chemical_composition %}
    <div class="section">
        <div class="section-title">Chemical Composition (%)</div>
        <table>
            <thead><tr><th>Element</th><th>Value</th><th>Spec Min</th><th>Spec Max</th></tr></thead>
            <tbody>
                {% for comp in chemical_composition %}
                <tr>
                    <td>{{ element }}</td>
                    <td>{{ value_percent }}</td>
                    <td>{{ spec_min or 'N/A' }}</td>
                    <td>{{ spec_max or 'N/A' }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% endif %}

    {% if mechanical_tests %}
    <div class="section">
        <div class="section-title">Mechanical Test Results</div>
        <table>
            <thead><tr><th>Test Type</th><th>Result</th><th>Acceptance Limit</th><th>Status</th><th>Date</th></tr></thead>
            <tbody>
                {% for test in mechanical_tests %}
                <tr>
                    <td>{{ test.test_type|upper }}</td>
                    <td>{{ test.result_value }}</td>
                    <td>{{ test.acceptance_limit or 'N/A' }}</td>
                    <td class="{{ 'pass' if test.passed else 'fail' }}">
                        {{ 'PASS' if test.passed else 'FAIL' }}
                    </td>
                    <td>{{ test.tested_at[:10] }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% endif %}

    <div class="section">
        <div class="section-title">Certification</div>
        <p>{{ certification_statement }}</p>
    </div>

    <div class="signature">
        <div class="sig-line">Authorized Signature</div>
        <div class="sig-line">Quality Manager</div>
    </div>
</body>
</html>
"""
        return Template(template_str)


# Export for easy import
__all__ = ["InspectionService"]
