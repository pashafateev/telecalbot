"""Tests for GitHub Actions workflow safety invariants."""

import tomllib
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "test.yml"
FLY_CONFIG = Path(__file__).resolve().parents[1] / "fly.toml"


def _deploy_job(workflow: str) -> str:
    return workflow.split("\n  deploy:\n", maxsplit=1)[1]


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
    assert config["http_service"]["auto_stop_machines"] == "off"
    assert config["http_service"]["auto_start_machines"] is True
    assert config["http_service"]["min_machines_running"] == 1
    assert config["http_service"]["checks"][0]["path"] == "/healthz"


def test_deploy_requires_public_fly_ingress_after_deploy():
    workflow = WORKFLOW.read_text()
    deploy_job = _deploy_job(workflow)

    deploy_command = "flyctl deploy --remote-only"
    ingress_command = "flyctl ips list --app telecalbot --json"

    assert deploy_command in deploy_job
    assert ingress_command in deploy_job
    assert deploy_job.index(ingress_command) > deploy_job.index(deploy_command)
    assert (
        'select(.Type == "shared_v4" or .Type == "v4" or .Type == "v6")' in deploy_job
    )
    assert "::error::No public ingress is allocated to telecalbot" in deploy_job
    assert "flyctl ips allocate" not in deploy_job
    assert "flyctl ips release" not in deploy_job


def test_deploy_requires_bounded_ready_response_after_deploy():
    workflow = WORKFLOW.read_text()
    deploy_job = _deploy_job(workflow)

    deploy_command = "flyctl deploy --remote-only"
    readiness_url = "https://telecalbot.fly.dev/readyz"

    assert readiness_url in deploy_job
    assert deploy_job.index(readiness_url) > deploy_job.index(deploy_command)
    assert "timeout-minutes: 7" in deploy_job
    assert "max_attempts=18" in deploy_job
    assert "retry_seconds=10" in deploy_job
    assert "--connect-timeout 5" in deploy_job
    assert "--max-time 10" in deploy_job
    assert '--write-out "%{http_code}"' in deploy_job
    assert '"$http_code" == "200"' in deploy_job
    assert "jq -e '.status == \"ready\"'" in deploy_job
    assert "sleep \"$retry_seconds\"" in deploy_job
    assert "flyctl status --app telecalbot" in deploy_job
    assert "flyctl checks list --app telecalbot" in deploy_job
    assert "::error::telecalbot did not become ready" in deploy_job
