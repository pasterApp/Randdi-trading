from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

from .diff import diff_policies
from .gate import apply_gate
from .loader import load_policy
from .validator import validate_report

DEFAULT_POLICY = "policy.yaml"
POLICIES_DIR = "policies"
RELEASES_DIR = "policies/releases"
CURRENT_FILE = "policies/current.yaml"
HISTORY_FILE = "policies/history.log"


def _emit_json(obj: dict, json_out: bool, out_path: str | None) -> None:
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
    dry_run: bool = False,
) -> int:
    _ensure_dirs()

    policy = load_policy(policy_path)
    rep = validate_report(policy)

    # 0) validator ERROR 차단
    if not rep["ok"]:
        _emit_json(rep, json_out=json_out, out_path=out_path)
        if not json_out:
            print(json.dumps(rep, ensure_ascii=False, indent=2))
        print("RELEASE BLOCKED: errors present")
        return 2

    # 1) validator strict: WARN 차단
    if strict and rep["summary"]["warnings"] > 0:
        _emit_json(rep, json_out=json_out, out_path=out_path)
        print("RELEASE BLOCKED: strict mode and validator warnings present")
        return 2

    # 2) diff + gate
    prev = load_policy(CURRENT_FILE) if Path(CURRENT_FILE).exists() else None
    diff = diff_policies(prev, policy)

    policy_gate = (policy.get("release") or {}).get("gate")
    gate_result = apply_gate(diff, policy_gate)

    rep_with_diff = dict(rep)
    rep_with_diff["diff"] = diff
    rep_with_diff["gate"] = gate_result

    if not gate_result["allowed"]:
        _emit_json(rep_with_diff, json_out=json_out, out_path=out_path)
        print("RELEASE BLOCKED BY GATE")
        for r in gate_result["reasons"]:
            print(f"  - {r}")
        return 2

    # 3) dry-run
    if dry_run:
        rep_with_diff["dry_run"] = True
        _emit_json(rep_with_diff, json_out=json_out, out_path=out_path)
        print("DRY-RUN OK: no files were written")
        return 0

    # 4) 텍스트 요약
    if diff["added"] or diff["removed"] or diff["changed"]:
        print("DIFF SUMMARY:")
        if diff["added"]:
            print(f"  added: {len(diff['added'])}")
        if diff["removed"]:
            print(f"  removed: {len(diff['removed'])}")
        if diff["changed"]:
            print(f"  changed: {len(diff['changed'])}")

    # risk flags
    if diff["risk_flags"]:
        print("RISK FLAGS:")
        for rf in diff["risk_flags"]:
            print(f"  [{rf['level']}] {rf['path']} - {rf['reason']}")
        print(f"RISK SCORE: {diff['risk_score']}")

        has_error = any(rf["level"] == "ERROR" for rf in diff["risk_flags"])
        if has_error:
            _emit_json(rep_with_diff, json_out=json_out, out_path=out_path)
            print("RELEASE BLOCKED: risk ERROR detected")
            return 2

        if strict and diff["risk_score"] > 0:
            _emit_json(rep_with_diff, json_out=json_out, out_path=out_path)
            print("RELEASE BLOCKED: strict mode and risk flags present")
            return 2

    # 5) version 확인
    version = (policy.get("meta") or {}).get("policy_version")
    if not version:
        _emit_json(rep_with_diff, json_out=json_out, out_path=out_path)
        print("RELEASE BLOCKED: meta.policy_version missing")
        return 2

    # 6) 버전 중복 차단
    dest_dir = Path(RELEASES_DIR) / version
    dest_file = dest_dir / "policy.yaml"
    if dest_file.exists():
        _emit_json(rep_with_diff, json_out=json_out, out_path=out_path)
        print(f"RELEASE BLOCKED: version already exists: {version}")
        return 2

    # 7) 릴리즈 확정(쓰기)
    dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(policy_path, dest_file)

    # releases/<ver>/report.json: “릴리즈 증빙”은 여기서 1번만 저장
    report_file = dest_dir / "report.json"
    report_file.write_text(
        json.dumps(rep_with_diff, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # current.yaml 갱신
    Path(POLICIES_DIR).mkdir(parents=True, exist_ok=True)
    shutil.copy2(dest_file, Path(CURRENT_FILE))

    # history.log
    ts = datetime.now().isoformat(timespec="seconds")
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(f"{ts}\trelease\t{version}\tfrom={policy_path}\n")

    print(f"RELEASED: {version}")

    # 최신 실행 결과(handoff)
    _emit_json(rep_with_diff, json_out=json_out, out_path=out_path)
    return 0


def cmd_rollback(target_version: str | None) -> int:
    _ensure_dirs()

    versions = _list_versions()
    if not versions:
        print("ROLLBACK FAILED: no releases found")
        return 2

    current_ver = _read_current_version()

    # target 결정
    if target_version is None:
        if current_ver in versions:
            idx = versions.index(current_ver)
            if idx == 0:
                print("ROLLBACK FAILED: already at oldest version")
                return 2
            target = versions[idx - 1]
        else:
            target = versions[-1]
    else:
        target = target_version
        if target not in versions:
            print(f"ROLLBACK FAILED: target version not found: {target}")
            return 2

    # 실제 롤백
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
