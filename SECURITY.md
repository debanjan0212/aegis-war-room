# Security

## Reporting a problem

Email **itsme.deb1995@gmail.com** with what you found and how to reproduce it.
Please do not open a public issue for anything exploitable.

## What the agents are allowed to do

The rules are in code and in [`config/policy.yaml`](config/policy.yaml), not in a prompt. A prompt can be argued with; these cannot.

- The planner can only choose an action that the policy file has enabled. Out of the box: switch a listed failure flag **off**, or escalate to a human. It cannot switch a flag on, and it cannot name an action that is not on the list.
- The defender checks every plan with fixed rules before a human is asked. It does not use an AI model.
- The executor needs three things before it acts: a human "go", a fingerprint that matches the exact plan the human saw, and a second pass of the policy checks.
- A blocked plan gets one retry. Blocked twice, the incident goes to a human and nothing is changed.
- Investigating agents only read. Only the executor can change anything.
- Text from logs and alerts is scanned for instructions aimed at an AI. Flagged lines are quarantined: shown on screen, kept out of every prompt.
- Service and flag names are validated before they are placed in a query or a file edit.
- Every agent message and every decision is written to an audit log. Each line carries the hash of the line before it, so an edited or deleted line breaks the chain (`aegis audit`).
- Agent output is shown as plain text, never as HTML.

`aegis drill` (or the Security panel on screen) throws eight real attacks at these defences and reports each one as held or failed. CI runs it on every change.

## How this maps to the OWASP Top 10 for Agentic Applications (2026)

| Risk | What Aegis does about it |
|---|---|
| ASI01 Agent Goal Hijack | Log and alert text is quarantined when it reads like instructions; the model is told the data is untrusted; the action list and the human go hold even if the filter misses |
| ASI02 Tool Misuse and Exploitation | One action per incident, from an allowlist, with allowed targets and values per action |
| ASI03 Identity and Privilege Abuse | Only the executor can act; investigators are read-only. **Gap:** agents do not yet have separate credentials |
| ASI04 Agentic Supply Chain Vulnerabilities | Hash-locked Python dependencies, npm lockfile, actions pinned to commits, weekly scans, Dependabot. No LiteLLM in the dependency tree |
| ASI05 Unexpected Code Execution | No agent writes or runs code. Actions are fixed functions with validated arguments |
| ASI06 Memory and Context Poisoning | No long-term agent memory. Each incident starts clean. Runbooks come from this repository only |
| ASI07 Insecure Inter-Agent Communication | Agents run in one process and pass typed data, not free text commands. **Gap:** this changes if agents move to separate services |
| ASI08 Cascading Failures | One retry after a block, then stop. A failing model falls back to offline rules. A failing scanner fails the scan instead of passing silently |
| ASI09 Human-Agent Trust Exploitation | The human sees the root cause, the checks, the undo step and any attack attempt before deciding. Voice "go" needs a spoken "confirm" |
| ASI10 Rogue Agents | Every step is in the tamper-evident audit log; the executor refuses anything without a matching approval |

## What is checked on every change

[`.github/workflows/security.yml`](.github/workflows/security.yml) runs on every push to `main` or `develop`, every pull request and once a week:

| Check | Tool | Fails the run when |
|---|---|---|
| Python code | Bandit (inside the Code Guard agent) | any medium or high finding |
| Python dependencies, core and cloud | pip-audit against the hash-locked files | any known vulnerability |
| JavaScript dependencies | npm audit | any medium or worse |
| Secrets in the working tree | Code Guard's built-in patterns | any match |
| Secrets in the full Git history | gitleaks | any match |
| Pipeline | Code Guard's pin check | any action not pinned to a commit SHA |
| Dependencies, secrets, Dockerfile config | Trivy | anything high or critical with a fix |
| Static analysis, Python and TypeScript | CodeQL, `security-extended` | results appear in the Security tab |

The Code Guard agent runs the first five from one command, `aegis scan`, so the screen, your terminal and CI share one definition of "clean". A scanner that cannot run counts as a failure, never as a pass.

Fixes: Dependabot opens a pull request for every dependency, base image and pinned action that has an update. Code Guard prints the fix next to each finding.

Suppressions are rare and each one says why: three `# nosec` comments in [`aegis/agents/codeguard.py`](aegis/agents/codeguard.py), where the agent starts the scanners with fixed command lists.

## Turn these on in the GitHub repository settings

They are free on public repositories and take a minute:

1. **Branch protection on `main` and `develop`:** require a pull request, one approval, review from code owners, and the `ci` and `security` checks to pass.
2. **Dependabot alerts** and **Dependabot security updates.**
3. **Secret scanning** with **push protection**, so a key is stopped before it lands.
4. **Private vulnerability reporting.**

## Voices

A cloned voice is a recording of a real person. The loader refuses any cloned voice whose `voice.yaml` has no consent line written by the speaker, and `.gitignore` keeps every personal voice folder out of Git. Do not add a voice of anyone who has not recorded it for this purpose themselves.

## What is not covered yet

- No login and no roles. The server listens on `127.0.0.1` by default. Set `AEGIS_API_TOKEN` before exposing it, and put a real login in front before using it on a shared network.
- The injection filter is pattern matching. It will miss clever wording. The allowlist, the defender and the human go are what hold when it does.
- The audit log proves that lines were not edited. It does not stop someone deleting the whole file; ship it to a log system for that.
- Cloud model calls send incident data (metrics, log lines, change history) to the provider you choose. Quarantined lines are never sent.
- Base images are pinned by tag, not by digest.
