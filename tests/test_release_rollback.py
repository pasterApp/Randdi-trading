from pathlib import Path
import yaml

from strategy_validator.cli import (
    cmd_release,
    cmd_rollback,
    cmd_status,
    CURRENT_FILE,
    RELEASES_DIR,
)
from strategy_validator.loader import load_policy


def write_policy(tmp: Path, version: str) -> Path:
    policy = {
        "meta": {
            "policy_version": version,
            "author": "t",
            "market": "KRX",
            "timezone": "Asia/Seoul",
        },
        "inputs": {
            "data": {"source": "x", "timeframe": {"primary": "5m", "confirm": "20m"}},
            "indicators": [],
        },
        "entry": {
            "trigger": {"description": "x", "checklist": ["a"]},
            "invalidation": {"description": "y"},
        },
        "risk": {
            "per_trade_loss_pct": 2.0,
            "daily_loss_limit_pct": 4.0,
            "position_sizing": "fixed_fraction",
        },
        "execution": {
            "order_type": "market",
            "costs": {"fee_pct": 0.01, "slippage_pct": 0.01},
        },
        "exit": {
            "stop_loss_pct": 2.0,
            "take_profit": {"type": "trailing", "trail_pct": 1.0},
            "time_stop_bars": 10,
        },
        "failsafe": {
            "on_data_disconnect": "halt_trading",
            "on_api_error": "close_positions",
        },
    }
    fp = tmp / "policy.yaml"
    fp.write_text(
        yaml.safe_dump(policy, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    return fp


def test_release_and_rollback(tmp_path, monkeypatch):
    # 작업 디렉터리를 tmp로 바꿔서 실제 파일 시스템 오염 방지
    monkeypatch.chdir(tmp_path)

    p1 = write_policy(tmp_path, "0.1.0")
    assert cmd_release(str(p1), strict=False, json_out=False, out_path=None) == 0

    # current.yaml 버전 확인
    cur = load_policy(CURRENT_FILE)
    assert cur["meta"]["policy_version"] == "0.1.0"

    # v2 릴리즈
    p2 = write_policy(tmp_path, "0.2.0")
    assert cmd_release(str(p2), strict=False, json_out=False, out_path=None) == 0
    cur2 = load_policy(CURRENT_FILE)
    assert cur2["meta"]["policy_version"] == "0.2.0"

    # 롤백(직전으로) => 0.1.0
    assert cmd_rollback(None) == 0
    cur3 = load_policy(CURRENT_FILE)
    assert cur3["meta"]["policy_version"] == "0.1.0"

    # 특정 버전으로 롤백(to=0.2.0)
    assert cmd_rollback("0.2.0") == 0
    cur4 = load_policy(CURRENT_FILE)
    assert cur4["meta"]["policy_version"] == "0.2.0"
