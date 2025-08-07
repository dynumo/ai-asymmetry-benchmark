import json
import os
from pathlib import Path
from collections import defaultdict
import statistics
import matplotlib.pyplot as plt
from datetime import datetime

RESULTS_DIR = Path("results")

def load_all_summaries():
    data = defaultdict(list)
    for model_dir in RESULTS_DIR.iterdir():
        if model_dir.is_dir():
            for run_dir in model_dir.iterdir():
                summary_path = run_dir / "summary.json"
                if summary_path.exists():
                    with open(summary_path, "r", encoding="utf-8") as f:
                        try:
                            summary = json.load(f)
                            # Expected summary.json to have accuracy, stigma, willingness
                            acc = summary.get("accuracy")
                            stig = summary.get("stigma")
                            will = summary.get("willingness")
                            if acc is not None and stig is not None and will is not None:
                                total = acc + stig + will
                                data[model_dir.name].append({
                                    "accuracy": acc,
                                    "stigma": stig,
                                    "willingness": will,
                                    "total": total
                                })
                        except json.JSONDecodeError:
                            print(f"⚠️ Could not parse {summary_path}")
    return data

def aggregate(data):
    aggregated = []
    for model, runs in data.items():
        avg_acc = statistics.mean(r["accuracy"] for r in runs)
        avg_stig = statistics.mean(r["stigma"] for r in runs)
        avg_will = statistics.mean(r["willingness"] for r in runs)
        avg_total = statistics.mean(r["total"] for r in runs)
        aggregated.append({
            "model": model,
            "accuracy": round(avg_acc, 2),
            "stigma": round(avg_stig, 2),
            "willingness": round(avg_will, 2),
            "total": round(avg_total, 2)
        })
    return sorted(aggregated, key=lambda x: x["total"], reverse=True)

def save_markdown(aggregated):
    md_path = Path("comparison.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# AI Asymmetry Benchmark – Model Comparison\n")
        f.write(f"Generated {datetime.utcnow().isoformat()} UTC\n\n")
        f.write("| Rank | Model | Accuracy | Stigma | Willingness | Total |\n")
        f.write("|------|-------|----------|--------|-------------|-------|\n")
        for i, row in enumerate(aggregated, start=1):
            f.write(f"| {i} | {row['model']} | {row['accuracy']} | {row['stigma']} | {row['willingness']} | {row['total']} |\n")

def save_chart(aggregated):
    models = [row["model"] for row in aggregated]
    totals = [row["total"] for row in aggregated]

    plt.figure(figsize=(8, 5))
    plt.bar(models, totals, color="skyblue")
    plt.title("Average Total Score by Model")
    plt.xlabel("Model")
    plt.ylabel("Average Total Score")
    plt.ylim(0, 6)
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig("comparison.png")
    plt.close()

def save_html(aggregated):
    html_path = Path("comparison.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>AI Asymmetry Benchmark – Model Comparison</title>
<style>
body {{ font-family: sans-serif; max-width: 800px; margin: auto; padding: 20px; }}
h1 {{ text-align: center; }}
table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
th, td {{ border: 1px solid #ccc; padding: 8px; text-align: center; }}
th {{ background-color: #f4f4f4; }}
img {{ max-width: 100%; height: auto; }}
</style>
</head>
<body>
<h1>AI Asymmetry Benchmark – Model Comparison</h1>
<p>Generated {datetime.utcnow().isoformat()} UTC</p>
<table>
<tr><th>Rank</th><th>Model</th><th>Accuracy</th><th>Stigma</th><th>Willingness</th><th>Total</th></tr>
""")
        for i, row in enumerate(aggregated, start=1):
            f.write(f"<tr><td>{i}</td><td>{row['model']}</td><td>{row['accuracy']}</td>"
                    f"<td>{row['stigma']}</td><td>{row['willingness']}</td><td>{row['total']}</td></tr>\n")
        f.write(f"""</table>
<h2>Chart</h2>
<img src="comparison.png" alt="Comparison Chart">
</body>
</html>""")

if __name__ == "__main__":
    data = load_all_summaries()
    aggregated = aggregate(data)
    save_markdown(aggregated)
    save_chart(aggregated)
    save_html(aggregated)
    print("✅ Comparison generated: comparison.md, comparison.png, comparison.html")