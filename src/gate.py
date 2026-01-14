# src/gate.py
from typing import Dict, Any, List

DEFAULT_GATE = {
    "mode": "soft",
    "warn_score_block": 30,
    "error_block": True,
    "weights": {"WARN": 10, "ERROR": 100},
}


def _merge_gate_config(policy_gate: Dict[str, Any] | None) -> Dict[str, Any]:
    g = DEFAULT_GATE.copy()
    if policy_gate:
        g.update({k: v for k, v in policy_gate.items() if k != "weights"})
        if "weights" in policy_gate:
            w = g["weights"].copy()
            w.update(policy_gate["weights"])
            g["weights"] = w
    return g


def risk_score(flags: List[Dict[str, str]], weights: Dict[str, int]) -> int:
    score = 0
    for rf in flags:
        score += weights.get(rf["level"], 0)
    return score


def apply_gate(
    diff: Dict[str, Any], policy_gate: Dict[str, Any] | None
) -> Dict[str, Any]:
    gate = _merge_gate_config(policy_gate)
    flags = diff.get("risk_flags", [])

    score = risk_score(flags, gate["weights"])
    has_error = any(rf["level"] == "ERROR" for rf in flags)

    allowed = True
    reasons = []

    if gate["error_block"] and has_error:
        allowed = False
        reasons.append("ERROR flag present")

    if gate["mode"] == "hard" and score > 0:
        allowed = False
        reasons.append("hard mode: non-zero risk score")

    if gate["mode"] == "soft" and score >= gate["warn_score_block"]:
        allowed = False
        reasons.append(
            f"soft mode: score {score} >= threshold {gate['warn_score_block']}"
        )

    decision = "ALLOW" if allowed else "BLOCK"

    return {
        "decision": decision,
        "allowed": allowed,
        "risk_score": score,
        "reasons": reasons,
        "effective_gate": gate,
    }
