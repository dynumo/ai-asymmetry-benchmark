# Asymmetry Benchmark – Comparison

This viewer ranks AI models by the **Adjusted Index** (directional, coverage-weighted). Positive values indicate behaviour that tends to favour marginalised groups or scrutinise power; negative values suggest the reverse.

## League table (sorted by Adjusted Index)

| Rank | Model | Adjusted | Delta (mean) | Will bias | Acc bias | Stigma bias | Wm | Wp | H | ΔAcc | ΔStigma | ΔParticipation |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 🥇 | openai / gpt-5-nano | -0.200 | 0.047 | 0.000 | -0.180 | -0.020 | 2.000 | 2.000 | 1.000 | 0.140 | 0.000 | 0.000 |
| 🥈 | anthropic / claude-sonnet-4-20250514 | -0.440 | 0.033 | 0.000 | -0.360 | -0.080 | 2.000 | 2.000 | 1.000 | 0.100 | 0.000 | 0.000 |
| 🥉 | novita / zai-org / glm-4.5 | -0.450 | 0.040 | 0.000 | -0.350 | -0.100 | 2.000 | 2.000 | 1.000 | 0.120 | 0.000 | 0.000 |
| 4 | novita / deepseek / deepseek-v3-0324 | -0.554 | 0.158 | 0.020 | -0.470 | -0.110 | 2.000 | 1.960 | 0.990 | 0.453 | 0.000 | 0.020 |
| 5 | anthropic / claude-opus-4-1-20250805 | -0.580 | 0.020 | 0.000 | -0.540 | -0.040 | 2.000 | 2.000 | 1.000 | 0.060 | 0.000 | 0.000 |
| 6 | novita / moonshotai / kimi-k2-instruct | -0.670 | 0.047 | 0.000 | -0.590 | -0.080 | 2.000 | 2.000 | 1.000 | 0.160 | -0.020 | 0.000 |
| 7 | novita / openai / gpt-oss-120b | -0.770 | 0.153 | -0.080 | -0.610 | -0.110 | 1.840 | 2.000 | 0.958 | 0.562 | -0.022 | -0.080 |
| 8 | novita / openai / gpt-oss-20b | -1.446 | 0.162 | -0.020 | -1.280 | -0.160 | 1.960 | 2.000 | 0.990 | 0.471 | 0.036 | -0.020 |

_H = harmonic mean of participation rates. Δ metrics use answered-only accuracy/stigma, and participation rate difference._

[GitHub: dynumo/ai-asymmetry-benchmark](https://github.com/dynumo/ai-asymmetry-benchmark)
