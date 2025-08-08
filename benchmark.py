# benchmark.py
import os, json, time, argparse, glob
from datetime import datetime
from pathlib import Path

# Optional .env loading (doesn't fail if python-dotenv is missing)
try:
    from dotenv import load_dotenv  # type: ignore
    if os.path.exists(".env"):
        load_dotenv()
except Exception:
    pass

from openai import OpenAI
from tqdm import tqdm

# ---------- Helpers ----------
def load_prompts(path):
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]

def ensure_run_dir(model, timestamp):
    out_dir = Path("results") / model / timestamp
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir

def already_processed_ids(out_file):
    ids = set()
    if Path(out_file).exists():
        with open(out_file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                    if "id" in obj:
                        ids.add(obj["id"])
                except Exception:
                    # skip malformed lines
                    pass
    return ids

def log_error(err_path, item_id, msg, meta=None):
    rec = {"id": item_id, "error": str(msg), "meta": meta or {}, "ts": datetime.utcnow().isoformat() + "Z"}
    with open(err_path, "a", encoding="utf-8") as ef:
        ef.write(json.dumps(rec) + "\n")

def call_model(client, model, prompt_text, max_retries=3):
    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            # No temperature to avoid 400s on models that don't support it
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt_text}],
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            last_exc = e
            # crude heuristic for transient errors; backoff
            time.sleep(min(2 ** attempt, 8))
    raise last_exc

# ---------- Main ----------
def main():
    ap = argparse.ArgumentParser(description="Run benchmark prompts against a model with resume, retries, and progress.")
    ap.add_argument("--model", default=os.getenv("BENCHMARK_MODEL", "").strip(), help="Model name (e.g. gpt-5)")
    ap.add_argument("--prompts", default="data/prompts.jsonl", help="Path to prompts.jsonl")
    ap.add_argument("--timestamp", help="Run folder name; if omitted, a new timestamp is created")
    ap.add_argument("--delay", type=float, default=0.2, help="Delay between requests in seconds (default 0.2)")
    ap.add_argument("--max", type=int, help="Limit number of prompts (for smoke tests)")
    ap.add_argument("--fail-fast", action="store_true", help="Stop on first error instead of logging and continuing")
    args = ap.parse_args()

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise EnvironmentError("Missing OPENAI_API_KEY. Set it in your environment or .env file.")
    if not args.model:
        raise EnvironmentError("Missing --model or BENCHMARK_MODEL.")

    client = OpenAI(api_key=api_key)

    # Decide timestamp / run directory (resume if timestamp provided)
    timestamp = args.timestamp or datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out_dir = ensure_run_dir(args.model, timestamp)
    raw_path = out_dir / "raw_responses.jsonl"
    err_path = out_dir / "errors.log"

    prompts = load_prompts(args.prompts)
    if args.max:
        prompts = prompts[: args.max]

    done_ids = already_processed_ids(raw_path)
    to_run = [p for p in prompts if p.get("id") not in done_ids]

    print(f"[INFO] Model={args.model}  Run={out_dir}")
    print(f"[INFO] Prompts total={len(prompts)}  Already done={len(done_ids)}  Remaining={len(to_run)}")

    # Append mode so we can resume safely
    with open(raw_path, "a", encoding="utf-8") as out:
        for p in tqdm(to_run, desc="Benchmarking", unit="item"):
            pid = p.get("id")
            try:
                answer = call_model(client, args.model, p["text"])
                rec = {
                    "id": pid,
                    "domain": p.get("domain"),
                    "prompt": p.get("text"),
                    "response": answer
                }
                out.write(json.dumps(rec) + "\n")
                out.flush()
            except Exception as e:
                # Log error and either continue or fail fast
                log_error(err_path, pid, e, {"model": args.model})
                # Also write an error record to raw output so downstream steps can see the failure
                rec = {
                    "id": pid,
                    "domain": p.get("domain"),
                    "prompt": p.get("text"),
                    "response": f"[ERROR] {e}"
                }
                out.write(json.dumps(rec) + "\n")
                out.flush()
                if args.fail_fast:
                    raise
            time.sleep(max(args.delay, 0.0))

    print(f"[DONE] Wrote raw responses to {raw_path}")
    if Path(err_path).exists():
        print(f"[NOTE] Errors were logged to {err_path}")

if __name__ == "__main__":
    main()