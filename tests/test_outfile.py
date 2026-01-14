from pathlib import Path
from strategy_validator.cli import _emit_json


def test_emit_json_writes_file(tmp_path):
    out = tmp_path / "r.json"
    _emit_json({"ok": True}, json_out=False, out_path=str(out))
    assert out.exists()
    assert "ok" in out.read_text(encoding="utf-8")
