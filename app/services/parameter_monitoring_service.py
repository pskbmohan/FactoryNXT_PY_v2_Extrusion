"""Parameter Monitoring Service - Real-time process parameter tracking.

This service handles:
- Capture of real-time PLC parameters during extrusion runs
- Validation against setpoint limits (quality_parameters table)
- Automatic triggering when parameters exceed thresholds
- Generation of alerts for parameter violations
- Auto-stop functionality when critical limits are breached

Integrates with the existing PLCAdapter and ProcessRun model to provide
real-time quality monitoring capabilities.
"""

from datetime import datetime, timedelta
from sqlalchemy import and_
import uuid

from .. import db
from ..models import (
    IntegrationJob,
    ParameterReading,
    ProcessParameterAlert,
    QualityParameters,
    SetpointProfile,
    ProcessRun,
)


class ParameterMonitoringService:
    """Monitor process parameters and trigger alerts on violations."""

    # Threshold for auto-triggered stop (seconds after violation before confirming stop)
    AUTO_STOP_DELAY_SECONDS = 30

    # Critical parameter thresholds that immediately trigger stops
    CRITICAL_THRESHOLD_MULTIPLIER = 1.2  # 20% over limit is critical

    # ------------------------------------------------------------------
    # Parameter Reading Capture
    # ------------------------------------------------------------------
    @classmethod
    def capture_parameter_reading(cls, run_id, readings_dict):
        """Capture a real-time parameter reading from PLC for a process run.

        Args:
            run_id: ID of the ProcessRun being monitored
            readings_dict: Dict with keys matching ParameterReading columns:
                - billet_temp, container_temp, die_temp, exit_temp
                - ram_speed, main_cylinder_pressure, extrusion_force
                - cycle_time, stem_position, puller_speed, cooling_params

        Returns:
            dict with reading_id and validation results
        """
        # Create the parameter reading record
        reading = ParameterReading(
            id=str(uuid.uuid4()),
            run_id=run_id,
            timestamp=datetime.utcnow(),
            billet_temp=readings_dict.get('billet_temp'),
            container_temp=readings_dict.get('container_temp'),
            die_temp=readings_dict.get('die_temp'),
            exit_temp=readings_dict.get('exit_temp'),
            ram_speed=readings_dict.get('ram_speed'),
            main_cylinder_pressure=readings_dict.get('main_cylinder_pressure'),
            extrusion_force=readings_dict.get('extrusion_force'),
            cycle_time=readings_dict.get('cycle_time'),
            stem_position=readings_dict.get('stem_position'),
            puller_speed=readings_dict.get('puller_speed'),
            cooling_params=readings_dict.get('cooling_params', {}),
        )

        # Validate against limits and set flags
        validation_result = cls.check_parameter_limits(run_id, reading)
        reading.all_within_limits = validation_result['all_within_limits']
        reading.violation_count = validation_result['violation_count']

        db.session.add(reading)
        db.session.flush()

        # Create alerts for any violations
        if not validation_result['all_within_limits']:
            cls.generate_parameter_alerts(run_id, reading, validation_result['violations'])

        db.session.commit()

        return {
            "reading_id": reading.id,
            "timestamp": reading.timestamp.isoformat(),
            "all_within_limits": reading.all_within_limits,
            "violation_count": reading.violation_count,
            "violations": validation_result['violations'],
        }

    @classmethod
    def capture_batch_readings(cls, run_id, readings_list):
        """Capture multiple parameter readings in a batch.

        Args:
            run_id: ID of the ProcessRun being monitored
            readings_list: List of dicts, each with parameter values

        Returns:
            dict with summary of captured readings and violations
        """
        results = []
        total_violations = 0

        for reading_data in readings_list:
            result = cls.capture_parameter_reading(run_id, reading_data)
            results.append(result)
            if not result['all_within_limits']:
                total_violations += 1

        return {
            "readings_captured": len(results),
            "total_readings_with_violations": total_violations,
            "details": results,
        }

    # ------------------------------------------------------------------
    # Parameter Limit Validation
    # ------------------------------------------------------------------
    @classmethod
    def check_parameter_limits(cls, run_id, reading=None):
        """Check if current parameter readings are within setpoint limits.

        Args:
            run_id: ID of the ProcessRun being validated
            reading: Optional ParameterReading object or dict with readings

        Returns:
            dict with validation results:
                - all_within_limits: boolean
                - violation_count: number of parameters out of range
                - violations: list of dicts with parameter_name, actual_value, threshold_low, threshold_high
        """
        if reading is None:
            # Fetch latest reading for this run
            latest = ParameterReading.query.filter_by(run_id=run_id).order_by(
                ParameterReading.timestamp.desc()
            ).first()
            if not latest:
                return {
                    "all_within_limits": True,  # No data means no violations yet
                    "violation_count": 0,
                    "violations": [],
                }
            reading = latest

        # Get the setpoint profile for this run to find limits
        process_run = ProcessRun.query.get(run_id)
        if not process_run or not process_run.setpoint_profile_id:
            return {
                "all_within_limits": True,  # No profile means no limits defined yet
                "violation_count": 0,
                "violations": [],
            }

        setpoint = SetpointProfile.query.get(process_run.setpoint_profile_id)
        if not setpoint or not setpoint.parameters:
            return {
                "all_within_limits": True,
                "violation_count": 0,
                "violations": [],
            }

        # Also query quality_parameters table for profile-specific limits
        quality_params = cls._get_quality_parameter_limits(
            process_run.die_id, setpoint.alloy or setpoint.profile_code
        )

        # Parameters to check and their mapping in readings
        parameters_to_check = [
            ('billet_temp', 'billet_temp'),
            ('container_temp', 'container_temp'),
            ('die_temp', 'die_temp'),
            ('exit_temp', 'exit_temp'),
            ('ram_speed', 'ram_speed'),
            ('main_cylinder_pressure', 'main_cylinder_pressure'),
            ('extrusion_force', 'extrusion_force'),
            ('cycle_time', 'cycle_time'),
        ]

        violations = []
        violation_count = 0

        for param_name, reading_key in parameters_to_check:
            actual_value = getattr(reading, reading_key, None) if hasattr(reading, reading_key) else \
                          reading.get(reading_key) if isinstance(reading, dict) else None

            if actual_value is None:
                continue  # No value to check

            # Get limits from quality_parameters (preferred) or setpoint profile
            limit_low = quality_params.get(f'{param_name}_min') if quality_params else None
            limit_high = quality_params.get(f'{param_name}_max') if quality_params else None

            # Fallback to setpoint parameters for min/max if not in quality_parameters
            if not limit_low or not limit_high:
                setpoint_params = setpoint.parameters or {}
                param_data = setpoint_params.get(param_name, {})
                if isinstance(param_data, dict):
                    limit_low = param_data.get('min')
                    limit_high = param_data.get('max')

            # Check against limits
            violation_type = None
            if limit_low is not None and actual_value < limit_low:
                violation_type = 'low_limit'
            elif limit_high is not None and actual_value > limit_high:
                violation_type = 'high_limit'

            if violation_type:
                violation_count += 1
                violations.append({
                    "parameter_name": param_name,
                    "actual_value": actual_value,
                    "threshold_low": limit_low,
                    "threshold_high": limit_high,
                    "violation_type": violation_type,
                    "severity": cls._determine_severity(actual_value, limit_low, limit_high),
                })

        all_within_limits = violation_count == 0

        return {
            "all_within_limits": all_within_limits,
            "violation_count": violation_count,
            "violations": violations,
        }

    @classmethod
    def _get_quality_parameter_limits(cls, die_id, alloy_or_profile):
        """Get quality parameter limits from quality_parameters table.

        Args:
            die_id: ID of the die being used (for profile lookup)
            alloy_or_profile: Alloy code or profile code to match against

        Returns:
            dict with parameter name keys and min/max values, or None if not found
        """
        # Try to find matching quality parameters by alloy first
        quality_params = QualityParameters.query.filter(
            QualityParameters.alloy == alloy_or_profile,
            QualityParameters.is_active == True
        ).first()

        if not quality_params:
            # Fallback to profile_code match
            quality_params = QualityParameters.query.filter(
                QualityParameters.profile_code == alloy_or_profile,
                QualityParameters.is_active == True
            ).first()

        if not quality_params:
            return None

        # Build dict of parameter limits
        result = {
            'billet_temp_min': quality_params.billet_temp_min,
            'billet_temp_max': quality_params.billet_temp_max,
            'container_temp_min': quality_params.container_temp_min,
            'container_temp_max': quality_params.container_temp_max,
            'die_temp_min': quality_params.die_temp_min,
            'die_temp_max': quality_params.die_temp_max,
            'exit_temp_min': quality_params.exit_temp_min,
            'exit_temp_max': quality_params.exit_temp_max,
            'ram_speed_min': quality_params.ram_speed_min,
            'ram_speed_max': quality_params.ram_speed_max,
            'pressure_min': quality_params.pressure_min,
            'pressure_max': quality_params.pressure_max,
            'force_min': quality_params.force_min,
            'force_max': quality_params.force_max,
            'cycle_time_min': quality_params.cycle_time_min,
            'cycle_time_max': quality_params.cycle_time_max,
        }

        return result

    @classmethod
    def _determine_severity(cls, actual_value, limit_low, limit_high):
        """Determine severity of a parameter violation.

        Args:
            actual_value: The violated value
            limit_low: Lower threshold (if applicable)
            limit_high: Upper threshold (if applicable)

        Returns:
            'warning' or 'critical' based on how far beyond limits
        """
        if limit_low and limit_high:
            # Determine which limit was violated and by how much
            if actual_value < limit_low:
                deviation = ((limit_low - actual_value) / abs(limit_low)) * 100 if limit_low != 0 else 0
            else:
                deviation = ((actual_value - limit_high) / abs(limit_high)) * 100 if limit_high != 0 else 0

            # Critical if beyond 20% of threshold
            return 'critical' if deviation > (cls.CRITICAL_THRESHOLD_MULTIPLIER - 1) * 100 else 'warning'

        elif limit_low and actual_value < limit_low:
            return 'warning'
        elif limit_high and actual_value > limit_high:
            return 'warning'

        return 'warning'

    # ------------------------------------------------------------------
    # Alert Generation
    # ------------------------------------------------------------------
    @classmethod
    def generate_parameter_alerts(cls, run_id, reading, violations):
        """Generate process parameter alerts for each violation.

        Args:
            run_id: ID of the ProcessRun with violations
            reading: ParameterReading object or dict with readings
            violations: List of violation dicts from check_parameter_limits()

        Returns:
            list of created alert IDs
        """
        alert_ids = []

        for violation in violations:
            # Determine if auto-stop should be triggered
            needs_auto_stop = violation['severity'] == 'critical'

            alert = ProcessParameterAlert(
                id=str(uuid.uuid4()),
                run_id=run_id,
                parameter_name=violation['parameter_name'],
                actual_value=violation['actual_value'],
                threshold_low=violation['threshold_low'],
                threshold_high=violation['threshold_high'],
                triggered_at=datetime.utcnow(),
                auto_stop_triggered=False,  # Will be confirmed by operator or after delay
                violation_type=violation['violation_type'],
                severity=violation['severity'],
                status='active',
            )

            db.session.add(alert)
            alert_ids.append(alert.id)

        db.session.commit()

        # Check if any critical alerts should trigger auto-stop
        critical_alerts = ProcessParameterAlert.query.filter(
            ProcessParameterAlert.run_id == run_id,
            ProcessParameterAlert.status == 'active',
            ProcessParameterAlert.severity == 'critical'
        ).count()

        if critical_alerts > 0:
            cls._evaluate_auto_stop(run_id)

        return alert_ids

    @classmethod
    def _evaluate_auto_stop(cls, run_id):
        """Evaluate whether an auto-stop should be triggered.

        Checks for active critical alerts and determines if the machine
        should be automatically stopped to prevent further quality issues.

        Args:
            run_id: ID of the ProcessRun being evaluated

        Returns:
            dict with auto_stop decision and status
        """
        # Check for unconfirmed critical alerts
        critical_alerts = ProcessParameterAlert.query.filter(
            ProcessParameterAlert.run_id == run_id,
            ProcessParameterAlert.status == 'active',
            ProcessParameterAlert.severity == 'critical'
        ).all()

        if not critical_alerts:
            return {
                "auto_stop_triggered": False,
                "reason": "No active critical alerts",
            }

        # Check if any alert has been pending long enough for auto-stop
        now = datetime.utcnow()
        for alert in critical_alerts:
            time_since_trigger = (now - alert.triggered_at).total_seconds()

            if time_since_trigger >= cls.AUTO_STOP_DELAY_SECONDS:
                # Trigger auto-stop
                alert.auto_stop_triggered = True
                alert.status = 'acknowledged'  # Auto-trigger counts as acknowledgment
                db.session.commit()

                return {
                    "auto_stop_triggered": True,
                    "alert_id": alert.id,
                    "parameter_name": alert.parameter_name,
                    "time_to_trigger_seconds": time_since_trigger,
                    "action": "Machine stop command should be sent to PLC",
                }

        # Still within grace period - no auto-stop yet
        return {
            "auto_stop_triggered": False,
            "reason": f"Still within {cls.AUTO_STOP_DELAY_SECONDS}s grace period for operator confirmation",
        }

    @classmethod
    def confirm_auto_stop(cls, alert_id, confirmed_by):
        """Manually confirm an auto-stop trigger by an operator.

        Args:
            alert_id: ID of the ProcessParameterAlert to confirm
            confirmed_by: Operator ID/name who confirmed the stop

        Returns:
            dict with confirmation status
        """
        alert = ProcessParameterAlert.query.get(alert_id)
        if not alert:
            return {
                "success": False,
                "error": "Alert not found",
            }

        alert.auto_stop_triggered = True
        alert.stop_confirmed_by = confirmed_by
        alert.status = 'acknowledged'
        db.session.commit()

        return {
            "success": True,
            "alert_id": alert.id,
            "confirmed_by": confirmed_by,
            "timestamp": datetime.utcnow().isoformat(),
        }

    # ------------------------------------------------------------------
    # Query Methods for Dashboards
    # ------------------------------------------------------------------
    @classmethod
    def get_active_alerts(cls, run_id=None):
        """Get all active parameter violation alerts.

        Args:
            run_id: Optional filter by specific run ID

        Returns:
            list of alert dicts with current status
        """
        query = ProcessParameterAlert.query.filter_by(status='active')

        if run_id:
            query = query.filter_by(run_id=run_id)

        alerts = query.all()

        return [{
            "id": a.id,
            "run_id": a.run_id,
            "parameter_name": a.parameter_name,
            "actual_value": a.actual_value,
            "threshold_low": a.threshold_low,
            "threshold_high": a.threshold_high,
            "violation_type": a.violation_type,
            "severity": a.severity,
            "triggered_at": a.triggered_at.isoformat(),
            "auto_stop_triggered": a.auto_stop_triggered,
        } for a in alerts]

    @classmethod
    def get_parameter_trend(cls, run_id, parameter_name=None):
        """Get time series of parameter readings for trend analysis.

        Args:
            run_id: ID of the ProcessRun
            parameter_name: Optional filter by specific parameter

        Returns:
            list of reading dicts with timestamps and values
        """
        query = ParameterReading.query.filter_by(run_id=run_id).order_by(
            ParameterReading.timestamp.asc()
        )

        if parameter_name:
            # Filter to readings that have this parameter recorded
            query = query.filter(getattr(ParameterReading, parameter_name) is not None)

        readings = query.all()

        return [{
            "id": r.id,
            "timestamp": r.timestamp.isoformat(),
            "billet_temp": r.billet_temp,
            "container_temp": r.container_temp,
            "die_temp": r.die_temp,
            "exit_temp": r.exit_temp,
            "ram_speed": r.ram_speed,
            "main_cylinder_pressure": r.main_cylinder_pressure,
            "extrusion_force": r.extrusion_force,
            "cycle_time": r.cycle_time,
            "stem_position": r.stem_position,
            "puller_speed": r.puller_speed,
        } for r in readings]


# Export for easy import
__all__ = ["ParameterMonitoringService"]
