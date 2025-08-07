import json
import os
import time
from openai import OpenAI
from dotenv import load_dotenv

# ===== LOAD ENV =====
if os.path.exists(".env"):
    load_dotenv()

GRADER_MODEL = os.getenv("GRADER_MODEL", "").strip()
API_KEY = os.getenv("OPENAI_API_KEY", "").strip()

if not API_KEY:
    raise EnvironmentError(
        "Missing OPENAI_API_KEY. Set it in your environment or .env file."
    )

if not GRADER_MODEL:
    raise EnvironmentError(
        "Missing GRADER_MODEL. Set it in your environment or .env file."
    )

client = OpenAI(api_key=API_KEY)

with open("data/rubric.json") as f:
    RUBRIC = json.load(f)


def grade_response(domain, response_text):
    grader_prompt = RUBRIC[domain]

    try:
        completion = client.chat.completions.create(
            model=GRADER_MODEL,
            messages=[
                {"role": "system", "content": grader_prompt},
                {"role": "user", "content": response_text}
            ],
            temperature=0
        )
        return json.loads(completion.choices[0].message.content)

    except json.JSONDecodeError:
        return {"accuracy": 0, "stigma": 0, "willingness": 0,
                "explanation": "[ERROR] Invalid JSON from grader"}
    except Exception as e:
        return {"accuracy": 0, "stigma": 0, "willingness": 0,
                "explanation": f"[ERROR] {e}"}


def run_grading(model_name, timestamp):
    in_dir = f"results/{model_name}/{timestamp}"
    graded_path = f"{in_dir}/graded_responses.jsonl"

    with open(f"{in_dir}/raw_responses.jsonl") as f:
        raw = [json.loads(line) for line in f]

    graded = []
    for r in raw:
        grade = grade_response(r["domain"], r["response"])
        graded.append({**r, **grade})
        time.sleep(0.5)

    with open(graded_path, "w") as out:
        for g in graded:
            out.write(json.dumps(g) + "\n")

    print(f"[DONE] Saved graded results to {graded_path}")


if __name__ == "__main__":
    # Example:
    # run_grading("gpt-5", "2025-08-07_20-31-00")
    pass