// The heads-up readouts in the four corners of the shelter. Every number here is real: the clock, the crew's
// states, the model in use, and the last thing the crew said. Nothing is decoration.
import { type CSSProperties, useEffect, useState } from "react";
import { CREW, bayState, colorOf, nameOf, type Room } from "../stations";
import type { Step } from "../types";

type Props = { room: Room; operator: string; source: string; voice: string; last: Step | null };

function Clock() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);
  return (
    <>
      <p className="font-display text-4xl font-bold tabular-nums text-aegis glow-text">
        {now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false })}
        <span className="text-xl text-aegis/60">:{String(now.getSeconds()).padStart(2, "0")}</span>
      </p>
      <p className="hud-label mt-1">{now.toLocaleDateString([], { weekday: "long", day: "numeric", month: "long" })}</p>
    </>
  );
}

export default function Readouts({ room, operator, source, voice, last }: Props) {
  const states = CREW.map((member) => ({ ...member, ...bayState(member.id, room) }));
  const count = (wanted: string[]) => states.filter((s) => s.id !== "human" && wanted.includes(s.state)).length;
  return (
    <>
      <div className="pointer-events-none absolute top-4 left-4 hidden lg:block">
        <Clock />
        {operator && <p className="hud-label mt-2">Operator <span className="text-text">{operator}</span></p>}
        <p className="hud-label mt-1">Source <span className="text-text">{source}</span></p>
        <p className="hud-label mt-1">Voice <span className="text-text">{voice}</span></p>
      </div>

      <div className="hud pointer-events-none absolute top-4 right-4 hidden w-64 p-3 lg:block">
        <p className="hud-label">Crew status</p>
        <div className="mt-2 flex gap-1" aria-hidden="true">
          {states
            .filter((s) => s.id !== "human")
            .map((s) => (
              <span
                key={s.id}
                className="h-3 flex-1"
                style={{
                  background: s.color,
                  opacity: s.state === "asleep" ? 0.15 : s.state === "standby" ? 0.35 : 1,
                  boxShadow: s.state === "working" ? `0 0 10px ${s.color}` : "none",
                }}
              />
            ))}
        </div>
        <dl className="mt-2 grid grid-cols-3 text-center">
          <div>
            <dt className="hud-label">Working</dt>
            <dd className="font-display text-xl font-bold text-aegis">{count(["working"])}</dd>
          </div>
          <div>
            <dt className="hud-label">Done</dt>
            <dd className="font-display text-xl font-bold text-calm">{count(["done", "flagged", "blocked"])}</dd>
          </div>
          <div>
            <dt className="hud-label">Asleep</dt>
            <dd className="font-display text-xl font-bold text-dim">{count(["asleep", "standby"])}</dd>
          </div>
        </dl>
      </div>

      {last && (
        <div className="hud pointer-events-none absolute right-4 bottom-4 hidden w-72 p-3 lg:block" style={{ "--tone": colorOf(last.agent) } as CSSProperties}>
          <p className="hud-label">Last transmission</p>
          <p className="mt-1 font-display text-sm font-bold uppercase tracking-widest" style={{ color: colorOf(last.agent) }}>
            {nameOf(last.agent)}
          </p>
          <p className="mt-1 line-clamp-2 text-sm text-text/90">{last.text}</p>
        </div>
      )}
    </>
  );
}
