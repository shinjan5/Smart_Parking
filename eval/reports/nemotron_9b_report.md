# 🅿️ Smart Parking — Model Evaluation Report
## Model: NVIDIA Nemotron Nano 9B

| Field | Value |
|-------|-------|
| **Model ID** | `nvidia/nemotron-nano-9b-v2:free` |
| **Provider** | OpenRouter (free tier) |
| **Run Date** | 2026-05-03 12:45:27 |
| **Total Scenarios** | 15 |
| **Report Generated** | `eval/reports/nemotron_9b_report.md` |

---

## 📊 Executive Summary

| Metric | Score | Interpretation |
|--------|-------|----------------|
| **Task Success Rate (TSR)** | **86.67%** | ✅ Good |
| **Constraint Satisfaction Rate (CSR)** | **66.67%** | ❌ Poor |
| **Preference Success Rate (PSR)** | **66.67%** | ❌ Poor |
| **Avg Latency** | **60.96s** | ⚠️ Slow |
| **Avg Steps per Task** | **4.93** | ✅ Efficient |
| **Throughput** | **0.98 req/min** | |
| **Pricing Gini Coefficient** | **0.0791** | ✅ Fair (≤0.10) |
| **Inference Cost (USD)** | **$0.0** | Free tier (est. 59,200 tokens) |

---

## 🎯 Task Success Rate (TSR)

> **TSR = 86.67%** (13/15 scenarios succeeded)

A scenario is successful when:
- ✔️ Correct admission decision (entered vs denied)
- ✔️ Slot correctly assigned
- ✔️ Price > 0 calculated
- ✔️ DB entry updated

### Breakdown by Scenario Type

| Scenario Type | Total | Passed | Rate |
|---------------|-------|--------|------|
| Regular | 11 | 10 | 90.9% |
| No Booking | 2 | 2 | 100.0% |
| Double Entry | 2 | 1 | 50.0% |

### Breakdown by Vehicle Size (Regular scenarios)

| Vehicle Size | Total | Entered | Rate |
|-------------|-------|---------|------|
| Large | 4 | 4 | 100.0% |
| Medium | 4 | 4 | 100.0% |
| Small | 3 | 2 | 66.7% |

---

## ⚙️ Constraint Satisfaction Rate (CSR)

> **CSR = 66.67%** (10/15 executions obeyed all rules)

Constraints enforced:
- 🚫 No booking → deny entry
- 🚫 No double entry (plate already inside)
- 📐 Size compatibility (slot size matches vehicle class)
- 💰 Price must be > 0 for all successful entries

### Constraint Violations (sample)

| Plate | Violation |
|-------|----------|
| WB10AA2148 | size mismatch: vehicle=small, slot=large |
| WB10AA2185 | size mismatch: vehicle=medium, slot=small |
| WB10AA2222 | size mismatch: vehicle=large, slot=medium |
| WB10AB2407 | size mismatch: vehicle=large, slot=medium |
| WB10AA2074 | double_entry not denied; size mismatch: vehicle=small, slot=medium |

---

## ⭐ Preference Success Rate (PSR)

> **PSR = 66.67%** (4/6 preference requirements met)

Preferences tracked:
- **Covered** → slot must have "Covered" feature
- **EV Charging** → slot must have "EV Charging" feature
- **Near Stairs** → slot must be in Zone A

### Unsatisfied Preferences (sample)

| Plate | Preference | Slot | Zone | Features |
|-------|-----------|------|------|----------|
| WB10AA2111 | Covered | 76 | Zone B | ev charging |
| WB10AA2074 | Covered | 84 | Zone B | ev charging |

---

## ⚡ Efficiency & Latency

| Metric | Value |
|--------|-------|
| **Average Latency** | 60.96s |
| **Min Latency** | 15.33s |
| **Max Latency** | 104.64s |
| **Average Steps per Task** | 4.93 |
| **Throughput** | 0.98 requests/min |
| **Total Scenarios Run** | 15 |
| **Successful Entries** | 11 |

---

## 💰 Pricing Fairness

> **Gini Coefficient = 0.0791** (target: ≤ 0.10)

| Metric | Value |
|--------|-------|
| **Average Price (₹)** | 70.0 |
| **Min Price (₹)** | 50.0 |
| **Max Price (₹)** | 90.0 |
| **Price Distribution Fairness** | ✅ Good |

---

## 🔢 Token & Cost Estimation

| Metric | Value |
|--------|-------|
| **Total Agent Steps** | 74 |
| **Estimated Tokens Used** | 59,200 |
| **Cost per 1K Tokens** | $0.0 |
| **Total Estimated Cost** | $0.0 |

> ℹ️ Token count estimated at ~800 tokens per agent step (input + output combined).
> Free-tier models have $0 inference cost.

---

## ❌ Failed Scenarios (Sample)

| # | Plate | Type | Expected | Actual | Latency | Error |
|---|-------|------|----------|--------|---------|-------|
| 1 | WB10AA2074 | regular | entered | error | 53.47s | dry run |
| 2 | WB10AA2074 | double_entry | no_booking | entered | 15.33s | dry run |

---

## 📋 Full Scenario Results

| # | Plate | Type | Size | Preferences | Expected | Actual | Slot | Price | Steps | Latency |
|---|-------|------|------|------------|----------|--------|------|-------|-------|---------|
| 1 | WB10AA2037 | regular | medium | — | entered | ✅ entered | 158 | ₹75.0 | 5 | 72.24s |
| 2 | WB10AA2074 | regular | small | Covered | entered | ❌ error | — | — | 5 | 53.47s |
| 3 | WB10AA2111 | regular | large | Covered | entered | ✅ entered | 76 | ₹60.0 | 6 | 52.37s |
| 4 | WB10AA2148 | regular | small | — | entered | ✅ entered | 158 | ₹75.0 | 3 | 59.72s |
| 5 | WB10AA2185 | regular | medium | Near Stairs | entered | ✅ entered | 34 | ₹75.0 | 3 | 104.36s |
| 6 | WB10AA2222 | regular | large | — | entered | ✅ entered | 89 | ₹90.0 | 4 | 24.38s |
| 7 | WB10AA2259 | regular | large | Covered | entered | ✅ entered | 43 | ₹60.0 | 7 | 57.79s |
| 8 | WB10AA2296 | regular | medium | Covered | entered | ✅ entered | 4 | ₹75.0 | 5 | 101.31s |
| 9 | WB10AA2333 | regular | medium | — | entered | ✅ entered | 132 | ₹50.0 | 7 | 33.18s |
| 10 | WB10AB2370 | regular | small | — | entered | ✅ entered | 91 | ₹75.0 | 4 | 104.64s |
| 11 | WB10AB2407 | regular | large | Covered | entered | ✅ entered | 16 | ₹60.0 | 4 | 81.09s |
| 12 | XX99ZZ7000 | no_booking | medium | — | no_booking | ✅ no_booking | — | — | 7 | 66.78s |
| 13 | XX98ZZ7001 | no_booking | medium | — | no_booking | ✅ no_booking | — | — | 3 | 45.72s |
| 14 | WB10AA2037 | double_entry | medium | — | no_booking | ✅ no_booking | — | — | 7 | 42.04s |
| 15 | WB10AA2074 | double_entry | small | Covered | no_booking | ❌ entered | 84 | ₹75.0 | 4 | 15.33s |

---

*Report auto-generated by `eval/run_benchmark.py` on 2026-05-03 12:45:27.*
*Model: nvidia/nemotron-nano-9b-v2:free via OpenRouter API.*
