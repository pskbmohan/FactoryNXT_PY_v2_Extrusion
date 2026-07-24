"""Work Order on-time delivery probability engine.

Pure Python, deterministic — no ML libraries. See app/routes/aps.py
(api_wo_probability) for the HTTP surface and
app/templates/aps/wo_probability.html for the dashboard that consumes it.

Formula
-------
progress_ratio = actual_qty / required_qty
time_ratio      = elapsed_hours / total_duration_hours   (time consumed as % of window)
pace_index      = progress_ratio / time_ratio            (>1 ahead, <1 behind)
probability     = clamp(50 + (pace_index - 1.0) * 50, 0, 100)
                  then -20% if time_buffer_hours < 0, +10% if time_buffer_hours > 8
                  then re-clamped to [0, 100]

Two cases short-circuit the formula entirely: already complete (100) and
overdue-and-incomplete (0).
"""
from datetime import datetime, timedelta

CRITICAL_MAX = 40
AT_RISK_MAX = 70
ON_TRACK_MAX = 90

_STATUS_MESSAGES = {
    "critical": "Critical — immediate action required to recover schedule.",
    "at_risk": "At risk — behind pace, monitor closely.",
    "on_track": "On track for on-time delivery.",
    "ahead": "Ahead of schedule.",
}


def _clamp(value, lo, hi):
    return max(lo, min(hi, value))


def _status_for(probability_pct):
    if probability_pct < CRITICAL_MAX:
        return "critical"
    if probability_pct < AT_RISK_MAX:
        return "at_risk"
    if probability_pct <= ON_TRACK_MAX:
        return "on_track"
    return "ahead"


def calculate_wo_probability(work_order, now=None) -> dict:
    """Compute the on-time delivery probability for one Work Order.

    `now` is injectable for tests; defaults to datetime.utcnow() to match
    this codebase's naive-UTC convention (see app/services/aps_engine.py).
    """
    now = now or datetime.utcnow()

    required_qty = float(work_order.quantity or 0)
    actual_qty = float(work_order.produced_qty or 0)
    target_date = work_order.due_date
    start_ref = work_order.started_at or work_order.released_at

    progress_pct = (actual_qty / required_qty * 100.0) if required_qty > 0 else 100.0

    elapsed_hours = (
        max(0.0, (now - start_ref).total_seconds() / 3600.0) if start_ref else 0.0
    )
    remaining_hours = (
        (target_date - now).total_seconds() / 3600.0 if target_date else None
    )

    current_rate_per_hour = (actual_qty / elapsed_hours) if elapsed_hours > 0 else 0.0
    remaining_qty = max(0.0, required_qty - actual_qty)

    if current_rate_per_hour > 0:
        projected_completion = now + timedelta(hours=remaining_qty / current_rate_per_hour)
    else:
        projected_completion = None

    if target_date and projected_completion:
        time_buffer_hours = (target_date - projected_completion).total_seconds() / 3600.0
    elif remaining_hours is not None:
        # No established rate yet (WO just started, or fully complete) — fall
        # back to raw time-to-target as the buffer signal.
        time_buffer_hours = remaining_hours
    else:
        time_buffer_hours = 0.0

    already_complete = required_qty > 0 and actual_qty >= required_qty
    overdue = target_date is not None and now > target_date and actual_qty < required_qty

    pace_index = None
    if already_complete or (required_qty == 0 and actual_qty == 0):
        probability_pct = 100.0
    elif overdue:
        probability_pct = 0.0
    else:
        progress_ratio = (actual_qty / required_qty) if required_qty > 0 else 1.0
        if elapsed_hours == 0:
            pace_index = 1.0
        else:
            total_duration_hours = (
                (target_date - start_ref).total_seconds() / 3600.0
                if target_date and start_ref
                else None
            )
            if total_duration_hours and total_duration_hours > 0:
                time_ratio = max(elapsed_hours / total_duration_hours, 0.01)
                pace_index = progress_ratio / time_ratio
            else:
                pace_index = 1.0

        probability_pct = _clamp(50 + (pace_index - 1.0) * 50, 0, 100)
        if time_buffer_hours < 0:
            probability_pct *= 0.80
        elif time_buffer_hours > 8:
            probability_pct *= 1.10
        probability_pct = _clamp(probability_pct, 0, 100)

    status = _status_for(probability_pct)

    if already_complete:
        alert_message = f"WO {work_order.order_number} is complete."
    elif overdue:
        alert_message = f"WO {work_order.order_number} is overdue and incomplete."
    else:
        alert_message = f"WO {work_order.order_number}: {_STATUS_MESSAGES[status]}"

    return {
        "wo_id": work_order.id,
        "wo_number": work_order.order_number,
        "product": work_order.part_number,
        "required_qty": required_qty,
        "actual_qty": actual_qty,
        "progress_pct": round(progress_pct, 2),
        "elapsed_hours": round(elapsed_hours, 2),
        "remaining_hours": round(remaining_hours, 2) if remaining_hours is not None else None,
        "current_rate_per_hour": round(current_rate_per_hour, 4),
        "projected_completion": projected_completion,
        "time_buffer_hours": round(time_buffer_hours, 2),
        "pace_index": round(pace_index, 4) if pace_index is not None else None,
        "probability_pct": round(probability_pct, 2),
        "status": status,
        "alert_message": alert_message,
    }
