// The whole screen: the shelter on the left, the conversation on the right, and a place to talk at the bottom.
import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import Boot from "./components/Boot";
import Composer from "./components/Composer";
import Readouts from "./components/Readouts";
import Shelter, { type Mood } from "./components/Shelter";
import Stream, { DecisionCard, type Entry } from "./components/Stream";
import { CREW, OPEN, bayState } from "./stations";
import type { Config, Gate, Result, Step } from "./types";
import { setSounds, sfx } from "./sfx";
import { canListen, intentOf, listenOnce, onSpeaking, speak, startListening, stopSpeaking } from "./voice";

type NewEntry = Entry extends unknown ? (Entry extends infer E ? (E extends Entry ? Omit<E, "id" | "ts"> : never) : never) : never;
let counter = 0;
const nowTs = () => Date.now() / 1000;

function greeting(name: string, hour = new Date().getHours()): string {
  const who = name ? `, ${name}` : "";
  if (hour < 5) return `Still up${who}?`;
  if (hour < 12) return `Good morning${who}.`;
  if (hour < 17) return `Good afternoon${who}.`;
  return `Good evening${who}.`;
}

const LINES: Record<string, string> = {
  idle: "All quiet",
  investigating: "Crew at work",
  awaiting_decision: "Your call",
  executing: "Carrying it out",
  resolved: "Resolved",
  not_resolved: "Not recovered",
  rejected: "Stood down",
  escalated: "Handed to you",
  failed: "Stopped",
};

export default function App() {
  const [config, setConfig] = useState<Config | null>(null);
  const [model, setModel] = useState("");
  const [voiceId, setVoiceId] = useState(() => localStorage.getItem("aegis_voice") ?? "butler");
  const [by, setBy] = useState(() => localStorage.getItem("aegis_by") ?? "");

  const [awake, setAwake] = useState(false);
  const [waking, setWaking] = useState(false);
  const [soundOn, setSoundOn] = useState(false);
  const [alwaysOn, setAlwaysOn] = useState(false);
  const [hearing, setHearing] = useState(false);
  const [speakingNow, setSpeakingNow] = useState(false);
  const [thinking, setThinking] = useState(false);

  const [entries, setEntries] = useState<Entry[]>([]);
  const [incidentId, setIncidentId] = useState<string | null>(null);
  const [steps, setSteps] = useState<Step[]>([]);
  const [status, setStatus] = useState("idle");
  const [gate, setGate] = useState<Gate | null>(null);
  const [result, setResult] = useState<Result>({});
  const [working, setWorking] = useState<string[]>([]);
  const [armed, setArmed] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [scanned, setScanned] = useState(false);

  // Callbacks from the microphone and timers outlive renders, so they read the latest values through this ref.
  const now = useRef({ status, gate, armed, incidentId, by, soundOn, voiceId, config, model });
  now.current = { status, gate, armed, incidentId, by, soundOn, voiceId, config, model };

  const add = (entry: NewEntry) => setEntries((before) => [...before, { ...entry, ts: nowTs(), id: `e${++counter}` } as Entry]);

  const say = (text: string, by?: string) => {
    add({ kind: "aegis", text, by });
    const { soundOn, config, voiceId } = now.current;
    if (soundOn) speak(text, config?.voices.find((voice) => voice.id === voiceId));
  };

  const attempt = async (what: string, work: () => Promise<unknown>) => {
    try {
      await work();
    } catch (err) {
      say(`${what} failed: ${err instanceof Error ? err.message : String(err)}`);
    }
  };

  useEffect(() => onSpeaking(setSpeakingNow), []);
  useEffect(() => setSounds(soundOn), [soundOn]);

  useEffect(() => {
    attempt("Loading the room", async () => {
      const loaded = await api.config();
      setConfig(loaded);
      setModel(loaded.default_model);
      if (loaded.operator && !localStorage.getItem("aegis_by")) setBy(loaded.operator);
    });
  }, []);

  // The live feed for the incident on screen: every report, and who is working right now.
  useEffect(() => {
    if (!incidentId) return;
    const feed = new EventSource(`/api/incidents/${incidentId}/stream`);
    feed.addEventListener("step", (event) => {
      const step: Step = JSON.parse((event as MessageEvent).data);
      setSteps((before) => {
        if (before.some((old) => old.seq === step.seq)) return before;
        if (["block", "error"].includes(step.kind)) sfx.blocked();
        else sfx.blip();
        return [...before, step];
      });
    });
    feed.addEventListener("status", (event) => {
      const update = JSON.parse((event as MessageEvent).data);
      setStatus(update.status);
      now.current.status = update.status;
      setGate(update.gate);
      setResult(update.result ?? {});
      setWorking(update.working ?? []);
      if (!OPEN.includes(update.status)) feed.close();
    });
    return () => feed.close();
  }, [incidentId]);

  // Keep the newest message in view.
  const bay = useRef<HTMLDivElement>(null);
  useEffect(() => {
    bay.current?.scrollTo({ top: bay.current.scrollHeight, behavior: "smooth" });
  }, [entries.length, steps.length, status]);

  // The two moments Aegis speaks without being asked: asking for your decision, and closing the incident.
  useEffect(() => {
    if (status === "awaiting_decision" && gate) {
      sfx.alert();
      say(gate.briefing);
    }
  }, [status, gate?.plan_hash]);
  useEffect(() => {
    if (!result.closing) return;
    add({ kind: "outcome", status: now.current.status, result }); // the outcome stays in the conversation where it happened
    if (now.current.status === "resolved") sfx.resolved();
    say(result.closing);
  }, [result.closing]);

  const follow = (id: string) => {
    setSteps([]);
    setGate(null);
    setResult({});
    setWorking([]);
    setArmed(false);
    setStatus("investigating");
    setIncidentId(id);
  };

  // Incidents also open without you: the live watcher, or an alert webhook. When the room is free, show the newest.
  useEffect(() => {
    const timer = setInterval(async () => {
      if (OPEN.includes(now.current.status)) return;
      try {
        const newest = (await api.incidents()).find((row) => OPEN.includes(row.status));
        if (newest && newest.id !== now.current.incidentId) {
          follow(newest.id);
          say(`Something broke: ${newest.title} on ${newest.service || "a service"}. Waking the crew.`);
        }
      } catch {
        // the server may be restarting; the next tick tries again
      }
    }, 3000);
    return () => clearInterval(timer);
  }, []);

  const open = (what: string, work: () => Promise<string | undefined>) =>
    attempt(what, async () => {
      const id = await work();
      if (!id) return say("Nothing is unhealthy right now. Break something first, wait a minute, then ask me again.");
      follow(id);
    });

  const decide = (decision: "go" | "no-go", note = "") =>
    attempt("Sending your decision", async () => {
      const { incidentId, gate, by } = now.current;
      if (!incidentId || !gate) return;
      setArmed(false);
      await api.decide(incidentId, decision, gate.plan_hash, by, note);
    });

  const runScan = () =>
    attempt("The code scan", async () => {
      setScanning(true);
      try {
        await api.startScan(now.current.model);
        for (;;) {
          await new Promise((resolve) => setTimeout(resolve, 1500));
          const { status, report } = await api.scanReport();
          if (status === "running") continue;
          add({ kind: "scan", report, problem: report ? "" : status });
          setScanned(true);
          if (report) say(report.findings.length ? `Code Guard found ${report.findings.length} problems. They are listed here.` : "Code Guard found no security problems.");
          return;
        }
      } finally {
        setScanning(false);
      }
    });

  const runDrill = () =>
    attempt("The security drill", async () => {
      const results = await api.drill();
      add({ kind: "drill", results });
      const held = results.filter((item) => item.held).length;
      say(held === results.length ? `All ${held} attacks held. My defences are intact.` : `${results.length - held} attacks got through. Look at the red lines.`);
    });

  const runAudit = () =>
    attempt("The audit check", async () => {
      const audit = await api.audit();
      add({ kind: "audit", ...audit });
      say(audit.ok ? "The audit log is intact. Nobody has edited the record." : "The audit log has been edited. Treat this record as untrusted.");
    });

  const talk = (text: string) => {
    sfx.send();
    add({ kind: "you", text });
    const { status, gate, armed, model } = now.current;
    const decision = intentOf(text);
    // Go and no-go never go to a model: they are matched word for word, and acting always takes two steps.
    if (decision && status === "awaiting_decision" && gate) {
      if (decision === "brief") return say(gate.briefing);
      if (decision === "no-go") return decide("no-go", "said to Aegis");
      if (decision === "go") {
        setArmed(true);
        return say("Say confirm, or press go, and I will proceed.");
      }
      if (decision === "confirm" && armed) return decide("go", "confirmed to Aegis");
    }
    setThinking(true);
    attempt("Understanding that", async () => {
      try {
        const answer = await api.talk(text, model);
        say(answer.reply, answer.answered_by);
        if (answer.intent === "start_drill") await open("Starting the drill", async () => (await api.trigger(answer.scenario, model)).id);
        else if (answer.intent === "scan_live") await open("Scanning the live system", async () => (await api.scanLive(model)).ids[0]);
        else if (answer.intent === "security_scan") await runScan();
        else if (answer.intent === "security_drill") await runDrill();
        else if (answer.intent === "audit") await runAudit();
        else if (answer.intent === "brief" && gate) say(gate.briefing);
      } finally {
        setThinking(false);
      }
    });
  };

  // Always listening: everything heard is treated as if you had typed it.
  useEffect(() => {
    if (!alwaysOn) return;
    const stop = startListening(talk);
    return () => stop?.();
  }, [alwaysOn]);

  const pushToTalk = () => {
    if (hearing) return;
    const stop = listenOnce(talk, () => setHearing(false));
    if (stop) setHearing(true);
  };

  if (!config) return <p className="p-6 font-display text-dim">Opening the shelter…</p>;

  const name = config.assistant;
  const room = { status, steps, working, scanning, scanned };
  const mood: Mood = !awake
    ? "asleep"
    : status === "awaiting_decision"
      ? "yourcall"
      : status === "resolved"
        ? "resolved"
        : status === "failed" || status === "not_resolved"
          ? "blocked"
          : "idle";
  const live = config.source !== "simulator";
  const line = !awake
    ? "Asleep"
    : hearing
      ? "Listening…"
      : thinking
        ? "Thinking…"
        : status === "idle" && live
          ? "Watching"
          : (LINES[status] ?? "Ready");
  const busy = awake && (thinking || working.length > 0 || scanning || status === "investigating" || status === "executing");

  const wake = (operator: string) => {
    setBy(operator);
    if (operator) localStorage.setItem("aegis_by", operator);
    setAwake(true);
    setSoundOn(true);
    setSounds(true);
    now.current.soundOn = true;
    setWaking(true);
    sfx.boot();
    CREW.forEach((_, i) => setTimeout(() => sfx.online(i), 900 + i * 140));
    setTimeout(() => setWaking(false), 2700);
    const crew = live
      ? config.watch_every
        ? `I'm watching ${config.source} every ${config.watch_every} seconds. The crew sleeps until something breaks.`
        : `I'm connected to ${config.source}. Ask me to scan it whenever you like.`
      : "Your crew of ten is asleep, and nothing is broken.";
    setTimeout(() => say(`${greeting(operator)} ${crew} What would you like me to do?`), 2600);
  };

  const explainBay = (id: string) => {
    const member = CREW.find((crew) => crew.id === id);
    if (!member) return;
    const { label } = bayState(id, room);
    say(id === "human" ? `That's you. ${member.about}` : `${member.name}: ${label.toLowerCase()}. ${member.about}`);
  };

  const ask = (label: string, said = label) => ({ label, say: said });
  const suggestions =
    status === "awaiting_decision"
      ? [ask("Brief me again"), ask("Who is working?"), ask("What does the defender do?")]
      : [
          ...(live
            ? [ask("Scan the live system")]
            : config.scenarios.map((scenario) => ask(scenario.title, `Run the drill: ${scenario.title.toLowerCase()}`))),
          ask("Who is working?"),
          ask("Attack your defences"),
          ask("Scan the code"),
          ask("What are you?"),
        ];

  const voiceName = config.voices.find((voice) => voice.id === voiceId)?.name ?? voiceId;
  const toneOf: Record<Mood, string> = { asleep: "#7f9bbd", idle: "#4ff3ff", yourcall: "#ffc24d", resolved: "#3df5a0", blocked: "#ff3d5a" };

  return (
    <div className="flex min-h-screen flex-col lg:h-screen">
      <header className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-line bg-void/60 px-4 py-2.5 backdrop-blur">
        <div className="mr-auto flex items-center gap-4">
          <span className="font-display text-2xl font-black tracking-[0.22em] text-aegis glow-text">{name.toUpperCase()}</span>
          <span className="hidden items-center gap-2 sm:flex">
            <span className="live-dot" style={{ background: toneOf[mood], boxShadow: `0 0 10px ${toneOf[mood]}` }} />
            <span className="hud-label" style={{ color: toneOf[mood] }}>
              {line}
            </span>
          </span>
        </div>
        <label>
          <span className="sr-only">Model</span>
          <select className="hud-select max-w-64" value={model} onChange={(event) => setModel(event.target.value)} title="Which model the crew uses">
            {config.models.map((option) => (
              <option key={option.id} value={option.id} disabled={!option.ready} title={option.missing.join(", ")}>
                {option.label}
                {option.ready ? "" : " (not set up)"}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span className="sr-only">Voice</span>
          <select
            className="hud-select"
            value={voiceId}
            onChange={(event) => {
              setVoiceId(event.target.value);
              localStorage.setItem("aegis_voice", event.target.value);
            }}
          >
            {config.voices.map((voice) => (
              <option key={voice.id} value={voice.id} disabled={!voice.ready} title={voice.problem || voice.description}>
                {voice.name} voice
              </option>
            ))}
          </select>
        </label>
        <button
          className="hud-btn"
          aria-pressed={soundOn}
          onClick={() => {
            if (soundOn) stopSpeaking();
            setSoundOn(!soundOn);
          }}
        >
          {soundOn ? "Sound on" : "Sound off"}
        </button>
        <button className="hud-btn" aria-pressed={alwaysOn} disabled={!canListen()} onClick={() => setAlwaysOn(!alwaysOn)} title="Everything it hears is treated as a message">
          {alwaysOn ? "Always listening" : "Listen on request"}
        </button>
      </header>

      <main className="grid flex-1 grid-cols-[minmax(0,1fr)] lg:min-h-0 lg:grid-cols-[minmax(0,1fr)_minmax(24rem,31rem)]">
        <section className="relative flex flex-col items-center justify-center px-2 py-4 lg:min-h-0" aria-label="The shelter">
          <Readouts
            room={room}
            operator={by}
            source={live ? config.source : "Simulator, nothing real can break"}
            voice={soundOn ? voiceName : "Muted"}
            last={awake ? (steps[steps.length - 1] ?? null) : null}
          />
          <div className="aspect-[6/5] w-full max-w-[min(100%,calc((100vh-11rem)*1.15))]">
            <Shelter
              room={room}
              name={name}
              line={line}
              mood={mood}
              busy={busy}
              speaking={speakingNow}
              waking={waking}
              onCore={() => (canListen() ? pushToTalk() : document.querySelector<HTMLInputElement>("input[aria-label^='Message']")?.focus())}
              onBay={explainBay}
            />
          </div>
          <p className="hud-label text-center lg:absolute lg:bottom-4 lg:left-4 lg:max-w-[15rem] lg:text-left">Tap the core to talk. Tap any bay to hear what that agent does.</p>
        </section>

        <aside className="flex flex-col border-line bg-void/40 lg:min-h-0 lg:border-l" aria-label="Comms">
          <div className="flex items-center gap-2 border-b border-line px-4 py-2.5">
            <span className="live-dot" />
            <span className="font-display text-sm font-bold tracking-[0.2em] text-text">COMMS</span>
            <span className="hud-label ml-auto">{entries.length + steps.length} messages</span>
          </div>
          <div ref={bay} className="flex-1 space-y-3 p-4 lg:overflow-y-auto">
            {entries.length === 0 && steps.length === 0 && (
              <p className="font-mono text-sm text-dim">&gt; Channel open. Talk to {name} here: run a drill, scan the code, attack its own defences, or ask who is working.</p>
            )}
            <Stream entries={entries} steps={steps} />
            {status === "awaiting_decision" && gate && (
              <DecisionCard
                gate={gate}
                armed={armed}
                by={by}
                onBy={(value) => {
                  setBy(value);
                  localStorage.setItem("aegis_by", value);
                }}
                onDecide={decide}
              />
            )}
          </div>
          <div className="sticky bottom-0">
            <Composer name={name} busy={thinking} hearing={hearing} canListen={canListen()} suggestions={suggestions} onSay={talk} onMic={pushToTalk} />
          </div>
        </aside>
      </main>

      {!awake && <Boot name={name} known={by || config.operator} crew={CREW.length - 1} onWake={wake} />}
    </div>
  );
}
