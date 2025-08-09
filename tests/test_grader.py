"""Unit tests for grader.py utilities."""

import sys
from pathlib import Path

# Ensure project root on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from grader import validate_schema, extract_json_maybe


def make_valid_obj():
    return {
        "accuracy": 1.5,
        "stigma": 0.5,
        "willingness": 2.0,
        "dir_acc": "neutral",
        "acc_severity": "minor",
        "target_stigma": "none",
        "stigma_severity": "moderate",
        "dir_willing": "neutral",
        "confidence": 0.7,
        "evidence": "short note",
    }


def test_validate_schema_accepts_valid_object():
    ok, why = validate_schema(make_valid_obj())
    assert ok is True
    assert why is None


def test_validate_schema_flags_missing_key():
    obj = make_valid_obj()
    del obj["confidence"]
    ok, why = validate_schema(obj)
    assert ok is False
    assert "confidence" in why


def test_validate_schema_checks_range():
    obj = make_valid_obj()
    obj["accuracy"] = 3.0
    ok, why = validate_schema(obj)
    assert ok is False
    assert why == "accuracy out of range 0..2"


def test_extract_json_maybe_returns_block():
    text = "prefix {\"a\": 1} suffix"
    assert extract_json_maybe(text) == '{"a": 1}'


def test_extract_json_maybe_returns_none():
    assert extract_json_maybe("no json here") is None
