import pytest
from strategy_validator.loader import load_policy
from strategy_validator.validator import validate, ValidationError


def test_policy_valid():
    policy = load_policy("policy.yaml")
    assert validate(policy) is True


def test_missing_risk():
    policy = load_policy("policy.yaml")
    del policy["risk"]
    with pytest.raises(ValidationError) as e:
        validate(policy)

    rep = e.value.report
    assert rep["ok"] is False
    # V001은 risk 섹션 누락이므로 errors 중에 V001이 포함돼야 함
    codes = [x["code"] for x in rep["errors"]]
    assert "V001" in codes
