"""The `aegis` command.

aegis serve     start the war room (screen + API) on http://localhost:8000
aegis demo      play one incident in the terminal, no browser needed
aegis scan      run the Code Guard agent over this repository
aegis drill     run the security drill
aegis audit     check that the audit log has not been edited
aegis models    list the models and what each one is missing; --test asks each ready one a tiny question

Settings in a .env file next to this repository are read first. Anything already set in the terminal wins.
"""

from __future__ import annotations

import argparse
import os
import sys
import time


def _load_env() -> None:
    """Read .env so nobody has to remember `source .env` in every new terminal."""
    from .settings import ROOT

    path = ROOT / ".env"
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
        line = line.strip().removeprefix("export ").strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        value = value.split(" #", 1)[0].strip().strip("'\"")  # drop a comment at the end of the line
        os.environ.setdefault(name.strip(), value)


def _serve(args) -> int:
    import uvicorn

    uvicorn.run("aegis.server:app", host=args.host, port=args.port)
    return 0


def _demo(args) -> int:
    os.environ.setdefault("AEGIS_PACE", "0.4")
    from . import flow, store
    from .connectors import get_connector

    store.LISTENERS.append(lambda event: print(f"  {event['agent']:>9} | {event['text']}"))
    print(f"\nScenario: {args.scenario}  (model: {args.model})\n")
    incident = flow.start(get_connector().trigger(args.scenario), args.model, wait=True)
    if incident.status == "awaiting_decision":
        answer = args.approve
        if answer == "ask":
            answer = "go" if input("\n  Your call. Type go or no-go: ").strip().lower() == "go" else "no-go"
        flow.decide(incident.id, answer, incident.gate["plan_hash"], by="you", wait=True)
    print(f"\nOutcome: {incident.status}\n\n--- message for the team ---\n{incident.result.get('stakeholder_update', '')}\n")
    return 0


def _scan(args) -> int:
    from .agents import codeguard

    report = codeguard.scan(model=args.model)
    for tool in report["tools"]:
        print(f"  {tool['tool']:<22} {'found ' + str(tool['found']) if tool['ran'] else 'COULD NOT RUN: ' + tool['problem']}")
    for finding in report["findings"]:
        print(f"  [{finding['severity']:>8}] {finding['title']}  ({finding['where']})\n             fix: {finding['fix']}")
    print(f"\n{report['summary']}")
    return 1 if codeguard.fails(report, args.fail_on) else 0


def _drill(_args) -> int:
    from .security import drill

    results = drill.run()
    for result in results:
        print(f"  {'HELD  ' if result['held'] else 'FAILED'} {result['attack']}\n         -> {result['defence']}")
    return 0 if all(r["held"] for r in results) else 1


def _audit(_args) -> int:
    from . import store

    ok, detail = store.verify_audit()
    print(f"audit log: {'intact' if ok else 'TAMPERED'} ({detail})")
    return 0 if ok else 1


def _models(args) -> int:
    """Which models are set up, and with --test, which ones really answer in the shape the agents need."""
    from pydantic import BaseModel, Field

    from .brain import Brain, models

    class Ping(BaseModel):
        ready: bool = Field(description="true")
        word: str = Field(description="the word aegis")

    failed = 0
    for entry in models():
        if not entry["ready"]:
            print(f"  NOT SET UP  {entry['label']}\n              needs: {'; '.join(entry['missing'])}")
        elif not args.test or entry["id"] == "offline":
            print(f"  READY       {entry['label']}")
        else:
            brain, started = Brain(entry["id"]), time.monotonic()
            _, who = brain.ask("Answer with ready set to true and word set to 'aegis'.", Ping, {"check": "ping"}, lambda _: None)
            took = time.monotonic() - started
            if who == entry["id"]:
                print(f"  ANSWERED    {entry['label']}  ({took:.1f} s)")
            else:
                failed += 1
                print(f"  FAILED      {entry['label']}  ({took:.1f} s)\n              {brain.last_error or brain.problem}")
    if not args.test:
        print("\nAdd --test to ask each ready model one tiny question.")
    return 1 if failed else 0


def main() -> None:
    _load_env()
    parser = argparse.ArgumentParser(prog="aegis", description="Aegis War Room")
    commands = parser.add_subparsers(dest="command", required=True)

    serve = commands.add_parser("serve", help="start the war room")
    serve.add_argument(
        "--host", default=os.getenv("AEGIS_HOST", "127.0.0.1"), help="use 0.0.0.0 only behind a login or on a trusted network"
    )
    serve.add_argument("--port", type=int, default=int(os.getenv("AEGIS_PORT", "8000")))
    serve.set_defaults(run=_serve)

    demo = commands.add_parser("demo", help="play one incident in the terminal")
    demo.add_argument("--scenario", default="payment-failure")
    demo.add_argument("--approve", choices=["ask", "go", "no-go"], default="ask")
    demo.add_argument("--model", default="offline")
    demo.set_defaults(run=_demo)

    scan = commands.add_parser("scan", help="scan this repository for security problems")
    scan.add_argument("--fail-on", choices=["low", "medium", "high", "critical"], default="medium")
    scan.add_argument("--model", default="offline")
    scan.set_defaults(run=_scan)

    commands.add_parser("drill", help="run the security drill").set_defaults(run=_drill)
    commands.add_parser("audit", help="verify the audit log").set_defaults(run=_audit)

    check = commands.add_parser("models", help="list the models; --test asks each ready one a tiny question")
    check.add_argument("--test", action="store_true")
    check.set_defaults(run=_models)

    args = parser.parse_args()
    sys.exit(args.run(args))
