from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List

from .errors import RULES


@dataclass
class Finding:
    code: str
    severity: str  # "ERROR" | "WARN"
    message: str
    path: str = ""
    detail: str = ""


def _add(findings: List[Finding], code: str, path: str = "", detail: str = "") -> None:
    r = RULES[code]
    findings.append(
        Finding(
            code=code,
            severity=r["severity"],
            message=r["message"],
            path=path,
            detail=detail,
        )
    )


def validate_report(policy: Dict[str, Any]) -> Dict[str, Any]:
    findings: List[Finding] = []

    # Rule 1: Completeness
    required = ["meta", "inputs", "entry", "risk", "execution", "exit", "failsafe"]
    for r in required:
        if r not in policy:
            _add(findings, "V001", path=f"$.{r}", detail="missing key")

    # Rule 2: Risk Budget
    if "risk" in policy:
        risk = policy["risk"] or {}
        if risk.get("per_trade_loss_pct") is None:
            _add(findings, "V002", path="$.risk.per_trade_loss_pct", detail="missing")
        if risk.get("daily_loss_limit_pct") is None:
            _add(findings, "V002", path="$.risk.daily_loss_limit_pct", detail="missing")

    # Rule 3: Signal Observability
    if "entry" in policy:
        entry = policy["entry"] or {}
        trig = entry.get("trigger") or {}
        checklist = trig.get("checklist")
        if checklist is None or not isinstance(checklist, list) or len(checklist) == 0:
            _add(
                findings,
                "V003",
                path="$.entry.trigger.checklist",
                detail="missing or empty",
            )

    # Rule 4: Timeframe Consistency
    try:
        tf = policy["inputs"]["data"]["timeframe"]
        if "primary" not in tf or "confirm" not in tf:
            _add(
                findings,
                "V004",
                path="$.inputs.data.timeframe",
                detail="primary/confirm missing",
            )
    except Exception:
        _add(findings, "V004", path="$.inputs.data.timeframe", detail="missing path")

    # Rule 5: Execution Realism (WARN by default)
    if "execution" in policy:
        execu = policy["execution"] or {}
        if "order_type" not in execu:
            _add(findings, "V005", path="$.execution.order_type", detail="missing")
        if "costs" not in execu:
            _add(findings, "V005", path="$.execution.costs", detail="missing")

    # Rule 6: Exit Dominance & Fail-safe
    if "exit" in policy:
        if "stop_loss_pct" not in (policy["exit"] or {}):
            _add(findings, "V006", path="$.exit.stop_loss_pct", detail="missing")
    if "failsafe" in policy:
        if "on_data_disconnect" not in (policy["failsafe"] or {}):
            _add(
                findings, "V006", path="$.failsafe.on_data_disconnect", detail="missing"
            )

    meta = policy.get("meta") or {}
    version = meta.get("policy_version")

    errors = [f for f in findings if f.severity == "ERROR"]
    warnings = [f for f in findings if f.severity == "WARN"]

    return {
        "ok": len(errors) == 0,
        "version": version,
        "summary": {"errors": len(errors), "warnings": len(warnings)},
        "errors": [f.__dict__ for f in errors],
        "warnings": [f.__dict__ for f in warnings],
    }


# 기존 validate() 호환: ERROR 있으면 예외처럼 동작시키고 싶을 때 사용
class ValidationError(Exception):
    def __init__(self, report: Dict[str, Any]):
        super().__init__("Policy validation failed")
        self.report = report


def validate(policy: Dict[str, Any]) -> bool:
    rep = validate_report(policy)
    if not rep["ok"]:
        raise ValidationError(rep)
    return True
