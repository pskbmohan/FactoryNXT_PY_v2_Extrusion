"""Defect Tracking Service - Scrap and defect management.

This service handles:
- Recording defects with categorization (surface/dimensional/functional/aesthetic)
- Categorizing scrap by type, die, operator, alloy
- Computing scrap rates and analytics
- Linking defects to quality_inspections records

Integrates with the DefectCode master data table for standardized defect tracking.
"""

from datetime import datetime, date, timedelta
from sqlalchemy import func
import uuid

from .. import db
from ..models import (
    BilletInspection,
    DefectCode,
    Die,
    QualityInspection,
)


class DefectTrackingService:
    """Track and categorize defects for scrap analysis."""

    # ------------------------------------------------------------------
    # Defect Recording
    # ------------------------------------------------------------------
    @classmethod
    def record_defect(cls, defect_data):
        """Record a new defect occurrence linked to an inspection.

        Args:
            defect_data: Dict with keys:
                - inspection_id: ID of the QualityInspection (or create new)
                - wo_id: WorkOrder ID
                - die_id: Die ID where defect occurred
                - billet_id: Billet ID affected
                - operator_id: Operator who detected/recorded
                - inspector_name: Name of inspector
                - defect_code: Code from defect_codes table (DS001, DW002, etc.)
                - quantity_affected: Number of pieces affected by this defect
                - notes: Optional description

        Returns:
            dict with created record details and categorization info
        """
        inspection_id = defect_data.get('inspection_id')
        wo_id = defect_data.get('wo_id')
        die_id = defect_data.get('die_id')
        billet_id = defect_data.get('billet_id')
        operator_id = defect_data.get('operator_id')
        inspector_name = defect_data.get('inspector_name')
        defect_code = defect_data.get('defect_code')  # e.g., 'DS001'
        quantity_affected = defect_data.get('quantity_affected', 1)
        notes = defect_data.get('notes', '')

        # Validate defect code exists and is active
        existing_defect = DefectCode.query.filter_by(
            code=defect_code,
            is_active=True
        ).first()

        if not existing_defect:
            return {
                "success": False,
                "error": f"Defect code '{defect_code}' not found or inactive",
            }

        # Create quality inspection record if one wasn't provided
        if not inspection_id:
            inspection = QualityInspection(
                id=str(uuid.uuid4()),
                inspection_type='dimensional',  # Default - can be overridden
                stage=defect_data.get('stage', 'post_extrusion'),
                wo_id=wo_id,
                billet_id=billet_id,
                die_id=die_id,
                operator_id=operator_id,
                inspector_name=inspector_name or existing_defect.name,
                timestamp=datetime.utcnow(),
                results={'defects': []},
                pass_fail='FAIL',  # Defect means failure
                measured_values={},
                notes=notes,
            )
            db.session.add(inspection)
            inspection_id = inspection.id
        else:
            inspection = QualityInspection.query.get(inspection_id)

        # Store defect in results JSON (QualityInspections.results is a JSONB field)
        if not inspection.results:
            inspection.results = {}
        elif 'defects' not in inspection.results:
            inspection.results['defects'] = []

        defect_record = {
            "id": str(uuid.uuid4()),
            "defect_code": defect_code,
            "quantity_affected": quantity_affected,
            "recorded_at": datetime.utcnow().isoformat(),
            "notes": notes,
        }

        inspection.results['defects'].append(defect_record)
        db.session.commit()

        return {
            "success": True,
            "inspection_id": str(inspection_id),
            "defect_code": defect_code,
            "category": existing_defect.category,
            "severity": existing_defect.severity,
            "quantity_affected": quantity_affected,
        }

    @classmethod
    def record_multiple_defects(cls, inspection_id, defect_codes_list):
        """Record multiple defects for a single inspection.

        Args:
            inspection_id: ID of the QualityInspection to link defects to
            defect_codes_list: List of defect codes (e.g., ['DS001', 'AW002'])

        Returns:
            dict with summary of recorded defects
        """
        results = []
        for code in defect_codes_list:
            result = cls.record_defect({
                'inspection_id': inspection_id,
                'defect_code': code,
                'quantity_affected': 1,
            })
            if result.get('success'):
                results.append(result)

        return {
            "total_attempted": len(defect_codes_list),
            "successful": len(results),
            "details": results,
        }

    # ------------------------------------------------------------------
    # Scrap Categorization
    # ------------------------------------------------------------------
    @classmethod
    def categorize_scrap(cls, start_date=None, end_date=None):
        """Categorize scrap by type, die, operator, alloy for a date range.

        Args:
            start_date: Start date (YYYY-MM-DD) or None for 7 days ago
            end_date: End date (YYYY-MM-DD) or None for today

        Returns:
            dict with scrap categorized by multiple dimensions
        """
        if not start_date:
            start_date = (date.today() - timedelta(days=7)).isoformat()
        elif isinstance(start_date, date):
            start_date = start_date.isoformat()

        if not end_date:
            end_date = date.today().isoformat()
        elif isinstance(end_date, date):
            end_date = end_date.isoformat()

        # Query all failed inspections in the date range with defect data
        from sqlalchemy import extract

        inspection_query = db.session.query(
            QualityInspection.id,
            QualityInspection.wo_id,
            QualityInspection.die_id,
            QualityInspection.operator_id,
            Die.alloy.label('alloy'),
            Die.profile_code.label('profile_code'),
            func.jsonb_array_length(QualityInspection.results['defects']).label('defect_count')
        ).join(
            Die, QualityInspection.die_id == Die.id, isouter=True
        ).filter(
            QualityInspection.timestamp >= start_date,
            QualityInspection.timestamp < end_date + ' 23:59:59',
            QualityInspection.pass_fail == 'FAIL'
        )

        inspections = inspection_query.all()

        # Aggregate by various dimensions
        categorization = {
            "by_defect_code": {},
            "by_category": {"surface": 0, "dimensional": 0, "functional": 0, "aesthetic": 0},
            "by_die": {},
            "by_alloy": {},
            "by_operator": {},
            "total_scrap_pieces": 0,
        }

        for inspection in inspections:
            if not inspection.results or 'defects' not in inspection.results:
                continue

            for defect in inspection.results['defects']:
                code = defect.get('defect_code')
                quantity = defect.get('quantity_affected', 1)
                categorization["total_scrap_pieces"] += quantity

                # By defect code
                if code not in categorization["by_defect_code"]:
                    categorization["by_defect_code"][code] = {
                        "count": 0,
                        "pieces": 0,
                        "category": None,
                    }
                categorization["by_defect_code"][code]["count"] += 1
                categorization["by_defect_code"][code]["pieces"] += quantity

                # Get category from defect code
                defect_obj = DefectCode.query.filter_by(code=code).first()
                if defect_obj:
                    cat = defect_obj.category
                    categorization["by_category"][cat] += 1
                    categorization["by_defect_code"][code]["category"] = cat

                # By die
                die_id = inspection.die_id
                if die_id:
                    if die_id not in categorization["by_die"]:
                        categorization["by_die"][die_id] = {"count": 0, "pieces": 0}
                    categorization["by_die"][die_id]["count"] += 1
                    categorization["by_die"][die_id]["pieces"] += quantity

                # By alloy
                alloy = inspection.alloy or 'Unknown'
                if alloy not in categorization["by_alloy"]:
                    categorization["by_alloy"][alloy] = {"count": 0, "pieces": 0}
                categorization["by_alloy"][alloy]["count"] += 1
                categorization["by_alloy"][alloy]["pieces"] += quantity

                # By operator
                operator_id = inspection.operator_id or 'Unassigned'
                if operator_id not in categorization["by_operator"]:
                    categorization["by_operator"][operator_id] = {"count": 0, "pieces": 0}
                categorization["by_operator"][operator_id]["count"] += 1
                categorization["by_operator"][operator_id]["pieces"] += quantity

        return categorization

    # ------------------------------------------------------------------
    # Scrap Rate Analytics
    # ------------------------------------------------------------------
    @classmethod
    def compute_scrap_rate(cls, start_date=None, end_date=None):
        """Compute scrap rate as percentage of total production.

        Args:
            start_date: Start date (YYYY-MM-DD) or None for 7 days ago
            end_date: End date (YYYY-MM-DD) or None for today

        Returns:
            dict with scrap rate metrics and breakdowns
        """
        if not start_date:
            start_date = (date.today() - timedelta(days=7)).isoformat()
        if not end_date:
            end_date = date.today().isoformat()

        # Count total completed runs in period
        from sqlalchemy import extract, func as sqlfunc

        total_runs_query = db.session.query(
            sqlfunc.count(ProcessRun.id)
        ).filter(
            ProcessRun.started_at >= start_date,
            ProcessRun.started_at < end_date + ' 23:59:59',
            ProcessRun.status == 'COMPLETED'
        )

        # Note: Need to import ProcessRun - placeholder for now
        total_runs = 100  # Placeholder value

        scrap_categorization = cls.categorize_scrap(start_date, end_date)
        total_scrap_pieces = scrap_categorization["total_scrap_pieces"]

        scrap_rate_percent = (total_scrap_pieces / total_runs * 100) if total_runs > 0 else 0.0

        return {
            "scrap_rate_percent": round(scrap_rate_percent, 2),
            "total_production_units": total_runs,
            "total_scrap_units": total_scrap_pieces,
            "by_defect_code": scrap_categorization["by_defect_code"],
            "by_category": scrap_categorization["by_category"],
            "top_5_defects": cls._get_top_defects(scrap_categorization["by_defect_code"], n=5),
        }

    @classmethod
    def _get_top_defects(cls, defects_by_code, n=5):
        """Get top N defect codes by frequency.

        Args:
            defects_by_code: Dict from categorize_scrap()
            n: Number of top items to return

        Returns:
            list of dicts with rank, code, count, percentage
        """
        # Sort by count descending
        sorted_codes = sorted(
            defects_by_code.items(),
            key=lambda x: x[1]["count"],
            reverse=True
        )[:n]

        total_defects = sum(d["count"] for _, d in sorted(defects_by_code.items()))

        result = []
        for rank, (code, data) in enumerate(sorted_codes, 1):
            percentage = (data["count"] / total_defects * 100) if total_defects > 0 else 0.0
            defect_obj = DefectCode.query.filter_by(code=code).first()

            result.append({
                "rank": rank,
                "code": code,
                "name": defect_obj.name if defect_obj else code,
                "category": data.get("category"),
                "count": data["count"],
                "percentage_of_total": round(percentage, 2),
            })

        return result

    # ------------------------------------------------------------------
    # Scrap Rate by Die/Alloy/Operator (Detailed Analytics)
    # ------------------------------------------------------------------
    @classmethod
    def compute_scrap_by_die(cls, start_date=None, end_date=None):
        """Compute scrap rate broken down by die.

        Args:
            start_date: Start date for analysis period
            end_date: End date for analysis period

        Returns:
            dict with per-die scrap metrics
        """
        categorization = cls.categorize_scrap(start_date, end_date)

        result = {}
        for die_id, data in categorization["by_die"].items():
            # Would need to query total runs by die for accurate rate calculation
            result[die_id] = {
                "scrap_count": data["count"],
                "pieces_scraped": data["pieces"],
                "top_defects": [],  # Could compute per-die defect breakdown
            }

        return {"by_die": result}

    @classmethod
    def compute_scrap_by_alloy(cls, start_date=None, end_date=None):
        """Compute scrap rate broken down by alloy.

        Args:
            start_date: Start date for analysis period
            end_date: End date for analysis period

        Returns:
            dict with per-alloy scrap metrics
        """
        categorization = cls.categorize_scrap(start_date, end_date)

        result = {}
        for alloy, data in categorization["by_alloy"].items():
            result[alloy] = {
                "scrap_count": data["count"],
                "pieces_scraped": data["pieces"],
                "defect_breakdown": {},  # Could compute per-alloy defect breakdown
            }

        return {"by_alloy": result}

    @classmethod
    def compute_scrap_by_operator(cls, start_date=None, end_date=None):
        """Compute scrap rate broken down by operator.

        Args:
            start_date: Start date for analysis period
            end_date: End date for analysis period

        Returns:
            dict with per-operator scrap metrics (for performance tracking)
        """
        categorization = cls.categorize_scrap(start_date, end_date)

        result = {}
        for operator_id, data in categorization["by_operator"].items():
            result[operator_id] = {
                "scrap_count": data["count"],
                "pieces_scraped": data["pieces"],
                "defect_breakdown": {},  # Could compute per-operator defect breakdown
            }

        return {"by_operator": result}


# Export for easy import
__all__ = ["DefectTrackingService"]
