# Changelog

Every release, newest first. Versions follow semantic versioning.

## Unreleased

- **A model on your laptop:** a "Local model" entry in the model toggle, through Ollama. No cloud, no key. `pip install -e ".[local]"`, a table in the README for which model fits your memory.
- **`aegis models --test`** (`make models`): asks every ready model one tiny question in the same fixed shape the agents use, and says ANSWERED or FAILED with the reason. `aegis models` alone says what each model is still missing.
- **The room wakes up by itself:** in live mode, `AEGIS_WATCH_EVERY` looks at the live system every few seconds and opens an incident for anything unhealthy. It stays quiet for a while after an incident (`AEGIS_WATCH_QUIET`), so a no-go is not asked again and again. The screen follows any incident it did not start itself, including ones from the alert webhook.
- **`make shop`, `make live`, `make drills`:** start the OpenTelemetry Demo shop (numbers every 15 seconds instead of every minute), run the war room against it, and run the simulated incidents next to it on port 8001 with their own audit log.
- **`.env` is read by itself.** No more `source .env` in every new terminal.
- **Fixes:** no data from the live system no longer reads as "healthy" to the verifier; "Scan the live system" says the shop is not reachable instead of a bare error; model settings keep their numbers and true / false as they are.
- **The defender blocks a change the evidence does not point at.** It was only a caution before, so a human was asked to approve it. The offline rules never proposed one, but a real 7B model did: for a bad release it proposed switching off an unrelated flag. The planner's prompt also now says to escalate releases and not to repeat a blocked plan.
- **The evidence check compares the kind of change, not just the name.** A flag plan needs a suspected flag; a release of `checkout` no longer makes a flag called `checkout` look justified. The planner is now told plainly that its plan was blocked and which rule it broke (a 7B model read the bare rule names as permission), and to keep its answers short.
- **The team hears only what the record shows.** The message for the team, and the "What was done" part of the postmortem, now come from the record, never from the model: a 7B model told the team a fix had been applied when the defender had blocked it. The model still writes the rest of the postmortem. When the defender blocked the fix, the write-up says so and why.
- **The runbook agent is told the kind of suspected change** (a release, a flag) as its own fact, so a model picks the release runbook for a bad release.
- **A new screen: the shelter.** Aegis is a glowing core with the whole crew in bays around it; every bay says in words what that agent is doing right now (asleep, standing by, working, done, blocked, your call), and beams flow while an agent works. It wakes with a roll call and greets you by name, out loud. You talk to it in your own words, typed or spoken, in one conversation that also holds the crew's reports and the go / no-go. New fonts (Oxanium, IBM Plex Sans), and it works on a phone.
- **Aegis understands plain words** (`POST /api/assistant`): a model picks one of a fixed list of commands (run a drill, scan the code, attack the defences, check the audit log, who is working, explain an agent, help), with keyword rules when there is no model. What it says about facts, like who worked and who slept, comes from the record. It can never approve or reject a fix.
- **Who is working, live:** each incident now carries the agents busy right now, and the live feed sends it, so the screen shows signals and changes working side by side.
- **Docs:** a plan for a solo hackathon day with a "before the day" list, and a demo script that works with the live shop and the simulated incidents side by side.

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
