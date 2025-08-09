"""Unit tests for :mod:`utils.io`."""

import json
import sys
from pathlib import Path

# Ensure the project root is on ``sys.path`` when tests run from an installed pytest script.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.io import load_jsonl


def test_load_jsonl_reads_objects(tmp_path):
    data = [{"a": 1}, {"b": 2}, {"c": 3}]
    p = tmp_path / "data.jsonl"
    with p.open("w", encoding="utf-8") as f:
        for obj in data:
            f.write(json.dumps(obj) + "\n")
        f.write("\n")  # trailing blank line should be ignored

    assert list(load_jsonl(str(p))) == data
