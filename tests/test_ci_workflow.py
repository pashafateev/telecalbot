"""Tests for GitHub Actions workflow safety invariants."""

import tomllib
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "test.yml"
FLY_CONFIG = Path(__file__).resolve().parents[1] / "fly.toml"


def test_deploy_uses_pinned_flyctl_install():
    workflow = WORKFLOW.read_text()

    assert "fly.io/install.sh" not in workflow
    assert "FLYCTL_VERSION:" in workflow
    assert "FLYCTL_SHA256:" in workflow
    assert "sha256sum --check flyctl.sha256" in workflow


def test_fly_uses_webhook_http_delivery():
    config = tomllib.loads(FLY_CONFIG.read_text())

    assert config["env"]["TELEGRAM_DELIVERY_MODE"] == "webhook"
    assert config["env"]["TELEGRAM_WEBHOOK_PATH"] == "/telegram/webhook"
    assert config["http_service"]["internal_port"] == 8080
    assert config["http_service"]["auto_stop_machines"] == "stop"
    assert config["http_service"]["auto_start_machines"] is True
    assert config["http_service"]["min_machines_running"] == 0
    assert config["http_service"]["checks"][0]["path"] == "/healthz"
