# tests/test_gate.py
from src.gate import apply_gate


def test_soft_mode_allows_low_warn():
    diff = {"risk_flags": [{"level": "WARN", "path": "x", "reason": "test"}]}
    gate = {"mode": "soft", "warn_score_block": 30}
    r = apply_gate(diff, gate)
    assert r["allowed"] is True


def test_soft_mode_blocks_high_warn():
    diff = {"risk_flags": [{"level": "WARN", "path": "x", "reason": "test"}] * 3}
    gate = {"mode": "soft", "warn_score_block": 20}
    r = apply_gate(diff, gate)
    assert r["allowed"] is False


def test_error_always_blocks():
    diff = {"risk_flags": [{"level": "ERROR", "path": "x", "reason": "boom"}]}
    gate = {"mode": "soft"}
    r = apply_gate(diff, gate)
    assert r["allowed"] is False


def test_hard_mode_blocks_any_risk():
    diff = {"risk_flags": [{"level": "WARN", "path": "x", "reason": "test"}]}
    gate = {"mode": "hard"}
    r = apply_gate(diff, gate)
    assert r["allowed"] is False
