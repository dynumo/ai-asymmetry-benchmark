# grader.py
import os, json, time, argparse
from datetime import datetime
from pathlib import Path

# Optional .env loading
try:
    from dotenv import load_dotenv  # type: ignore
    if os.path.exists(".env"):
        load_dotenv()
except Exception:
    pass

from openai import OpenAI
from tqdm import tqdm

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

def log_error(err_path, item_id, msg, meta=None):
    rec = {"id": item_id, "error": str(msg), "meta": meta or {}, "ts": datetime.utcnow().isoformat() + "Z"}
    with open(err_path, "a", encoding="utf-8") as ef:
        ef.write(json.dumps(rec) + "\n")

def call_grader(client, model, rubric_prompt, response_text, max_retries=3):
    """Call the grader model with retries and conditional temperature."""
    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            kwargs = {
                "model": model,
                "messages": [
                    {"role": "system", "content": rubric_prompt},
                    {"role": "user", "content": response_text}
                ]
            }
            # Only set temperature if model likely supports it
            if not model.startswith("o1") and not model.startswith("gpt-4o"):
                kwargs["temperature"] = 0

            resp = client.chat.completions.create(**kwargs)
            return json.loads(resp.choices[0].message.content)
        except json.JSONDecodeError:
            return {
                "accuracy": 0,
                "stigma": 0,
                "willingness": 0,
                "explanation": "[ERROR] Invalid JSON from grader"
            }
        except Exception as e:
            last_exc = e
            time.sleep(min(2 ** attempt, 8))
    raise last_exc

# ---------- Main ----------
def main():
    ap = argparse.ArgumentParser(description="Grade benchmark results using a grader model with resume and error logging.")
    ap.add_argument("--model", default=os.getenv("GRADER_MODEL", "").strip(), help="Grader model name (e.g. gpt-5)")
    ap.add_argument("--rubric", default="data/rubric.json", help="Path to rubric.json")
    ap.add_argument("--run-dir", required=True, help="Path to run folder (e.g. results/gpt-5/2025-08-08_16-10-22)")
    ap.add_argument("--delay", type=float, default=0.5, help="Delay between requests in seconds (default 0.5)")
    ap.add_argument("--max", type=int, help="Limit number of responses to grade")
    ap.add_argument("--fail-fast", action="store_true", help="Stop on first error instead of logging and continuing")
    args = ap.parse_args()

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise EnvironmentError("Missing OPENAI_API_KEY. Set it in your environment or .env file.")
    if not args.model:
        raise EnvironmentError("Missing --model or GRADER_MODEL.")

    client = OpenAI(api_key=api_key)
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
    print(f"[INFO] Total to grade={len(raw)}  Already graded={len(done_ids)}  Remaining={len(to_grade)}")

    with open(graded_path, "a", encoding="utf-8") as out:
        for r in tqdm(to_grade, desc="Grading", unit="item"):
            rid = r.get("id")
            domain = r.get("domain")
            try:
                rubric_prompt = RUBRIC.get(domain, "")
                if not rubric_prompt:
                    raise ValueError(f"No rubric entry for domain '{domain}'")
                grade = call_grader(client, args.model, rubric_prompt, r["response"])
                rec = {**r, **grade}
                out.write(json.dumps(rec) + "\n")
                out.flush()
            except Exception as e:
                log_error(err_path, rid, e, {"grader_model": args.model})
                rec = {**r, "accuracy": 0, "stigma": 0, "willingness": 0, "explanation": f"[ERROR] {e}"}
                out.write(json.dumps(rec) + "\n")
                out.flush()
                if args.fail_fast:
                    raise
            time.sleep(max(args.delay, 0.0))

    print(f"[DONE] Wrote graded results to {graded_path}")
    if Path(err_path).exists():
        print(f"[NOTE] Errors were logged to {err_path}")

if __name__ == "__main__":
    main()