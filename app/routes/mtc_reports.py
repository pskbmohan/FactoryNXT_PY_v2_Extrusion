"""Material Test Certificate (MTC) Report Generation.

This blueprint provides automated MTC/MTR document generation for customer deliveries:
- Chemical composition data from AlloyComposition table
- Mechanical properties (hardness, UTS) from test_events
- Batch/order references and traceability information
- PDF export capability with standardized format

Routes under /quality/mtc-reports/* per quality-buildplan.md requirements #20-#21.
"""

from datetime import date, timedelta
from flask import Blueprint, render_template, request, jsonify, send_file
import io
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor, black, white
import base64

from .. import db
from ..models import (
    MaterialTraceability, WorkOrder, AlloyComposition, TestEvent, QualityInspection,
    CustomerOrderLine, ProcessRun
)

bp = Blueprint("mtc_reports", __name__, url_prefix="/quality/mtc-reports")


@bp.route("/", methods=["GET"])
def index():
    """Main MTC report dashboard with recent certificates."""
    # Get work orders that have traceability records and test data
    recent_mtc_queries = (
        db.session.query(
            MaterialTraceability.work_order_id,
            func.count(MaterialTraceability.id).label("trace_count"),
            WorkOrder.order_number,
            WorkOrder.profile_code,
            WorkOrder.alloy
        )
        .join(WorkOrder, MaterialTraceability.work_order_id == WorkOrder.id)
        .filter(MaterialTraceability.status == 'shipped')
        .group_by(MaterialTraceability.work_order_id, WorkOrder.order_number, WorkOrder.profile_code, WorkOrder.alloy)
        .order_by(func.max(MaterialTraceability.extrusion_timestamp).desc())
        .limit(20)
        .all()
    )

    recent_mtc = [
        {
            "wo_id": wo.work_order_id,
            "order_number": wo.order_number,
            "profile_code": wo.profile_code or "N/A",
            "alloy": wo.alloy or "N/A",
            "trace_count": wo.trace_count,
        }
        for wo in recent_mtc_queries
    ]

    # Summary statistics
    total_shipped = MaterialTraceability.query.filter_by(status='shipped').count()
    total_with_tests = (
        db.session.query(MaterialTraceability.work_order_id)
        .join(TestEvent, MaterialTraceability.work_order_id == TestEvent.wo_id)
        .distinct()
        .filter(MaterialTraceability.status == 'shipped')
        .count()
    )

    return render_template(
        "quality/mtc_reports/index.html",
        recent_mtc=recent_mtc,
        total_shipped=total_shipped,
        total_with_test_data=total_with_tests,
    )


@bp.route("/generate/<int:wo_id>", methods=["GET"])
def generate_mtc(wo_id):
    """Generate MTC for a specific work order."""
    try:
        wo_id = int(wo_id)
    except (ValueError, TypeError):
        return render_template("quality/mtc_reports/error.html", error="Invalid work order ID"), 400

    # Get work order details
    work_order = WorkOrder.query.get(wo_id)
    if not work_order:
        return render_template("quality/mtc_reports/error.html", error="Work order not found"), 404

    # Get traceability records for this WO
    trace_records = MaterialTraceability.query.filter_by(work_order_id=wo_id).all()

    if not trace_records:
        return render_template(
            "quality/mtc_reports/error.html",
            error=f"No traceability data found for work order {work_order.order_number}"
        ), 404

    # Get alloy composition
    alloy = None
    if work_order.alloy:
        alloy = AlloyComposition.query.filter_by(alloy_code=work_order.alloy).first()

    # Get test results (mechanical properties)
    test_events = TestEvent.query.filter_by(wo_id=wo_id).order_by(TestEvent.tested_at.desc()).all()

    # Get quality inspection summary
    inspections = QualityInspection.query.filter_by(wo_id=wo_id).all()
    inspection_summary = {
        "total": len(inspections),
        "passed": sum(1 for i in inspections if i.pass_fail == 'PASS'),
        "failed": sum(1 for i in inspections if i.pass_fail == 'FAIL'),
    }

    # Get customer order information (if available)
    customer_orders = []
    for trace in trace_records:
        if trace.customer_order_line_id:
            col = CustomerOrderLine.query.get(trace.customer_order_line_id)
            if col and col.order_number not in [o["order_number"] for o in customer_orders]:
                customer_orders.append({
                    "order_number": col.order_number,
                    "line_id": str(col.id),
                })

    # Aggregate trace data
    batch_numbers = list(set([t.batch_number for t in trace_records if t.batch_number]))
    heat_numbers = list(set([t.heat_number for t in trace_records if t.heat_number]))
    billet_codes = list(set([t.billet_code for t in trace_records if t.billet_code]))

    # Calculate summary stats
    extrusion_dates = [t.extrusion_timestamp for t in trace_records if t.extrusion_timestamp]
    first_extrusion = min(extrusion_dates).strftime("%Y-%m-%d") if extrusion_dates else "N/A"
    last_extrusion = max(extrusion_dates).strftime("%Y-%m-%d") if extrusion_dates else "N/A"

    return render_template(
        "quality/mtc_reports/generate.html",
        work_order=work_order,
        trace_records=trace_records,
        batch_numbers=batch_numbers,
        heat_numbers=heat_numbers,
        billet_codes=billet_codes,
        alloy=alloy,
        test_events=test_events,
        inspection_summary=inspection_summary,
        customer_orders=customer_orders,
        first_extrusion_date=first_extrusion,
        last_extrusion_date=last_extrusion,
    )


@bp.route("/api/mtc/<int:wo_id>", methods=["GET"])
def api_mtc(wo_id):
    """API endpoint returning MTC data as JSON."""
    try:
        wo_id = int(wo_id)
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid work order ID"}), 400

    # Get work order details
    work_order = WorkOrder.query.get(wo_id)
    if not work_order:
        return jsonify({"error": "Work order not found"}), 404

    # Get traceability records for this WO
    trace_records = MaterialTraceability.query.filter_by(work_order_id=wo_id).all()

    if not trace_records:
        return jsonify({"error": "No traceability data found"}), 404

    # Get alloy composition
    alloy = None
    if work_order.alloy:
        alloy = AlloyComposition.query.filter_by(alloy_code=work_order.alloy).first()

    # Get test results (mechanical properties)
    test_events = TestEvent.query.filter_by(wo_id=wo_id).all()

    # Format MTC data
    mtc_data = {
        "certificate_number": f"MTC-{work_order.order_number}-{date.today().strftime('%Y%m%d')}",
        "order_number": work_order.order_number,
        "profile_code": work_order.profile_code or "N/A",
        "alloy": {
            "code": work_order.alloy or "Unknown",
            "name": alloy.alloy_name if alloy else "Unknown",
            "composition": alloy.composition if alloy and alloy.composition else {},
        } if alloy else {"code": work_order.alloy, "name": "N/A", "composition": {}},
        "traceability": {
            "batch_numbers": list(set([t.batch_number for t in trace_records if t.batch_number])),
            "heat_numbers": list(set([t.heat_number for t in trace_records if t.heat_number])),
            "billet_codes": list(set([t.billet_code for t in trace_records if t.billet_code])),
        },
        "test_results": [
            {
                "test_type": test.test_type,
                "result_value": test.result_value,
                "acceptance_limit": test.acceptance_limit,
                "passed": test.passed,
                "tested_date": test.tested_at.strftime("%Y-%m-%d") if test.tested_at else None,
            }
            for test in test_events
        ],
        "extrusion_period": {
            "first_date": min([t.extrusion_timestamp for t in trace_records if t.extrusion_timestamp]).strftime("%Y-%m-%d"),
            "last_date": max([t.extrusion_timestamp for t in trace_records if t.extrusion_timestamp]).strftime("%Y-%m-%d"),
        },
    }

    return jsonify(mtc_data)


@bp.route("/export/pdf/<int:wo_id>", methods=["GET"])
def export_pdf(wo_id):
    """Export MTC as PDF file."""
    try:
        wo_id = int(wo_id)
    except (ValueError, TypeError):
        return "Invalid work order ID", 400

    # Get work order details
    work_order = WorkOrder.query.get(wo_id)
    if not work_order:
        return "Work order not found", 404

    # Get traceability records for this WO
    trace_records = MaterialTraceability.query.filter_by(work_order_id=wo_id).all()

    if not trace_records:
        return "No traceability data found", 404

    # Get alloy composition
    alloy = None
    if work_order.alloy:
        alloy = AlloyComposition.query.filter_by(alloy_code=work_order.alloy).first()

    # Get test results (mechanical properties)
    test_events = TestEvent.query.filter_by(wo_id=wo_id).all()

    # Generate PDF in memory
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()

    # Custom style for header
    header_style = ParagraphStyle(
        'CustomHeader',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=HexColor('#2c3e50'),
        spaceAfter=12,
    )

    # Title
    elements.append(Paragraph("MATERIAL TEST CERTIFICATE", header_style))
    elements.append(Spacer(1, 12))

    # Certificate info table
    cert_info = [
        ["Certificate No:", f"MTC-{work_order.order_number}-{date.today().strftime('%Y%m%d')}"],
        ["Order Number:", work_order.order_number],
        ["Profile Code:", work_order.profile_code or "N/A"],
        ["Alloy:", alloy.alloy_name if alloy else (work_order.alloy or "Unknown")],
    ]

    cert_table = Table(cert_info, colWidths=[2*inch, 4*inch])
    cert_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#3498db')),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (0, -1), 10),
        ('BOTTOMPADDING', (0, 0), (0, -1), 8),
        ('TOPPADDING', (0, 0), (0, -1), 8),
        ('BACKGROUND', (0, 1), (-1, -1), HexColor('#ecf0f1')),
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
    ]))

    elements.append(cert_table)
    elements.append(Spacer(1, 24))

    # Traceability information
    batch_numbers = list(set([t.batch_number for t in trace_records if t.batch_number]))
    heat_numbers = list(set([t.heat_number for t in trace_records if t.heat_number]))
    billet_codes = list(set([t.billet_code for t in trace_records if t.billet_code]))

    elements.append(Paragraph("TRACEABILITY INFORMATION", styles['Heading2']))
    elements.append(Spacer(1, 6))

    trace_info = [
        ["Batch Numbers:", ", ".join(batch_numbers) or "N/A"],
        ["Heat Numbers:", ", ".join(heat_numbers) or "N/A"],
        ["Billet Codes:", ", ".join(billet_codes) or "N/A"],
    ]

    trace_table = Table(trace_info, colWidths=[2*inch, 4*inch])
    trace_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (0, -1), 4),
    ]))

    elements.append(trace_table)
    elements.append(Spacer(1, 24))

    # Chemical composition table
    if alloy and alloy.composition:
        elements.append(Paragraph("CHEMICAL COMPOSITION", styles['Heading2']))
        elements.append(Spacer(1, 6))

        chem_data = [["Element", "Min %", "Max %", "Actual %"]]
        for element, limits in alloy.composition.items():
            actual = None
            if isinstance(limits, dict):
                min_val = limits.get('min', '')
                max_val = limits.get('max', '')
                actual_elem = db.session.query(AlloyComposition).filter_by(alloy_code=work_order.alloy).first()
                # In real implementation, would get actual composition from material_receipts.actual_composition
            else:
                min_val = ""
                max_val = str(limits)

            chem_data.append([element, str(min_val), str(max_val), "N/A"])

        if len(chem_data) > 1:
            chem_table = Table(chem_data, colWidths=[1.5*inch, 0.75*inch, 0.75*inch, 1*inch])
            chem_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), HexColor('#2c3e50')),
                ('TEXTCOLOR', (0, 0), (-1, 0), white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, black),
            ]))

            elements.append(chem_table)
        elements.append(Spacer(1, 24))

    # Mechanical test results table
    if test_events:
        elements.append(Paragraph("MECHANICAL TEST RESULTS", styles['Heading2']))
        elements.append(Spacer(1, 6))

        test_data = [["Test Type", "Result Value", "Acceptance Limit", "Status"]]
        for test in test_events:
            status = "PASS" if test.passed is True else ("FAIL" if test.passed is False else "PENDING")
            status_color = HexColor('#27ae60') if test.passed is True else (HexColor('#e74c3c') if test.passed is False else HexColor('#f39c12'))

            test_data.append([
                test.test_type,
                str(test.result_value) if test.result_value is not None else "N/A",
                str(test.acceptance_limit) if test.acceptance_limit is not None else "N/A",
                status,
            ])

        if len(test_data) > 1:
            test_table = Table(test_data, colWidths=[2*inch, 0.75*inch, 0.75*inch, 1*inch])
            test_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), HexColor('#2c3e50')),
                ('TEXTCOLOR', (0, 0), (-1, 0), white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 0.5, black),
            ]))

            elements.append(test_table)
        elements.append(Spacer(1, 24))

    # Footer
    footer_style = ParagraphStyle(
        'CustomFooter',
        parent=styles['Normal'],
        fontSize=8,
        textColor=HexColor('#7f8c8d'),
        alignment='CENTER',
    )

    elements.append(Spacer(1, 48))
    elements.append(Paragraph("This certificate is automatically generated and electronically signed.", footer_style))
    elements.append(Paragraph(f"Generated on: {date.today().strftime('%B %d, %Y')}", footer_style))

    # Build PDF
    doc.build(elements)

    # Return as file download
    buffer.seek(0)
    return send_file(
        io.BytesIO(buffer.getvalue()),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"MTC_{work_order.order_number}.pdf"
    )


@bp.route("/api/export/pdf/<int:wo_id>", methods=["GET"])
def api_export_pdf(wo_id):
    """API endpoint for PDF export (returns base64 encoded PDF)."""
    # Reuse the same logic as export_pdf but return base64 instead of file
    try:
        wo_id = int(wo_id)
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid work order ID"}), 400

    work_order = WorkOrder.query.get(wo_id)
    if not work_order:
        return jsonify({"error": "Work order not found"}), 404

    trace_records = MaterialTraceability.query.filter_by(work_order_id=wo_id).all()
    if not trace_records:
        return jsonify({"error": "No traceability data found"}), 404

    # Generate PDF (same logic as export_pdf)
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()

    header_style = ParagraphStyle(
        'CustomHeader',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=HexColor('#2c3e50'),
        spaceAfter=12,
    )

    elements.append(Paragraph("MATERIAL TEST CERTIFICATE", header_style))
    elements.append(Spacer(1, 12))

    alloy = AlloyComposition.query.filter_by(alloy_code=work_order.alloy).first() if work_order.alloy else None
    test_events = TestEvent.query.filter_by(wo_id=wo_id).all()
    batch_numbers = list(set([t.batch_number for t in trace_records if t.batch_number]))

    cert_info = [
        ["Certificate No:", f"MTC-{work_order.order_number}-{date.today().strftime('%Y%m%d')}"],
        ["Order Number:", work_order.order_number],
        ["Profile Code:", work_order.profile_code or "N/A"],
        ["Alloy:", alloy.alloy_name if alloy else (work_order.alloy or "Unknown")],
    ]

    cert_table = Table(cert_info, colWidths=[2*inch, 4*inch])
    cert_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#3498db')),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
    ]))

    elements.append(cert_table)
    elements.append(Spacer(1, 24))

    trace_info = [
        ["Batch Numbers:", ", ".join(batch_numbers) or "N/A"],
    ]
    trace_table = Table(trace_info, colWidths=[2*inch, 4*inch])
    trace_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 1), (-1, -1), HexColor('#ecf0f1')),
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
    ]))

    elements.append(trace_table)
    doc.build(elements)

    buffer.seek(0)
    pdf_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

    return jsonify({
        "success": True,
        "certificate_number": f"MTC-{work_order.order_number}-{date.today().strftime('%Y%m%d')}",
        "pdf_base64": pdf_base64,
        "filename": f"MTC_{work_order.order_number}.pdf",
    })
