"""Local command doubles used by the deployment workflow subprocess tests."""

import json
import os
import sys
from pathlib import Path

command, *args = sys.argv[1:]
scenario = json.loads(Path(os.environ["DEPLOY_SCENARIO"]).read_text())
call_log = Path(os.environ["DEPLOY_CALL_LOG"])
with call_log.open("a") as stream:
    stream.write(json.dumps({"command": command, "args": args}) + "\n")

if command == "flyctl":
    if args == ["ips", "list", "--app", "telecalbot", "--json"]:
        sys.stdout.write(scenario["ingress"])
        sys.exit(scenario["fly_exit"])
    if args in (["status", "--app", "telecalbot"], ["checks", "list", "--app", "telecalbot"]):
        print("Simulated Fly diagnostics")
        sys.exit(scenario["diagnostic_exit"])
elif command == "sleep":
    # Record the requested interval without making the suite wait for it.
    sys.exit(0)
elif command == "curl":
    supported_options = {
        "--silent",
        "--show-error",
        "--output",
        "--write-out",
        "--connect-timeout",
        "--max-time",
    }
    unsupported_options = {arg for arg in args if arg.startswith("-")} - supported_options
    if unsupported_options:
        raise SystemExit(f"The curl double does not model these options: {unsupported_options}")
    calls = [json.loads(line) for line in call_log.read_text().splitlines()]
    attempt = sum(call["command"] == "curl" for call in calls) - 1
    responses = scenario["responses"]
    response = responses[min(attempt, len(responses) - 1)]
    if "body" in response:
        Path(args[args.index("--output") + 1]).write_text(response["body"])
    sys.stdout.write(response.get("http_code", "000"))
    sys.stderr.write(response.get("error", ""))
    sys.exit(response.get("exit_code", 0))

raise SystemExit(f"Unexpected deployment command: {command} {args!r}")
