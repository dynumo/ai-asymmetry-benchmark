import json
import os
import time
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv

# ===== LOAD ENV =====
if os.path.exists(".env"):
    load_dotenv()

MODEL_UNDER_TEST = os.getenv("BENCHMARK_MODEL", "").strip()
API_KEY = os.getenv("OPENAI_API_KEY", "").strip()

if not API_KEY:
    raise EnvironmentError(
        "Missing OPENAI_API_KEY. Set it in your environment or .env file."
    )

if not MODEL_UNDER_TEST:
    raise EnvironmentError(
        "Missing BENCHMARK_MODEL. Set it in your environment or .env file."
    )

client = OpenAI(api_key=API_KEY)

# Timestamped results directory
timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
out_dir = f"results/{MODEL_UNDER_TEST}/{timestamp}"
os.makedirs(out_dir, exist_ok=True)


def run_benchmark():
    with open("data/prompts.jsonl") as f:
        prompts = [json.loads(line) for line in f]

    raw_results = []

    for p in prompts:
        try:
            completion = client.chat.completions.create(
                model=MODEL_UNDER_TEST,
                messages=[{"role": "user", "content": p["text"]}],
                temperature=0
            )
            answer = completion.choices[0].message.content.strip()

        except Exception as e:
            answer = f"[ERROR] {e}"

        raw_results.append({
            "id": p["id"],
            "domain": p["domain"],
            "prompt": p["text"],
            "response": answer
        })

        time.sleep(0.5)  # avoid hammering API

    raw_path = f"{out_dir}/raw_responses.jsonl"
    with open(raw_path, "w") as out:
        for r in raw_results:
            out.write(json.dumps(r) + "\n")

    print(f"[DONE] Saved raw results to {raw_path}")
    return MODEL_UNDER_TEST, timestamp


if __name__ == "__main__":
    run_benchmark()