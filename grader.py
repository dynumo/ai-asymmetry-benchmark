# grader.py (async concurrent, multi-provider)
import os, json, argparse, asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any

try:
    from dotenv import load_dotenv
    if os.path.exists(".env"):
        load_dotenv()
except Exception:
    pass

from tqdm.asyncio import tqdm_asyncio
from llm_client import ask  # unified model call

# ---------- Helpers ----------
def load_rubric(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

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
                    pass
    return ids

def log_error_sync(err_path, item_id, msg, meta=None):
    rec = {
        "id": item_id,
        "error": str(msg),
        "meta": meta or {},
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    with open(err_path, "a", encoding="utf-8") as ef:
        ef.write(json.dumps(rec) + "\n")

async def call_grader_sync_in_thread(model: str, rubric_prompt: str, response_text: str, max_retries=3):
    """Run grading call with retries, parsing JSON from the model."""
    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            raw = await asyncio.to_thread(
                ask,
                model,
                f"{rubric_prompt}\n\nResponse:\n{response_text}"
            )
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return {
                    "accuracy": 0,
                    "stigma": 0,
                    "willingness": 0,
                    "explanation": "[ERROR] Invalid JSON from grader"
                }
        except Exception as e:
            last_exc = e
            await asyncio.sleep(min(2 ** attempt, 8))
    raise last_exc

# ---------- Main ----------
async def main_async():
    ap = argparse.ArgumentParser(description="Grade benchmark results with concurrency and resume.")
    ap.add_argument("--model", default=os.getenv("GRADER_MODEL", "").strip(), help="Grader model name")
    ap.add_argument("--rubric", default="data/rubric.json", help="Path to rubric.json")
    ap.add_argument("--run-dir", required=True, help="Path to run folder")
    ap.add_argument("--max", type=int, help="Limit number of responses to grade")
    ap.add_argument("--fail-fast", action="store_true", help="Stop on first error")
    ap.add_argument("--concurrency", type=int, default=10, help="Max in-flight requests")
    args = ap.parse_args()

    if not args.model:
        raise EnvironmentError("Missing --model or GRADER_MODEL.")

    RUBRIC = load_rubric(args.rubric)

    raw_path = Path(args.run_dir) / "raw_responses.jsonl"
    graded_path = Path(args.run_dir) / "graded_responses.jsonl"
    err_path = Path(args.run_dir) / "grader_errors.log"

    with open(raw_path, "r", encoding="utf-8") as f:
        raw = [json.loads(line) for line in f]

    if args.max:
        raw = raw[: args.max]

    done_ids = already_processed_ids(graded_path)
    to_grade = [r for r in raw if r.get("id") not in done_ids]

    print(f"[INFO] Grader model={args.model}")
    print(f"[INFO] Total={len(raw)}  Already graded={len(done_ids)}  Remaining={len(to_grade)}")
    if not to_grade:
        print("[DONE] Nothing to do.")
        return

    sem = asyncio.Semaphore(max(1, args.concurrency))
    write_lock = asyncio.Lock()
    out_f = open(graded_path, "a", encoding="utf-8")

    async def worker(r: Dict[str, Any]):
        rid = r.get("id")
        domain = r.get("domain")
        try:
            rubric_prompt = RUBRIC.get(domain, "")
            if not rubric_prompt:
                raise ValueError(f"No rubric entry for domain '{domain}'")
            async with sem:
                grade = await call_grader_sync_in_thread(args.model, rubric_prompt, r["response"])
            rec = {**r, **grade}
            async with write_lock:
                out_f.write(json.dumps(rec) + "\n")
                out_f.flush()
        except Exception as e:
            log_error_sync(err_path, rid, e, {"grader_model": args.model})
            err_rec = {
                **r,
                "accuracy": 0,
                "stigma": 0,
                "willingness": 0,
                "explanation": f"[ERROR] {e}"
            }
            async with write_lock:
                out_f.write(json.dumps(err_rec) + "\n")
                out_f.flush()
            if args.fail_fast:
                raise

    try:
        await tqdm_asyncio.gather(*(worker(r) for r in to_grade), desc="Grading", unit="item")
    finally:
        out_f.close()

    print(f"[DONE] Wrote graded results to {graded_path}")
    if Path(err_path).exists():
        print(f"[NOTE] Errors were logged to {err_path}")

if __name__ == "__main__":
    asyncio.run(main_async())