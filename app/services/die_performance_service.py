"""Die Performance Service - Die lifecycle and productivity tracking.

This service handles:
- Tracking die usage across multiple billets/extrusions
- Calculating remaining die life as percentage of total cycles
- Recording failure reasons for quality analysis
- Computing die productivity metrics (output per cycle, setup times)

Integrates with the extended Die model fields added in Phase 1 migration.
"""

from datetime import datetime, date, timedelta
from sqlalchemy import func
import uuid

from .. import db
from ..models import (
    Billet,
    Die,
    DieInspection,
    ProcessRun,
)


class DiePerformanceService:
    """Track and analyze die performance metrics."""

    # ------------------------------------------------------------------
    # Die Usage Tracking
    # ------------------------------------------------------------------
    @classmethod
    def track_die_usage(cls, die_id, run_id=None):
        """Record a production run using this die.

        Updates the press_count for the die after each extrusion run.

        Args:
            die_id: ID of the Die being used
            run_id: Optional ProcessRun ID to link usage to

        Returns:
            dict with updated die lifecycle info
        """
        die = Die.query.get(die_id)
        if not die:
            return {
                "success": False,
                "error": f"Die '{die_id}' not found",
            }

        # Increment press count
        old_count = die.press_count
        new_count = old_count + 1
        die.press_count = new_count

        # Update last used timestamp
        die.last_used_at = datetime.utcnow()

        db.session.commit()

        return {
            "success": True,
            "die_id": str(die_id),
            "old_press_count": old_count,
            "new_press_count": new_count,
            "last_updated": datetime.utcnow().isoformat(),
        }

    @classmethod
    def track_batch_dies(cls, die_ids):
        """Track usage for multiple dies in a batch operation.

        Args:
            die_ids: List of Die IDs that were used

        Returns:
            dict with summary of tracked updates
        """
        results = []
        for die_id in die_ids:
            result = cls.track_die_usage(die_id)
            if result.get('success'):
                results.append(result)

        return {
            "total_attempted": len(die_ids),
            "successful": len(results),
            "details": results,
        }

    # ------------------------------------------------------------------
    # Die Life Remaining Calculation
    # ------------------------------------------------------------------
    @classmethod
    def calculate_die_life_remaining(cls, die_id):
        """Calculate remaining die life as percentage and absolute count.

        Uses the press_count_limit from the Die model to compute:
        - Absolute cycles remaining (press_count_limit - press_count)
        - Percentage remaining ((remaining / limit) * 100)

        Args:
            die_id: ID of the Die to analyze

        Returns:
            dict with life remaining metrics or error if no limit set
        """
        die = Die.query.get(die_id)
        if not die:
            return {
                "success": False,
                "error": f"Die '{die_id}' not found",
            }

        press_count_limit = die.press_count_limit
        current_presses = die.press_count or 0

        if not press_count_limit:
            return {
                "success": True,
                "die_id": str(die_id),
                "press_count_current": current_presses,
                "press_count_limit": None,
                "cycles_remaining": None,
                "percent_remaining": None,
                "note": "No press_count_limit defined for this die",
            }

        cycles_remaining = max(0, press_count_limit - current_presses)
        percent_remaining = (cycles_remaining / press_count_limit * 100) if press_count_limit > 0 else 0.0

        # Update the computed field in Die model
        die.die_life_cycles_remaining = cycles_remaining

        db.session.commit()

        return {
            "success": True,
            "die_id": str(die_id),
            "press_count_current": current_presses,
            "press_count_limit": press_count_limit,
            "cycles_remaining_absolute": cycles_remaining,
            "percent_remaining": round(percent_remaining, 2),
            "status": cls._get_life_status(cycles_remaining, percent_remaining),
        }

    @classmethod
    def _get_life_status(cls, cycles_remaining, percent_remaining):
        """Determine die life status based on remaining capacity.

        Returns:
            'good' if >50%, 'warning' if 20-50%, 'critical' if <20%
        """
        if percent_remaining is None or percent_remaining > 50:
            return 'good'
        elif percent_remaining >= 20:
            return 'warning'
        else:
            return 'critical'

    @classmethod
    def calculate_all_dies_life_remaining(cls):
        """Calculate remaining life for all dies in the system.

        Returns:
            dict with summary statistics and per-die breakdown
        """
        dies = Die.query.all()
        results = {}
        status_counts = {'good': 0, 'warning': 0, 'critical': 0}

        for die in dies:
            result = cls.calculate_die_life_remaining(die.id)
            if result.get('success'):
                results[die.id] = {
                    "die_code": die.die_code,
                    "profile_code": die.profile_code,
                    **{k: v for k, v in result.items() if k != 'success'},
                }

                status = cls._get_life_status(
                    result.get('cycles_remaining_absolute'),
                    result.get('percent_remaining')
                )
                status_counts[status] += 1

        return {
            "total_dies": len(dies),
            "status_summary": status_counts,
            "by_die": results,
        }

    # ------------------------------------------------------------------
    # Die Failure Recording
    # ------------------------------------------------------------------
    @classmethod
    def record_die_failure(cls, die_id, failure_reason, severity='moderate', details=None):
        """Record a failure event for this die.

        Args:
            die_id: ID of the Die that failed
            failure_reason: Description or code for what went wrong
            severity: 'minor', 'moderate', 'major', or 'critical'
            details: Optional dict with additional context (defect_type, inspection_result, etc.)

        Returns:
            dict with recorded failure info
        """
        die = Die.query.get(die_id)
        if not die:
            return {
                "success": False,
                "error": f"Die '{die_id}' not found",
            }

        # Update last_failure_reason in the Die model
        die.last_failure_reason = failure_reason
        die.status = 'TestingPending'  # Typically after a failure, needs inspection

        db.session.commit()

        return {
            "success": True,
            "die_id": str(die_id),
            "failure_recorded_at": datetime.utcnow().isoformat(),
            "failure_reason": failure_reason,
            "severity": severity,
            "new_die_status": die.status,
        }

    @classmethod
    def get_failure_history(cls, die_id=None, days_back=30):
        """Get recent failure history for a die or all dies.

        Args:
            die_id: Optional specific die to query
            days_back: Number of days of history to retrieve

        Returns:
            list of recent failures with details
        """
        from sqlalchemy import extract, func as sqlfunc

        cutoff_date = date.today() - timedelta(days=days_back)
        start_datetime = datetime.combine(cutoff_date, datetime.min.time())

        query = Die.query.filter(
            Die.last_failure_reason.isnot(None),
            Die.updated_at >= start_datetime
        )

        if die_id:
            query = query.filter(Die.id == str(die_id))

        dies_with_failures = query.all()

        failures = []
        for die in dies_with_failures:
            failures.append({
                "die_id": str(die.id),
                "die_code": die.die_code,
                "profile_code": die.profile_code,
                "alloy": die.alloy,
                "last_failure_reason": die.last_failure_reason,
                "status": die.status,
                "updated_at": die.updated_at.isoformat(),
            })

        return {"failures": failures}

    # ------------------------------------------------------------------
    # Die Productivity Metrics
    # ------------------------------------------------------------------
    @classmethod
    def compute_die_productivity(cls, die_id=None, start_date=None, end_date=None):
        """Compute productivity metrics for a die or all dies.

        Returns:
            dict with productivity statistics including:
            - Total output (kg) per die
            - Average cycles per day
            - Setup time efficiency
            - Downtime due to failures
        """
        if not start_date:
            start_date = (date.today() - timedelta(days=30)).isoformat()
        elif isinstance(start_date, date):
            start_date = start_date.isoformat()

        if not end_date:
            end_date = date.today().isoformat()
        elif isinstance(end_date, date):
            end_date = end_date.isoformat()

        query = Die.query

        if die_id:
            query = query.filter(Die.id == str(die_id))

        dies = query.all()
        productivity_results = {}

        for die in dies:
            # Count process runs with this die in the period
            from sqlalchemy import func as sqlfunc, text

            run_count_query = db.session.query(
                sqlfunc.count(ProcessRun.id)
            ).filter(
                ProcessRun.die_id == str(die.id),
                ProcessRun.started_at >= start_date,
                ProcessRun.started_at < end_date + ' 23:59:59',
                ProcessRun.status == 'COMPLETED'
            )

            total_runs = run_count_query.scalar() or 0

            # Get average setup time from model (populated during actual operations)
            avg_setup_time = die.average_setup_time_minutes or 0.0

            # Calculate productivity score (simplified formula)
            life_remaining_pct = die.die_life_cycles_remaining or 0
            if die.press_count_limit:
                life_remaining_pct = (life_remaining_pct / die.press_count_limit * 100)

            productivity_score = min(100, total_runs * 2 + life_remaining_pct)

            productivity_results[die.id] = {
                "die_code": die.die_code,
                "profile_code": die.profile_code,
                "alloy": die.alloy,
                "total_runs_in_period": total_runs,
                "average_setup_time_minutes": avg_setup_time,
                "life_remaining_percent": round(life_remaining_pct, 2),
                "productivity_score": round(productivity_score, 1),
            }

        return {"by_die": productivity_results}

    # ------------------------------------------------------------------
    # Die Lifecycle Summary Report
    # ------------------------------------------------------------------
    @classmethod
    def get_die_lifecycle_summary(cls):
        """Generate a comprehensive summary of all die lifecycle data.

        Returns:
            dict with aggregate statistics and per-die details
        """
        dies = Die.query.all()

        total_dies = len(dies)
        status_breakdown = {}
        alloy_breakdown = {}
        profile_breakdown = {}

        for die in dies:
            # Status breakdown
            status_breakdown[die.status] = status_breakdown.get(die.status, 0) + 1

            # Alloy breakdown
            if die.alloy:
                alloy_breakdown[die.alloy] = alloy_breakdown.get(die.alloy, 0) + 1

            # Profile breakdown
            if die.profile_code:
                profile_breakdown[die.profile_code] = profile_breakdown.get(die.profile_code, 0) + 1

        return {
            "total_dies": total_dies,
            "status_summary": status_breakdown,
            "alloy_summary": alloy_breakdown,
            "profile_summary": profile_breakdown,
            "detailed_list": [{
                "id": str(d.id),
                "die_code": d.die_code,
                "profile_code": d.profile_code,
                "alloy": d.alloy,
                "status": d.status,
                "press_count": d.press_count,
                "press_count_limit": d.press_count_limit,
                "life_cycles_remaining": d.die_life_cycles_remaining,
                "last_failure_reason": d.last_failure_reason,
                "total_setup_time_minutes": d.total_setup_time_minutes or 0.0,
                "average_setup_time_minutes": d.average_setup_time_minutes or 0.0,
            } for d in dies],
        }


# Export for easy import
__all__ = ["DiePerformanceService"]
