# 🅿️ Smart Parking — Evaluation Framework

## Overview

This directory contains the full evaluation infrastructure for the Smart Parking Agentic Pipeline. It benchmarks multiple LLM models across **200 standardized test scenarios** and generates per-model markdown reports.

## Directory Structure

```
eval/
├── generate_test_data.py    # Step 1: Generate & register 200 test scenarios
├── run_benchmark.py         # Step 2: Run multi-model benchmark
├── metrics.py               # Metric computation library
├── test_scenarios.json      # Generated test scenarios (200 records)
├── results/                 # Raw JSON results per model
│   ├── nemotron_9b_results.json
│   ├── gemma3_4b_results.json
│   └── ...
└── reports/                 # Markdown evaluation reports
    ├── nemotron_9b_report.md
    ├── gemma3_4b_report.md
    ├── llama32_3b_report.md
    ├── gpt_oss_20b_report.md
    ├── qwen3_80b_report.md
    └── comparison_report.md
```

## Models Evaluated

| Model | OpenRouter ID | Size | Tool Calling |
|-------|--------------|------|-------------|
| NVIDIA Nemotron Nano 9B | `nvidia/nemotron-nano-9b-v2:free` | 9B | ✅ |
| Google Gemma 3 4B | `google/gemma-3-4b-it:free` | 4B | ✅ |
| Meta LLaMA 3.2 3B | `meta-llama/llama-3.2-3b-instruct:free` | 3B | ✅ |
| OpenAI GPT-OSS 20B | `openai/gpt-oss-20b:free` | 20B | ✅ |
| Qwen3 Next 80B MoE | `qwen/qwen3-next-80b-a3b-instruct:free` | 80B MoE | ✅ |

## Metrics

| Metric | Definition | Target |
|--------|-----------|--------|
| **TSR** | Task Success Rate — full pipeline success (correct decision + slot + price + DB) | ≥ 90% |
| **CSR** | Constraint Satisfaction Rate — all rules obeyed (no double entry, size compat, etc.) | ≥ 95% |
| **PSR** | Preference Success Rate — requested features (Covered/EV/Stairs) actually assigned | ≥ 70% |
| **Gini** | Pricing fairness coefficient (0 = equal, 1 = max inequality) | ≤ 0.10 |
| **Avg Steps** | Mean agent tool-calling steps per scenario | ≤ 7 |
| **Avg Latency** | Mean wall-clock time per scenario (seconds) | Minimize |
| **Throughput** | Requests per minute (60 / avg_latency) | Maximize |

## Test Scenarios (200 total)

| Type | Count | Description |
|------|-------|-------------|
| **Regular** | 180 | Valid pre-booked vehicles, expecting `entered` status |
| **No-Booking** | 10 | Plates not in DB, expecting denial |
| **Double-Entry** | 10 | Already-entered plates, expecting denial |

### Size Distribution (Regular)
- Small (Two Wheelers, Hatchbacks): ~69 scenarios
- Medium (Sedans, Compact SUVs, Mid-size SUVs): ~56 scenarios  
- Large (Full-size SUVs, Luxury, MPVs): ~55 scenarios

## How to Run

### Step 1: Generate Test Data (run once)
```bash
python eval/generate_test_data.py
```

### Step 2: Run Full Benchmark (all 5 models × 200 scenarios)
```bash
python -X utf8 eval/run_benchmark.py
```
> ⚠️ This will take **several hours** on free-tier models (avg ~60s/scenario × 200 = ~3.5h per model).

### Run Single Model
```bash
python -X utf8 eval/run_benchmark.py --model google/gemma-3-4b-it:free
```

### Quick Test (10 scenarios, dry-run)
```bash
python -X utf8 eval/run_benchmark.py --dry-run --scenarios 10
```

### Quick Test (10 scenarios, real LLM)
```bash
python -X utf8 eval/run_benchmark.py --scenarios 10 --model nvidia/nemotron-nano-9b-v2:free
```

## Notes

- All models use the **same 200 scenarios** for fair comparison
- The digital twin and DB are reset before each model's run
- Reports are auto-generated in `eval/reports/`
- Raw results JSON is saved in `eval/results/` for custom analysis
