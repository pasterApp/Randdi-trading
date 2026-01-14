from pathlib import Path


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
