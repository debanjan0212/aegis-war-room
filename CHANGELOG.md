# Changelog

Every release, newest first. Versions follow semantic versioning.

## 0.1.0 (16 November 2026)

The first working version.

- **Incident flow:** nine agents (triage, signals, changes, runbook, planner, defender, executor, verifier, scribe) and a human go / no-go, built on LangGraph.
- **Defender:** an allowlist of actions, a filter that quarantines log lines aimed at the AI, a fingerprint that ties the approval to the exact plan, and a tamper-evident audit log.
- **Code Guard agent:** scans the repository with Bandit, pip-audit, npm audit, a secret scan and a check that pipeline actions are pinned.
- **Security drill:** eight attacks on the defences, run from the screen, the terminal and CI.
- **War room screen:** stations that report in, the conversation as strips, the go / no-go desk, the defender's corner.
- **Voice:** a spoken briefing written for the ear, and "go", "confirm", "no-go" and "brief me" by voice. Voices come from the `voices/` folder.
- **Model toggle:** offline rules by default; Azure OpenAI, AWS Bedrock and Google Vertex AI from `config/models.yaml`.
- **Connectors:** a built-in simulator with three incidents, and a first connector for the OpenTelemetry Demo.
- **Pipelines:** `ci` and `security` workflows with every action pinned to a commit, hash-locked dependencies, Dependabot.
- **Documents:** the hackathon plan, the architecture, the long-term roadmap and the build blueprint.

Not in this release: real model calls have not been proven, live mode has not been run against a live shop, there is no login, and voice cloning is not installed. See "What is not done yet" in the README.
