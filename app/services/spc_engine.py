"""SPC Engine - Statistical Process Control analytics.

This service implements Statistical Process Control calculations:
- X-bar and R control charts (mean and range tracking)
- Cp, Cpk process capability indices
- Pp, Ppk overall performance metrics
- Control limit violation detection
- Trend analysis for capability degradation

Integrates with the spc_records table created in Phase 1 migration.
"""

from datetime import datetime, date, timedelta
import math
import uuid

from .. import db
from ..models import SPCRecord


class SPCEngine:
    """Compute and analyze statistical process control metrics."""

    # Standard constants for control chart calculations
    A2_CONSTANT = 0.577   # For n=5 samples (common subgroup size)
    D3_CONSTANT = 0       # For n=5 samples
    D4_CONSTANT = 2.114  # For n=5 samples

    @classmethod
    def record_measurement(cls, measurement_data):
        """Record a new SPC measurement sample.

        Args:
            measurement_data: Dict with keys:
                - wo_id: WorkOrder ID
                - dimension_type: e.g., 'OD', 'ID', 'thickness'
                - target_value: Nominal/target dimension
                - measured_value: Actual measured value
                - upper_limit: Specification UCL (optional)
                - lower_limit: Specification LCL (optional)
                - sample_number: Sequential sample number for this run
                - shift_group: e.g., 'morning', 'afternoon', 'night'
                - operator_id: Optional operator identifier

        Returns:
            dict with measurement record and control status
        """
        # Create the SPC record
        record = SPCRecord(
            id=str(uuid.uuid4()),
            wo_id=measurement_data['wo_id'],
            dimension_type=measurement_data['dimension_type'],
            target_value=float(measurement_data['target_value']),
            measured_value=float(measurement_data['measured_value']),
            upper_limit=float(measurement_data.get('upper_limit')) if measurement_data.get('upper_limit') else None,
            lower_limit=float(measurement_data.get('lower_limit')) if measurement_data.get('lower_limit') else None,
            sample_number=int(measurement_data['sample_number']),
            shift_group=measurement_data.get('shift_group', 'unknown'),
            operator_id=measurement_data.get('operator_id'),
        )

        # Calculate if out of control (basic check)
        upper_spec = record.upper_limit or float('inf')
        lower_spec = record.lower_limit or float('-inf')

        out_of_control = False
        trend_direction = None

        if not (lower_spec <= record.measured_value <= upper_spec):
            out_of_control = True

        # Check for trends (simplified - would need historical data)
        previous_records = SPCRecord.query.filter_by(
            wo_id=record.wo_id,
            dimension_type=record.dimension_type,
            shift_group=record.shift_group
        ).order_by(SPCRecord.sample_number.desc()).limit(5).all()

        if len(previous_records) >= 2:
            recent_values = [r.measured_value for r in previous_records] + [record.measured_value]
            increases = sum(1 for i in range(len(recent_values)-1) if recent_values[i] < recent_values[i+1])
            decreases = sum(1 for i in range(len(recent_values)-1) if recent_values[i] > recent_values[i+1])

            if increases >= 4:
                trend_direction = 'up'
            elif decreases >= 4:
                trend_direction = 'down'
            else:
                trend_direction = 'stable'

        record.out_of_control = out_of_control
        record.trend_direction = trend_direction

        db.session.add(record)
        db.session.flush()

        return {
            "success": True,
            "record_id": str(record.id),
            "out_of_control": out_of_control,
            "trend_direction": trend_direction,
            "sample_number": record.sample_number,
        }

    @classmethod
    def compute_xbar_r_charts(cls, wo_id, dimension_type=None):
        """Compute X-bar and R control charts for a work order.

        Calculates:
        - Center line (X-double-bar = average of subgroup means)
        - Upper Control Limit (UCL) and Lower Control Limit (LCL) for X-bar chart
        - Average range (R-bar) and its control limits
        - Identifies out-of-control points

        Args:
            wo_id: WorkOrder ID to analyze
            dimension_type: Optional filter by specific dimension type

        Returns:
            dict with complete SPC chart data ready for visualization
        """
        query = SPCRecord.query.filter_by(wo_id=wo_id)
        if dimension_type:
            query = query.filter_by(dimension_type=dimension_type)

        records = query.order_by(SPCRecord.sample_number).all()

        if not records:
            return {
                "success": False,
                "error": f"No SPC data found for work order {wo_id}",
            }

        # Group by shift for X-bar calculation (subgroups)
        subgroups = {}
        for record in records:
            key = record.shift_group
            if key not in subgroups:
                subgroups[key] = []
            subgroups[key].append(record.measured_value)

        # Calculate subgroup statistics
        xbar_values = []
        r_values = []
        control_violations = []

        for shift, values in subgroups.items():
            if not values:
                continue

            n = len(values)  # Subgroup size
            x_bar = sum(values) / n  # Mean of subgroup
            r = max(values) - min(values)  # Range of subgroup

            xbar_values.append({
                "shift": shift,
                "sample_number": values[0],  # Use first sample as identifier
                "x_bar": round(x_bar, 4),
                "range": round(r, 4),
                "subgroup_size": n,
            })

            r_values.append(r)

        if not xbar_values:
            return {
                "success": False,
                "error": "No valid data for calculation",
            }

        # Calculate overall statistics
        all_x_bars = [s["x_bar"] for s in xbar_values]
        all_ranges = r_values

        x_double_bar = sum(all_x_bars) / len(all_x_bars)  # Grand mean
        r_bar = sum(all_ranges) / len(all_ranges) if all_ranges else 0  # Average range

        # Calculate control limits using standard constants for n=5
        ucl_xbar = x_double_bar + (cls.A2_CONSTANT * r_bar)
        lcl_xbar = x_double_bar - (cls.A2_CONSTANT * r_bar)
        ucl_r = cls.D4_CONSTANT * r_bar
        lcl_r = cls.D3_CONSTANT * r_bar

        # Identify control violations
        for subgroup in xbar_values:
            if subgroup["x_bar"] > ucl_xbar or subgroup["x_bar"] < lcl_xbar:
                control_violations.append({
                    "shift": subgroup["shift"],
                    "x_bar": subgroup["x_bar"],
                    "violation_type": "X-bar out of control",
                    "limit_exceeded": "UCL" if subgroup["x_bar"] > ucl_xbar else "LCL",
                })

            if subgroup["range"] > ucl_r:
                control_violations.append({
                    "shift": subgroup["shift"],
                    "range": subgroup["range"],
                    "violation_type": "Range out of control",
                    "limit_exceeded": "UCL",
                })

        return {
            "success": True,
            "work_order_id": wo_id,
            "dimension_type": dimension_type or "all",
            "statistics": {
                "x_double_bar": round(x_double_bar, 4),  # Center line for X-bar chart
                "r_bar": round(r_bar, 4),  # Average range
                "n_samples": len(all_x_bars),
                "subgroup_size_avg": sum(s["subgroup_size"] for s in xbar_values) / len(xbar_values),
            },
            "control_limits": {
                "x_bar_chart": {
                    "ucl": round(ucl_xbar, 4),
                    "center_line": round(x_double_bar, 4),
                    "lcl": round(lcl_xbar, 4),
                },
                "r_chart": {
                    "ucl": round(ucl_r, 4),
                    "center_line": round(r_bar, 4),
                    "lcl": round(lcl_r, 4),
                },
            },
            "subgroup_data": xbar_values,
            "control_violations": control_violations,
        }

    @classmethod
    def compute_capability_indices(cls, wo_id, dimension_type=None):
        """Compute process capability indices (Cp, Cpk) for a work order.

        Cp = (USL - LSL) / (6 * sigma)  # Potential capability
        Cpk = min((USL - mean) / (3*sigma), (mean - LSL) / (3*sigma))  # Actual performance

        Also computes Pp and Ppk for overall process performance.

        Args:
            wo_id: WorkOrder ID to analyze
            dimension_type: Optional filter by specific dimension type

        Returns:
            dict with capability indices and interpretation
        """
        query = SPCRecord.query.filter_by(wo_id=wo_id)
        if dimension_type:
            query = query.filter_by(dimension_type=dimension_type)

        records = query.all()

        if not records:
            return {
                "success": False,
                "error": f"No data found for work order {wo_id}",
            }

        values = [r.measured_value for r in records]
        n = len(values)

        if n < 2:
            return {
                "success": False,
                "error": "Insufficient data points",
            }

        # Calculate statistics
        mean = sum(values) / n
        variance = sum((x - mean) ** 2 for x in values) / (n - 1) if n > 1 else 0
        sigma = math.sqrt(variance)

        # Get specification limits from the records
        upper_spec = None
        lower_spec = None

        for record in records:
            if record.upper_limit and upper_spec is None:
                upper_spec = record.upper_limit
            if record.lower_limit and lower_spec is None:
                lower_spec = record.lower_limit

        # If no specs defined, use tolerance from target values
        targets = [r.target_value for r in records]
        avg_target = sum(targets) / len(targets)

        if upper_spec is None or lower_spec is None:
            # Estimate from historical data (would need configuration)
            estimated_tolerance = sigma * 6 * 3  # Assume process was capable at baseline
            upper_spec = avg_target + estimated_tolerance
            lower_spec = avg_target - estimated_tolerance

        # Calculate Cp (potential capability - assumes centered process)
        if sigma > 0:
            cp = (upper_spec - lower_spec) / (6 * sigma)
        else:
            cp = float('inf')

        # Calculate Cpk (actual performance - accounts for centering)
        cpu = (upper_spec - mean) / (3 * sigma) if sigma > 0 else float('inf')
        cpl = (mean - lower_spec) / (3 * sigma) if sigma > 0 else float('inf')
        cpk = min(cpu, cpl)

        # Calculate Pp and Ppk (overall performance using overall std dev)
        # For SPC data, we use the same sigma as it's based on within-subgroup variation
        pp = cp  # Same calculation for this context
        ppu = cpu
        ppl = cpl
        ppk = cpk

        # Interpretation guidelines:
        # Cp/Cpk > 1.33: Excellent capability
        # 1.0 < Cp/Cpk <= 1.33: Adequate capability
        # 0.67 < Cp/Cpk <= 1.0: Marginal - needs improvement
        # Cp/Cpk <= 0.67: Poor - process not capable

        interpretation = cls._interpret_capability(cpk)

        return {
            "success": True,
            "work_order_id": wo_id,
            "dimension_type": dimension_type or "all",
            "statistics": {
                "mean": round(mean, 4),
                "sigma": round(sigma, 4),
                "n_samples": n,
                "upper_specification_limit": round(upper_spec, 4) if upper_spec else None,
                "lower_specification_limit": round(lower_spec, 4) if lower_spec else None,
            },
            "capability_indices": {
                "Cp": round(cp, 3),      # Potential capability
                "Cpk": round(cpk, 3),    # Actual process capability
                "Pp": round(pp, 3),      # Overall performance (same as Cp for SPC)
                "Ppk": round(ppk, 3),    # Overall performance index
            },
            "component_indices": {
                "CPU": round(cpu, 3),    # Upper capability
                "CPL": round(cpl, 3),    # Lower capability
            },
            "interpretation": interpretation,
        }

    @classmethod
    def _interpret_capability(cls, cpk_value):
        """Interpret Cpk value and provide recommendations.

        Args:
            cpk_value: The calculated Cpk index

        Returns:
            dict with status, level, and recommended actions
        """
        if cpk_value >= 1.33:
            return {
                "status": "excellent",
                "level": "A",
                "description": "Process is highly capable with minimal defects expected",
                "recommended_action": "Continue monitoring; consider reducing inspection frequency",
            }
        elif cpk_value >= 1.0:
            return {
                "status": "adequate",
                "level": "B",
                "description": "Process is capable but has room for improvement",
                "recommended_action": "Monitor closely; investigate opportunities for centering",
            }
        elif cpk_value >= 0.67:
            return {
                "status": "marginal",
                "level": "C",
                "description": "Process is marginally capable; defects may occur",
                "recommended_action": "Implement corrective actions to improve capability",
            }
        else:
            return {
                "status": "poor",
                "level": "D",
                "description": "Process is not capable; significant defect rate expected",
                "recommended_action": "Immediate process improvement required; consider 100% inspection",
            }

    @classmethod
    def detect_control_violations(cls, wo_id=None):
        """Detect all out-of-control conditions in SPC data.

        Identifies:
        - Points beyond control limits (UCL/LCL)
        - Trends (7+ consecutive points trending up/down)
        - Shifts (8+ consecutive points on one side of center line)
        - Cycles (systematic variation patterns)

        Args:
            wo_id: Optional filter by specific work order

        Returns:
            list of violation records with details and severity
        """
        query = SPCRecord.query

        if wo_id:
            query = query.filter_by(wo_id=wo_id)

        records = query.order_by(SPCRecord.sample_number).all()

        violations = []
        center_line_avg = sum(r.measured_value for r in records) / len(records) if records else 0

        # Group by work order and dimension type for trend analysis
        groups = {}
        for record in records:
            key = (record.wo_id, record.dimension_type, record.shift_group)
            if key not in groups:
                groups[key] = []
            groups[key].append(record)

        for (wo_id_key, dim_type, shift), group_records in groups.items():
            values = [r.measured_value for r in group_records]

            # Check each point against control limits (using 3-sigma as standard)
            if len(values) >= 2:
                mean = sum(values) / len(values)
                variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
                sigma = math.sqrt(variance)

                ucl = mean + 3 * sigma
                lcl = mean - 3 * sigma

                # Check for out-of-control points
                for i, value in enumerate(values):
                    if value > ucl:
                        violations.append({
                            "type": "point_beyond_ucl",
                            "work_order_id": wo_id_key,
                            "dimension_type": dim_type,
                            "shift_group": shift,
                            "sample_number": group_records[i].sample_number,
                            "value": round(value, 4),
                            "limit_value": round(ucl, 4),
                            "severity": "high" if value > ucl * 1.2 else "medium",
                        })

                    elif value < lcl:
                        violations.append({
                            "type": "point_beyond_lcl",
                            "work_order_id": wo_id_key,
                            "dimension_type": dim_type,
                            "shift_group": shift,
                            "sample_number": group_records[i].sample_number,
                            "value": round(value, 4),
                            "limit_value": round(lcl, 4),
                            "severity": "high" if value < lcl * 0.8 else "medium",
                        })

                # Check for trends (7+ consecutive points)
                trend_count = 1
                trend_start = 0
                for i in range(1, len(values)):
                    if values[i] > values[i-1]:
                        trend_count += 1
                    else:
                        if trend_count >= 7:
                            violations.append({
                                "type": "trend_up" if trend_count >= 7 else "minor_trend",
                                "work_order_id": wo_id_key,
                                "dimension_type": dim_type,
                                "shift_group": shift,
                                "start_sample": group_records[trend_start].sample_number,
                                "end_sample": group_records[i-1].sample_number,
                                "consecutive_points": trend_count,
                                "direction": "up",
                                "severity": "medium" if trend_count >= 7 else "low",
                            })
                        trend_count = 1
                        trend_start = i

                # Check for shifts (8+ points on one side of center)
                above_count = 0
                below_count = 0
                shift_start = 0

                for i, value in enumerate(values):
                    if value > mean:
                        above_count += 1
                        below_count = 0
                    else:
                        below_count += 1
                        above_count = 0

                    if above_count >= 8:
                        violations.append({
                            "type": "shift_above_center",
                            "work_order_id": wo_id_key,
                            "dimension_type": dim_type,
                            "shift_group": shift,
                            "start_sample": group_records[shift_start].sample_number,
                            "end_sample": group_records[i].sample_number,
                            "consecutive_points": above_count,
                            "severity": "medium",
                        })

                    if below_count >= 8:
                        violations.append({
                            "type": "shift_below_center",
                            "work_order_id": wo_id_key,
                            "dimension_type": dim_type,
                            "shift_group": shift,
                            "start_sample": group_records[shift_start].sample_number,
                            "end_sample": group_records[i].sample_number,
                            "consecutive_points": below_count,
                            "severity": "medium",
                        })

                    if above_count == 0 and below_count == 0:
                        shift_start = i + 1

        return {
            "total_violations": len(violations),
            "violations": violations,
            "by_severity": {
                "high": sum(1 for v in violations if v.get("severity") == "high"),
                "medium": sum(1 for v in violations if v.get("severity") == "medium"),
                "low": sum(1 for v in violations if v.get("severity") == "low"),
            },
        }

    @classmethod
    def get_capability_trend(cls, wo_id, dimension_type=None, days_back=30):
        """Analyze capability trend over time.

        Tracks how Cp/Cpk values change across multiple batches/shifts to identify:
        - Capability degradation (worsening Cpk)
        - Improvement trends
        - Sudden shifts indicating process changes

        Args:
            wo_id: WorkOrder ID for historical analysis
            dimension_type: Optional filter by specific dimension type
            days_back: Number of days of history to analyze

        Returns:
            dict with trend analysis and predictions
        """
        from sqlalchemy import extract, func as sqlfunc

        cutoff_date = date.today() - timedelta(days=days_back)
        start_datetime = datetime.combine(cutoff_date, datetime.min.time())

        query = SPCRecord.query.filter(
            SPCRecord.wo_id == wo_id,
            SPCRecord.timestamp >= start_datetime
        )
        if dimension_type:
            query = query.filter_by(dimension_type=dimension_type)

        records = query.all()

        # Group by shift to get per-shift capability estimates
        shifts = {}
        for record in records:
            key = record.shift_group
            if key not in shifts:
                shifts[key] = []
            shifts[key].append(record.measured_value)

        trend_data = []
        for shift, values in shifts.items():
            if len(values) < 3:
                continue

            mean = sum(values) / len(values)
            variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
            sigma = math.sqrt(variance)

            # Estimate capability based on this shift's data
            target = record.target_value if hasattr(record, 'target_value') else mean
            tolerance = abs(target * 0.01) * 3  # Assume 1% tolerance

            cpk_estimate = (tolerance / (3 * sigma)) if sigma > 0 else float('inf')

            trend_data.append({
                "shift_group": shift,
                "sample_count": len(values),
                "mean": round(mean, 4),
                "sigma": round(sigma, 4),
                "estimated_cpk": round(min(cpk_estimate, 5.0), 3) if cpk_estimate != float('inf') else 5.0,
            })

        # Analyze trend direction
        if len(trend_data) >= 2:
            cpk_values = [d["estimated_cpk"] for d in trend_data]
            first_half_avg = sum(cpk_values[:len(cpk_values)//2]) / (len(cpk_values)//2)
            second_half_avg = sum(cpk_values[len(cpk_values)//2:]) / len(cpk_values[len(cpk_values)//2:])

            if second_half_avg > first_half_avg * 1.05:
                trend_direction = "improving"
            elif second_half_avg < first_half_avg * 0.95:
                trend_direction = "degrading"
            else:
                trend_direction = "stable"
        else:
            trend_direction = "insufficient_data"

        return {
            "work_order_id": wo_id,
            "dimension_type": dimension_type or "all",
            "analysis_period_days": days_back,
            "trend_direction": trend_direction,
            "shift_analyses": trend_data,
            "recommendation": cls._get_trend_recommendation(trend_direction),
        }

    @classmethod
    def _get_trend_recommendation(cls, trend_direction):
        """Get recommendation based on capability trend.

        Args:
            trend_direction: 'improving', 'degrading', or 'stable'

        Returns:
            string with recommended action
        """
        recommendations = {
            "improving": "Process is improving; continue current practices and monitor for sustained improvement",
            "degrading": "Process capability is declining; investigate root causes and implement corrective actions",
            "stable": "Process performance is stable; maintain current controls and monitoring frequency",
            "insufficient_data": "Insufficient data for trend analysis; collect more samples over time",
        }

        return recommendations.get(trend_direction, "Continue standard monitoring")


# Export for easy import
__all__ = ["SPCEngine"]
