from pathlib import Path
from src.cli import cmd_release
from tests.helpers import write_policy


def test_release_writes_version_report(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    p = write_policy(tmp_path, "0.9.9")
    rc = cmd_release(
        str(p),
        strict=False,
        json_out=False,
        out_path="artifacts/last.json",
        dry_run=False,
    )
    assert rc == 0

    report = Path("policies/releases/0.9.9/report.json")
    assert report.exists()
    txt = report.read_text(encoding="utf-8")
    assert '"risk_score"' in txt
