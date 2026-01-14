# src/strategy_validator/cli.py
from __future__ import annotations
import argparse

# ✅ 구현은 cli_commands에 있지만,
# ✅ 예전 import 경로(strategy_validator.cli)를 깨지 않기 위해 재노출한다.
from .cli_commands import (
    DEFAULT_POLICY,
    POLICIES_DIR,
    RELEASES_DIR,
    CURRENT_FILE,
    HISTORY_FILE,
    _emit_json,
    cmd_validate,
    cmd_release,
    cmd_rollback,
    cmd_status,
)

__all__ = [
    "DEFAULT_POLICY",
    "POLICIES_DIR",
    "RELEASES_DIR",
    "CURRENT_FILE",
    "HISTORY_FILE",
    "_emit_json",
    "cmd_validate",
    "cmd_release",
    "cmd_rollback",
    "cmd_status",
    "main",
    "main_entry",
]


def main_entry() -> None:
    raise SystemExit(main())


def main() -> int:
    p = argparse.ArgumentParser(prog="sv", description="Strategy policy validator")
    sub = p.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("validate", help="Validate a policy file")
    v.add_argument("--policy", default=DEFAULT_POLICY)
    v.add_argument("--json", action="store_true")
    v.add_argument("--out", default=None)

    r = sub.add_parser("release", help="Validate and release policy")
    r.add_argument("--policy", default=DEFAULT_POLICY)
    r.add_argument("--strict", action="store_true")
    r.add_argument("--json", action="store_true")
    r.add_argument("--out", default=None)
    r.add_argument("--dry-run", action="store_true")

    rb = sub.add_parser("rollback", help="Rollback current.yaml")
    rb.add_argument("--to", default=None)

    sub.add_parser("status", help="Show current version and available releases")

    args = p.parse_args()

    if args.cmd == "validate":
        return cmd_validate(args.policy, args.json, args.out)
    if args.cmd == "release":
        return cmd_release(args.policy, args.strict, args.json, args.out, args.dry_run)
    if args.cmd == "rollback":
        return cmd_rollback(args.to)
    if args.cmd == "status":
        return cmd_status()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
