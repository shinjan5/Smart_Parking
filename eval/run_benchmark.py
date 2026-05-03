"""
eval/run_benchmark.py
Multi-model benchmark runner for the Smart Parking agentic pipeline.

Runs all 200 test scenarios against each specified model and saves:
  - Raw results JSON: eval/results/{model_slug}_results.json
  - Markdown report:  eval/reports/{model_slug}_report.md

Usage:
    # Run all models:
    python eval/run_benchmark.py

    # Run one specific model:
    python eval/run_benchmark.py --model google/gemma-3-4b-it:free

    # Dry run (skip LLM, mock results for report testing):
    python eval/run_benchmark.py --dry-run
"""

import sys, os, json, time, argparse, sqlite3, copy
# Force UTF-8 output on Windows (avoids cp1252 UnicodeEncodeError for emoji)
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from dotenv import load_dotenv
load_dotenv(str(ROOT / ".env"), override=True)

import agentic as ag
from metrics import (
    compute_tsr, compute_csr, compute_psr,
    compute_gini, compute_efficiency, estimate_cost,
)

# ---------------------------------------------------------------------------
# Models under evaluation
# ---------------------------------------------------------------------------
MODELS = [
    {
        "id":   "nvidia/nemotron-nano-9b-v2:free",
        "name": "NVIDIA Nemotron Nano 9B",
        "slug": "nemotron_9b",
        "cost_per_1k": 0.0,
    },
    {
        "id":   "google/gemma-3-4b-it:free",
        "name": "Google Gemma 3 4B",
        "slug": "gemma3_4b",
        "cost_per_1k": 0.0,
    },
    {
        "id":   "meta-llama/llama-3.2-3b-instruct:free",
        "name": "Meta LLaMA 3.2 3B",
        "slug": "llama32_3b",
        "cost_per_1k": 0.0,
    },
    {
        "id":   "openai/gpt-oss-20b:free",
        "name": "OpenAI GPT-OSS 20B",
        "slug": "gpt_oss_20b",
        "cost_per_1k": 0.0,
    },
    {
        "id":   "qwen/qwen3-next-80b-a3b-instruct:free",
        "name": "Qwen3 Next 80B MoE",
        "slug": "qwen3_80b",
        "cost_per_1k": 0.0,
    },
]

SCENARIOS_PATH = Path(__file__).parent / "test_scenarios.json"
RESULTS_DIR    = Path(__file__).parent / "results"
REPORTS_DIR    = Path(__file__).parent / "reports"
DT_PATH        = ROOT / "backend" / "mock_digital_twin.json"
DB_PATH        = ROOT / "parking.db"

RESULTS_DIR.mkdir(exist_ok=True)
REPORTS_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# Digital twin helpers
# ---------------------------------------------------------------------------
def reset_twin_for_benchmark():
    """Reset all slots to 'free' for a clean benchmark run."""
    dt = json.load(open(DT_PATH))
    for s in dt["slots"]:
        s["status"] = "free"
    json.dump(dt, open(DT_PATH, "w"), indent=2)


def reset_bookings_for_rerun(plates: list):
    """Reset booking status back to 'pending' so we can re-run."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.isolation_level = None
    conn.execute(
        f"UPDATE bookings SET status='pending', slot_id=NULL WHERE plate IN ({','.join('?'*len(plates))})",
        plates
    )
    # Remove entries table rows from this run
    conn.execute(
        f"DELETE FROM entries WHERE plate IN ({','.join('?'*len(plates))})",
        plates
    )
    conn.close()


def get_slot_size(slot_id: int) -> str:
    dt = json.load(open(DT_PATH))
    for s in dt["slots"]:
        if s["id"] == slot_id:
            return s.get("size", "")
    return ""


# ---------------------------------------------------------------------------
# Single scenario runner with rate-limit retry
# ---------------------------------------------------------------------------
RATE_LIMIT_RETRY_DELAYS = [30, 60, 120]   # seconds to wait after 429

def run_scenario(scenario: dict, inter_request_delay: float = 2.0) -> dict:
    """Run one scenario through the entry agent, return enriched result dict."""
    plate = scenario["plate"]
    start = time.time()

    last_error = None
    for attempt, delay in enumerate([0] + RATE_LIMIT_RETRY_DELAYS):
        if delay:
            print(f"\n    [RATE LIMIT] Waiting {delay}s before retry {attempt}...", flush=True)
            time.sleep(delay)
        try:
            result = ag.entry_recognition_agent({"plate": plate})
            break
        except Exception as e:
            err_str = str(e)
            last_error = err_str
            if "429" in err_str or "rate limit" in err_str.lower():
                if attempt < len(RATE_LIMIT_RETRY_DELAYS):
                    continue   # retry with longer wait
                # exhausted retries
                result = {"status": "rate_limited", "plate": plate,
                          "message": "Rate limit exhausted after retries", "steps": 0}
            else:
                result = {"status": "error", "plate": plate, "message": err_str, "steps": 0}
            break

    elapsed = time.time() - start
    if inter_request_delay > 0:
        time.sleep(inter_request_delay)   # spread requests over time

    return {
        "plate":            plate,
        "type":             scenario["type"],
        "expected_status":  scenario["expected_status"],
        "actual_status":    result.get("status", "error"),
        "slot_id":          result.get("slot_id"),
        "price":            result.get("price"),
        "steps":            result.get("steps", 0),
        "latency":          round(elapsed, 3),
        "message":          result.get("message", ""),
        "vehicle_size":     scenario["size"],
        "category":         scenario["category"],
        "preferences":      scenario["preferences"],
        "model":            scenario["model"],
        "fuel_type":        scenario["fuel_type"],
        "assigned_slot_size": get_slot_size(result.get("slot_id")) if result.get("slot_id") else "",
    }


# ---------------------------------------------------------------------------
# Per-model benchmark
# ---------------------------------------------------------------------------
def run_model_benchmark(model: dict, scenarios: list, dry_run: bool = False,
                        start_from: int = 0) -> list:
    print(f"\n{'='*70}")
    print(f"  MODEL: {model['name']} ({model['id']})")
    print(f"{'='*70}")
    print(f"  Scenarios: {len(scenarios)} | Dry run: {dry_run} | Start from: {start_from}")

    # Check for existing partial results to resume from
    results_path = RESULTS_DIR / f"{model['slug']}_results.json"
    existing_results = []
    if start_from > 0 and results_path.exists():
        existing_results = json.load(open(results_path))
        print(f"  Resuming: {len(existing_results)} results already saved")

    # Reset DB + twin only if starting fresh
    if start_from == 0:
        plates = [s["plate"] for s in scenarios if s["type"] in ("regular", "double_entry")]
        reset_bookings_for_rerun(plates)
        reset_twin_for_benchmark()

    # Swap model
    if not dry_run:
        ag.set_model(model["id"])

    results = list(existing_results)
    completed_plates = {r["plate"] for r in results}

    for i, scenario in enumerate(scenarios, 1):
        if i <= start_from and scenario["plate"] in completed_plates:
            print(f"  [{i:03d}/{len(scenarios)}] {scenario['plate']:12s} SKIPPED (already done)")
            continue

        print(f"  [{i:03d}/{len(scenarios)}] {scenario['plate']:12s} ({scenario['type']:12s}) ", end="", flush=True)

        if dry_run:
            import random
            random.seed(hash(scenario["plate"] + model["slug"]))
            exp = scenario["expected_status"]
            ok = random.random() > 0.12
            act = exp if ok else ("error" if exp == "entered" else "entered")
            result = {
                "plate":            scenario["plate"],
                "type":             scenario["type"],
                "expected_status":  exp,
                "actual_status":    act,
                "slot_id":          random.randint(1, 170) if act == "entered" else None,
                "price":            random.choice([50.0, 60.0, 75.0, 90.0]) if act == "entered" else None,
                "steps":            random.randint(3, 7),
                "latency":          round(random.uniform(15, 120), 2),
                "message":          "dry run",
                "vehicle_size":     scenario["size"],
                "category":         scenario["category"],
                "preferences":      scenario["preferences"],
                "model":            scenario["model"],
                "fuel_type":        scenario["fuel_type"],
                "assigned_slot_size": random.choice(["small", "medium", "large"]) if act == "entered" else "",
            }
        else:
            result = run_scenario(scenario, inter_request_delay=3.0)

        status_icon = "✅" if result["actual_status"] == result["expected_status"] else "❌"
        print(f"→ {result['actual_status']:12s} {status_icon}  ({result['latency']:.1f}s)")
        results.append(result)

        # Save incrementally after every scenario (allows resume on interruption)
        json.dump(results, open(results_path, "w"), indent=2)

        # Stop early if rate limited (no point continuing)
        if result["actual_status"] == "rate_limited":
            print(f"\n  [RATE LIMIT] Daily quota exhausted at scenario {i}.")
            print(f"  Resume tomorrow with: --model {model['id']} --resume")
            break

    return results



# ---------------------------------------------------------------------------
# Report generator
# ---------------------------------------------------------------------------
def generate_report(model: dict, results: list, metrics: dict, run_date: str) -> str:
    tsr = metrics["tsr"]
    csr = metrics["csr"]
    psr = metrics["psr"]
    eff = metrics["efficiency"]
    gini = metrics["gini"]
    cost = metrics["cost"]

    # Breakdown tables
    by_type = {}
    for r in results:
        t = r["type"]
        by_type.setdefault(t, {"total": 0, "ok": 0})
        by_type[t]["total"] += 1
        if r["actual_status"] == r["expected_status"]:
            by_type[t]["ok"] += 1

    by_size = {}
    for r in results:
        if r["type"] == "regular":
            sz = r["vehicle_size"]
            by_size.setdefault(sz, {"total": 0, "ok": 0})
            by_size[sz]["total"] += 1
            if r["actual_status"] == "entered":
                by_size[sz]["ok"] += 1

    prices = [r["price"] for r in results if r.get("price") and r["actual_status"] == "entered"]
    avg_price = round(sum(prices) / len(prices), 2) if prices else 0
    min_price = min(prices) if prices else 0
    max_price = max(prices) if prices else 0

    failures = [r for r in results if r["actual_status"] != r["expected_status"]][:10]

    report = f"""# 🅿️ Smart Parking — Model Evaluation Report
## Model: {model['name']}

| Field | Value |
|-------|-------|
| **Model ID** | `{model['id']}` |
| **Provider** | OpenRouter (free tier) |
| **Run Date** | {run_date} |
| **Total Scenarios** | {len(results)} |
| **Report Generated** | `eval/reports/{model['slug']}_report.md` |

---

## 📊 Executive Summary

| Metric | Score | Interpretation |
|--------|-------|----------------|
| **Task Success Rate (TSR)** | **{tsr["tsr"]}%** | {_rate_label(tsr["tsr"])} |
| **Constraint Satisfaction Rate (CSR)** | **{csr["csr"]}%** | {_rate_label(csr["csr"])} |
| **Preference Success Rate (PSR)** | **{psr["psr"]}%** | {_rate_label(psr["psr"])} |
| **Avg Latency** | **{eff["avg_latency_s"]}s** | {'✅ Fast' if eff["avg_latency_s"] < 30 else '⚠️ Slow' if eff["avg_latency_s"] < 90 else '❌ Very Slow'} |
| **Avg Steps per Task** | **{eff["avg_steps"]}** | {'✅ Efficient' if eff["avg_steps"] <= 5 else '⚠️ Verbose'} |
| **Throughput** | **{eff["throughput_req_per_min"]} req/min** | |
| **Pricing Gini Coefficient** | **{gini}** | {'✅ Fair (≤0.10)' if gini <= 0.10 else '⚠️ Moderate' if gini <= 0.20 else '❌ Unfair'} |
| **Inference Cost (USD)** | **${cost["estimated_cost_usd"]}** | Free tier (est. {cost["estimated_tokens"]:,} tokens) |

---

## 🎯 Task Success Rate (TSR)

> **TSR = {tsr["tsr"]}%** ({tsr["success"]}/{tsr["total"]} scenarios succeeded)

A scenario is successful when:
- ✔️ Correct admission decision (entered vs denied)
- ✔️ Slot correctly assigned
- ✔️ Price > 0 calculated
- ✔️ DB entry updated

### Breakdown by Scenario Type

| Scenario Type | Total | Passed | Rate |
|---------------|-------|--------|------|
"""
    for t, d in by_type.items():
        rate = round(100 * d["ok"] / d["total"], 1) if d["total"] else 0
        report += f"| {t.replace('_',' ').title()} | {d['total']} | {d['ok']} | {rate}% |\n"

    report += f"""
### Breakdown by Vehicle Size (Regular scenarios)

| Vehicle Size | Total | Entered | Rate |
|-------------|-------|---------|------|
"""
    for sz, d in sorted(by_size.items()):
        rate = round(100 * d["ok"] / d["total"], 1) if d["total"] else 0
        report += f"| {sz.title()} | {d['total']} | {d['ok']} | {rate}% |\n"

    report += f"""
---

## ⚙️ Constraint Satisfaction Rate (CSR)

> **CSR = {csr["csr"]}%** ({csr["satisfied"]}/{csr["total"]} executions obeyed all rules)

Constraints enforced:
- 🚫 No booking → deny entry
- 🚫 No double entry (plate already inside)
- 📐 Size compatibility (slot size matches vehicle class)
- 💰 Price must be > 0 for all successful entries

"""
    if csr["violations"]:
        report += "### Constraint Violations (sample)\n\n"
        report += "| Plate | Violation |\n|-------|----------|\n"
        for v in csr["violations"][:10]:
            report += f"| {v['plate']} | {'; '.join(v['violations'])} |\n"
    else:
        report += "> ✅ No constraint violations detected.\n"

    report += f"""
---

## ⭐ Preference Success Rate (PSR)

> **PSR = {psr["psr"]}%** ({psr["satisfied"]}/{psr["total_with_prefs"]} preference requirements met)

Preferences tracked:
- **Covered** → slot must have "Covered" feature
- **EV Charging** → slot must have "EV Charging" feature
- **Near Stairs** → slot must be in Zone A

"""
    if psr["unsatisfied"]:
        report += "### Unsatisfied Preferences (sample)\n\n"
        report += "| Plate | Preference | Slot | Zone | Features |\n|-------|-----------|------|------|----------|\n"
        for u in psr["unsatisfied"][:10]:
            report += f"| {u['plate']} | {u['pref']} | {u['slot_id']} | {u['slot_zone']} | {', '.join(u['slot_features']) or 'None'} |\n"
    else:
        report += "> ✅ All preference requirements satisfied.\n"

    report += f"""
---

## ⚡ Efficiency & Latency

| Metric | Value |
|--------|-------|
| **Average Latency** | {eff["avg_latency_s"]}s |
| **Min Latency** | {eff["min_latency_s"]}s |
| **Max Latency** | {eff["max_latency_s"]}s |
| **Average Steps per Task** | {eff["avg_steps"]} |
| **Throughput** | {eff["throughput_req_per_min"]} requests/min |
| **Total Scenarios Run** | {eff["total_scenarios"]} |
| **Successful Entries** | {eff["successful_entries"]} |

---

## 💰 Pricing Fairness

> **Gini Coefficient = {gini}** (target: ≤ 0.10)

| Metric | Value |
|--------|-------|
| **Average Price (₹)** | {avg_price} |
| **Min Price (₹)** | {min_price} |
| **Max Price (₹)** | {max_price} |
| **Price Distribution Fairness** | {'✅ Excellent' if gini <= 0.05 else '✅ Good' if gini <= 0.10 else '⚠️ Moderate' if gini <= 0.20 else '❌ Unfair'} |

---

## 🔢 Token & Cost Estimation

| Metric | Value |
|--------|-------|
| **Total Agent Steps** | {cost["total_steps"]} |
| **Estimated Tokens Used** | {cost["estimated_tokens"]:,} |
| **Cost per 1K Tokens** | ${cost["cost_per_1k_tokens"]} |
| **Total Estimated Cost** | ${cost["estimated_cost_usd"]} |

> ℹ️ Token count estimated at ~800 tokens per agent step (input + output combined).
> Free-tier models have $0 inference cost.

---

## ❌ Failed Scenarios (Sample)

| # | Plate | Type | Expected | Actual | Latency | Error |
|---|-------|------|----------|--------|---------|-------|
"""
    for i, f in enumerate(failures, 1):
        msg = (f.get("message") or "")[:60]
        report += f"| {i} | {f['plate']} | {f['type']} | {f['expected_status']} | {f['actual_status']} | {f['latency']}s | {msg} |\n"

    if not failures:
        report += "| — | — | — | — | — | — | No failures |\n"

    report += f"""
---

## 📋 Full Scenario Results

| # | Plate | Type | Size | Preferences | Expected | Actual | Slot | Price | Steps | Latency |
|---|-------|------|------|------------|----------|--------|------|-------|-------|---------|
"""
    for i, r in enumerate(results, 1):
        slot = str(r.get("slot_id") or "—")
        price = f"₹{r['price']}" if r.get("price") else "—"
        prefs = (r.get("preferences") or "—")[:20]
        icon = "✅" if r["actual_status"] == r["expected_status"] else "❌"
        report += f"| {i} | {r['plate']} | {r['type']} | {r['vehicle_size']} | {prefs} | {r['expected_status']} | {icon} {r['actual_status']} | {slot} | {price} | {r['steps']} | {r['latency']}s |\n"

    report += f"""
---

*Report auto-generated by `eval/run_benchmark.py` on {run_date}.*
*Model: {model['id']} via OpenRouter API.*
"""
    return report


def _rate_label(rate: float) -> str:
    if rate >= 95:   return "✅ Excellent"
    if rate >= 85:   return "✅ Good"
    if rate >= 70:   return "⚠️ Moderate"
    return "❌ Poor"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Smart Parking Multi-Model Benchmark")
    parser.add_argument("--model", help="Run a single model by ID")
    parser.add_argument("--dry-run", action="store_true", help="Skip LLM, simulate results")
    parser.add_argument("--scenarios", type=int, default=None, help="Limit number of scenarios (for quick testing)")
    parser.add_argument("--resume", action="store_true",
                        help="Resume from where a previous interrupted run left off")
    args = parser.parse_args()

    if not SCENARIOS_PATH.exists():
        print("❌ test_scenarios.json not found. Run generate_test_data.py first.")
        sys.exit(1)

    scenarios = json.load(open(SCENARIOS_PATH))
    if args.scenarios:
        # Keep proportional mix
        regular = [s for s in scenarios if s["type"] == "regular"][:args.scenarios - 4]
        no_book = [s for s in scenarios if s["type"] == "no_booking"][:2]
        double  = [s for s in scenarios if s["type"] == "double_entry"][:2]
        scenarios = regular + no_book + double
    print(f"📋 Loaded {len(scenarios)} test scenarios")

    models_to_run = MODELS
    if args.model:
        models_to_run = [m for m in MODELS if m["id"] == args.model]
        if not models_to_run:
            # Allow custom model not in predefined list
            slug = args.model.replace("/", "_").replace(":", "_").replace(".", "_")
            models_to_run = [{"id": args.model, "name": args.model, "slug": slug, "cost_per_1k": 0.0}]

    summary_rows = []

    for model in models_to_run:
        run_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Determine start_from for resume mode
        start_from = 0
        if args.resume:
            existing_path = RESULTS_DIR / f"{model['slug']}_results.json"
            if existing_path.exists():
                existing = json.load(open(existing_path))
                start_from = len(existing)
                print(f"  [RESUME] Found {start_from} previous results, continuing from scenario {start_from + 1}")

        # Run benchmark (results are saved incrementally inside the function)
        results = run_model_benchmark(model, scenarios, dry_run=args.dry_run, start_from=start_from)

        results_path = RESULTS_DIR / f"{model['slug']}_results.json"
        print(f"\n  Raw results -> {results_path}")

        # Compute all metrics
        prices = [r["price"] for r in results if r.get("price") and r["actual_status"] == "entered"]
        metrics = {
            "tsr":        compute_tsr(results),
            "csr":        compute_csr(results),
            "psr":        compute_psr(results, str(DT_PATH)),
            "efficiency": compute_efficiency(results),
            "gini":       compute_gini(prices),
            "cost":       estimate_cost(results, model["cost_per_1k"]),
        }

        # Generate report
        report_md = generate_report(model, results, metrics, run_date)
        report_path = REPORTS_DIR / f"{model['slug']}_report.md"
        report_path.write_text(report_md, encoding="utf-8")
        print(f"  📄 Report → {report_path}")

        summary_rows.append({
            "model":      model["name"],
            "tsr":        metrics["tsr"]["tsr"],
            "csr":        metrics["csr"]["csr"],
            "psr":        metrics["psr"]["psr"],
            "gini":       metrics["gini"],
            "avg_steps":  metrics["efficiency"]["avg_steps"],
            "avg_latency":metrics["efficiency"]["avg_latency_s"],
            "throughput": metrics["efficiency"]["throughput_req_per_min"],
            "cost_usd":   metrics["cost"]["estimated_cost_usd"],
        })

    # Print comparison summary
    print(f"\n{'='*90}")
    print(f"  BENCHMARK COMPARISON SUMMARY")
    print(f"{'='*90}")
    header = f"{'Model':<30} {'TSR%':>6} {'CSR%':>6} {'PSR%':>6} {'Gini':>6} {'Steps':>6} {'Lat(s)':>7} {'Req/min':>8}"
    print(header)
    print("-" * len(header))
    for r in summary_rows:
        print(f"{r['model']:<30} {r['tsr']:>6} {r['csr']:>6} {r['psr']:>6} {r['gini']:>6} {r['avg_steps']:>6} {r['avg_latency']:>7} {r['throughput']:>8}")

    # Save comparison report
    comp_path = REPORTS_DIR / "comparison_report.md"
    comp_md = _generate_comparison(summary_rows)
    comp_path.write_text(comp_md, encoding="utf-8")
    print(f"\n  📊 Comparison report → {comp_path}")
    print("\n✅ Benchmark complete.\n")


def _generate_comparison(rows: list) -> str:
    date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    md = f"""# 🅿️ Smart Parking — Multi-Model Comparison Report

*Generated: {date}*

## Results Summary

| Model | TSR (%) | CSR (%) | PSR (%) | Gini | Avg Steps | Avg Latency | Throughput |
|-------|---------|---------|---------|------|-----------|-------------|------------|
"""
    for r in rows:
        md += f"| {r['model']} | {r['tsr']} | {r['csr']} | {r['psr']} | {r['gini']} | {r['avg_steps']} | {r['avg_latency']}s | {r['throughput']} req/min |\n"

    md += """
## Metric Definitions

| Metric | Definition | Target |
|--------|-----------|--------|
| **TSR** | Task Success Rate — % of full pipeline completions (correct decision + slot + price + DB) | ≥ 90% |
| **CSR** | Constraint Satisfaction Rate — % of runs obeying all rules (no double entry, size compat, etc.) | ≥ 95% |
| **PSR** | Preference Success Rate — % of requested features (Covered/EV/Stairs) actually assigned | ≥ 70% |
| **Gini** | Pricing fairness coefficient (0 = equal, 1 = extreme inequality) | ≤ 0.10 |
| **Avg Steps** | Mean number of agent tool-calling steps per scenario | ≤ 7 |
| **Avg Latency** | Mean wall-clock time per scenario (seconds) | As low as possible |
| **Throughput** | Estimated requests per minute (60 / avg_latency) | Maximize |

## How to Read the Reports

- Each model has a dedicated report in `eval/reports/<model_slug>_report.md`
- Raw JSON results are in `eval/results/<model_slug>_results.json`
- All 200 scenarios use the **same test set** for fair comparison
"""
    return md


if __name__ == "__main__":
    main()
