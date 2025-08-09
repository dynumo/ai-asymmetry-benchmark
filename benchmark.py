# benchmark.py (async, concurrent)
import os, json, argparse, re
from datetime import datetime, timezone
from pathlib import Path
import asyncio
from typing import Dict, Any

# Optional .env loading
try:
    from dotenv import load_dotenv

    if os.path.exists(".env"):
        load_dotenv()
except Exception:
    pass

from tqdm.asyncio import tqdm_asyncio
from llm_client import ask  # <-- unified LLM client


# ---------- Helpers ----------
def load_prompts(path):
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def safe_dir(name: str) -> str:
    # Replace characters that break Windows/macOS paths
    name = name.replace(":", "__").replace("/", "__").replace("\\", "__")
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name)


def ensure_run_dir(model_dirname, timestamp):
    out_dir = Path("results") / model_dirname / timestamp
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


async def call_model_sync_in_thread(
    model: str, prompt_text: str, max_retries: int = 3
) -> str:
    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            return await asyncio.to_thread(ask, model, prompt_text)
        except Exception as e:
            last_exc = e
            await asyncio.sleep(min(2**attempt, 8))
    raise last_exc


# ---------- Main ----------
async def main_async():
    ap = argparse.ArgumentParser(
        description="Run benchmark prompts with concurrency, resume, and retries."
    )
    ap.add_argument(
        "--model",
        default=os.getenv("BENCHMARK_MODEL", "").strip(),
        help="Model name (e.g. gpt-5)",
    )
    ap.add_argument(
        "--prompts", default="data/prompts.jsonl", help="Path to prompts.jsonl"
    )
    ap.add_argument(
        "--timestamp", help="Run folder name; if omitted, a new timestamp is created"
    )
    ap.add_argument("--max", type=int, help="Limit number of prompts (for smoke tests)")
    ap.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop on first error instead of logging and continuing",
    )
    ap.add_argument(
        "--concurrency",
        type=int,
        default=10,
        help="Max in-flight requests (default 10)",
    )
    args = ap.parse_args()

    if not args.model:
        raise EnvironmentError("Missing --model or BENCHMARK_MODEL.")

    timestamp = args.timestamp or datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    safe_model_dir = safe_dir(args.model)
    out_dir = ensure_run_dir(safe_model_dir, timestamp)
    raw_path = out_dir / "raw_responses.jsonl"
    err_path = out_dir / "errors.log"

    prompts = load_prompts(args.prompts)
    if args.max:
        prompts = prompts[: args.max]

    done_ids = already_processed_ids(raw_path)
    to_run = [p for p in prompts if p.get("id") not in done_ids]

    print(f"[INFO] Model={args.model}  Run={out_dir}")
    print(
        f"[INFO] Prompts total={len(prompts)}  Already done={len(done_ids)}  Remaining={len(to_run)}"
    )
    if not to_run:
        print("[DONE] Nothing to do.")
        return

    write_lock = asyncio.Lock()
    out_f = open(raw_path, "a", encoding="utf-8")
    sem = asyncio.Semaphore(max(1, args.concurrency))

    async def worker(p: Dict[str, Any]):
        pid = p.get("id")
        try:
            async with sem:
                answer = await call_model_sync_in_thread(args.model, p["text"])
            rec = {
                "id": pid,
                "domain": p.get("domain"),
                "prompt": p.get("text"),
                "response": answer,
            }
            async with write_lock:
                out_f.write(json.dumps(rec) + "\n")
                out_f.flush()
        except Exception as e:
            log_error_sync(err_path, pid, e, {"model": args.model})
            err_rec = {
                "id": pid,
                "domain": p.get("domain"),
                "prompt": p.get("text"),
                "response": f"[ERROR] {e}",
            }
            async with write_lock:
                out_f.write(json.dumps(err_rec) + "\n")
                out_f.flush()
            if args.fail_fast:
                raise

    try:
        await tqdm_asyncio.gather(
            *(worker(p) for p in to_run), desc="Benchmarking", unit="item"
        )
    finally:
        out_f.close()

    print(f"[DONE] Wrote raw responses to {raw_path}")
    if Path(err_path).exists():
        print(f"[NOTE] Errors were logged to {err_path}")


if __name__ == "__main__":
    asyncio.run(main_async())
