"""The `aegis` command.

aegis serve     start the war room (screen + API) on http://localhost:8000
aegis demo      play one incident in the terminal, no browser needed
aegis scan      run the Code Guard agent over this repository
aegis drill     run the security drill
aegis audit     check that the audit log has not been edited
"""

from __future__ import annotations

import argparse
import os
import sys


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


def main() -> None:
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

    args = parser.parse_args()
    sys.exit(args.run(args))
