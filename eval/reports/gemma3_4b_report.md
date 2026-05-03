# 🅿️ Smart Parking — Model Evaluation Report
## Model: Google Gemma 3 4B

| Field | Value |
|-------|-------|
| **Model ID** | `google/gemma-3-4b-it:free` |
| **Provider** | OpenRouter (free tier) |
| **Run Date** | 2026-05-03 12:45:27 |
| **Total Scenarios** | 15 |
| **Report Generated** | `eval/reports/gemma3_4b_report.md` |

---

## 📊 Executive Summary

| Metric | Score | Interpretation |
|--------|-------|----------------|
| **Task Success Rate (TSR)** | **100.0%** | ✅ Excellent |
| **Constraint Satisfaction Rate (CSR)** | **53.33%** | ❌ Poor |
| **Preference Success Rate (PSR)** | **50.0%** | ❌ Poor |
| **Avg Latency** | **69.93s** | ⚠️ Slow |
| **Avg Steps per Task** | **5.33** | ⚠️ Verbose |
| **Throughput** | **0.86 req/min** | |
| **Pricing Gini Coefficient** | **0.0785** | ✅ Fair (≤0.10) |
| **Inference Cost (USD)** | **$0.0** | Free tier (est. 64,000 tokens) |

---

## 🎯 Task Success Rate (TSR)

> **TSR = 100.0%** (15/15 scenarios succeeded)

A scenario is successful when:
- ✔️ Correct admission decision (entered vs denied)
- ✔️ Slot correctly assigned
- ✔️ Price > 0 calculated
- ✔️ DB entry updated

### Breakdown by Scenario Type

| Scenario Type | Total | Passed | Rate |
|---------------|-------|--------|------|
| Regular | 11 | 11 | 100.0% |
| No Booking | 2 | 2 | 100.0% |
| Double Entry | 2 | 2 | 100.0% |

### Breakdown by Vehicle Size (Regular scenarios)

| Vehicle Size | Total | Entered | Rate |
|-------------|-------|---------|------|
| Large | 4 | 4 | 100.0% |
| Medium | 4 | 4 | 100.0% |
| Small | 3 | 3 | 100.0% |

---

## ⚙️ Constraint Satisfaction Rate (CSR)

> **CSR = 53.33%** (8/15 executions obeyed all rules)

Constraints enforced:
- 🚫 No booking → deny entry
- 🚫 No double entry (plate already inside)
- 📐 Size compatibility (slot size matches vehicle class)
- 💰 Price must be > 0 for all successful entries

### Constraint Violations (sample)

| Plate | Violation |
|-------|----------|
| WB10AA2074 | size mismatch: vehicle=small, slot=medium |
| WB10AA2111 | size mismatch: vehicle=large, slot=medium |
| WB10AA2148 | size mismatch: vehicle=small, slot=large |
| WB10AA2222 | size mismatch: vehicle=large, slot=small |
| WB10AA2259 | size mismatch: vehicle=large, slot=medium |
| WB10AB2370 | size mismatch: vehicle=small, slot=large |
| WB10AB2407 | size mismatch: vehicle=large, slot=small |

---

## ⭐ Preference Success Rate (PSR)

> **PSR = 50.0%** (3/6 preference requirements met)

Preferences tracked:
- **Covered** → slot must have "Covered" feature
- **EV Charging** → slot must have "EV Charging" feature
- **Near Stairs** → slot must be in Zone A

### Unsatisfied Preferences (sample)

| Plate | Preference | Slot | Zone | Features |
|-------|-----------|------|------|----------|
| WB10AA2074 | Covered | 118 | Zone C | None |
| WB10AA2259 | Covered | 121 | Zone C | None |
| WB10AB2407 | Covered | 117 | Zone C | None |

---

## ⚡ Efficiency & Latency

| Metric | Value |
|--------|-------|
| **Average Latency** | 69.93s |
| **Min Latency** | 26.57s |
| **Max Latency** | 118.62s |
| **Average Steps per Task** | 5.33 |
| **Throughput** | 0.86 requests/min |
| **Total Scenarios Run** | 15 |
| **Successful Entries** | 11 |

---

## 💰 Pricing Fairness

> **Gini Coefficient = 0.0785** (target: ≤ 0.10)

| Metric | Value |
|--------|-------|
| **Average Price (₹)** | 66.36 |
| **Min Price (₹)** | 50.0 |
| **Max Price (₹)** | 75.0 |
| **Price Distribution Fairness** | ✅ Good |

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
| — | — | — | — | — | — | No failures |

---

## 📋 Full Scenario Results

| # | Plate | Type | Size | Preferences | Expected | Actual | Slot | Price | Steps | Latency |
|---|-------|------|------|------------|----------|--------|------|-------|-------|---------|
| 1 | WB10AA2037 | regular | medium | — | entered | ✅ entered | 69 | ₹75.0 | 7 | 116.43s |
| 2 | WB10AA2074 | regular | small | Covered | entered | ✅ entered | 118 | ₹75.0 | 6 | 26.57s |
| 3 | WB10AA2111 | regular | large | Covered | entered | ✅ entered | 26 | ₹75.0 | 4 | 66.6s |
| 4 | WB10AA2148 | regular | small | — | entered | ✅ entered | 101 | ₹75.0 | 3 | 42.77s |
| 5 | WB10AA2185 | regular | medium | Near Stairs | entered | ✅ entered | 36 | ₹60.0 | 5 | 66.73s |
| 6 | WB10AA2222 | regular | large | — | entered | ✅ entered | 156 | ₹60.0 | 4 | 42.91s |
| 7 | WB10AA2259 | regular | large | Covered | entered | ✅ entered | 121 | ₹60.0 | 7 | 68.33s |
| 8 | WB10AA2296 | regular | medium | Covered | entered | ✅ entered | 28 | ₹50.0 | 7 | 28.32s |
| 9 | WB10AA2333 | regular | medium | — | entered | ✅ entered | 137 | ₹75.0 | 4 | 86.14s |
| 10 | WB10AB2370 | regular | small | — | entered | ✅ entered | 96 | ₹75.0 | 6 | 83.37s |
| 11 | WB10AB2407 | regular | large | Covered | entered | ✅ entered | 117 | ₹50.0 | 6 | 66.48s |
| 12 | XX99ZZ7000 | no_booking | medium | — | no_booking | ✅ no_booking | — | — | 7 | 118.62s |
| 13 | XX98ZZ7001 | no_booking | medium | — | no_booking | ✅ no_booking | — | — | 3 | 77.31s |
| 14 | WB10AA2037 | double_entry | medium | — | no_booking | ✅ no_booking | — | — | 5 | 50.3s |
| 15 | WB10AA2074 | double_entry | small | Covered | no_booking | ✅ no_booking | — | — | 6 | 108.01s |

---

*Report auto-generated by `eval/run_benchmark.py` on 2026-05-03 12:45:27.*
*Model: google/gemma-3-4b-it:free via OpenRouter API.*
