# 🅿️ Smart Parking — Multi-Model Comparison Report

*Generated: 2026-05-03 12:45:27*

## Results Summary

| Model | TSR (%) | CSR (%) | PSR (%) | Gini | Avg Steps | Avg Latency | Throughput |
|-------|---------|---------|---------|------|-----------|-------------|------------|
| NVIDIA Nemotron Nano 9B | 86.67 | 66.67 | 66.67 | 0.0791 | 4.93 | 60.96s | 0.98 req/min |
| Google Gemma 3 4B | 100.0 | 53.33 | 50.0 | 0.0785 | 5.33 | 69.93s | 0.86 req/min |
| Meta LLaMA 3.2 3B | 100.0 | 46.67 | 50.0 | 0.1273 | 4.2 | 65.0s | 0.92 req/min |
| OpenAI GPT-OSS 20B | 86.67 | 60.0 | 0.0 | 0.1079 | 5.07 | 62.21s | 0.96 req/min |
| Qwen3 Next 80B MoE | 80.0 | 60.0 | 40.0 | 0.1099 | 5.33 | 67.44s | 0.89 req/min |

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
