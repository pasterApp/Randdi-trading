from pathlib import Path
from strategy_validator.cli import cmd_release
from tests.helpers import write_policy


def test_release_dryrun_does_not_write_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    p = write_policy(tmp_path, "1.0.0")
    rc = cmd_release(
        str(p),
        strict=False,
        json_out=False,
        out_path="artifacts/dryrun.json",
        dry_run=True,
    )
    assert rc == 0

    # releases 디렉터리가 생기지 않아야 함
    assert not Path("policies/releases/1.0.0").exists()

    # current.yaml도 없어야 함
    assert not Path("policies/current.yaml").exists()

    # 대신 report는 생성
    assert Path("artifacts/dryrun.json").exists()
