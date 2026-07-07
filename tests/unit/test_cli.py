"""CLI smoke test — offline, stub backend, JSON output ordered verdict-first."""

from __future__ import annotations

import json

from prooflens.__main__ import main
from tests.helpers import IMAGES_DIR


def test_cli_scores_and_prints_json(capsys):
    rc = main(["score", str(IMAGES_DIR / "meeting.jpg")])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["band"] == "Clear"
    assert "reason" in out and out["rubric_version"] == "v2"
    # first structural key after image path is the decision-driver band
    assert list(out.keys())[:3] == ["image", "band", "score"]


def test_cli_missing_file_errors(capsys):
    rc = main(["score", "/no/such/image.jpg"])
    assert rc == 2
    assert "not found" in capsys.readouterr().err
