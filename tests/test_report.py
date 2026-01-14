from strategy_validator.loader import load_policy
from strategy_validator.validator import validate_report


def test_report_ok_has_version():
    policy = load_policy("policy.yaml")
    rep = validate_report(policy)
    assert "ok" in rep and "summary" in rep
    assert rep["version"] == policy["meta"]["policy_version"]
