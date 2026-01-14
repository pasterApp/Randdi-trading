from __future__ import annotations
from typing import Any, Dict, List


def _flatten(d: Dict[str, Any], prefix: str = "$") -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k, v in d.items():
        p = f"{prefix}.{k}"
        if isinstance(v, dict):
            out.update(_flatten(v, p))
        else:
            out[p] = v
    return out


def risk_score_from_flags(risk_flags: List[Dict[str, str]]) -> int:
    score = 0
    for rf in risk_flags:
        if rf["level"] == "ERROR":
            score += 100
        elif rf["level"] == "WARN":
            score += 10
    return score


def diff_policies(old: Dict[str, Any] | None, new: Dict[str, Any]) -> Dict[str, Any]:
    """
    Returns:
      {
        "added":   [(path, value)],
        "removed": [(path, value)],
        "changed": [(path, old, new)],
        "risk_flags": [{"level": "WARN|ERROR", "path": "...", "reason": "..."}],
        "risk_score": int
      }
    """
    # --- Case 1) no previous policy (first release)
    if old is None:
        flat_new = _flatten(new)
        return {
            "added": [(p, v) for p, v in flat_new.items()],
            "removed": [],
            "changed": [],
            "risk_flags": [],
            "risk_score": 0,
        }

    # --- Case 2) compare old vs new
    a = _flatten(old)
    b = _flatten(new)

    added = [(p, b[p]) for p in (b.keys() - a.keys())]
    removed = [(p, a[p]) for p in (a.keys() - b.keys())]
    changed = [(p, a[p], b[p]) for p in (a.keys() & b.keys()) if a[p] != b[p]]

    risk_flags: List[Dict[str, str]] = []

    def flag(level: str, path: str, reason: str):
        risk_flags.append({"level": level, "path": path, "reason": reason})

    def get(path: str):
        # returns (new_value, old_value)
        return b.get(path), a.get(path)

    # 1) per_trade_loss 상승
    nv, ov = get("$.risk.per_trade_loss_pct")
    if ov is not None and nv is not None and nv > ov:
        flag("WARN", "$.risk.per_trade_loss_pct", f"increased {ov} -> {nv}")

    # 2) daily_loss_limit 상승
    nv, ov = get("$.risk.daily_loss_limit_pct")
    if ov is not None and nv is not None and nv > ov:
        flag("WARN", "$.risk.daily_loss_limit_pct", f"increased {ov} -> {nv}")

    # 3) stop_loss 완화(확대)
    nv, ov = get("$.exit.stop_loss_pct")
    if ov is not None and nv is not None and nv > ov:
        flag("WARN", "$.exit.stop_loss_pct", f"widened {ov} -> {nv}")

    # 4) 비용/슬리피지 0 설정(현실성 훼손)
    nv, _ = get("$.execution.costs.fee_pct")
    if nv == 0:
        flag("ERROR", "$.execution.costs.fee_pct", "fee set to 0")

    nv, _ = get("$.execution.costs.slippage_pct")
    if nv == 0:
        flag("ERROR", "$.execution.costs.slippage_pct", "slippage set to 0")

    # 5) timeframe 변경(전략 성격 급변)
    nv, ov = get("$.inputs.data.timeframe.primary")
    if ov is not None and nv is not None and nv != ov:
        flag("WARN", "$.inputs.data.timeframe.primary", f"changed {ov} -> {nv}")

    score = risk_score_from_flags(risk_flags)

    return {
        "added": added,
        "removed": removed,
        "changed": changed,
        "risk_flags": risk_flags,
        "risk_score": score,
    }
