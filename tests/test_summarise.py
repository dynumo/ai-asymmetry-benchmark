"""Unit tests for summarise.py statistics functions."""

import sys
from pathlib import Path

# Ensure project root on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from summarise import compute_domain_stats, compute_directional


def test_compute_domain_stats_calculates_metrics():
    rows = [
        {"domain": "marginalised", "willingness": 2, "accuracy": 1, "stigma": 1},
        {"domain": "marginalised", "willingness": 0, "accuracy": 0.5, "stigma": 1.5},
        {"domain": "power-critique", "willingness": 1, "accuracy": 2, "stigma": 0.5},
    ]
    stats = compute_domain_stats(rows)
    assert stats["marginalised"]["count"] == 2
    assert stats["marginalised"]["participation"] == 0.5
    assert stats["marginalised"]["accuracy_mean"] == 0.75
    assert stats["marginalised"]["stigma_cond"] == 1.0
    assert stats["power-critique"]["count"] == 1
    assert stats["power-critique"]["participation"] == 1.0
    assert stats["power-critique"]["accuracy_cond"] == 2.0
    assert stats["power-critique"]["stigma_cond"] == 0.5


def test_compute_directional_returns_expected_biases():
    rows = [
        {
            "domain": "marginalised",
            "willingness": 2,
            "dir_acc": "anti_power",
            "acc_severity": "moderate",
            "target_stigma": "marginalised",
            "stigma_severity": "minor",
        },
        {
            "domain": "marginalised",
            "willingness": 0,
            "dir_acc": "neutral",
            "acc_severity": "none",
            "target_stigma": "power",
            "stigma_severity": "severe",
        },
        {
            "domain": "power-critique",
            "willingness": 1,
            "dir_acc": "pro_power",
            "acc_severity": "minor",
            "target_stigma": "none",
            "stigma_severity": "none",
        },
    ]
    acc_bias, stigma_bias, will_bias = compute_directional(rows)
    assert acc_bias == -0.333
    assert stigma_bias == -0.667
    assert will_bias == -0.5
