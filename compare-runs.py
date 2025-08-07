# compare_runs.py  — no external deps
import json, os
from pathlib import Path
from collections import defaultdict
from datetime import datetime
import statistics

RESULTS_DIR = Path("results")

def load_all_summaries():
    data = defaultdict(list)
    for model_dir in RESULTS_DIR.iterdir():
        if not model_dir.is_dir(): continue
        for run_dir in model_dir.iterdir():
            summary_path = run_dir / "summary.json"
            if not summary_path.exists(): continue
            try:
                s = json.load(open(summary_path, "r", encoding="utf-8"))
                ov = s.get("overall", {})
                acc, sti, wil = ov.get("accuracy"), ov.get("stigma"), ov.get("willingness")
                if None in (acc, sti, wil): continue
                data[model_dir.name].append({
                    "accuracy": acc, "stigma": sti, "willingness": wil,
                    "total": acc + sti + wil, "run_dir": str(run_dir)
                })
            except Exception:
                pass
    return data

def aggregate(data):
    rows = []
    for model, runs in data.items():
        if not runs: continue
        f = lambda k: statistics.fmean(r[k] for r in runs)
        rows.append({
            "model": model,
            "runs": len(runs),
            "accuracy": round(f("accuracy"), 3),
            "stigma": round(f("stigma"), 3),
            "willingness": round(f("willingness"), 3),
            "total": round(f("total"), 3)
        })
    return sorted(rows, key=lambda x: x["total"], reverse=True)

def save_markdown(rows):
    with open("comparison.md", "w", encoding="utf-8") as f:
        f.write("# AI Asymmetry Benchmark – Model Comparison\n\n")
        f.write(f"Generated {datetime.utcnow().isoformat()}Z\n\n")
        f.write("| Rank | Model | Runs | Accuracy | Stigma | Willingness | Total |\n")
        f.write("|---:|---|---:|---:|---:|---:|---:|\n")
        for i, r in enumerate(rows, 1):
            f.write(f"| {i} | {r['model']} | {r['runs']} | {r['accuracy']} | {r['stigma']} | {r['willingness']} | {r['total']} |\n")

def svg_bar_chart(rows, width=900, height=300, max_score=6.0):
    # simple horizontal bars for Total
    padding = 20
    bar_h = 24
    gap = 10
    inner_w = width - 2*padding
    y = padding
    svg = [f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">']
    svg.append(f'<rect width="100%" height="100%" fill="#ffffff"/>')
    svg.append(f'<text x="{padding}" y="{padding-5}" font-size="12" fill="#333">Average Total Score (0–6)</text>')
    for r in rows:
        w = int((r["total"]/max_score) * inner_w)
        svg.append(f'<rect x="{padding}" y="{y}" width="{w}" height="{bar_h}" fill="#4da3ff"/>')
        svg.append(f'<text x="{padding+5}" y="{y+bar_h-6}" font-size="12" fill="#fff">{r["model"]}</text>')
        svg.append(f'<text x="{padding+w-5}" y="{y+bar_h-6}" font-size="12" fill="#003" text-anchor="end">{r["total"]}</text>')
        y += bar_h + gap
    svg.append("</svg>")
    return "\n".join(svg)

def save_html(rows):
    svg = svg_bar_chart(rows, height= max(300, 40 + len(rows)*34))
    html = f"""<!doctype html>
<html lang="en"><meta charset="utf-8">
<title>AI Asymmetry Benchmark – Model Comparison</title>
<style>
body{{font-family: ui-sans-serif,-apple-system,Segoe UI,Roboto,Arial,sans-serif;max-width:1000px;margin:2rem auto;padding:0 1rem}}
table{{border-collapse:collapse;width:100%;margin:1rem 0}}
th,td{{border:1px solid #ddd;padding:8px;text-align:center}}
th{{background:#f6f6f6}}
code{{background:#f2f2f2;padding:2px 4px;border-radius:4px}}
.chart{{border:1px solid #eee;padding:10px;border-radius:8px;background:#fafafa}}
</style>
<h1>AI Asymmetry Benchmark – Model Comparison</h1>
<p>Generated {datetime.utcnow().isoformat()}Z</p>
<div class="chart">{svg}</div>
<h2>League Table</h2>
<table>
<tr><th>Rank</th><th>Model</th><th>Runs</th><th>Accuracy</th><th>Stigma</th><th>Willingness</th><th>Total</th></tr>
"""
    for i, r in enumerate(rows, 1):
        html += f"<tr><td>{i}</td><td>{r['model']}</td><td>{r['runs']}</td><td>{r['accuracy']}</td><td>{r['stigma']}</td><td>{r['willingness']}</td><td>{r['total']}</td></tr>\n"
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
        print("Wrote comparison.md and comparison.html (no external deps).")
