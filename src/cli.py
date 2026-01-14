from __future__ import annotations
from .diff import diff_policies

import argparse
import json
import shutil
from pathlib import Path
from datetime import datetime

from .loader import load_policy
from .validator import validate_report


DEFAULT_POLICY = "policy.yaml"
POLICIES_DIR = "policies"
RELEASES_DIR = "policies/releases"
CURRENT_FILE = "policies/current.yaml"
HISTORY_FILE = "policies/history.log"


def _emit_json(obj: dict, json_out: bool, out_path: str | None) -> None:
    import json

    s = json.dumps(obj, ensure_ascii=False, indent=2)

    if json_out:
        print(s)

    if out_path:
        p = Path(out_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(s, encoding="utf-8")


def _ensure_dirs() -> None:
    Path(RELEASES_DIR).mkdir(parents=True, exist_ok=True)
    Path(POLICIES_DIR).mkdir(parents=True, exist_ok=True)


def _read_current_version() -> str | None:
    cur = Path(CURRENT_FILE)
    if not cur.exists():
        return None
    policy = load_policy(str(cur))
    return (policy.get("meta") or {}).get("policy_version")


def _list_versions() -> list[str]:
    base = Path(RELEASES_DIR)
    if not base.exists():
        return []
    versions = [p.name for p in base.iterdir() if p.is_dir()]

    def key(v: str):
        parts = v.split(".")
        return (
            tuple(int(x) for x in parts)
            if len(parts) == 3 and all(x.isdigit() for x in parts)
            else (999, 999, 999)
        )

    return sorted(versions, key=key)


def cmd_validate(policy_path: str, json_out: bool, out_path: str | None) -> int:
    policy = load_policy(policy_path)
    rep = validate_report(policy)

    # JSON 출력 또는 파일 저장
    _emit_json(rep, json_out=json_out, out_path=out_path)

    if not json_out:
        if rep["ok"]:
            print("OK: policy valid")
        else:
            print(
                f"FAIL: {rep['summary']['errors']} errors, {rep['summary']['warnings']} warnings"
            )

    return 0 if rep["ok"] else 2


def cmd_release(
    policy_path: str,
    strict: bool,
    json_out: bool,
    out_path: str | None,
    dry_run: bool = False,  # ✅ 추가
) -> int:

    _ensure_dirs()

    policy = load_policy(policy_path)
    rep = validate_report(policy)

    # 0) validator ERROR 있으면 차단 (rep 저장 가능)
    if not rep["ok"]:
        _emit_json(rep, json_out=json_out, out_path=out_path)
        if not json_out:
            print(json.dumps(rep, ensure_ascii=False, indent=2))
        print("RELEASE BLOCKED: errors present")
        return 2

    # 1) validator strict: validator WARN 있으면 차단 (rep 저장 가능)
    if strict and rep["summary"]["warnings"] > 0:
        _emit_json(rep, json_out=json_out, out_path=out_path)
        print("RELEASE BLOCKED: strict mode and validator warnings present")
        return 2

    from src.gate import apply_gate

    # 2) Diff & Risk Summary (항상 실행: 이후 모든 차단/성공에서 rep_with_diff 사용)
    prev = None

    # 2) Diff & Gate (항상 실행: 이후 모든 차단/성공에서 rep_with_diff 사용)
    prev = None
    if Path(CURRENT_FILE).exists():
        prev = load_policy(CURRENT_FILE)

    diff = diff_policies(prev, policy)

    policy_gate = (policy.get("release") or {}).get("gate")
    gate_result = apply_gate(diff, policy_gate)

    # report에 diff/gate 결과 포함
    rep_with_diff = dict(rep)
    rep_with_diff["diff"] = diff
    rep_with_diff["gate"] = gate_result

    # Gate 차단
    if not gate_result["allowed"]:
        _emit_json(rep_with_diff, json_out=json_out, out_path=out_path)
        print("RELEASE BLOCKED BY GATE")
        for r in gate_result["reasons"]:
            print(f"  - {r}")
        return 2

    # --- Dry-run: 여기서 중단 (쓰기 없음)
    if dry_run:
        rep_with_diff["dry_run"] = True
        _emit_json(rep_with_diff, json_out=json_out, out_path=out_path)
        print("DRY-RUN OK: no files were written")
        return 0

    # 요약 출력(텍스트)
    if diff["added"] or diff["removed"] or diff["changed"]:
        print("DIFF SUMMARY:")
        if diff["added"]:
            print(f"  added: {len(diff['added'])}")
        if diff["removed"]:
            print(f"  removed: {len(diff['removed'])}")
        if diff["changed"]:
            print(f"  changed: {len(diff['changed'])}")

    # 위험 플래그 출력은 "changed 유무"와 무관하게 항상 가능해야 함
    if diff["risk_flags"]:
        print("RISK FLAGS:")
        for rf in diff["risk_flags"]:
            print(f"  [{rf['level']}] {rf['path']} - {rf['reason']}")
        print(f"RISK SCORE: {diff['risk_score']}")

        # ERROR는 strict와 무관하게 무조건 차단
        has_error = any(rf["level"] == "ERROR" for rf in diff["risk_flags"])
        if has_error:
            _emit_json(rep_with_diff, json_out=json_out, out_path=out_path)
            print("RELEASE BLOCKED: risk ERROR detected")
            return 2

        # 3) diff strict: WARN도 차단하고 싶으면 여기서 차단
        if strict and diff["risk_score"] > 0:
            _emit_json(rep_with_diff, json_out=json_out, out_path=out_path)
            print("RELEASE BLOCKED: strict mode and risk flags present")
            return 2

    # 4) version 확인
    meta = policy.get("meta") or {}
    version = meta.get("policy_version")
    if not version:
        _emit_json(rep_with_diff, json_out=json_out, out_path=out_path)
        print("RELEASE BLOCKED: meta.policy_version missing")
        return 2

    # 5) 버전 중복 차단
    dest_dir = Path(RELEASES_DIR) / version
    dest_file = dest_dir / "policy.yaml"

    if dest_file.exists():
        _emit_json(rep_with_diff, json_out=json_out, out_path=out_path)
        print(f"RELEASE BLOCKED: version already exists: {version}")
        return 2

    # 6) 파일 복사(릴리즈 확정)
    dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(policy_path, dest_file)
    # ✅ releases/<ver>/report.json (항상 저장: 릴리즈 아카이빙 증빙)
    import json

    report_file = dest_dir / "report.json"
    report_file.write_text(
        json.dumps(rep_with_diff, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    Path(POLICIES_DIR).mkdir(parents=True, exist_ok=True)
    shutil.copy2(dest_file, Path(CURRENT_FILE))

    ts = datetime.now().isoformat(timespec="seconds")
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(f"{ts}\trelease\t{version}\tfrom={policy_path}\n")

    print(f"RELEASED: {version}")
    # --- 버전별 report.json 저장
    report_file = dest_dir / "report.json"
    report_file.write_text(
        json.dumps(rep_with_diff, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # --- 최신 실행 report (handoff)
    _emit_json(rep_with_diff, json_out=json_out, out_path=out_path)
    return 0


def write_policy(base_dir: Path, version: str) -> Path:
    content = f"""\
meta:
  policy_version: "{version}"

inputs:
  data:
    timeframe:
      primary: "5m"
      confirm: "20m"

risk:
  per_trade_loss_pct: 1.0
  daily_loss_limit_pct: 2.0

execution:
  order_type: "market"
  costs:
    fee_pct: 0.01
    slippage_pct: 0.01

entry:
  trigger:
    description: "x"
    checklist: ["a"]
  invalidation:
    description: "y"

exit:
  stop_loss_pct: 1.0
  trailing_stop_pct: 1.0

failsafe:
  on_api_error: "close_positions"
  on_data_disconnect: "halt_trading"
"""
    p = base_dir / f"policy_{version}.yaml"
    p.write_text(content, encoding="utf-8")
    return p


def _emit_json(obj: dict, json_out: bool, out_path: str | None) -> None:
    import json

    s = json.dumps(obj, ensure_ascii=False, indent=2)

    if json_out:
        print(s)

    if out_path:
        p = Path(out_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(s, encoding="utf-8")


def cmd_rollback(target_version: str | None) -> int:
    _ensure_dirs()

    versions = _list_versions()
    if not versions:
        print("ROLLBACK FAILED: no releases found")
        return 2

    current_ver = _read_current_version()

    # target 결정
    if target_version is None:
        # 현재가 가장 오래된 버전이면 롤백 불가
        if current_ver in versions:
            idx = versions.index(current_ver)
            if idx == 0:
                print("ROLLBACK FAILED: already at oldest version")
                return 2
            target = versions[idx - 1]
        else:
            # current가 releases에 없으면 최신 이전으로 가는 기본 동작
            target = versions[-1]
    else:
        target = target_version
        if target not in versions:
            print(f"ROLLBACK FAILED: target version not found: {target}")
            return 2

    # 실제 롤백 수행
    try:
        src_policy = Path(RELEASES_DIR) / target / "policy.yaml"
        if not src_policy.exists():
            print(f"ROLLBACK FAILED: release policy not found for {target}")
            return 2

        Path(POLICIES_DIR).mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_policy, Path(CURRENT_FILE))

        ts = datetime.now().isoformat(timespec="seconds")
        with open(HISTORY_FILE, "a", encoding="utf-8") as f:
            f.write(f"{ts}\trollback\t{target}\n")

        success = True
        msg = f"ROLLED BACK: {target}"
        print(msg)
        rc = 0

    except Exception as e:
        success = False
        msg = f"ROLLBACK FAILED: {e}"
        print(msg)
        rc = 2

    # report는 반드시 마지막에 만든다
    rep = {
        "report_schema": "1.0",
        "action": "rollback",
        "from_version": current_ver,
        "to_version": target if success else None,
        "ok": success,
        "message": msg,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }
    _emit_json(rep, json_out=False, out_path="artifacts/last_rollback.json")

    return rc


def cmd_status() -> int:
    _ensure_dirs()
    versions = _list_versions()
    cur = _read_current_version()
    print(f"current: {cur}")
    print(f"releases: {versions if versions else '[]'}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(
        prog="sv", description="Strategy policy validator (MVP Week1)"
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("validate", help="Validate a policy file")
    v.add_argument("--policy", default=DEFAULT_POLICY)
    v.add_argument("--json", action="store_true", help="Print JSON report")
    v.add_argument("--out", default=None, help="Write JSON report to a file")

    r = sub.add_parser(
        "release",
        help="Validate and release policy into versioned archive + current.yaml",
    )
    r.add_argument("--policy", default=DEFAULT_POLICY)
    r.add_argument(
        "--strict", action="store_true", help="Block release if warnings exist"
    )
    r.add_argument(
        "--json", action="store_true", help="Print JSON report including diff"
    )
    r.add_argument(
        "--out", default=None, help="Write JSON report (with diff) to a file"
    )
    r.add_argument(
        "--dry-run", action="store_true", help="simulate release without writing files"
    )

    rb = sub.add_parser(
        "rollback", help="Rollback current.yaml to previous or target version"
    )
    rb.add_argument(
        "--to",
        default=None,
        help="Target version (e.g., 0.1.0). If omitted, rollback to previous.",
    )

    sub.add_parser("status", help="Show current version and available releases")

    args = p.parse_args()

    if args.cmd == "validate":
        return cmd_validate(args.policy, args.json, args.out)

    if args.cmd == "release":
        return cmd_release(
            policy_path=args.policy,
            strict=args.strict,
            json_out=args.json,
            out_path=args.out,
            dry_run=args.dry_run,
        )

    if args.cmd == "rollback":
        return cmd_rollback(args.to)

    if args.cmd == "status":
        return cmd_status()

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
