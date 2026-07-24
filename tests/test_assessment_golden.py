import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "data" / "assessment" / "v1.1_bundle" / "grounded_growth_assessment_v1_1"


def test_assessment_fixture_hashes_are_unchanged():
    manifest = json.loads((ROOT / "tests/fixtures/assessment/manifest.json").read_text())
    for filename, expected_hash in manifest.items():
        actual_hash = hashlib.sha256((BUNDLE / filename).read_bytes()).hexdigest()
        assert actual_hash == expected_hash, f"{filename} changed without a golden update"


def test_browser_scoring_matches_complete_golden_result():
    node = shutil.which("node")
    if node is None:
        pytest.fail("Node.js is required for the assessment reference golden test")
    result = subprocess.run(
        [node, str(ROOT / "scripts/verify_assessment_golden.js")],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    summary = json.loads(result.stdout)
    assert summary == {
        "assessment_version": "1.1",
        "core_answers": 50,
        "lever_outputs": 37,
        "archetype_outputs": 15,
        "share_prefix": "GGA11.",
        "legacy_answers": 58,
    }
