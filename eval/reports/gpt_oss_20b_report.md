# 🅿️ Smart Parking — Model Evaluation Report
## Model: OpenAI GPT-OSS 20B

| Field | Value |
|-------|-------|
| **Model ID** | `openai/gpt-oss-20b:free` |
| **Provider** | OpenRouter (free tier) |
| **Run Date** | 2026-05-03 12:45:27 |
| **Total Scenarios** | 15 |
| **Report Generated** | `eval/reports/gpt_oss_20b_report.md` |

---

## 📊 Executive Summary

| Metric | Score | Interpretation |
|--------|-------|----------------|
| **Task Success Rate (TSR)** | **86.67%** | ✅ Good |
| **Constraint Satisfaction Rate (CSR)** | **60.0%** | ❌ Poor |
| **Preference Success Rate (PSR)** | **0.0%** | ❌ Poor |
| **Avg Latency** | **62.21s** | ⚠️ Slow |
| **Avg Steps per Task** | **5.07** | ⚠️ Verbose |
| **Throughput** | **0.96 req/min** | |
| **Pricing Gini Coefficient** | **0.1079** | ⚠️ Moderate |
| **Inference Cost (USD)** | **$0.0** | Free tier (est. 60,800 tokens) |

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
| Regular | 11 | 9 | 81.8% |
| No Booking | 2 | 2 | 100.0% |
| Double Entry | 2 | 2 | 100.0% |

### Breakdown by Vehicle Size (Regular scenarios)

| Vehicle Size | Total | Entered | Rate |
|-------------|-------|---------|------|
| Large | 4 | 2 | 50.0% |
| Medium | 4 | 4 | 100.0% |
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
| WB10AA2037 | size mismatch: vehicle=medium, slot=small |
| WB10AA2148 | size mismatch: vehicle=small, slot=large |
| WB10AA2185 | size mismatch: vehicle=medium, slot=small |
| WB10AA2222 | size mismatch: vehicle=large, slot=small |
| WB10AA2259 | size mismatch: vehicle=large, slot=small |
| WB10AA2333 | size mismatch: vehicle=medium, slot=small |

---

## ⭐ Preference Success Rate (PSR)

> **PSR = 0.0%** (0/4 preference requirements met)

Preferences tracked:
- **Covered** → slot must have "Covered" feature
- **EV Charging** → slot must have "EV Charging" feature
- **Near Stairs** → slot must be in Zone A

### Unsatisfied Preferences (sample)

| Plate | Preference | Slot | Zone | Features |
|-------|-----------|------|------|----------|
| WB10AA2074 | Covered | 96 | Zone B | ev charging |
| WB10AA2185 | Near Stairs | 72 | Zone B | ev charging |
| WB10AA2259 | Covered | 146 | Zone C | None |
| WB10AA2296 | Covered | 169 | Zone C | None |

---

## ⚡ Efficiency & Latency

| Metric | Value |
|--------|-------|
| **Average Latency** | 62.21s |
| **Min Latency** | 17.64s |
| **Max Latency** | 113.88s |
| **Average Steps per Task** | 5.07 |
| **Throughput** | 0.96 requests/min |
| **Total Scenarios Run** | 15 |
| **Successful Entries** | 9 |

---

## 💰 Pricing Fairness

> **Gini Coefficient = 0.1079** (target: ≤ 0.10)

| Metric | Value |
|--------|-------|
| **Average Price (₹)** | 58.33 |
| **Min Price (₹)** | 50.0 |
| **Max Price (₹)** | 90.0 |
| **Price Distribution Fairness** | ⚠️ Moderate |

---

## 🔢 Token & Cost Estimation

| Metric | Value |
|--------|-------|
| **Total Agent Steps** | 76 |
| **Estimated Tokens Used** | 60,800 |
| **Cost per 1K Tokens** | $0.0 |
| **Total Estimated Cost** | $0.0 |

> ℹ️ Token count estimated at ~800 tokens per agent step (input + output combined).
> Free-tier models have $0 inference cost.

---

## ❌ Failed Scenarios (Sample)

| # | Plate | Type | Expected | Actual | Latency | Error |
|---|-------|------|----------|--------|---------|-------|
| 1 | WB10AA2111 | regular | entered | error | 113.88s | dry run |
| 2 | WB10AB2407 | regular | entered | error | 49.75s | dry run |

---

## 📋 Full Scenario Results

| # | Plate | Type | Size | Preferences | Expected | Actual | Slot | Price | Steps | Latency |
|---|-------|------|------|------------|----------|--------|------|-------|-------|---------|
| 1 | WB10AA2037 | regular | medium | — | entered | ✅ entered | 147 | ₹50.0 | 6 | 46.1s |
| 2 | WB10AA2074 | regular | small | Covered | entered | ✅ entered | 96 | ₹50.0 | 3 | 51.33s |
| 3 | WB10AA2111 | regular | large | Covered | entered | ❌ error | — | — | 3 | 113.88s |
| 4 | WB10AA2148 | regular | small | — | entered | ✅ entered | 5 | ₹50.0 | 6 | 79.28s |
| 5 | WB10AA2185 | regular | medium | Near Stairs | entered | ✅ entered | 72 | ₹75.0 | 6 | 106.13s |
| 6 | WB10AA2222 | regular | large | — | entered | ✅ entered | 11 | ₹50.0 | 4 | 17.64s |
| 7 | WB10AA2259 | regular | large | Covered | entered | ✅ entered | 146 | ₹90.0 | 4 | 69.38s |
| 8 | WB10AA2296 | regular | medium | Covered | entered | ✅ entered | 169 | ₹50.0 | 6 | 98.62s |
| 9 | WB10AA2333 | regular | medium | — | entered | ✅ entered | 136 | ₹60.0 | 7 | 47.77s |
| 10 | WB10AB2370 | regular | small | — | entered | ✅ entered | 20 | ₹50.0 | 5 | 20.99s |
| 11 | WB10AB2407 | regular | large | Covered | entered | ❌ error | — | — | 3 | 49.75s |
| 12 | XX99ZZ7000 | no_booking | medium | — | no_booking | ✅ no_booking | — | — | 4 | 41.24s |
| 13 | XX98ZZ7001 | no_booking | medium | — | no_booking | ✅ no_booking | — | — | 7 | 86.28s |
| 14 | WB10AA2037 | double_entry | medium | — | no_booking | ✅ no_booking | — | — | 7 | 82.39s |
| 15 | WB10AA2074 | double_entry | small | Covered | no_booking | ✅ no_booking | — | — | 5 | 22.44s |

---

*Report auto-generated by `eval/run_benchmark.py` on 2026-05-03 12:45:27.*
*Model: openai/gpt-oss-20b:free via OpenRouter API.*
