"""Small Telegram/Cal.com HTTP fake shared by journey and container tests.

This module uses only the standard library so the production image can run it
as a separate service. Unknown endpoints fail closed and appear in /__state.
"""

import argparse
import copy
import json
import threading
from collections import deque
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

BOT = {"id": 9000, "is_bot": True, "first_name": "Telecalbot", "username": "telecalbot_test_bot"}


class FakeServices:
    def __init__(self):
        self.requests = []
        self.messages = []
        self.unexpected_requests = []
        self.booking_failures = deque()
        self.lock = threading.Lock()
        future_day = (datetime.now(timezone.utc) + timedelta(days=2)).date()
        self.slots = [f"{future_day}T10:00:00+03:00", f"{future_day}T11:00:00+03:00"]
        self.bookings = []

    def snapshot(self):
        with self.lock:
            return copy.deepcopy({
                "requests": self.requests,
                "messages": self.messages,
                "unexpected_requests": self.unexpected_requests,
            })

    def respond(self, method, path, query, body):
        with self.lock:
            request = {"method": method, "path": path, "query": query, "body": body}
            self.requests.append(request)
            if method == "POST" and path.startswith("/bot"):
                result = self._telegram(path.rsplit("/", 1)[-1], body)
                if result is not None:
                    return 200, {"ok": True, "result": result}
            if method == "GET" and path == "/v2/slots":
                return 200, {"status": "success", "data": {
                    self.slots[0][:10]: [{"start": slot} for slot in self.slots]
                }}
            if method == "POST" and path == "/v2/bookings":
                if self.booking_failures:
                    return self.booking_failures.popleft()
                booking_id = 700 + len(self.bookings)
                start = datetime.fromisoformat(body["start"].replace("Z", "+00:00"))
                result = {
                    "id": booking_id, "uid": f"local-booking-{booking_id}",
                    "title": "Test meeting", "start": body["start"],
                    "end": (start + timedelta(minutes=body.get("lengthInMinutes", 30))).isoformat(),
                    "status": "accepted",
                }
                self.bookings.append(result)
                return 201, {"status": "success", "data": result}
            if method == "POST" and any(
                path == f"/v2/bookings/{booking['uid']}/cancel" for booking in self.bookings
            ):
                return 200, {"status": "success", "data": {}}
            self.unexpected_requests.append(request)
            return 500, {"error": "Unexpected fake-service request", "path": path}

    def _telegram(self, method, body):
        if method == "getMe":
            return BOT
        if method in {"setMyCommands", "setWebhook", "answerCallbackQuery"}:
            return True
        if method in {"sendMessage", "editMessageText"}:
            message = {
                "message_id": int(body.get("message_id", len(self.messages) + 1000)),
                "date": 1_800_000_000,
                "chat": {"id": int(body["chat_id"]), "type": "private"},
                "from": BOT, "text": body["text"],
            }
            if body.get("reply_markup"):
                markup = body["reply_markup"]
                message["reply_markup"] = json.loads(markup) if isinstance(markup, str) else markup
            self.messages.append(message)
            return message
        return None


class FakeServer:
    def __init__(self, host="127.0.0.1", port=0):
        self.services = FakeServices()
        services = self.services

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                self._respond()

            def do_POST(self):
                self._respond()

            def _respond(self):
                parsed = urlsplit(self.path)
                if self.command == "GET" and parsed.path == "/__state":
                    status, payload = 200, services.snapshot()
                else:
                    raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                    if self.headers.get("Content-Type", "").startswith("application/json"):
                        body = json.loads(raw) if raw else {}
                    else:
                        body = {key: values[0] for key, values in parse_qs(raw.decode()).items()}
                    status, payload = services.respond(
                        self.command, parsed.path, parse_qs(parsed.query), body,
                    )
                encoded = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

        self.server = ThreadingHTTPServer((host, port), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.url = f"http://{host}:{self.server.server_port}"

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        assert not self.thread.is_alive(), "Fake HTTP server did not stop"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8081)
    args = parser.parse_args()
    server = FakeServer(args.host, args.port)
    server.server.serve_forever()
