"""KPI engine service.

Computes aggregate KPIs for the foundry domain:
- OEE (availability × performance × quality) per machine per shift
- Die lifetime (aggregate life_cycles_total across dies)
- Shortage risk (die + billet shortages that could delay production)

The engine follows the existing ``OeeSnapshot`` pattern for legacy SMT
records while also reading the new ``ProcessRun`` table for extrusion
data. Results are persisted to ``KPIRecord`` so the dashboard can render
without recomputing on every load.
"""

from datetime import datetime, date
from .. import db
from ..models import (
    Alert,
    AlertRule,
    Billet,
    Die,
    DowntimeEvent,
    KPIRecord,
    ProcessRun,
)


class KPIEngine:
    """Compute and persist foundry KPIs."""

    SHIFT_HOURS = 8.0
    SHIFT_MIN = SHIFT_HOURS * 60

    # ------------------------------------------------------------------
    # OEE
    # ------------------------------------------------------------------
    @classmethod
    def compute_oee(cls, machine_id, shift_date):
        """Compute OEE for a machine on a specific shift_date.

        OEE = availability * performance * quality
        - availability = (planned_time - downtime) / planned_time
        - performance = (actual_runs / ideal_runs)  [using ProcessRun count]
        - quality = (completed_runs / total_runs)
        """
        if isinstance(shift_date, str):
            try:
                shift_date = datetime.strptime(shift_date, "%Y-%m-%d").date()
            except ValueError:
                shift_date = date.today()

        if not isinstance(shift_date, date):
            shift_date = date.today()

        shift_start = datetime.combine(shift_date, datetime.min.time())
        shift_end = shift_start.replace(
            hour=int(cls.SHIFT_HOURS), minute=0, second=0
        )

        # Downtime from legacy table
        downtime_min = (
            db.session.query(db.func.coalesce(db.func.sum(DowntimeEvent.duration_min), 0))
            .filter(DowntimeEvent.machine_id == str(machine_id))
            .filter(DowntimeEvent.started_at >= shift_start)
            .filter(DowntimeEvent.started_at < shift_end)
            .scalar()
            or 0.0
        )

        # Process runs for this machine/shift
        runs = ProcessRun.query.filter(
            ProcessRun.machine_id == str(machine_id),
            ProcessRun.started_at >= shift_start,
            ProcessRun.started_at < shift_end,
        ).all()

        total_runs = len(runs)
        completed_runs = sum(1 for r in runs if r.status == "COMPLETED")
        failed_runs = sum(1 for r in runs if r.status == "FAILED")

        planned_time_min = cls.SHIFT_MIN
        availability = (
            (planned_time_min - downtime_min) / planned_time_min
            if planned_time_min > 0
            else 0.0
        )
        # Performance: assume 1 run per hour as ideal
        ideal_runs = cls.SHIFT_HOURS
        performance = min(1.0, total_runs / ideal_runs) if ideal_runs else 0.0

        # Quality: ratio of completed (good) runs to all runs
        quality = (
            completed_runs / total_runs if total_runs > 0 else 1.0
        )

        oee = availability * performance * quality

        record = KPIRecord(
            id=str(db.func.gen_random_uuid().self_group())
            if hasattr(db.func, "gen_random_uuid")
            else str(__import__("uuid").uuid4()),
            kpi_type="OEE",
            machine_id=str(machine_id),
            shift_date=shift_date,
            value=round(oee * 100, 2),
            unit="%",
            details={
                "availability": round(availability, 4),
                "performance": round(performance, 4),
                "quality": round(quality, 4),
                "downtime_min": downtime_min,
                "total_runs": total_runs,
                "completed_runs": completed_runs,
                "failed_runs": failed_runs,
            },
            calculated_at=datetime.utcnow(),
        )
        db.session.add(record)
        db.session.commit()

        return {
            "machine_id": machine_id,
            "shift_date": shift_date.isoformat(),
            "oee": record.value,
            "availability": record.details["availability"],
            "performance": record.details["performance"],
            "quality": record.details["quality"],
            "downtime_min": downtime_min,
            "total_runs": total_runs,
            "completed_runs": completed_runs,
            "failed_runs": failed_runs,
        }

    # ------------------------------------------------------------------
    # Die lifetime
    # ------------------------------------------------------------------
    @classmethod
    def compute_die_lifetime(cls):
        """Aggregate die lifecycle data: avg cycles, min/max, count by status."""
        dies = Die.query.all()
        total = len(dies)
        if total == 0:
            avg_cycles = 0.0
            min_cycles = 0
            max_cycles = 0
        else:
            cycles = [d.life_cycles_total for d in dies]
            avg_cycles = sum(cycles) / total
            min_cycles = min(cycles)
            max_cycles = max(cycles)

        status_buckets = {}
        for d in dies:
            status_buckets[d.status] = status_buckets.get(d.status, 0) + 1

        record = KPIRecord(
            id=str(__import__("uuid").uuid4()),
            kpi_type="DIE_LIFETIME",
            machine_id=None,
            shift_date=date.today(),
            value=round(avg_cycles, 2),
            unit="cycles",
            details={
                "total_dies": total,
                "min_cycles": min_cycles,
                "max_cycles": max_cycles,
                "status_buckets": status_buckets,
            },
            calculated_at=datetime.utcnow(),
        )
        db.session.add(record)
        db.session.commit()

        return {
            "total_dies": total,
            "avg_cycles": avg_cycles,
            "min_cycles": min_cycles,
            "max_cycles": max_cycles,
            "status_buckets": status_buckets,
        }

    # ------------------------------------------------------------------
    # Shortage risk
    # ------------------------------------------------------------------
    @classmethod
    def compute_shortage_risk(cls):
        """Compute planning risk alerts due to die/billet shortages.

        Returns a dict listing open shortages and auto-creates Alert rows
        for items that breach the threshold (die shortage >= 2 or billet
        shortage >= 5 tons of equivalent demand).
        """
        available_dies = Die.query.filter_by(status="Available").count()
        available_billets = Billet.query.filter_by(status="AVAILABLE").count()

        # Simple heuristic: compare against a baseline (configurable later)
        from .scheduler import ScheduleOptimizer

        shortages = ScheduleOptimizer.compute_shortages()
        die_shortages = shortages.get("die_shortages", [])
        billet_shortages = shortages.get("billet_shortages", [])

        alerts_created = []
        for s in die_shortages:
            if s.get("shortage", 0) >= 2:
                existing = Alert.query.filter_by(
                    source="PLANNING",
                    source_id=f"die-{s.get('alloy')}-{s.get('profile_shape')}",
                    status="Open",
                ).first()
                if not existing:
                    alert = Alert(
                        id=str(__import__("uuid").uuid4()),
                        severity="WARNING",
                        title="Die shortage projected",
                        message=(
                            f"Alloy {s.get('alloy')} profile "
                            f"{s.get('profile_shape')}: need {s.get('needed')}, "
                            f"have {s.get('available')}."
                        ),
                        source="PLANNING",
                        source_id=f"die-{s.get('alloy')}-{s.get('profile_shape')}",
                    )
                    db.session.add(alert)
                    alerts_created.append(alert.id)

        for s in billet_shortages:
            if s.get("shortage", 0) >= 5:
                existing = Alert.query.filter_by(
                    source="PLANNING",
                    source_id=f"billet-{s.get('alloy')}",
                    status="Open",
                ).first()
                if not existing:
                    alert = Alert(
                        id=str(__import__("uuid").uuid4()),
                        severity="CRITICAL",
                        title="Billet shortage projected",
                        message=(
                            f"Alloy {s.get('alloy')}: need {s.get('needed')}, "
                            f"have {s.get('available')}."
                        ),
                        source="PLANNING",
                        source_id=f"billet-{s.get('alloy')}",
                    )
                    db.session.add(alert)
                    alerts_created.append(alert.id)

        db.session.commit()

        # Persist a snapshot
        record = KPIRecord(
            id=str(__import__("uuid").uuid4()),
            kpi_type="SHORTAGE",
            machine_id=None,
            shift_date=date.today(),
            value=len(die_shortages) + len(billet_shortages),
            unit="alerts",
            details={
                "die_shortages": die_shortages,
                "billet_shortages": billet_shortages,
                "new_alerts": alerts_created,
            },
            calculated_at=datetime.utcnow(),
        )
        db.session.add(record)
        db.session.commit()

        return {
            "die_shortages": die_shortages,
            "billet_shortages": billet_shortages,
            "new_alerts": alerts_created,
        }

    # ------------------------------------------------------------------
    # Rule evaluation
    # ------------------------------------------------------------------
    @classmethod
    def evaluate_rules(cls, kpi_records):
        """Evaluate active AlertRules against the provided KPI records.

        Any rule breach creates a new Alert with severity from the rule.
        """
        rules = AlertRule.query.filter_by(is_active=True).all()
        triggered = 0

        for rule in rules:
            threshold = rule.threshold_value or {}
            threshold_val = threshold.get("value")
            if threshold_val is None:
                continue

            for record in kpi_records:
                if record.kpi_type != rule.metric:
                    continue

                breach = False
                if rule.operator == "GT" and (record.value or 0) > threshold_val:
                    breach = True
                elif rule.operator == "LT" and (record.value or 0) < threshold_val:
                    breach = True
                elif rule.operator == "EQ" and (record.value or 0) == threshold_val:
                    breach = True
                elif rule.operator == "BETWEEN":
                    low = threshold.get("low")
                    high = threshold.get("high")
                    if low is not None and high is not None:
                        breach = low <= (record.value or 0) <= high

                if breach:
                    existing = Alert.query.filter_by(
                        rule_id=rule.id, source="KPI",
                        source_id=str(record.id), status="Open",
                    ).first()
                    if existing:
                        continue
                    alert = Alert(
                        id=str(__import__("uuid").uuid4()),
                        rule_id=rule.id,
                        severity=rule.severity,
                        title=f"{rule.name} breached",
                        message=(
                            f"{rule.metric} = {record.value} {record.unit} "
                            f"({rule.operator} {threshold_val})"
                        ),
                        source="KPI",
                        source_id=str(record.id),
                    )
                    db.session.add(alert)
                    triggered += 1

        db.session.commit()
        return {"rules_evaluated": len(rules), "alerts_triggered": triggered}
