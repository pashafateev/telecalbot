"""Tests for GitHub Actions workflow safety invariants."""

from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "test.yml"


def test_deploy_uses_pinned_flyctl_install():
    workflow = WORKFLOW.read_text()

    assert "fly.io/install.sh" not in workflow
    assert "FLYCTL_VERSION:" in workflow
    assert "FLYCTL_SHA256:" in workflow
    assert "sha256sum --check flyctl.sha256" in workflow
