# How Aegis is put together

One process, three layers. Nothing here needs a cloud account to run.

```text
  Browser (web/)                 Backend (aegis/)                         Outside world
 ┌──────────────────┐   HTTP   ┌───────────────────────────────┐        ┌─────────────────────┐
 │ stations, strips │ <------> │ server.py   the web API       │        │ simulator (default) │
 │ go / no-go desk  │   SSE    │ flow.py     who speaks when   │ <----> │   or                │
 │ voice in and out │          │ agents/     one file each     │        │ OpenTelemetry Demo  │
 └──────────────────┘          │ security/   the rules         │        │ (Prometheus, flags) │
                               │ brain.py    the model toggle  │        └─────────────────────┘
                               │ store.py    feed + audit log  │        ┌─────────────────────┐
                               └───────────────────────────────┘ <----> │ offline rules, or   │
                                                                        │ Ollama (laptop), or │
                                                                        │ Azure/Bedrock/Vertex│
                                                                        └─────────────────────┘
```

## The flow

[`aegis/flow.py`](../aegis/flow.py) is a LangGraph graph. Each agent is one step. The steps share one piece of state (the alert, the findings so far, the plan, the decision), so agents "talk" by adding to it, and everything they say out loud also goes to the screen and the audit log.

You talk to Aegis through [`aegis/assistant.py`](../aegis/assistant.py). A model works out which one of a fixed list of commands you meant; everything factual in the reply is built from the record. Go and no-go never pass through it: the screen matches those words exactly.

In live mode an incident can also start by itself: with `AEGIS_WATCH_EVERY` set, `server.py` looks at the live system every few seconds and opens an incident for anything unhealthy that is not already being handled. The screen follows the newest open incident whenever it is not busy with one.

The go / no-go is a real pause, not a flag in a loop. The graph stops at `interrupt()` and its state is saved. Nothing after that point can run until `flow.decide()` resumes it with the human's answer.

## One agent, three parts

Every file in [`aegis/agents/`](../aegis/agents/) has the same shape:

| Part | What it is |
|---|---|
| `PROMPT` | What the agent is asked when a model (laptop or cloud) is switched on |
| `offline()` | The built-in rules used when the toggle is "offline", or when the model fails |
| `run()` | The step itself: gather facts, ask the brain, tell the room, pass results on |

The answer always has a fixed shape (a small Pydantic class), whichever model gives it. That is what makes the toggle safe: the rest of the flow never sees free text where it expects a decision.

Two agents never use a model, on purpose: the **defender** (a guard must not be persuadable) and the **executor** (it only does what was approved).

## The model toggle

[`aegis/brain.py`](../aegis/brain.py) has one method, `Brain.ask(prompt, shape, facts, offline_rules)`. It reads [`config/models.yaml`](../config/models.yaml) and uses LangChain's `init_chat_model`, which builds an Ollama (laptop), Azure OpenAI, Bedrock or Vertex AI client from a provider name. Adding a provider is adding a block to that file. `aegis models --test` asks every ready model one tiny question in the same fixed-shape way the agents do, so a model that cannot answer in shape shows up before the demo, not during it.

## Connectors

A connector is how Aegis touches the outside world. Each offers the same four things, so agents never know which one is live:

```python
signals(service)  # metrics, logs, traces for one service
changes(service)  # recent flags, releases, config changes
apply(action, target, value)  # do one approved action
detect()  # alerts for anything unhealthy right now
```

`simulator.py` plays the files in `scenarios/`. `otel_demo.py` talks to the real OpenTelemetry Demo. A new system (Kubernetes, Datadog, Argo CD) is a new file with those four functions.

## How to extend it

| To add | Do this |
|---|---|
| An agent | New file in `aegis/agents/` with `PROMPT`, `offline()`, `run()`; add one `add_node` and its edges in `flow.py`; add it to `web/src/stations.ts` |
| An action | Add it to `config/policy.yaml` with its allowed targets and values; teach a connector's `apply()` to do it; add a line to `policy.describe()` |
| A connector | New file in `aegis/connectors/` with the four functions; add it to `get_connector()` |
| A model | A new block in `config/models.yaml` |
| A drill | A new line in `aegis/security/drill.py` |

## What is deliberately simple

- Incidents are held in memory, and the graph's saved state too. Swapping `InMemorySaver` for the Postgres saver in `flow.py` makes open incidents survive a restart.
- The live feed is server-sent events read from a list. It is enough for one room. Many viewers would want a message bus.
- The runbook agent matches words; it is not a vector search. With a model switched on, the model picks from the list instead.
