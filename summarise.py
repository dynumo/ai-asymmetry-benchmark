# summarise.py
import argparse, json, os, glob, statistics
from datetime import datetime

def load_jsonl(path):
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)

def latest_run_dir(model_dir):
    runs = [d for d in glob.glob(os.path.join(model_dir, "*")) if os.path.isdir(d)]
    if not runs:
        raise FileNotFoundError(f"No runs found under {model_dir}")
    # assume timestamp folders are lexicographically sortable
    return sorted(runs)[-1]

def mean(vals):
    return round(statistics.fmean(vals), 3) if vals else 0.0

def summarise(run_dir):
    graded_path = os.path.join(run_dir, "graded_responses.jsonl")
    if not os.path.exists(graded_path):
        raise FileNotFoundError(f"Missing {graded_path}")

    rows = list(load_jsonl(graded_path))
    if not rows:
        raise ValueError("No graded rows found.")

    by_domain = {"marginalised": [], "power-critique": []}
    for r in rows:
        d = r["domain"]
        if d not in by_domain:
            by_domain[d] = []
        by_domain[d].append(r)

    def domain_scores(domain):
        items = by_domain.get(domain, [])
        acc = [x.get("accuracy", 0) for x in items]
        sti = [x.get("stigma", 0) for x in items]
        wil = [x.get("willingness", 0) for x in items]
        return {
            "count": len(items),
            "accuracy": mean(acc),
            "stigma": mean(sti),
            "willingness": mean(wil)
        }

    marg = domain_scores("marginalised")
    powc = domain_scores("power-critique")

    # overall averages across all rows
    all_acc = mean([x.get("accuracy", 0) for x in rows])
    all_sti = mean([x.get("stigma", 0) for x in rows])
    all_wil = mean([x.get("willingness", 0) for x in rows])

    # asymmetry index: marginalised − power-critique (per metric and mean of three)
    asym = {
        "accuracy_delta": round(marg["accuracy"] - powc["accuracy"], 3),
        "stigma_delta": round(marg["stigma"] - powc["stigma"], 3),
        "willingness_delta": round(marg["willingness"] - powc["willingness"], 3),
    }
    asym["asymmetry_index"] = round(
        (asym["accuracy_delta"] + asym["stigma_delta"] + asym["willingness_delta"]) / 3, 3
    )

    summary = {
        "run_dir": run_dir,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "counts": {
            "total": len(rows),
            "marginalised": marg["count"],
            "power-critique": powc["count"]
        },
        "domains": {
            "marginalised": {k: v for k, v in marg.items() if k != "count"},
            "power-critique": {k: v for k, v in powc.items() if k != "count"}
        },
        "overall": {
            "accuracy": all_acc,
            "stigma": all_sti,
            "willingness": all_wil
        },
        "asymmetry": asym
    }

    # Write JSON
    json_path = os.path.join(run_dir, "summary.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    # Write Markdown
    md_path = os.path.join(run_dir, "summary.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Asymmetry Benchmark Summary\n\n")
        f.write(f"- Run: `{run_dir}`\n")
        f.write(f"- Generated: {summary['generated_at']}\n")
        f.write(f"- Items: total {summary['counts']['total']}  "
                f"(marginalised {summary['counts']['marginalised']}, "
                f"power-critique {summary['counts']['power-critique']})\n\n")

        f.write("## Scores by domain\n\n")
        f.write("| Domain | Accuracy | Stigma | Willingness |\n")
        f.write("|---|---:|---:|---:|\n")
        f.write(f"| marginalised | {summary['domains']['marginalised']['accuracy']} | "
                f"{summary['domains']['marginalised']['stigma']} | "
                f"{summary['domains']['marginalised']['willingness']} |\n")
        f.write(f"| power-critique | {summary['domains']['power-critique']['accuracy']} | "
                f"{summary['domains']['power-critique']['stigma']} | "
                f"{summary['domains']['power-critique']['willingness']} |\n\n")

        f.write("## Overall averages\n\n")
        f.write("| Accuracy | Stigma | Willingness |\n")
        f.write("|---:|---:|---:|\n")
        f.write(f"| {summary['overall']['accuracy']} | {summary['overall']['stigma']} | {summary['overall']['willingness']} |\n\n")

        f.write("## Asymmetry\n\n")
        f.write("| Metric | Marginalised − Power-critique |\n")
        f.write("|---|---:|\n")
        f.write(f"| Accuracy Δ | {summary['asymmetry']['accuracy_delta']} |\n")
        f.write(f"| Stigma Δ | {summary['asymmetry']['stigma_delta']} |\n")
        f.write(f"| Willingness Δ | {summary['asymmetry']['willingness_delta']} |\n\n")
        f.write(f"**Asymmetry Index** (mean of three deltas): **{summary['asymmetry']['asymmetry_index']}**\n")

    print(f"[DONE] Wrote {json_path} and {md_path}")

def main():
    ap = argparse.ArgumentParser(description="Summarise a benchmark run.")
    ap.add_argument("--model", help="Model name (directory under results/)")
    ap.add_argument("--timestamp", help="Run timestamp folder (e.g. 2025-08-07_20-31-00)")
    ap.add_argument("--path", help="Direct path to run dir (overrides model/timestamp)")
    args = ap.parse_args()

    if args.path:
        run_dir = args.path
    else:
        if not args.model:
            raise SystemExit("Provide --model (and optionally --timestamp) or --path to run dir.")
        model_dir = os.path.join("results", args.model)
        if not os.path.isdir(model_dir):
            raise SystemExit(f"Model dir not found: {model_dir}")
        run_dir = os.path.join(model_dir, args.timestamp) if args.timestamp else latest_run_dir(model_dir)

    summarise(run_dir)

if __name__ == "__main__":
    main()