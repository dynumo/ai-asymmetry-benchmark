# AI Asymmetry Benchmark

Benchmark LLMs for **asymmetry** in how they answer:
- Questions about **marginalised/vulnerable groups**
- **Critiques of powerful** institutions/actors

Pipeline:
1) Run prompts → raw model answers
2) Grade answers with a rubric
3) Summarise a run
4) Compare runs across models/dates

## Structure
```
data/
  prompts.jsonl
  rubric.json
results/
  <model>/
    <timestamp>/
      raw_responses.jsonl
      graded_responses.jsonl
      errors.log
      grader_errors.log
      summary.json
      summary.md
tools/
  viewer.html
benchmark.py
grader.py
summariser.py
compare_runs.py
llm_client.py
```

## Setup

### Requirements
```
openai>=1.0.0
python-dotenv>=1.0.0
tqdm>=4.66.0
anthropic
```

Install:
```bash
pip install -r requirements.txt
```

### Environment
Create `.env` (kept out of Git):

```
# API keys
OPENAI_API_KEY=sk-XXXXXXXXXXXXXXXXXXXXXXXX
# Add ANTHROPIC_API_KEY=… / GROQ_API_KEY=… etc. as needed

# Benchmark run
BENCHMARK_PROVIDER=openai
BENCHMARK_MODEL=gpt-5

# Grading run
GRADER_PROVIDER=openai
GRADER_MODEL=gpt-5-mini
```

(Windows PowerShell alternative for a single session:)
```powershell
$env:OPENAI_API_KEY="sk-XXXXXXXXXXXXXXXX"
$env:BENCHMARK_PROVIDER="openai"
$env:BENCHMARK_MODEL="gpt-5"
$env:GRADER_PROVIDER="openai"
$env:GRADER_MODEL="gpt-5-mini"
```

## Run the pipeline

### 1) Benchmark (collect raw answers)
```bash
python benchmark.py --model gpt-5
```
Options:
- `--prompts data/prompts.jsonl`
- `--max 10` (limit prompts for smoke tests)
- `--fail-fast`
- `--timestamp 2025-08-08_16-10-22` (to resume)
- `--concurrency 5` (set max parallel requests)

Outputs:
```
results/gpt-5/<timestamp>/raw_responses.jsonl
results/gpt-5/<timestamp>/errors.log
```

### 2) Grade (apply rubric with grader model)
```bash
python grader.py --model gpt-5-mini --run-dir results/gpt-5/<timestamp>
```
Options:
- `--rubric data/rubric.json`
- `--max 10`
- `--fail-fast`
- `--concurrency 5`

Outputs:
```
results/gpt-5/<timestamp>/graded_responses.jsonl
results/gpt-5/<timestamp>/grader_errors.log
```

### 3) Summarise a run
```bash
python summariser.py --path results/gpt-5/<timestamp>
# or
python summariser.py --model gpt-5
```

Outputs:
```
results/gpt-5/<timestamp>/summary.json
results/gpt-5/<timestamp>/summary.md
```

### 4) Compare runs (league table)
```bash
python compare_runs.py
```

Outputs:
```
comparison.md
comparison.html
```

## Notes
- **Resume-safe**: benchmark & grader append one JSON line per item and skip already-processed IDs.
- **Errors** are logged per run; runs continue unless `--fail-fast` is set.
- **Provider flexibility**: change `BENCHMARK_PROVIDER` / `GRADER_PROVIDER` in `.env` to swap APIs without touching code.
- **Charts**: `compare_runs.py` uses inline SVG (no external libs).

## Licence
MIT — see `LICENSE`.