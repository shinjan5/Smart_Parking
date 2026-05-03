# 🅿️ Smart Parking — Model Evaluation Report
## Model: Meta LLaMA 3.2 3B

| Field | Value |
|-------|-------|
| **Model ID** | `meta-llama/llama-3.2-3b-instruct:free` |
| **Provider** | OpenRouter (free tier) |
| **Run Date** | 2026-05-03 12:45:27 |
| **Total Scenarios** | 15 |
| **Report Generated** | `eval/reports/llama32_3b_report.md` |

---

## 📊 Executive Summary

| Metric | Score | Interpretation |
|--------|-------|----------------|
| **Task Success Rate (TSR)** | **100.0%** | ✅ Excellent |
| **Constraint Satisfaction Rate (CSR)** | **46.67%** | ❌ Poor |
| **Preference Success Rate (PSR)** | **50.0%** | ❌ Poor |
| **Avg Latency** | **65.0s** | ⚠️ Slow |
| **Avg Steps per Task** | **4.2** | ✅ Efficient |
| **Throughput** | **0.92 req/min** | |
| **Pricing Gini Coefficient** | **0.1273** | ⚠️ Moderate |
| **Inference Cost (USD)** | **$0.0** | Free tier (est. 50,400 tokens) |

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

> **CSR = 46.67%** (7/15 executions obeyed all rules)

Constraints enforced:
- 🚫 No booking → deny entry
- 🚫 No double entry (plate already inside)
- 📐 Size compatibility (slot size matches vehicle class)
- 💰 Price must be > 0 for all successful entries

### Constraint Violations (sample)

| Plate | Violation |
|-------|----------|
| WB10AA2037 | size mismatch: vehicle=medium, slot=small |
| WB10AA2074 | size mismatch: vehicle=small, slot=large |
| WB10AA2111 | size mismatch: vehicle=large, slot=medium |
| WB10AA2148 | size mismatch: vehicle=small, slot=medium |
| WB10AA2222 | size mismatch: vehicle=large, slot=medium |
| WB10AA2259 | size mismatch: vehicle=large, slot=medium |
| WB10AA2296 | size mismatch: vehicle=medium, slot=small |
| WB10AA2333 | size mismatch: vehicle=medium, slot=small |

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
| WB10AA2185 | Near Stairs | 144 | Zone C | None |
| WB10AA2296 | Covered | 81 | Zone B | ev charging |
| WB10AB2407 | Covered | 147 | Zone C | None |

---

## ⚡ Efficiency & Latency

| Metric | Value |
|--------|-------|
| **Average Latency** | 65.0s |
| **Min Latency** | 18.8s |
| **Max Latency** | 115.14s |
| **Average Steps per Task** | 4.2 |
| **Throughput** | 0.92 requests/min |
| **Total Scenarios Run** | 15 |
| **Successful Entries** | 11 |

---

## 💰 Pricing Fairness

> **Gini Coefficient = 0.1273** (target: ≤ 0.10)

| Metric | Value |
|--------|-------|
| **Average Price (₹)** | 68.18 |
| **Min Price (₹)** | 50.0 |
| **Max Price (₹)** | 90.0 |
| **Price Distribution Fairness** | ⚠️ Moderate |

---

## 🔢 Token & Cost Estimation

| Metric | Value |
|--------|-------|
| **Total Agent Steps** | 63 |
| **Estimated Tokens Used** | 50,400 |
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
| 1 | WB10AA2037 | regular | medium | — | entered | ✅ entered | 62 | ₹90.0 | 3 | 61.93s |
| 2 | WB10AA2074 | regular | small | Covered | entered | ✅ entered | 56 | ₹60.0 | 3 | 114.85s |
| 3 | WB10AA2111 | regular | large | Covered | entered | ✅ entered | 47 | ₹90.0 | 3 | 81.33s |
| 4 | WB10AA2148 | regular | small | — | entered | ✅ entered | 10 | ₹75.0 | 5 | 55.11s |
| 5 | WB10AA2185 | regular | medium | Near Stairs | entered | ✅ entered | 144 | ₹75.0 | 5 | 42.14s |
| 6 | WB10AA2222 | regular | large | — | entered | ✅ entered | 125 | ₹50.0 | 3 | 41.08s |
| 7 | WB10AA2259 | regular | large | Covered | entered | ✅ entered | 3 | ₹90.0 | 5 | 26.93s |
| 8 | WB10AA2296 | regular | medium | Covered | entered | ✅ entered | 81 | ₹60.0 | 6 | 42.89s |
| 9 | WB10AA2333 | regular | medium | — | entered | ✅ entered | 101 | ₹50.0 | 5 | 58.69s |
| 10 | WB10AB2370 | regular | small | — | entered | ✅ entered | 148 | ₹60.0 | 3 | 111.71s |
| 11 | WB10AB2407 | regular | large | Covered | entered | ✅ entered | 147 | ₹50.0 | 6 | 18.8s |
| 12 | XX99ZZ7000 | no_booking | medium | — | no_booking | ✅ no_booking | — | — | 5 | 33.18s |
| 13 | XX98ZZ7001 | no_booking | medium | — | no_booking | ✅ no_booking | — | — | 3 | 89.48s |
| 14 | WB10AA2037 | double_entry | medium | — | no_booking | ✅ no_booking | — | — | 4 | 115.14s |
| 15 | WB10AA2074 | double_entry | small | Covered | no_booking | ✅ no_booking | — | — | 4 | 81.78s |

---

*Report auto-generated by `eval/run_benchmark.py` on 2026-05-03 12:45:27.*
*Model: meta-llama/llama-3.2-3b-instruct:free via OpenRouter API.*
