"""ERP adapter service — Lighthouse Info System Pvt Ltd · V15 · Oracle connector.

Production ERP target:
    ERP Software : Lighthouse Info System Pvt Ltd
    Version      : V15
    Database     : Oracle Database (local server)
    Connectivity : Direct DB connection
    Major tables : Itemtran_Head, Itemtran_Body, Acc_Mast, Item_Mast

Wraps all ERP-facing operations (``post_inspection``, ``post_test``,
``post_nitriding``, ``import_orders``) in an IntegrationJob so that transient
failures can be retried asynchronously without blocking the UI. Every
external call also writes an ERPTransactionLog row so admins can audit
exactly what was sent / received.

This is a mock implementation — replace ``_call_erp`` with the real
Oracle/JDBC/ODBC bridge once the endpoint contract is shared by the
Lighthouse ERP team.
"""

import json
import uuid
from datetime import datetime, timedelta

from .. import db
from ..models import (
    CustomerOrder,
    DieInspection,
    DieTest,
    IntegrationJob,
    NitridingRecord,
    ERPTransactionLog,
)


class ERPAdapter:
    """Thin adapter that wraps ERP-facing calls with retry + audit."""

    # ------------------------------------------------------------------
    # internal helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _new_log_id():
        # Use a monotonic-ish integer PK (BigInteger); use microsecond epoch.
        return int(datetime.utcnow().timestamp() * 1_000_000)

    @classmethod
    def _call_erp(cls, endpoint, payload):
        """Mock ERP HTTP call. Returns a dict shaped like a normal response.

        In production this would do ``requests.post(...)`` to the real ERP
        endpoint. The mock always succeeds so the smoke flow works.
        """
        return {
            "status": "OK",
            "erp_ref": f"ERP-{uuid.uuid4().hex[:8].upper()}",
            "timestamp": datetime.utcnow().isoformat(),
        }

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
    def _write_txlog(cls, direction, entity_type, entity_id, payload,
                     status="PENDING", erp_response=None):
        log = ERPTransactionLog(
            id=cls._new_log_id(),
            direction=direction,
            entity_type=entity_type,
            entity_id=entity_id,
            payload=payload,
            erp_response=erp_response or {},
            status=status,
        )
        db.session.add(log)
        return log

    @classmethod
    def _finalize_job(cls, job, response, success=True):
        now = datetime.utcnow()
        job.result = {"erp_response": response}
        job.completed_at = now
        job.status = "Success" if success else "Failed"
        if not success and job.retries < job.max_retries:
            job.status = "RetryQueued"
            job.retries += 1
            job.next_retry_at = now + timedelta(minutes=2 ** job.retries)

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    @classmethod
    def post_inspection(cls, die_inspection):
        """Post a DieInspection record to the ERP.

        Creates an IntegrationJob (so it can be retried) and an
        ERPTransactionLog (for auditing). Marks the inspection as posted
        on success.
        """
        if not isinstance(die_inspection, DieInspection):
            raise TypeError("post_inspection expects a DieInspection instance")

        payload = {
            "die_id": die_inspection.die_id,
            "inspection_id": die_inspection.id,
            "inspection_date": (
                die_inspection.inspection_date.isoformat()
                if die_inspection.inspection_date
                else None
            ),
            "inspector": die_inspection.inspector,
            "dimensions_ok": die_inspection.dimensions_ok,
            "surface_ok": die_inspection.surface_ok,
            "hardness": die_inspection.hardness,
            "notes": die_inspection.notes,
        }

        job = cls._create_job("ERP_POST_INSPECTION", payload)
        txlog = cls._write_txlog(
            direction="OUTBOUND",
            entity_type="DieInspection",
            entity_id=die_inspection.id,
            payload=payload,
        )

        try:
            job.status = "Running"
            job.started_at = datetime.utcnow()
            response = cls._call_erp("die-inspection", payload)
            cls._finalize_job(job, response, success=True)
            die_inspection.erp_posted = True
            die_inspection.erp_posted_at = datetime.utcnow()
            txlog.status = "SUCCESS"
            txlog.erp_response = response
        except Exception as exc:  # pragma: no cover - mock always succeeds
            cls._finalize_job(job, {"error": str(exc)}, success=False)
            txlog.status = "FAILED"
            txlog.erp_response = {"error": str(exc)}

        return {
            "success": job.status == "Success",
            "job_id": job.id,
            "job_status": job.status,
        }

    @classmethod
    def post_test(cls, die_test):
        """Post a DieTest record to the ERP."""
        if not isinstance(die_test, DieTest):
            raise TypeError("post_test expects a DieTest instance")

        payload = {
            "die_id": die_test.die_id,
            "test_id": die_test.id,
            "test_date": (
                die_test.test_date.isoformat() if die_test.test_date else None
            ),
            "tester": die_test.tester,
            "press_force": die_test.press_force,
            "temperature": die_test.temperature,
            "profile_quality": die_test.profile_quality,
            "result": die_test.result,
        }

        job = cls._create_job("ERP_POST_TEST", payload)
        txlog = cls._write_txlog(
            direction="OUTBOUND",
            entity_type="DieTest",
            entity_id=die_test.id,
            payload=payload,
        )

        try:
            job.status = "Running"
            job.started_at = datetime.utcnow()
            response = cls._call_erp("die-test", payload)
            cls._finalize_job(job, response, success=True)
            die_test.erp_posted = True
            die_test.erp_posted_at = datetime.utcnow()
            txlog.status = "SUCCESS"
            txlog.erp_response = response
        except Exception as exc:
            cls._finalize_job(job, {"error": str(exc)}, success=False)
            txlog.status = "FAILED"
            txlog.erp_response = {"error": str(exc)}

        return {
            "success": job.status == "Success",
            "job_id": job.id,
            "job_status": job.status,
        }

    @classmethod
    def post_nitriding(cls, nitriding_record):
        """Post a NitridingRecord to the ERP."""
        if not isinstance(nitriding_record, NitridingRecord):
            raise TypeError("post_nitriding expects a NitridingRecord instance")

        payload = {
            "die_id": nitriding_record.die_id,
            "record_id": nitriding_record.id,
            "furnace_id": nitriding_record.furnace_id,
            "start_temp": nitriding_record.start_temp,
            "end_temp": nitriding_record.end_temp,
            "duration_hours": nitriding_record.duration_hours,
            "atmosphere": nitriding_record.atmosphere,
            "hardness_before": nitriding_record.hardness_before,
            "hardness_after": nitriding_record.hardness_after,
            "operator": nitriding_record.operator,
        }

        job = cls._create_job("ERP_POST_NITRIDING", payload)
        txlog = cls._write_txlog(
            direction="OUTBOUND",
            entity_type="NitridingRecord",
            entity_id=nitriding_record.id,
            payload=payload,
        )

        try:
            job.status = "Running"
            job.started_at = datetime.utcnow()
            response = cls._call_erp("nitriding", payload)
            cls._finalize_job(job, response, success=True)
            nitriding_record.erp_posted = True
            nitriding_record.erp_posted_at = datetime.utcnow()
            txlog.status = "SUCCESS"
            txlog.erp_response = response
        except Exception as exc:
            cls._finalize_job(job, {"error": str(exc)}, success=False)
            txlog.status = "FAILED"
            txlog.erp_response = {"error": str(exc)}

        return {
            "success": job.status == "Success",
            "job_id": job.id,
            "job_status": job.status,
        }

    @classmethod
    def import_orders(cls):
        """Fetch customer orders from the ERP and create ``CustomerOrder`` rows.

        In production this would call the ERP orders endpoint; the mock
        returns an empty list so the smoke flow still exercises the path.
        """
        job = cls._create_job(
            "ERP_ORDER_IMPORT",
            {"scope": "customer_orders"},
        )
        txlog = cls._write_txlog(
            direction="INBOUND",
            entity_type="CustomerOrder",
            entity_id=None,
            payload={"scope": "customer_orders"},
        )

        imported = 0
        try:
            job.status = "Running"
            job.started_at = datetime.utcnow()

            # Mock fetch — replace with real HTTP call to ERP orders endpoint
            remote_orders = cls._call_erp("orders-list", {})
            orders_payload = remote_orders.get("orders", [])

            for row in orders_payload:
                order_number = row.get("order_number")
                if not order_number:
                    continue
                existing = CustomerOrder.query.filter_by(
                    order_number=order_number
                ).first()
                if existing:
                    continue
                order = CustomerOrder(
                    id=str(uuid.uuid4()),
                    order_number=order_number,
                    customer_name=row.get("customer_name", ""),
                    product_profile=row.get("product_profile"),
                    alloy=row.get("alloy"),
                    quantity_tons=float(row.get("quantity_tons") or 0),
                    due_date=(
                        datetime.strptime(row["due_date"], "%Y-%m-%d").date()
                        if row.get("due_date")
                        else None
                    ),
                    erp_reference=row.get("erp_reference"),
                    status=row.get("status", "CONFIRMED"),
                )
                db.session.add(order)
                imported += 1

            response = {"imported": imported, "skipped_duplicates": 0}
            cls._finalize_job(job, response, success=True)
            txlog.status = "SUCCESS"
            txlog.erp_response = response
        except Exception as exc:
            response = {"error": str(exc), "imported": imported}
            cls._finalize_job(job, response, success=False)
            txlog.status = "FAILED"
            txlog.erp_response = response

        return {
            "success": job.status == "Success",
            "job_id": job.id,
            "imported": imported,
        }
