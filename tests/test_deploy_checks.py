"""Execute the real workflow checks without Fly access, HTTP calls, or sleeps.

Requires Bash and jq, both available on the Ubuntu CI runner. Only safe local
utilities are exposed through PATH, and subprocesses inherit no credentials.
"""

import json
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "test.yml"
COMMAND_DOUBLE = Path(__file__).parent / "fixtures" / "deploy_command.py"
INGRESS = "Verify public ingress"
READINESS = "Verify webhook readiness"
READY = {"http_code": "200", "body": '{"status":"ready"}'}
STARTING = {"http_code": "503", "body": '{"status":"starting"}'}


@pytest.fixture
def deploy_steps():
    return yaml.safe_load(WORKFLOW.read_text())["jobs"]["deploy"]["steps"]


@pytest.fixture
def run_check(tmp_path, deploy_steps):
    commands = tmp_path / "bin"
    commands.mkdir()
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    for command in ("bash", "jq", "mktemp", "rm", "seq", "tr", "cut"):
        executable = shutil.which(command)
        assert executable, f"Deployment tests require {command} on PATH"
        (commands / command).symlink_to(executable)

    for command in ("curl", "flyctl", "sleep"):
        wrapper = commands / command
        wrapper.write_text(
            "#!/bin/sh\n"
            f"exec {shlex.quote(sys.executable)} {shlex.quote(str(COMMAND_DOUBLE))} "
            f'{command} "$@"\n'
        )
        wrapper.chmod(0o755)

    def run(name, *, ingress="[]", fly_exit=0, responses=(), diagnostic_exit=0):
        scenario = tmp_path / "scenario.json"
        scenario.write_text(
            json.dumps(
                {
                    "ingress": ingress,
                    "fly_exit": fly_exit,
                    "responses": responses,
                    "diagnostic_exit": diagnostic_exit,
                }
            )
        )
        call_log = tmp_path / "calls.jsonl"
        script = next(step["run"] for step in deploy_steps if step.get("name") == name)
        result = subprocess.run(
            [str(commands / "bash"), "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", script],
            cwd=tmp_path,
            env={
                "PATH": str(commands),
                "TMPDIR": str(scratch),
                "LC_ALL": "C",
                "DEPLOY_SCENARIO": str(scenario),
                "DEPLOY_CALL_LOG": str(call_log),
            },
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        calls = [json.loads(line) for line in call_log.read_text().splitlines()]
        assert not list(scratch.iterdir()), "Readiness response/error files were not cleaned up"
        return result, calls

    return run


def _calls(calls, command):
    return [call["args"] for call in calls if call["command"] == command]


def _assert_polling(calls, attempts):
    curl_calls = _calls(calls, "curl")
    assert len(curl_calls) == attempts
    assert _calls(calls, "sleep") == [["10"]] * (attempts - 1)
    for args in curl_calls:
        assert args[-1] == "https://telecalbot.fly.dev/readyz"
        assert args[args.index("--connect-timeout") + 1] == "5"
        assert args[args.index("--max-time") + 1] == "10"
        assert args[args.index("--write-out") + 1] == "%{http_code}"


def test_verification_steps_are_mandatory_and_ordered(deploy_steps):
    names = [step["name"] for step in deploy_steps]
    assert names.index("Deploy") < names.index(INGRESS) < names.index(READINESS)
    for step in deploy_steps:
        if step["name"] in (INGRESS, READINESS):
            assert not step.get("continue-on-error", False)
            assert "if" not in step
        if step["name"] == READINESS:
            assert step["timeout-minutes"] == 7


@pytest.mark.parametrize("ip_type", ["shared_v4", "v4", "v6"])
def test_ingress_accepts_each_public_address_type(run_check, ip_type):
    result, calls = run_check(
        INGRESS,
        ingress=json.dumps(
            [
                {"Type": "private_v6"},
                {"Type": ip_type},
            ]
        ),
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert _calls(calls, "flyctl") == [["ips", "list", "--app", "telecalbot", "--json"]]


@pytest.mark.parametrize(
    "ingress",
    [
        "[]",
        '[{"Type":"private_v6"}]',
        '[{"Type":"unknown"}]',
        '[{"type":"v4"}]',
        "[{}]",
        "null",
        "invalid json",
        "",
    ],
    ids=[
        "empty",
        "private",
        "unknown",
        "wrong-field-case",
        "missing-type",
        "null",
        "malformed",
        "no-output",
    ],
)
def test_ingress_rejects_missing_or_unreadable_public_addresses(run_check, ingress):
    result, calls = run_check(INGRESS, ingress=ingress)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "::error::No public ingress" in result.stdout
    assert _calls(calls, "flyctl") == [["ips", "list", "--app", "telecalbot", "--json"]]


def test_ingress_rejects_fly_failure_even_with_valid_output(run_check):
    result, calls = run_check(INGRESS, ingress='[{"Type":"v4"}]', fly_exit=1)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "::error::Unable to inspect public ingress" in result.stdout
    assert len(_calls(calls, "flyctl")) == 1


@pytest.mark.parametrize("attempts", [1, 2, 18])
def test_readiness_succeeds_and_stops_polling_when_ready(run_check, attempts):
    result, calls = run_check(READINESS, responses=[STARTING] * (attempts - 1) + [READY])

    assert result.returncode == 0, result.stdout + result.stderr
    assert f"Webhook service is ready (attempt {attempts}/18)" in result.stdout
    _assert_polling(calls, attempts)
    assert not _calls(calls, "flyctl")


@pytest.mark.parametrize(
    "response, message",
    [
        (STARTING, "HTTP 503"),
        ({**READY, "http_code": "503"}, "HTTP 503"),
        ({**READY, "http_code": "302"}, "HTTP 302"),
        ({"http_code": "200", "body": '{"status":"starting"}'}, "unexpected readiness payload"),
        ({"http_code": "200", "body": "{}"}, "unexpected readiness payload"),
        ({"http_code": "200", "body": "null"}, "unexpected readiness payload"),
        ({"http_code": "200", "body": "<html>error</html>"}, "unexpected readiness payload"),
        ({"http_code": "200", "body": ""}, "unexpected readiness payload"),
        ({"exit_code": 6, "error": "Could not resolve host"}, "Could not resolve host"),
        ({"exit_code": 28, "error": "Operation timed out"}, "Operation timed out"),
        ({"exit_code": 7}, "request failed without an HTTP response"),
        ({**READY, "exit_code": 28, "error": "Incomplete transfer"}, "Incomplete transfer"),
    ],
    ids=[
        "starting",
        "error-with-ready-body",
        "redirect",
        "wrong-status",
        "missing-status",
        "null",
        "malformed",
        "empty",
        "dns-failure",
        "timeout",
        "silent-failure",
        "partial-ready-response",
    ],
)
def test_readiness_fails_after_bounded_retries_with_diagnostics(run_check, response, message):
    result, calls = run_check(READINESS, responses=[response])

    assert result.returncode == 1, result.stdout + result.stderr
    assert "::error::telecalbot did not become ready after 18 attempts" in result.stdout
    assert message in result.stdout.split("Last result: ", maxsplit=1)[1]
    _assert_polling(calls, 18)
    assert _calls(calls, "flyctl") == [
        ["status", "--app", "telecalbot"],
        ["checks", "list", "--app", "telecalbot"],
    ]


def test_readiness_recovers_after_dns_failure(run_check):
    result, calls = run_check(
        READINESS,
        responses=[
            {"exit_code": 6, "error": "Could not resolve host"},
            READY,
        ],
    )

    assert result.returncode == 0, result.stdout + result.stderr
    _assert_polling(calls, 2)
    assert not _calls(calls, "flyctl")


def test_readiness_reports_exhaustion_even_when_diagnostics_fail(run_check):
    result, calls = run_check(READINESS, responses=[STARTING], diagnostic_exit=1)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "::error::telecalbot did not become ready" in result.stdout
    _assert_polling(calls, 18)
    assert _calls(calls, "flyctl") == [
        ["status", "--app", "telecalbot"],
        ["checks", "list", "--app", "telecalbot"],
    ]
