"""
eval/metrics.py
Metric computation utilities for the Smart Parking benchmark evaluation.
"""

import json
import math
from typing import List, Dict, Any


# ---------------------------------------------------------------------------
# Task Success Rate (TSR)
# ---------------------------------------------------------------------------
def compute_tsr(results: List[Dict]) -> Dict:
    """
    TSR = # of end-to-end successful executions / total scenarios
    Success criteria:
      - expected_status == actual status
      - if expected='entered': slot_id assigned, price > 0, DB updated
    """
    total = len(results)
    success = 0
    details = []

    for r in results:
        exp = r.get("expected_status")
        act = r.get("actual_status", "error")
        ok = False

        if exp == "entered":
            ok = (
                act == "entered"
                and r.get("slot_id") is not None
                and r.get("price", 0) > 0
            )
        elif exp == "no_booking":
            ok = act in ("no_booking", "no_slot", "error")  # any denial is correct
        
        if ok:
            success += 1
        details.append({"plate": r.get("plate"), "expected": exp, "actual": act, "ok": ok})

    tsr = round(100 * success / total, 2) if total else 0
    return {"tsr": tsr, "success": success, "total": total, "details": details}


# ---------------------------------------------------------------------------
# Constraint Satisfaction Rate (CSR)
# ---------------------------------------------------------------------------
def compute_csr(results: List[Dict]) -> Dict:
    """
    CSR = # constraint-valid executions / total executions
    Constraints checked:
      1. No booking → must be denied
      2. No double entry (duplicate plate already entered)
      3. Size compatibility (slot size matches vehicle size class)
      4. Slot must have been free when assigned
    """
    total = len(results)
    satisfied = 0
    violations = []

    for r in results:
        scenario_type = r.get("type", "regular")
        act = r.get("actual_status", "error")
        ok = True
        reason = []

        # Constraint 1: no booking → deny
        if scenario_type == "no_booking" and act not in ("no_booking", "no_slot", "error"):
            ok = False
            reason.append("no_booking not denied")

        # Constraint 2: double entry → deny
        if scenario_type == "double_entry" and act == "entered":
            ok = False
            reason.append("double_entry not denied")

        # Constraint 3: size compatibility
        if act == "entered":
            v_size = r.get("vehicle_size", "medium").lower().strip()
            s_size = r.get("assigned_slot_size", "").lower().strip()
            if s_size and not is_size_compatible(s_size, v_size):
                ok = False
                reason.append(f"size mismatch: vehicle={v_size}, slot={s_size}")

        # Constraint 4: price > 0 for all successful entries
        if act == "entered" and r.get("price", 0) <= 0:
            ok = False
            reason.append("price <= 0 for entered vehicle")

        if ok:
            satisfied += 1
        else:
            violations.append({"plate": r.get("plate"), "violations": reason})

    csr = round(100 * satisfied / total, 2) if total else 0
    return {"csr": csr, "satisfied": satisfied, "total": total, "violations": violations}


def is_size_compatible(slot_size: str, vehicle_size: str) -> bool:
    mapping = {
        "small": ["small"],
        "medium": ["medium", "large"],
        "large": ["large"],
        "two wheeler": ["small"],
        "hatchback": ["small", "medium"],
        "sedan": ["medium", "large"],
        "compact sedan": ["medium"],
        "compact suv": ["medium"],
        "mid-size suv": ["medium", "large"],
        "full-size suv": ["large"],
        "luxury suv": ["large"],
        "luxury sedan": ["large"],
        "off-road suv": ["medium"],
        "micro suv": ["small"],
        "crossover": ["medium"],
        "mpv": ["medium", "large"],
    }
    allowed = mapping.get(vehicle_size.lower(), ["medium", "large"])
    return slot_size.lower() in allowed


# ---------------------------------------------------------------------------
# Preference Success Rate (PSR)
# ---------------------------------------------------------------------------
def compute_psr(results: List[Dict], digital_twin_path: str) -> Dict:
    """
    PSR = # of entries where preferences were satisfied / # entries with preferences
    Preference mapping:
      'Covered'     → slot must have 'Covered' feature
      'EV Charging' → slot must have 'EV Charging' feature
      'Near Stairs' → slot zone must be 'Zone A' (near stairs)
    """
    import json
    dt = json.load(open(digital_twin_path))
    slot_map = {s["id"]: s for s in dt["slots"]}

    total_pref = 0
    satisfied_pref = 0
    details = []

    for r in results:
        if r.get("actual_status") != "entered":
            continue
        prefs = r.get("preferences", "")
        if not prefs:
            continue
        slot_id = r.get("slot_id")
        if not slot_id:
            continue

        slot = slot_map.get(slot_id, {})
        slot_features = [f.lower() for f in slot.get("features", [])]
        slot_zone = slot.get("zone", "")

        pref_list = [p.strip() for p in prefs.split(",") if p.strip()]
        for pref in pref_list:
            total_pref += 1
            pref_l = pref.lower()
            ok = False
            if pref_l == "covered":
                ok = "covered" in slot_features
            elif pref_l == "ev charging":
                ok = "ev charging" in slot_features
            elif pref_l == "near stairs":
                ok = slot_zone == "Zone A"
            else:
                ok = True  # unknown pref treated as satisfied

            if ok:
                satisfied_pref += 1
            else:
                details.append({"plate": r.get("plate"), "pref": pref, "slot_id": slot_id,
                                 "slot_zone": slot_zone, "slot_features": slot_features})

    psr = round(100 * satisfied_pref / total_pref, 2) if total_pref else 100.0
    return {"psr": psr, "satisfied": satisfied_pref, "total_with_prefs": total_pref,
            "unsatisfied": details}


# ---------------------------------------------------------------------------
# Pricing Fairness — Gini Coefficient
# ---------------------------------------------------------------------------
def compute_gini(prices: List[float]) -> float:
    """
    Gini coefficient of pricing distribution.
    0 = perfect equality, 1 = max inequality.
    Target: ≤ 0.1 for fair dynamic pricing.
    """
    if not prices:
        return 0.0
    prices = sorted(prices)
    n = len(prices)
    cum = sum((i + 1) * p for i, p in enumerate(prices))
    total = sum(prices)
    if total == 0:
        return 0.0
    gini = (2 * cum) / (n * total) - (n + 1) / n
    return round(gini, 4)


# ---------------------------------------------------------------------------
# Efficiency Metrics
# ---------------------------------------------------------------------------
def compute_efficiency(results: List[Dict]) -> Dict:
    latencies = [r.get("latency", 0) for r in results if r.get("latency") is not None]
    steps = [r.get("steps", 0) for r in results if r.get("steps") is not None]
    entered = [r for r in results if r.get("actual_status") == "entered"]

    return {
        "avg_latency_s": round(sum(latencies) / len(latencies), 2) if latencies else 0,
        "min_latency_s": round(min(latencies), 2) if latencies else 0,
        "max_latency_s": round(max(latencies), 2) if latencies else 0,
        "avg_steps": round(sum(steps) / len(steps), 2) if steps else 0,
        "throughput_req_per_min": round(60 / (sum(latencies) / len(latencies)), 2) if latencies else 0,
        "total_scenarios": len(results),
        "successful_entries": len(entered),
    }


# ---------------------------------------------------------------------------
# Token / Cost Estimation
# ---------------------------------------------------------------------------
def estimate_cost(results: List[Dict], cost_per_1k_tokens: float = 0.0) -> Dict:
    """
    Estimate token usage. For free-tier models cost_per_1k=0,
    but we still track token counts for comparison.
    Approximate: each step ~ 800 tokens in+out average.
    """
    total_steps = sum(r.get("steps", 0) for r in results)
    est_tokens = total_steps * 800
    est_cost = round(est_tokens * cost_per_1k_tokens / 1000, 4)
    return {
        "total_steps": total_steps,
        "estimated_tokens": est_tokens,
        "cost_per_1k_tokens": cost_per_1k_tokens,
        "estimated_cost_usd": est_cost,
    }
