#!/usr/bin/env python3
"""Run benchmark → grade → summarise for a model using default settings."""
import argparse
import os
import subprocess
import sys
from pathlib import Path

from benchmark import safe_dir

# load environment variables
try:
    from dotenv import load_dotenv

    if os.path.exists(".env"):
        load_dotenv()
except Exception:
    pass


def latest_run_dir(model: str) -> Path:
    safe = safe_dir(model)
    model_dir = Path("results") / safe
    if not model_dir.exists():
        raise FileNotFoundError(f"No results for model {model}")
    runs = [p for p in model_dir.iterdir() if p.is_dir()]
    if not runs:
        raise FileNotFoundError(f"No runs for model {model}")
    return max(runs, key=lambda p: p.stat().st_mtime)


def main():
    ap = argparse.ArgumentParser(description="Run full benchmark→grade→summarise pipeline")
    ap.add_argument(
        "--model",
        default=os.getenv("BENCHMARK_MODEL", "").strip(),
        help="Model to benchmark",
    )
    args = ap.parse_args()
    if not args.model:
        raise EnvironmentError("Missing --model or BENCHMARK_MODEL.")

    # 1) benchmark
    subprocess.run([sys.executable, "benchmark.py", "--model", args.model], check=True)
    run_dir = latest_run_dir(args.model)

    # 2) grade (uses default GRADER_MODEL)
    raw_path = run_dir / "raw_responses.jsonl"
    subprocess.run([sys.executable, "grader.py", "--input", str(raw_path)], check=True)

    # 3) summarise
    graded_path = run_dir / "graded_responses.jsonl"
    subprocess.run(
        [sys.executable, "summarise.py", "--input", str(graded_path), "--outdir", str(run_dir)],
        check=True,
    )
    print(f"[done] Pipeline complete. Summary at {run_dir / 'summary.md'}")


if __name__ == "__main__":
    main()
