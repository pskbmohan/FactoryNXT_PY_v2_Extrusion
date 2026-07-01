"""Process-line simulation service.

Generates live-looking sensor readings setpoints and actuals for the
extrusion floor (HLS, Press, Quench, Puller, Stretch, Final Cut, Oven).
These values drive the station pages even when no real PLC is connected.

The simulator is deterministic per-machine/per-process-type so that
reloading a page during a demo shows stable yet realistic numbers.
"""

import random
from datetime import datetime, timedelta


def _rng(seed: str) -> random.Random:
    """Create a deterministic RNG seeded by a string key."""
    return random.Random(hash(tuple(seed)) & 0xFFFFFFFF)


def simulate_setpoint(process_type: str, alloy: str = "6061"):
    """Return a setpoint dict (target values) for the given process type."""
    base = {
        "HLS": {"billet_temp_c": 460, "ram_speed_mm_s": 6.5, "target_force_ton": 1800},
        "PRESSING": {"ram_pressure_bar": 280, "container_temp_c": 460,
                     "speed_mm_s": 5.0},
        "QUENCHING": {"entry_temp_c": 520, "exit_temp_c": 250, "water_flow_lpm": 120},
        "PULLING": {"pull_force_kn": 8.5, "pull_speed_m_min": 3.2, "profile_temp_c": 500},
        "STRETCHING": {"elongation_pct": 1.5, "peak_tension_kn": 35, "head_speed_m_min": 0.4},
        "FINAL_CUT": {"target_length_m": 6.0, "tolerance_mm": 2.0, "saw_speed_m_min": 0.2},
        "OVEN": {"set_temp_c": 520, "soak_time_min": 45},
    }.get(process_type, {})
    if alloy.endswith("63"):
        # 6063 runs slightly cooler than 6061
        if "billet_temp_c" in base: base["billet_temp_c"] -= 10
        if "container_temp_c" in base: base["container_temp_c"] -= 10
        if "set_temp_c" in base: base["set_temp_c"] -= 10
    return base


def simulate_actuals(process_type: str, machine_name: str = "Press-01"):
    """Return live-looking actual values for the station."""
    rng = _rng((process_type, machine_name, datetime.utcnow().date().isoformat()))
    sp = simulate_setpoint(process_type)

    # Add small noise to setpoints -> actuals
    def noisy(val, pct=0.03):
        if val is None: return None
        return round(val * (1 + rng.uniform(-pct, pct)), 2)

    actual = {k: noisy(v) for k, v in sp.items()}

    # Inject a few extras per process_type
    if process_type == "HLS":
        actual["soak_time_min"] = noisy(sp.get("billet_temp_c", 460) / 12, 0.05)
        actual["exit_temp_c"] = noisy(sp.get("billet_temp_c", 460), 0.02)
    elif process_type == "PRESSING":
        actual["cycle_time_s"] = round(rng.uniform(25, 60), 1)
        actual["profile_length_mm"] = round(rng.uniform(5000, 7000), 0)
        actual["die_code"] = f"DIE-{rng.randint(2000, 2023):04d}"
    elif process_type == "QUENCHING":
        actual["quench_type"] = rng.choice(["WATER_SPRAY", "AIR_FAN", "WATER_BATH"])
        actual["duration_s"] = round(rng.uniform(8, 25), 1)
        actual["cooling_rate_c_s"] = round(rng.uniform(8, 25), 1)
    elif process_type == "PULLING":
        actual["profile_temp_c"] = noisy(sp.get("profile_temp_c", 500), 0.03)
    elif process_type == "STRETCHING":
        actual["deviation_pct"] = round(rng.uniform(-0.3, 0.3), 2)
        actual["in_spec"] = abs(actual["deviation_pct"]) < 0.3
    elif process_type == "FINAL_CUT":
        actual["actual_length_m"] = noisy(sp.get("target_length_m", 6.0), 0.01)
        actual["in_spec"] = abs(actual["actual_length_m"] - sp.get("target_length_m", 6.0)) <= sp.get("tolerance_mm", 2) / 1000
        actual["bundle_id"] = f"BND-{rng.randint(1000, 1100):04d}"
        actual["pieces"] = rng.randint(15, 40)
        actual["weight_kg"] = round(rng.uniform(800, 2200), 1)
    elif process_type == "OVEN":
        actual["soak_time_used_min"] = noisy(sp.get("soak_time_min", 45), 0.10)
        actual["reached_target"] = abs(actual.get("set_temp_c", 0) - sp.get("set_temp_c", 0)) < 10
        actual["die_code"] = f"DIE-{rng.randint(2000, 2023):04d}"

    return {"setpoint": sp, "actual": actual, "timestamp": datetime.utcnow().isoformat()}


def simulate_recent_runs(process_type: str, count: int = 8):
    """Return a list of recently completed ProcessRun-like dicts for a station."""
    rng = _rng((process_type, "recent"))
    runs = []
    base_time = datetime.utcnow() - timedelta(hours=count * 2)
    for i in range(count):
        start = base_time + timedelta(hours=i * 2)
        end = start + timedelta(minutes=rng.uniform(15, 60))
        runs.append({
            "run_id": f"RUN-{rng.randint(10000, 99999):05d}",
            "started_at": start,
            "ended_at": end,
            "status": rng.choice(["COMPLETED", "COMPLETED", "COMPLETED", "FAIL" if rng.random() < 0.1 else "COMPLETED"]),
            "operator_id": rng.choice(["R.Singh", "S.Menon", "A.Patel", "V.Kumar"]),
            "die_code": f"DIE-{rng.randint(2000, 2023):04d}",
            "alloy": rng.choice(["6061", "6063", "6082"]),
            "billet_code": f"BIL-{rng.randint(5000, 5020):04d}",
        })
    return runs


def simulate_bundles(count: int = 6):
    """Return a list of final-cut bundle records."""
    rng = _rng(("final_cut", "bundles"))
    bundles = []
    for i in range(count):
        target = 6.0
        actual = round(target + rng.uniform(-0.001, 0.001), 3)
        bundles.append({
            "run_id": f"RUN-{rng.randint(10000, 99999):05d}",
            "profile_code": f"P{100 + i:03d}",
            "bundle_id": f"BND-{rng.randint(1000, 1100):04d}",
            "length_m": actual,
            "pieces": rng.randint(15, 40),
            "weight_kg": round(rng.uniform(800, 2200), 1),
            "in_spec": abs(actual - target) <= 0.002,
            "recorded_at": datetime.utcnow() - timedelta(minutes=rng.randint(5, 400)),
        })
    return bundles


def simulate_oven_records(count: int = 5):
    """Return die-oven pre-heat records."""
    rng = _rng(("oven", "records"))
    recs = []
    for i in range(count):
        s_temp = 520
        a_temp = round(s_temp + rng.uniform(-8, 8), 1)
        soak_used = round(rng.uniform(30, 60), 1)
        target_soak = 45
        recs.append({
            "die_code": f"DIE-{rng.randint(2000, 2023):04d}",
            "setpoint_temp": s_temp,
            "actual_temp": a_temp,
            "target_soak_min": target_soak,
            "soak_time_used_min": soak_used,
            "reached_target": abs(a_temp - s_temp) < 10,
            "recorded_at": datetime.utcnow() - timedelta(minutes=rng.randint(10, 600)),
        })
    return recs


# ── Station-specific record simulators ────────────────────────────────────────
# These produce the per-station record dicts that the station templates iterate
# in the history table. Each returns a list of dicts with the exact field names
# the matching template expects (hls.html, pressing.html, quenching.html,
# puller.html, stretching.html).

def simulate_hls_records(count: int = 8):
    """Return HLS history records (billet heating/shear)."""
    rng = _rng(("hls", "records"))
    recs = []
    base_time = datetime.utcnow() - timedelta(hours=count * 2)
    for i in range(count):
        target = 460
        actual = round(target + rng.uniform(-15, 15), 1)
        recs.append({
            "run_id": f"RUN-{rng.randint(10000, 99999):05d}",
            "alloy": rng.choice(["6061", "6063", "6082"]),
            "target_temp": target,
            "actual_temp": actual,
            "soak_time_min": round(rng.uniform(10, 30), 1),
            "status": rng.choice(["COMPLETED", "COMPLETED", "COMPLETED", "FAIL" if rng.random() < 0.1 else "COMPLETED"]),
        })
    return recs


def simulate_press_records(count: int = 8):
    """Return PRESSING history records."""
    rng = _rng(("press", "records"))
    recs = []
    for i in range(count):
        pressure = round(rng.uniform(240, 320), 1)
        recs.append({
            "run_id": f"RUN-{rng.randint(10000, 99999):05d}",
            "die_code": f"DIE-{rng.randint(2000, 2023):04d}",
            "ram_pressure": pressure,
            "actual_pressure": round(pressure + rng.uniform(-10, 10), 1),
            "speed_mm_s": round(rng.uniform(4.0, 6.5), 2),
            "length_mm": round(rng.uniform(5000, 7000), 0),
            "status": rng.choice(["COMPLETED", "COMPLETED", "COMPLETED", "FAIL" if rng.random() < 0.1 else "COMPLETED"]),
        })
    return recs


def simulate_quench_records(count: int = 8):
    """Return QUENCHING history records."""
    rng = _rng(("quench", "records"))
    recs = []
    base_time = datetime.utcnow() - timedelta(hours=count * 2)
    for i in range(count):
        entry = round(rng.uniform(500, 540), 1)
        exit_ = round(rng.uniform(200, 280), 1)
        recs.append({
            "run_id": f"RUN-{rng.randint(10000, 99999):05d}",
            "quench_type": rng.choice(["WATER_SPRAY", "AIR_FAN", "WATER_BATH"]),
            "entry_temp": entry,
            "exit_temp": exit_,
            "duration_s": round(rng.uniform(8, 25), 1),
            "recorded_at": base_time + timedelta(hours=i * 2) + timedelta(minutes=rng.uniform(5, 60)),
        })
    return recs


def simulate_puller_records(count: int = 8):
    """Return PULLING history records."""
    rng = _rng(("puller", "records"))
    recs = []
    base_time = datetime.utcnow() - timedelta(hours=count * 2)
    for i in range(count):
        recs.append({
            "run_id": f"RUN-{rng.randint(10000, 99999):05d}",
            "pull_force_kn": round(rng.uniform(7.0, 10.0), 2),
            "pull_speed": round(rng.uniform(2.5, 4.0), 2),
            "profile_temp": round(rng.uniform(480, 520), 1),
            "recorded_at": base_time + timedelta(hours=i * 2) + timedelta(minutes=rng.uniform(5, 60)),
        })
    return recs


def simulate_stretch_records(count: int = 8):
    """Return STRETCHING history records."""
    rng = _rng(("stretch", "records"))
    recs = []
    base_time = datetime.utcnow() - timedelta(hours=count * 2)
    for i in range(count):
        target = 1.5
        actual = round(target + rng.uniform(-0.3, 0.3), 3)
        recs.append({
            "run_id": f"RUN-{rng.randint(10000, 99999):05d}",
            "target_elongation_pct": target,
            "actual_elongation_pct": actual,
            "deviation_pct": round(actual - target, 3),
            "peak_tension_kn": round(rng.uniform(28, 42), 2),
            "in_spec": abs(actual - target) < 0.3,
            "recorded_at": base_time + timedelta(hours=i * 2) + timedelta(minutes=rng.uniform(5, 60)),
        })
    return recs
