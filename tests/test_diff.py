from src.diff import diff_policies


def test_risk_score_increases():
    old = {
        "risk": {"per_trade_loss_pct": 1.0},
        "execution": {"costs": {"fee_pct": 0.01, "slippage_pct": 0.01}},
        "exit": {"stop_loss_pct": 1.0},
        "inputs": {"data": {"timeframe": {"primary": "5m"}}},
    }
    new = {
        "risk": {"per_trade_loss_pct": 2.0},
        "execution": {"costs": {"fee_pct": 0.01, "slippage_pct": 0.01}},
        "exit": {"stop_loss_pct": 1.0},
        "inputs": {"data": {"timeframe": {"primary": "5m"}}},
    }
    d = diff_policies(old, new)
    assert d["risk_score"] >= 10


def test_risk_increase_flag():
    old = {
        "risk": {"per_trade_loss_pct": 1.0, "daily_loss_limit_pct": 2.0},
        "exit": {"stop_loss_pct": 1.0},
        "execution": {"costs": {"fee_pct": 0.01, "slippage_pct": 0.01}},
        "inputs": {"data": {"timeframe": {"primary": "5m"}}},
    }
    new = {
        "risk": {"per_trade_loss_pct": 2.0, "daily_loss_limit_pct": 2.0},
        "exit": {"stop_loss_pct": 1.5},
        "execution": {"costs": {"fee_pct": 0.01, "slippage_pct": 0.01}},
        "inputs": {"data": {"timeframe": {"primary": "5m"}}},
    }
    d = diff_policies(old, new)
    levels = [f["level"] for f in d["risk_flags"]]
    assert "WARN" in levels
