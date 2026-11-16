// The whole screen: top bar (model, voice, microphone), the stations, the conversation, the desk.
import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import Desk from "./components/Desk";
import Security from "./components/Security";
import Stations from "./components/Stations";
import StripBay from "./components/StripBay";
import { OPEN } from "./stations";
import type { Config, Gate, Result, Step } from "./types";
import { canListen, speak, startListening, stopSpeaking, type Intent } from "./voice";

export default function App() {
  const [config, setConfig] = useState<Config | null>(null);
  const [model, setModel] = useState("");
  const [voiceId, setVoiceId] = useState(() => localStorage.getItem("aegis_voice") ?? "butler");
  const [by, setBy] = useState(() => localStorage.getItem("aegis_by") ?? "");
  const [soundOn, setSoundOn] = useState(false);
  const [micOn, setMicOn] = useState(false);

  const [incidentId, setIncidentId] = useState<string | null>(null);
  const [steps, setSteps] = useState<Step[]>([]);
  const [status, setStatus] = useState("idle");
  const [gate, setGate] = useState<Gate | null>(null);
  const [result, setResult] = useState<Result>({});

  const [armed, setArmed] = useState(false); // "go" was heard; waiting for "confirm"
  const [busy, setBusy] = useState(false);
  const [caption, setCaption] = useState("");
  const [heard, setHeard] = useState("");
  const [problem, setProblem] = useState("");

  // The microphone callback outlives renders, so it reads the latest values through this ref.
  const now = useRef({ status, gate, armed, incidentId, by, soundOn, voiceId, config });
  now.current = { status, gate, armed, incidentId, by, soundOn, voiceId, config };

  const say = (text: string) => {
    setCaption(text);
    const { soundOn, config, voiceId } = now.current;
    if (soundOn) speak(text, config?.voices.find((voice) => voice.id === voiceId));
  };
  const attempt = async (work: () => Promise<unknown>) => {
    setBusy(true);
    setProblem("");
    try {
      await work();
    } catch (err) {
      setProblem(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    attempt(async () => {
      const loaded = await api.config();
      setConfig(loaded);
      setModel(loaded.default_model);
    });
  }, []);

  // Live feed for the current incident.
  useEffect(() => {
    if (!incidentId) return;
    const feed = new EventSource(`/api/incidents/${incidentId}/stream`);
    feed.addEventListener("step", (event) => {
      const step: Step = JSON.parse((event as MessageEvent).data);
      setSteps((before) => (before.some((old) => old.seq === step.seq) ? before : [...before, step]));
    });
    feed.addEventListener("status", (event) => {
      const update = JSON.parse((event as MessageEvent).data);
      setStatus(update.status);
      setGate(update.gate);
      setResult(update.result ?? {});
      if (!OPEN.includes(update.status)) feed.close();
    });
    return () => feed.close();
  }, [incidentId]);

  // Keep the newest strip in view. On a wide screen the conversation scrolls inside its own column, so the
  // stations and the go / no-go buttons never move. On a phone the page is left alone: the buttons stay on top.
  const bay = useRef<HTMLDivElement>(null);
  useEffect(() => {
    bay.current?.scrollTo({ top: bay.current.scrollHeight });
  }, [steps.length]);

  // The two moments the assistant speaks: asking for the decision, and closing the incident.
  useEffect(() => {
    if (status === "awaiting_decision" && gate) say(gate.briefing);
  }, [status, gate?.plan_hash]);
  useEffect(() => {
    if (result.closing) say(result.closing);
  }, [result.closing]);

  const follow = (id: string) => {
    setSteps([]);
    setGate(null);
    setResult({});
    setArmed(false);
    setStatus("investigating");
    setIncidentId(id);
  };

  const open = (work: () => Promise<string | undefined>) =>
    attempt(async () => {
      const id = await work();
      if (!id) return setProblem("Nothing is unhealthy right now. Break something first, wait a minute, then scan again.");
      follow(id);
    });

  // Incidents also open without a click: the live watcher, or an alert webhook. When the room is not busy, show the newest one.
  useEffect(() => {
    const timer = setInterval(async () => {
      if (OPEN.includes(now.current.status)) return; // never pull anyone away from an incident that is still open
      try {
        const newest = (await api.incidents()).find((row) => OPEN.includes(row.status));
        if (newest && newest.id !== now.current.incidentId) follow(newest.id);
      } catch {
        // the server may be restarting; the next tick tries again
      }
    }, 3000);
    return () => clearInterval(timer);
  }, []);

  const decide = (decision: "go" | "no-go", note = "") =>
    attempt(async () => {
      const { incidentId, gate, by } = now.current;
      if (!incidentId || !gate) return;
      setArmed(false);
      await api.decide(incidentId, decision, gate.plan_hash, by, note);
    });

  const onHeard = (text: string, intent: Intent | null) => {
    setHeard(text);
    const { status, gate, armed } = now.current;
    if (intent === "brief" && gate) return say(gate.briefing);
    if (!intent || status !== "awaiting_decision") return;
    if (intent === "no-go") decide("no-go", "said by voice");
    else if (intent === "go") {
      setArmed(true);
      say("Say confirm, or tap go, and I will proceed.");
    } else if (intent === "confirm" && armed) decide("go", "confirmed by voice");
  };

  useEffect(() => {
    if (!micOn) return;
    const stop = startListening(onHeard);
    if (!stop) setProblem("This browser cannot listen. Use Chrome or Edge for voice commands; the buttons work everywhere.");
    return () => stop?.();
  }, [micOn]);

  if (!config) return <p className="p-6">{problem || "Opening the war room…"}</p>;

  const toggleSound = () => {
    const next = !soundOn;
    setSoundOn(next);
    now.current.soundOn = next;
    if (next) say(`${config.assistant} here. Voice is on.`);
    else stopSpeaking();
  };

  const desk = (
    <Desk
      config={config}
      status={status}
      steps={steps}
      gate={gate}
      result={result}
      armed={armed}
      busy={busy}
      by={by}
      onBy={(name) => {
        setBy(name);
        localStorage.setItem("aegis_by", name);
      }}
      onStart={(scenario) => open(async () => (await api.trigger(scenario, model)).id)}
      onScanLive={() => open(async () => (await api.scanLive(model)).ids[0])}
      onDecide={decide}
      onReset={() => {
        setIncidentId(null);
        setSteps([]);
        setStatus("idle");
        setCaption("");
      }}
    />
  );

  return (
    <div className="mx-auto flex min-h-screen max-w-[1500px] flex-col lg:h-screen">
      <header className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-rule px-4 py-3 sm:px-6">
        <h1 className="mr-auto font-display text-3xl leading-none">
          {config.assistant} war room <span className="text-lg text-chalk-dim">on {config.source}</span>
        </h1>
        <label className="text-sm text-chalk-dim">
          Model{" "}
          <select className="field text-base" value={model} onChange={(event) => setModel(event.target.value)}>
            {config.models.map((option) => (
              <option key={option.id} value={option.id} disabled={!option.ready} title={option.missing.join(", ")}>
                {option.label}
                {option.ready ? "" : " (not set up)"}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm text-chalk-dim">
          Voice{" "}
          <select
            className="field text-base"
            value={voiceId}
            onChange={(event) => {
              setVoiceId(event.target.value);
              localStorage.setItem("aegis_voice", event.target.value);
            }}
          >
            {config.voices.map((voice) => (
              <option key={voice.id} value={voice.id} disabled={!voice.ready} title={voice.problem || voice.description}>
                {voice.name}
                {voice.ready ? "" : " (not ready)"}
              </option>
            ))}
          </select>
        </label>
        <button className="quiet-button" aria-pressed={soundOn} onClick={toggleSound}>
          {soundOn ? "Speaking: on" : "Speaking: off"}
        </button>
        <button className="quiet-button" aria-pressed={micOn} disabled={!canListen()} onClick={() => setMicOn(!micOn)}>
          {micOn ? "Listening: on" : "Listening: off"}
        </button>
      </header>

      <Stations steps={steps} status={status} />

      {/* Subtitles for the voice, so a noisy room can still follow. Hidden when speaking is off: the desk says it all. */}
      {((soundOn && caption) || (micOn && heard) || problem) && (
        <div className="border-b border-rule px-4 py-2 sm:px-6" aria-live="polite">
          {problem && <p className="text-amber">{problem}</p>}
          {soundOn && caption && (
            <p className="line-clamp-2">
              <span className="text-chalk-dim">{config.assistant}: </span>
              {caption}
            </p>
          )}
          {micOn && heard && <p className="text-chalk-dim">Heard: “{heard}”</p>}
        </div>
      )}

      {status === "idle" ? (
        <main className="flex-1 lg:min-h-0 lg:overflow-y-auto">
          <div className="px-4 py-6 sm:px-6">{desk}</div>
          <Security model={model} />
        </main>
      ) : (
        <main className="grid flex-1 lg:min-h-0 lg:grid-cols-[minmax(0,1fr)_28rem]">
          <div ref={bay} className="order-2 lg:order-1 lg:overflow-y-auto">
            <div className="px-4 py-5 sm:px-6">
              <StripBay steps={steps} />
            </div>
            <Security model={model} />
          </div>
          <aside className="order-1 border-rule px-4 py-5 sm:px-6 lg:order-2 lg:overflow-y-auto lg:border-l">{desk}</aside>
        </main>
      )}
    </div>
  );
}
