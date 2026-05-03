# 🅿️ Smart Parking — Model Evaluation Report
## Model: Qwen3 Next 80B MoE

| Field | Value |
|-------|-------|
| **Model ID** | `qwen/qwen3-next-80b-a3b-instruct:free` |
| **Provider** | OpenRouter (free tier) |
| **Run Date** | 2026-05-03 12:45:27 |
| **Total Scenarios** | 15 |
| **Report Generated** | `eval/reports/qwen3_80b_report.md` |

---

## 📊 Executive Summary

| Metric | Score | Interpretation |
|--------|-------|----------------|
| **Task Success Rate (TSR)** | **80.0%** | ⚠️ Moderate |
| **Constraint Satisfaction Rate (CSR)** | **60.0%** | ❌ Poor |
| **Preference Success Rate (PSR)** | **40.0%** | ❌ Poor |
| **Avg Latency** | **67.44s** | ⚠️ Slow |
| **Avg Steps per Task** | **5.33** | ⚠️ Verbose |
| **Throughput** | **0.89 req/min** | |
| **Pricing Gini Coefficient** | **0.1099** | ⚠️ Moderate |
| **Inference Cost (USD)** | **$0.0** | Free tier (est. 64,000 tokens) |

---

## 🎯 Task Success Rate (TSR)

> **TSR = 80.0%** (12/15 scenarios succeeded)

A scenario is successful when:
- ✔️ Correct admission decision (entered vs denied)
- ✔️ Slot correctly assigned
- ✔️ Price > 0 calculated
- ✔️ DB entry updated

### Breakdown by Scenario Type

| Scenario Type | Total | Passed | Rate |
|---------------|-------|--------|------|
| Regular | 11 | 9 | 81.8% |
| No Booking | 2 | 2 | 100.0% |
| Double Entry | 2 | 1 | 50.0% |

### Breakdown by Vehicle Size (Regular scenarios)

| Vehicle Size | Total | Entered | Rate |
|-------------|-------|---------|------|
| Large | 4 | 4 | 100.0% |
| Medium | 4 | 2 | 50.0% |
| Small | 3 | 3 | 100.0% |

---

## ⚙️ Constraint Satisfaction Rate (CSR)

> **CSR = 60.0%** (9/15 executions obeyed all rules)

Constraints enforced:
- 🚫 No booking → deny entry
- 🚫 No double entry (plate already inside)
- 📐 Size compatibility (slot size matches vehicle class)
- 💰 Price must be > 0 for all successful entries

### Constraint Violations (sample)

| Plate | Violation |
|-------|----------|
| WB10AA2074 | size mismatch: vehicle=small, slot=medium |
| WB10AA2148 | size mismatch: vehicle=small, slot=medium |
| WB10AA2259 | size mismatch: vehicle=large, slot=small |
| WB10AB2370 | size mismatch: vehicle=small, slot=large |
| WB10AB2407 | size mismatch: vehicle=large, slot=small |
| WB10AA2037 | double_entry not denied |

---

## ⭐ Preference Success Rate (PSR)

> **PSR = 40.0%** (2/5 preference requirements met)

Preferences tracked:
- **Covered** → slot must have "Covered" feature
- **EV Charging** → slot must have "EV Charging" feature
- **Near Stairs** → slot must be in Zone A

### Unsatisfied Preferences (sample)

| Plate | Preference | Slot | Zone | Features |
|-------|-----------|------|------|----------|
| WB10AA2074 | Covered | 116 | Zone C | None |
| WB10AA2259 | Covered | 126 | Zone C | None |
| WB10AB2407 | Covered | 67 | Zone B | ev charging |

---

## ⚡ Efficiency & Latency

| Metric | Value |
|--------|-------|
| **Average Latency** | 67.44s |
| **Min Latency** | 17.34s |
| **Max Latency** | 119.48s |
| **Average Steps per Task** | 5.33 |
| **Throughput** | 0.89 requests/min |
| **Total Scenarios Run** | 15 |
| **Successful Entries** | 10 |

---

## 💰 Pricing Fairness

> **Gini Coefficient = 0.1099** (target: ≤ 0.10)

| Metric | Value |
|--------|-------|
| **Average Price (₹)** | 71.0 |
| **Min Price (₹)** | 50.0 |
| **Max Price (₹)** | 90.0 |
| **Price Distribution Fairness** | ⚠️ Moderate |

---

## 🔢 Token & Cost Estimation

| Metric | Value |
|--------|-------|
| **Total Agent Steps** | 80 |
| **Estimated Tokens Used** | 64,000 |
| **Cost per 1K Tokens** | $0.0 |
| **Total Estimated Cost** | $0.0 |

> ℹ️ Token count estimated at ~800 tokens per agent step (input + output combined).
> Free-tier models have $0 inference cost.

---

## ❌ Failed Scenarios (Sample)

| # | Plate | Type | Expected | Actual | Latency | Error |
|---|-------|------|----------|--------|---------|-------|
| 1 | WB10AA2037 | regular | entered | error | 87.04s | dry run |
| 2 | WB10AA2296 | regular | entered | error | 52.16s | dry run |
| 3 | WB10AA2037 | double_entry | no_booking | entered | 44.8s | dry run |

---

## 📋 Full Scenario Results

| # | Plate | Type | Size | Preferences | Expected | Actual | Slot | Price | Steps | Latency |
|---|-------|------|------|------------|----------|--------|------|-------|-------|---------|
| 1 | WB10AA2037 | regular | medium | — | entered | ❌ error | — | — | 5 | 87.04s |
| 2 | WB10AA2074 | regular | small | Covered | entered | ✅ entered | 116 | ₹60.0 | 3 | 89.5s |
| 3 | WB10AA2111 | regular | large | Covered | entered | ✅ entered | 29 | ₹50.0 | 7 | 45.78s |
| 4 | WB10AA2148 | regular | small | — | entered | ✅ entered | 59 | ₹60.0 | 3 | 72.83s |
| 5 | WB10AA2185 | regular | medium | Near Stairs | entered | ✅ entered | 7 | ₹90.0 | 7 | 17.34s |
| 6 | WB10AA2222 | regular | large | — | entered | ✅ entered | 104 | ₹75.0 | 7 | 52.25s |
| 7 | WB10AA2259 | regular | large | Covered | entered | ✅ entered | 126 | ₹75.0 | 4 | 119.48s |
| 8 | WB10AA2296 | regular | medium | Covered | entered | ❌ error | — | — | 5 | 52.16s |
| 9 | WB10AA2333 | regular | medium | — | entered | ✅ entered | 137 | ₹90.0 | 5 | 25.04s |
| 10 | WB10AB2370 | regular | small | — | entered | ✅ entered | 100 | ₹60.0 | 7 | 88.06s |
| 11 | WB10AB2407 | regular | large | Covered | entered | ✅ entered | 67 | ₹60.0 | 5 | 72.25s |
| 12 | XX99ZZ7000 | no_booking | medium | — | no_booking | ✅ no_booking | — | — | 6 | 35.79s |
| 13 | XX98ZZ7001 | no_booking | medium | — | no_booking | ✅ no_booking | — | — | 3 | 108.19s |
| 14 | WB10AA2037 | double_entry | medium | — | no_booking | ❌ entered | 84 | ₹90.0 | 7 | 44.8s |
| 15 | WB10AA2074 | double_entry | small | Covered | no_booking | ✅ no_booking | — | — | 6 | 101.12s |

---

*Report auto-generated by `eval/run_benchmark.py` on 2026-05-03 12:45:27.*
*Model: qwen/qwen3-next-80b-a3b-instruct:free via OpenRouter API.*
