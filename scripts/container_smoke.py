"""Run the image's default entrypoint with local HTTP fakes on an internal network.

Usage: python3 scripts/container_smoke.py --image telecalbot:ci
Requires a built image and Docker; the probe itself uses only the standard library.
"""

import argparse
import json
import signal
import subprocess
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

TOKEN = "123456:integration-test"
SECRET = "container-smoke-secret"
ADMIN_ID = 10001
USER = {"id": ADMIN_ID, "is_bot": False, "first_name": "Smoke"}
HTTP = build_opener(ProxyHandler({}))


def request(url, payload=None, secret=None):
    headers = {"Content-Type": "application/json"}
    if secret is not None:
        headers["X-Telegram-Bot-Api-Secret-Token"] = secret
    data = json.dumps(payload).encode() if payload is not None else None
    try:
        with HTTP.open(Request(url, data=data, headers=headers), timeout=1) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        return error.code, None


def wait_for(description, check, timeout=10):
    deadline = time.monotonic() + timeout
    last_error = None
    while time.monotonic() < deadline:
        try:
            value = check()
            if value:
                return value
        except (URLError, TimeoutError, ConnectionError) as error:
            last_error = error
        time.sleep(0.1)
    raise AssertionError(f"Timed out waiting for {description}; last error: {last_error}")


def wait_for_fakes(fake_url):
    wait_for("local fake service", lambda: request(f"{fake_url}/__state")[0] == 200)


def probe(app_url, fake_url):
    """Exercise real HTTP ingress, command/callback routing, and Cal.com availability."""
    wait_for_fakes(fake_url)
    wait_for(
        "application readiness",
        lambda: request(f"{app_url}/readyz") == (200, {"status": "ready"}),
        timeout=35,
    )
    assert request(f"{app_url}/healthz") == (200, {"status": "ok"})
    update_id = 0

    def command(text):
        return {"message": {
            "message_id": update_id + 1, "date": int(time.time()),
            "chat": {"id": ADMIN_ID, "type": "private"}, "from": USER, "text": text,
            "entities": [{"type": "bot_command", "offset": 0, "length": len(text)}],
        }}

    def send(payload, secret=SECRET, expected=200):
        nonlocal update_id
        update_id += 1
        status, body = request(
            f"{app_url}/telegram/webhook", {"update_id": update_id, **payload}, secret,
        )
        assert status == expected, f"Webhook returned {status}, expected {expected}"
        if expected == 200:
            assert body == {"status": "accepted"}

    def state():
        status, body = request(f"{fake_url}/__state")
        assert status == 200
        return body

    def button_message(prefix):
        for message in reversed(state()["messages"]):
            for row in message.get("reply_markup", {}).get("inline_keyboard", []):
                for button in row:
                    if button.get("callback_data", "").startswith(prefix):
                        return message, button["callback_data"]
        return None

    def click(prefix):
        message, data = wait_for(f"{prefix} button", lambda: button_message(prefix))
        send({"callback_query": {
            "id": f"smoke-{update_id + 1}", "chat_instance": "smoke-chat", "from": USER,
            "message": message, "data": data,
        }})

    # An accepted HTTP response alone does not prove the queue or handlers work.
    send(command("/start"), secret=None, expected=403)
    send(command("/start"), secret="wrong-secret", expected=403)
    send(command("/start"))
    wait_for(
        "admin welcome and help responses",
        lambda: len(state()["messages"]) >= 2,
    )
    messages = state()["messages"]
    assert len(messages) == 2, "Unauthenticated updates reached a handler"
    assert all(message["chat"]["id"] == ADMIN_ID for message in messages)
    assert "Добро пожаловать, Smoke!" in messages[0]["text"]
    assert "/book" in messages[1]["text"]

    # /start has to migrate/write SQLite for admin access before /book can proceed.
    send(command("/book"))
    click("tz:")
    click("duration:30")
    wait_for("available slot buttons", lambda: button_message("slot:"))
    snapshot = state()
    assert not snapshot["unexpected_requests"], snapshot["unexpected_requests"]
    slots = [req for req in snapshot["requests"] if req["path"] == "/v2/slots"]
    assert len(slots) == 1, f"Expected one Cal.com availability request, got {slots}"
    assert slots[0]["method"] == "GET"
    assert slots[0]["query"]["eventTypeId"] == ["99"]
    registrations = [
        req for req in snapshot["requests"] if req["path"].endswith("/setWebhook")
    ]
    assert len(registrations) == 1
    assert registrations[0]["body"]["secret_token"] == SECRET
    assert registrations[0]["body"]["url"] == "https://smoke.invalid/telegram/webhook"
    print("container-smoke: ready, authenticated webhook routed, Cal.com slots rendered", flush=True)


def docker(*args, timeout=30, check=True):
    result = subprocess.run(
        ["docker", *args], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        timeout=timeout, check=False,
    )
    if check and result.returncode:
        raise RuntimeError(f"docker {' '.join(args)} failed:\n{result.stdout}")
    return result


def run_container_smoke(image):
    root = Path(__file__).resolve().parents[1]
    suffix = uuid.uuid4().hex[:10]
    network = f"telecalbot-smoke-{suffix}"
    app = f"{network}-app"
    fake = f"{network}-fake"

    try:
        # No container in this test can reach Telegram, Cal.com, or the public internet.
        docker("network", "create", "--internal", network)
        docker(
            "run", "--detach", "--name", fake, "--network", network,
            "--network-alias", "fake-services",
            "--mount", f"type=bind,src={root / 'tests/integration/fakes.py'},dst=/smoke/fakes.py,readonly",
            "--mount", f"type=bind,src={Path(__file__).resolve()},dst=/smoke/container_smoke.py,readonly",
            image, "/app/.venv/bin/python", "/smoke/fakes.py", "--host", "0.0.0.0",
        )
        docker(
            "exec", fake, "/app/.venv/bin/python", "/smoke/container_smoke.py", "--wait-for-fakes",
        )
        environment = {
            "TELEGRAM_BOT_TOKEN": TOKEN,
            "TELEGRAM_API_BASE_URL": "http://fake-services:8081/bot",
            "CALCOM_API_KEY": "integration-calcom-key",
            "CALCOM_API_BASE_URL": "http://fake-services:8081/v2",
            "CALCOM_EVENT_TYPE_ID": "99",
            "ADMIN_TELEGRAM_ID": str(ADMIN_ID),
            "DATABASE_PATH": "/tmp/telecalbot-smoke.db",
            "TELEGRAM_DELIVERY_MODE": "webhook",
            "TELEGRAM_WEBHOOK_URL": "https://smoke.invalid/telegram/webhook",
            "TELEGRAM_WEBHOOK_SECRET_TOKEN": SECRET,
        }
        env_args = [arg for key, value in environment.items() for arg in ("--env", f"{key}={value}")]
        # Deliberately supply no command or entrypoint override for the application.
        docker(
            "run", "--detach", "--name", app, "--network", network,
            "--network-alias", "telecalbot", *env_args, image,
        )
        result = docker(
            "exec", fake, "/app/.venv/bin/python", "/smoke/container_smoke.py", "--probe",
            timeout=90,
        )
        print(result.stdout, end="")
        docker("stop", "--time", "10", app, timeout=20)
        status = json.loads(docker("inspect", "--format", "{{json .State}}", app).stdout)
        assert not status["Running"] and status["ExitCode"] == 0, status
        assert not status["OOMKilled"] and not status["Error"], status
        print("container-smoke: SIGTERM shutdown exited cleanly with code 0", flush=True)
    except BaseException:
        for name in (app, fake):
            print(f"--- {name} logs ---", flush=True)
            print(docker("logs", "--tail", "100", name, check=False).stdout, flush=True)
        raise
    finally:
        docker("rm", "--force", app, fake, check=False)
        docker("network", "rm", network, check=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="telecalbot:ci")
    parser.add_argument("--probe", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--wait-for-fakes", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--app-url", default="http://telecalbot:8080", help=argparse.SUPPRESS)
    parser.add_argument("--fake-url", default="http://127.0.0.1:8081", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.wait_for_fakes:
        wait_for_fakes(args.fake_url)
    elif args.probe:
        probe(args.app_url, args.fake_url)
    else:
        def stop(signum, frame):
            raise SystemExit(128 + signum)

        signal.signal(signal.SIGTERM, stop)
        run_container_smoke(args.image)


if __name__ == "__main__":
    main()
