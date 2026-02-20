"""
Tests for PBL Guardian — Timing Checker
"""

import json
import pytest
from scripts.timing_checker import check_timing


@pytest.fixture
def sample_config():
    return {
        "class_days": ["Monday", "Saturday"],
        "timezone": "Asia/Kolkata",
        "grace_period_hours": 2,
        "milestones": [
            {"phase": "Phase 1 - Setup", "deadline": "2026-03-01"},
            {"phase": "Phase 2 - Core", "deadline": "2026-03-15"},
        ],
    }


class TestTimingChecker:
    def test_on_time_before_deadline(self, sample_config):
        # Feb 28 is a Saturday (class day), 1 day before Phase 1 deadline
        result = check_timing(sample_config, "2026-02-28T10:30:00+05:30")
        assert result["passed"] is True
        assert result["current_phase"] == "Phase 1 - Setup"
        assert result["is_class_day"] is True
        assert result["is_late"] is False

    def test_late_after_deadline(self, sample_config):
        # March 5 is well past Phase 1 deadline (March 1) but before Phase 2
        result = check_timing(sample_config, "2026-03-10T10:30:00+05:30")
        assert result["passed"] is True
        assert result["current_phase"] == "Phase 2 - Core"

    def test_way_past_all_deadlines(self, sample_config):
        # April 1 is past all deadlines
        result = check_timing(sample_config, "2026-04-01T10:30:00+05:30")
        assert result["passed"] is False
        assert result["is_late"] is True

    def test_within_grace_period(self, sample_config):
        # March 1 at 1:30 AM IST — within 2-hour grace period after midnight deadline
        result = check_timing(sample_config, "2026-03-01T01:30:00+05:30")
        assert result["passed"] is True
        assert result["is_late"] is False

    def test_not_class_day(self, sample_config):
        # Feb 25 is a Wednesday — not a class day
        result = check_timing(sample_config, "2026-02-25T10:30:00+05:30")
        assert result["is_class_day"] is False

    def test_no_milestones(self):
        config = {
            "class_days": ["Monday"],
            "timezone": "UTC",
            "milestones": [],
        }
        result = check_timing(config, "2026-03-01T10:00:00Z")
        assert result["passed"] is True
        assert result["current_phase"] is None

    def test_utc_timestamp(self, sample_config):
        result = check_timing(sample_config, "2026-02-28T05:00:00Z")
        assert result["passed"] is True
        assert "commit_day" in result
        assert "commit_local_time" in result

    def test_result_structure(self, sample_config):
        result = check_timing(sample_config, "2026-02-28T10:30:00+05:30")
        required_keys = [
            "passed", "is_class_day", "is_within_milestone", "is_late",
            "current_phase", "days_until_deadline", "commit_day",
            "commit_local_time", "status", "status_emoji", "detail",
        ]
        for key in required_keys:
            assert key in result, f"Missing key: {key}"
"""
Tests for PBL Guardian — Contribution Checker (Gini calculation)
"""

from scripts.contribution_checker import _calculate_gini


class TestGiniCoefficient:
    def test_perfect_equality(self):
        # All members contribute equally
        assert _calculate_gini([10, 10, 10, 10]) == 0.0

    def test_single_member(self):
        assert _calculate_gini([50]) == 0.0

    def test_empty_list(self):
        assert _calculate_gini([]) == 0.0

    def test_all_zeros(self):
        assert _calculate_gini([0, 0, 0]) == 0.0

    def test_total_inequality(self):
        # One person does everything
        gini = _calculate_gini([0, 0, 0, 100])
        assert gini > 0.7  # Should be high inequality

    def test_moderate_inequality(self):
        gini = _calculate_gini([5, 10, 15, 20])
        assert 0.1 < gini < 0.5  # Moderate inequality

    def test_two_members_unequal(self):
        gini = _calculate_gini([1, 9])
        assert gini > 0.3


"""
Tests for PBL Guardian — Proof Checker
"""

import os
import tempfile
from unittest.mock import patch
from scripts.proof_checker import check_proofs


class TestProofChecker:
    def test_no_proof_dir(self):
        """When proof directory doesn't exist."""
        with patch("scripts.proof_checker.subprocess.run") as mock_run:
            mock_run.return_value.stdout = ""
            mock_run.return_value.returncode = 0
            result = check_proofs(proof_dir="/nonexistent/path", commit_sha="HEAD")
            assert result["total_proofs_in_repo"] == 0

    def test_result_structure(self):
        with patch("scripts.proof_checker.subprocess.run") as mock_run:
            mock_run.return_value.stdout = ""
            mock_run.return_value.returncode = 0
            result = check_proofs(proof_dir="/nonexistent", commit_sha="HEAD")
            required_keys = [
                "passed", "has_screenshots", "has_progress_log",
                "new_proofs", "code_changed", "status", "status_emoji", "detail",
            ]
            for key in required_keys:
                assert key in result, f"Missing key: {key}"

    def test_detail_stripping_no_garbled_text(self):
        """Ensure the detail field doesn't have garbled emoji residue."""
        with patch("scripts.proof_checker.subprocess.run") as mock_run:
            mock_run.return_value.stdout = "src/main.py\nproofs/screenshot1.png\n"
            mock_run.return_value.returncode = 0

            with tempfile.TemporaryDirectory() as tmpdir:
                proof_dir = os.path.join(tmpdir, "proofs")
                os.makedirs(proof_dir)
                # Create a fake screenshot
                with open(os.path.join(proof_dir, "screenshot1.png"), "wb") as f:
                    f.write(b"fake")
                result = check_proofs(proof_dir=proof_dir, commit_sha="HEAD")
                # detail should not start with emoji characters
                assert not result["detail"].startswith("✅")
                assert not result["detail"].startswith("❌")


"""
Tests for PBL Guardian — Plagiarism Checker (L4 AI Detection, L5 Commit Patterns)
"""

import os
import tempfile
from scripts.plagiarism_checker import layer4_ai_detection, layer5_commit_patterns


class TestL4AIDetection:
    def test_no_python_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = layer4_ai_detection(tmpdir)
            assert result["passed"] is True
            assert result["ai_score"] == 0.0

    def test_simple_human_code(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Write simple, human-like code (few comments, short vars)
            with open(os.path.join(tmpdir, "main.py"), "w") as f:
                f.write("""
def add(a, b):
    return a + b

def mul(x, y):
    return x * y

def run():
    n = int(input())
    print(add(n, 5))
    print(mul(n, 3))

if __name__ == "__main__":
    run()
""")
            result = layer4_ai_detection(tmpdir)
            assert result["ai_score"] < 0.5
            assert result["passed"] is True

    def test_result_structure(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "test.py"), "w") as f:
                f.write("x = 1\n")
            result = layer4_ai_detection(tmpdir)
            assert "ai_score" in result
            assert "flags" in result
            assert "passed" in result
            assert "detail" in result


class TestL5CommitPatterns:
    def test_result_structure(self):
        result = layer5_commit_patterns()
        required_keys = ["passed", "flags", "detail", "status_emoji"]
        for key in required_keys:
            assert key in result, f"Missing key: {key}"

    def test_runs_without_crash(self):
        """Should not crash even if not in a git repo."""
        result = layer5_commit_patterns()
        assert isinstance(result["passed"], bool)


"""
Tests for PBL Guardian — Quality Checker
"""

from scripts.quality_checker import check_quality


class TestQualityChecker:
    def test_no_python_files(self):
        result = check_quality(source_dir="/nonexistent/path")
        assert result["passed"] is True
        assert result["score"] is None

    def test_non_python_language(self):
        result = check_quality(source_dir="src", language="java")
        assert result["passed"] is True
        assert "not configured" in result["detail"]

    def test_real_code(self):
        """Run on PBL Guardian's own scripts directory as a smoke test."""
        result = check_quality(
            source_dir=os.path.join(os.path.dirname(__file__), "..", "scripts")
        )
        assert "score" in result
        assert "issues" in result
        assert result["status_emoji"] in ("✅", "❌", "⚠️")

    def test_result_structure(self):
        result = check_quality(source_dir="/nonexistent")
        required_keys = ["passed", "score", "issues", "detail", "status", "status_emoji"]
        for key in required_keys:
            assert key in result, f"Missing key: {key}"
