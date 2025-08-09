"""Unit tests for helper functions in benchmark.py."""

import json
import sys
from pathlib import Path

# Ensure project root on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmark import safe_dir, already_processed_ids


def test_safe_dir_replaces_disallowed_chars():
    assert safe_dir("a:b/c\\d*e?f") == "a__b__c__d_e_f"


def test_safe_dir_preserves_allowed_chars():
    original = "Model-1.0_name"
    assert safe_dir(original) == original


def test_already_processed_ids_reads_file(tmp_path):
    p = tmp_path / "out.jsonl"
    lines = [
        "{\"id\": 1}\n",
        "{\"foo\": 2}\n",
        "{\"id\": 2}\n",
        "invalid json\n",
    ]
    with p.open("w", encoding="utf-8") as f:
        f.writelines(lines)

    assert already_processed_ids(str(p)) == {1, 2}


def test_already_processed_ids_missing_file(tmp_path):
    missing = tmp_path / "missing.jsonl"
    assert already_processed_ids(str(missing)) == set()
