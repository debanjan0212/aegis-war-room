# The plan

Where the project stands, what to do on hackathon day, and how it grows into something you can show clients.

## Where it stands

| Piece | State | How it was checked |
|---|---|---|
| Incident flow: nine agents and a human go / no-go | Working | 39 automated tests, three scenarios played end to end |
| Defender: policy, injection filter, plan fingerprint, audit chain | Working | `aegis drill`: eight attacks, all held |
| Code Guard agent | Working | Run on this repository: Bandit, pip-audit, npm audit, secrets, pin check all clean |
| War room screen | Working | Driven through a full incident in Chrome, desktop and phone size |
| Voice commands | Parsing tested | 18 phrases map to the right command. Not yet tried with a real microphone and speaker |
| Model toggle | Wired | Azure and Bedrock clients build and accept the answer shapes. No real model call made yet |
| Live mode (OpenTelemetry Demo) | Wired | Tested against recorded Prometheus answers and a real flag file. Not yet run against the live shop |
| Container image | Written | Not built yet. CI builds it on the first push |
| Voice cloning | Not started | Folder layout, menu and consent check are in place |

## Hackathon day: 24 hours

The skeleton exists, so the day goes on the parts that only work when proven live.

| Hours | Do | Done when |
|---|---|---|
| 0 to 1 | Clone, `make check`, `make serve`. Everyone on the team plays one incident | All green on every laptop |
| 1 to 4 | **Live mode.** Start the OpenTelemetry Demo, set the three settings in the README, break `paymentFailure`, scan | A real incident opens, go switches the real flag off, the verifier sees real recovery |
| 4 to 5 | If the flag service does not pick up the file change (possible on Docker Desktop), switch `otel_demo.py` to the flag page's API | Flag flips within seconds |
| 5 to 8 | **One real model.** Fill in `.env` for the cloud you trust most. Play all three scenarios. Fix prompts where the model's answer is worse than the offline rules | Three scenarios pass on a real model |
| 8 to 10 | **Second cloud.** Same three scenarios | The toggle is real, not a slide |
| 10 to 13 | **Live logs.** Add log search to `otel_demo.py` so the injection demo works on the real shop (plant a log line, watch it get quarantined) | Quarantine strip appears in live mode |
| 13 to 16 | **Voice.** Try it in the room you will present in. Tune `voices/butler/voice.yaml`. Add the cloning engine if the recording is ready (see below) | Briefing is audible, "no-go" and "go, confirm" work from where you stand |
| 16 to 19 | Polish what judges see: scenario wording, the postmortem, the team message | You would be happy to screenshot any moment of the demo |
| 19 to 21 | Run `make check` and the Security panel. Fix anything found. Push | CI and security workflows green |
| 21 to 24 | Rehearse three times with a timer. Record a backup video. Stop changing code | A full run fits in five minutes |

**Cut first if you fall behind:** second cloud, live logs, voice cloning. Never cut: live mode with one real model, and the rehearsal.

## The five-minute demo

1. **The promise (20 seconds).** "Agents investigate. A defender checks. A human decides. Only then is anything changed."
2. **Break it (30 seconds).** Switch `paymentFailure` on in the shop. Show Grafana going red.
3. **The room wakes up (60 seconds).** Stations report in one by one. Point at the amber Signals station: a log line tried to give the AI orders and was quarantined. Open it.
4. **Your call (45 seconds).** The voice briefs you. Say "go", then "confirm". Mention: stopping takes one word, acting takes two.
5. **Proof (30 seconds).** Verifier shows recovery. Grafana goes green. Open the message for the team.
6. **Restraint (40 seconds).** Play "A release broke checkout". Aegis finds the cause, is not allowed to roll back, and hands over without touching anything.
7. **Defender's corner (45 seconds).** Run the drill: eight attacks, eight held. Run the code scan.
8. **The toggle (30 seconds).** Switch the model menu to another cloud and start an incident. Each strip says which model answered.

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
