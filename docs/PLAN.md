# The plan

Where the project stands, what to do on hackathon day, and how it grows into something you can show clients.

## Where it stands

| Piece | State | How it was checked |
|---|---|---|
| Incident flow: nine agents and a human go / no-go | Working | 48 automated tests, three scenarios played end to end |
| Defender: policy, injection filter, plan fingerprint, audit chain | Working | `aegis drill`: eight attacks, all held |
| Code Guard agent | Working | Run on this repository: Bandit, pip-audit, npm audit, secrets, pin check all clean |
| War room screen | Working | Driven through a full incident in Chrome, desktop and phone size |
| Voice | Partly tested | The briefing is written for the ear and tested. 18 spoken phrases map to the right command. Not yet tried with a real microphone and speaker. Listening uses the browser's speech service, which needs internet |
| Model toggle | Laptop model working; clouds wired | `qwen2.5:7b` through Ollama on an M4 Pro: answers in about 1.4 seconds and played all three scenarios. It once proposed switching off an unrelated flag for a bad release; the defender now blocks that. Azure and Bedrock clients build; no cloud call made yet. `aegis models --test` checks each one in seconds |
| Live mode (OpenTelemetry Demo) | Wired | `make shop` and `make live`. Watches by itself and opens incidents. Played end to end, in Chrome, against a stand-in Prometheus and a real flag file: broke the flag, the room woke up, go, flag off, recovered. Not yet run against the live shop |
| Container image | Working | CI builds it, starts it and plays an incident inside it up to the go / no-go |
| Voice cloning | Not started | Folder layout, menu and consent check are in place |

## Before the day

Do these at home, on good Wi-Fi. None of them should eat hackathon hours.

1. Merge the `release/0.1.0` pull request into `main`, so the repository link shows the code.
2. `make install`, then `pip install -e ".[cloud]"`.
3. `make shop` once. It downloads the shop's images, several GB. Then `make shop-stop`.
4. Install Ollama and pull the model for your memory (README, step 4). Put `OLLAMA_MODEL` and `AEGIS_MODEL=local` in `.env`.
5. Sort out access to one cloud and put it in `.env`.
6. `make models`. Every model you plan to show must say ANSWERED.
7. Ask the organisers about the venue Wi-Fi. Voice listening needs internet; the buttons do not.

## Hackathon day: 24 hours, solo

The skeleton exists, so the day goes on proving what only works live. Real models come first: they are what makes this agentic AI, and they depend on access you do not control.

| Hours | Do | Done when |
|---|---|---|
| 0 to 1 | `make check`, `make models`, `make serve`. Play the three scenarios offline | All green |
| 1 to 4 | **Real models.** The laptop model and your one cloud. `aegis demo --model local --approve go` for each scenario, then the same with the cloud. Fix prompts where a model's answer is worse than the offline rules | Three scenarios pass on both. Every strip says which model answered |
| 4 to 8 | **The live shop.** `make shop`, then `make live`. Break `paymentFailure` at http://localhost:8080/feature. If the flag service does not notice the file change (possible on Docker Desktop), switch `otel_demo.py` to the flag page's API | The room wakes up by itself, go switches the real flag off, the verifier sees the real recovery |
| | **Hard stop at hour 8.** If the shop is not working, drop it: demo on the simulator with the real model, and say so | |
| 8 to 10 | **Voice**, in the room you will present in: microphone, speaker, Wi-Fi. Tune `voices/butler/voice.yaml` | The briefing is audible; "no-go" and "go, confirm" work from where you stand |
| 10 to 12 | Polish what judges see: scenario wording, the postmortem, the team message | You would be happy to screenshot any moment |
| 12 to 13 | `make check` and the Security panel. Fix anything found. Push | CI and security workflows green |
| 13 to 18 | **Sleep.** | A tired solo presenter loses more marks than any missing feature |
| 18 to 22 | Rehearse three times with a timer, both tabs (below). Record a backup video | A full run fits in about five minutes |
| 22 to 24 | Stop changing code. This is the buffer for surprises | |

**Cut from the start, because you are solo:** a second cloud (keep it only if it already says ANSWERED), live logs, voice cloning. **Never cut:** one real model, the rehearsal, the backup video.

## The five-minute demo

Two tabs, because the live shop and the simulated incidents run as two copies of Aegis:

- **Tab 1, live:** `make shop`, then `make live`. http://localhost:8000
- **Tab 2, drills:** `make drills`. http://localhost:8001. Its own audit log, so the two never mix

Have Grafana open at http://localhost:8080/grafana/ and the flag page at http://localhost:8080/feature.

1. **Break it first (20 seconds).** Set `paymentFailure` to 50% on the flag page. The numbers take about a minute to move, so talk while they do.
2. **The promise (40 seconds).** "Agents investigate. A defender checks. A human decides. Only then is anything changed." Show Grafana turning red.
3. **The room wakes up by itself (60 seconds).** Nobody pressed anything. Stations report in one by one. Point at Changes: it found the real flag. Point at a strip: it says which model answered, on this laptop.
4. **Your call (45 seconds).** The voice briefs you. Say "go", then "confirm". Mention: stopping takes one word, acting takes two.
5. **While the shop recovers (45 seconds), tab 2.** Play "Customers cannot pay". Open the amber Signals strip: a log line tried to give the AI orders and was quarantined.
6. **Proof (20 seconds), tab 1.** The verifier shows recovery. Grafana goes green. Open the message for the team.
7. **Restraint (30 seconds), tab 2.** Play "A release broke checkout". Aegis finds the cause, is not allowed to roll back, and hands over without touching anything.
8. **Defender's corner (30 seconds).** Run the drill: eight attacks, eight held.
9. **The toggle (20 seconds), tab 2.** Switch the model menu to your cloud and start an incident. Each strip says which model answered.

## Voice cloning: the next step

When the recording arrives:

1. Put it in `voices/<name>/sample.wav` with a `voice.yaml` carrying the speaker's consent line.
2. Choose the engine: a hosted cloning service (fastest to set up, the recording leaves your machine) or an open-source model running locally (the recording stays with you, needs a decent CPU or a GPU).
3. Add `aegis/speech.py` with one function, `synthesize(text, voice) -> audio bytes`, and a `POST /api/speak` route that calls it.
4. In `web/src/voice.ts`, when the chosen voice has `engine: clone`, play the audio from `/api/speak`; fall back to the stock voice if it fails.

Keep the stock voice as the fallback on stage. A demo should never depend on the clone working.

## After the hackathon: towards client demos

In the order that removes the most risk first.

1. **Login and roles.** Single sign-on in front of the server; "can approve" as a role; the approver's identity comes from the login, not a text box.
2. **Durable state.** Postgres for incidents and for the graph's saved state, so a restart loses nothing.
3. **Real actions through Git.** Rollback as a pull request to a GitOps repository, so every change has a diff and a reviewer. Enable `rollback_deployment` in the policy only then.
4. **Where people already are.** Post the briefing and the go / no-go to Slack or Teams; send the team message there after approval.
5. **See the agents in your own tools.** OpenTelemetry traces and metrics for every agent step, next to the traces of the system they investigate.
6. **Separate credentials per agent.** Read-only for investigators, a narrow write credential for the executor alone.
7. **More connectors.** Kubernetes, Datadog, Argo CD, PagerDuty: each is one file with four functions.
8. **Evaluation.** A scored set of recorded incidents per model, so "which model is best for us" has a number.
9. **Kubernetes packaging.** A Helm chart, once there is a second place to run it.

## How many repositories

**One, for now**, with `main` and `develop` from day one. A single repository is easier to understand, to demo and to keep secure: one pipeline, one set of lock files, one place to look.

**Nine at the goal**, plus one private configuration repository per client, every one following the same Gitflow. Which repositories, what triggers each split, the 22 agents and how they work together are all in [`ROADMAP.md`](ROADMAP.md). How to build each one is in [`BLUEPRINT.md`](BLUEPRINT.md).
