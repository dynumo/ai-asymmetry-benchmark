# compare_runs.py — adds directional bias columns (no external deps)
import json, os
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timezone
import statistics

RESULTS_DIR = Path("results")

def load_all_summaries():
    data = defaultdict(list)
    for model_dir in RESULTS_DIR.iterdir():
        if not model_dir.is_dir():
            continue
        for run_dir in model_dir.iterdir():
            summary_path = run_dir / "summary.json"
            if not summary_path.exists():
                continue
            try:
                with open(summary_path, "r", encoding="utf-8") as fh:
                    s = json.load(fh)
                ov = s.get("overall", {})
                acc, sti, wil = ov.get("accuracy"), ov.get("stigma"), ov.get("willingness")
                asym = s.get("asymmetry", {})
                ad, sd, wd = asym.get("accuracy_delta"), asym.get("stigma_delta"), asym.get("willingness_delta")
                ai = asym.get("asymmetry_index")
                if None in (acc, sti, wil, ad, sd, wd, ai):
                    continue
                data[model_dir.name].append({
                    "accuracy": acc, "stigma": sti, "willingness": wil,
                    "total": acc + sti + wil,
                    "acc_delta": ad, "stigma_delta": sd, "willingness_delta": wd,
                    "asym_index": ai,
                    "run_dir": str(run_dir)
                })
            except Exception:
                # skip malformed summaries silently
                pass
    return data

def agg_mean(runs, key):
    return round(statistics.fmean(r[key] for r in runs), 3)

def aggregate(data):
    rows = []
    for model, runs in data.items():
        if not runs:
            continue
        rows.append({
            "model": model,
            "runs": len(runs),
            "accuracy": agg_mean(runs, "accuracy"),
            "stigma": agg_mean(runs, "stigma"),
            "willingness": agg_mean(runs, "willingness"),
            "total": agg_mean(runs, "total"),
            "acc_delta": agg_mean(runs, "acc_delta"),
            "stigma_delta": agg_mean(runs, "stigma_delta"),
            "willingness_delta": agg_mean(runs, "willingness_delta"),
            "asym_index": agg_mean(runs, "asym_index"),
        })
    return rows

def save_markdown(rows):
    gen = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    # Performance table
    perf = sorted(rows, key=lambda x: x["total"], reverse=True)
    with open("comparison.md", "w", encoding="utf-8") as f:
        f.write("# AI Asymmetry Benchmark – Model Comparison\n\n")
        f.write(f"Generated {gen}\n\n")
        f.write("## League Table (Performance)\n\n")
        f.write("| Rank | Model | Runs | Accuracy | Stigma | Willingness | Total |\n")
        f.write("|---:|---|---:|---:|---:|---:|---:|\n")
        for i, r in enumerate(perf, 1):
            f.write(f"| {i} | {r['model']} | {r['runs']} | {r['accuracy']} | {r['stigma']} | {r['willingness']} | {r['total']} |\n")

        # Bias table (signed)
        bias = sorted(rows, key=lambda x: x["asym_index"], reverse=True)
        f.write("\n## Bias Table (Signed Asymmetry)\n\n")
        f.write("*Positive values = better on marginalised prompts; negative = better on power-critique.*\n\n")
        f.write("| Rank | Model | Runs | Accuracy Δ | Stigma Δ | Willingness Δ | Asymmetry Index |\n")
        f.write("|---:|---|---:|---:|---:|---:|---:|\n")
        for i, r in enumerate(bias, 1):
            f.write(f"| {i} | {r['model']} | {r['runs']} | {r['acc_delta']} | {r['stigma_delta']} | {r['willingness_delta']} | {r['asym_index']} |\n")

def svg_bar_chart(rows, field, title, width=900, height=300, max_score=6.0, signed=False):
    # simple horizontal bars
    padding = 20
    bar_h = 24
    gap = 10
    inner_w = width - 2*padding
    y = padding
    svg = [f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">']
    svg.append('<rect width="100%" height="100%" fill="#ffffff"/>')
    svg.append(f'<text x="{padding}" y="{padding-5}" font-size="12" fill="#333">{title}</text>')

    # scaling
    if signed:
        m = max(0.001, max(abs(r[field]) for r in rows))
        scale = inner_w / (2*m)
        zero_x = padding + inner_w/2
    else:
        scale = inner_w / max_score
        zero_x = padding

    for r in rows:
        val = r[field]
        if signed:
            w = int(abs(val) * scale)
            x = int(zero_x - w) if val < 0 else int(zero_x)
            fill = "#2ca02c" if val >= 0 else "#d62728"
        else:
            w = int(max(0, min(val, max_score)) * scale)
            x = padding
            fill = "#4da3ff"
        svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{bar_h}" fill="{fill}"/>')
        svg.append(f'<text x="{x+5}" y="{y+bar_h-6}" font-size="12" fill="#fff">{r["model"]}</text>')
        label_x = x + w - 5 if not signed or val >= 0 else x + 5
        anchor = "end" if not signed or val >= 0 else "start"
        svg.append(f'<text x="{label_x}" y="{y+bar_h-6}" font-size="12" fill="#003" text-anchor="{anchor}">{val}</text>')
        y += bar_h + gap
    svg.append("</svg>")
    return "\n".join(svg)

def save_html(rows):
    gen = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    perf = sorted(rows, key=lambda x: x["total"], reverse=True)
    bias = sorted(rows, key=lambda x: x["asym_index"], reverse=True)

    svg1 = svg_bar_chart(perf, "total", "Average Total Score (0–6)")
    svg2 = svg_bar_chart(bias, "asym_index", "Asymmetry Index (signed: +marginalised, −power)", signed=True,
                         height=max(300, 40 + len(bias)*34))

    html = f"""<!doctype html>
<html lang="en"><meta charset="utf-8">
<title>AI Asymmetry Benchmark – Model Comparison</title>
<style>
body{{font-family:ui-sans-serif,-apple-system,Segoe UI,Roboto,Arial,sans-serif;max-width:1000px;margin:2rem auto;padding:0 1rem}}
table{{border-collapse:collapse;width:100%;margin:1rem 0}}
th,td{{border:1px solid #ddd;padding:8px;text-align:center}}
th{{background:#f6f6f6}}
.chart{{border:1px solid #eee;padding:10px;border-radius:8px;background:#fafafa;margin-bottom:1rem}}
small{{color:#555}}
</style>
<h1>AI Asymmetry Benchmark – Model Comparison</h1>
<p>Generated {gen}</p>
<div class="chart">{svg1}</div>
<div class="chart">{svg2}<br><small>Green = skew toward marginalised prompts; Red = skew toward power-critique prompts.</small></div>
<h2>League Table (Performance)</h2>
<table>
<tr><th>Rank</th><th>Model</th><th>Runs</th><th>Accuracy</th><th>Stigma</th><th>Willingness</th><th>Total</th></tr>
"""
    for i, r in enumerate(perf, 1):
        html += f"<tr><td>{i}</td><td>{r['model']}</td><td>{r['runs']}</td><td>{r['accuracy']}</td><td>{r['stigma']}</td><td>{r['willingness']}</td><td>{r['total']}</td></tr>\n"

    html += """</table>
<h2>Bias Table (Signed Asymmetry)</h2>
<p><em>Positive = better on marginalised prompts; Negative = better on power-critique.</em></p>
<table>
<tr><th>Rank</th><th>Model</th><th>Runs</th><th>Accuracy Δ</th><th>Stigma Δ</th><th>Willingness Δ</th><th>Asymmetry Index</th></tr>
"""
    for i, r in enumerate(bias, 1):
        html += (f"<tr><td>{i}</td><td>{r['model']}</td><td>{r['runs']}</td>"
                 f"<td>{r['acc_delta']}</td><td>{r['stigma_delta']}</td><td>{r['willingness_delta']}</td>"
                 f"<td>{r['asym_index']}</td></tr>\n")
    html += "</table>"
    Path("comparison.html").write_text(html, encoding="utf-8")

if __name__ == "__main__":
    data = load_all_summaries()
    rows = aggregate(data)
    if not rows:
        print("No summaries found under results/*/*/summary.json")
    else:
        save_markdown(rows)
        save_html(rows)
        print("Wrote comparison.md and comparison.html with performance + signed bias.")