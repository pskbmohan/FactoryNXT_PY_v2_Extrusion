"""PLC adapter service.

Abstracts the protocol-level details (OPC-UA, Modbus, MQTT) behind a
uniform Python API. The current implementation is a mock that returns
deterministic fake values; in production it would instantiate a real
driver selected from the PLCSignalMapping table.

Each external call is wrapped in an IntegrationJob so the UI can track
whether the PLC command succeeded end-to-end.
"""

import random
import uuid
from datetime import datetime

from .. import db
from ..models import IntegrationJob, PLCSignalMapping, ProcessRun


class PLCAdapter:
    """High-level PLC façade — setpoints, capture, query."""

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    @classmethod
    def _create_job(cls, job_type, payload):
        job = IntegrationJob(
            id=str(uuid.uuid4()),
            job_type=job_type,
            status="Pending",
            payload=payload,
        )
        db.session.add(job)
        db.session.flush()
        return job

    @classmethod
    def _finalize(cls, job, result, success=True):
        now = datetime.utcnow()
        job.result = result
        job.completed_at = now
        job.status = "Success" if success else "Failed"

    @classmethod
    def _get_signals(cls, machine_name, signal_type=None):
        q = PLCSignalMapping.query.filter_by(machine_name=machine_name, is_active=True)
        if signal_type:
            q = q.filter_by(signal_type=signal_type)
        return q.all()

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    @classmethod
    def load_setpoint(cls, machine_name, setpoint_profile):
        """Push the setpoint profile's parameter values to ``machine_name``.

        ``setpoint_profile`` is a SetpointProfile row; its ``parameters``
        dict maps signal tags to numerical values.

        In production this maps each tag through PLCSignalMapping →
        OPC-UA write / Modbus register write. Mock writes return a fake
        acknowledgement.
        """
        params = setpoint_profile.parameters or {}
        payload = {
            "machine_name": machine_name,
            "setpoint_profile_id": getattr(setpoint_profile, "id", None),
            "process_type": getattr(setpoint_profile, "process_type", None),
            "parameters": params,
        }
        job = cls._create_job("PLC_SETPOINT_LOAD", payload)
        job.status = "Running"
        job.started_at = datetime.utcnow()

        # Mock: pretend each signal was accepted
        written = []
        for tag, value in params.items():
            mapping = PLCSignalMapping.query.filter_by(
                machine_name=machine_name, signal_tag=tag, is_active=True
            ).first()
            written.append({
                "tag": tag,
                "value": value,
                "mapped": mapping is not None,
            })

        cls._finalize(job, {"written": written, "machine": machine_name}, success=True)
        return {
            "success": True,
            "job_id": job.id,
            "written": written,
        }

    @classmethod
    def capture_actuals(cls, machine_name, process_run):
        """Read current actuals from ``machine_name`` and bind to a ProcessRun.

        Returns the values it captured so callers can persist a record.
        """
        payload = {
            "machine_name": machine_name,
            "process_run_id": process_run.id,
            "process_type": process_run.process_type,
        }
        job = cls._create_job("PLC_CAPTURE", payload)
        job.status = "Running"
        job.started_at = datetime.utcnow()

        # Mock data: one reading per active ACTUAL signal
        actuals = cls._get_signals(machine_name, signal_type="ACTUAL")
        readings = []
        for sig in actuals:
            readings.append({
                "tag": sig.signal_tag,
                "unit": sig.unit,
                "value": round(random.uniform(100.0, 500.0), 2),
            })

        cls._finalize(job, {"readings": readings}, success=True)
        return {
            "success": True,
            "job_id": job.id,
            "readings": readings,
        }

    @classmethod
    def query_signal(cls, machine_name, signal_tag):
        """Return the current value for a single signal.

        This is a read-only probe (no IntegrationJob needed).
        Mock returns a deterministic pseudo-random value seeded by the
        tag so the dashboard sees stable-looking numbers between polls.
        """
        mapping = PLCSignalMapping.query.filter_by(
            machine_name=machine_name, signal_tag=signal_tag, is_active=True
        ).first()

        unit = mapping.unit if mapping else ""
        rng = random.Random(hash((machine_name, signal_tag)) & 0xFFFFFFFF)
        value = round(rng.uniform(100.0, 600.0), 2)

        return {
            "machine_name": machine_name,
            "signal_tag": signal_tag,
            "value": value,
            "unit": unit,
            "mapped": mapping is not None,
            "timestamp": datetime.utcnow().isoformat(),
        }
