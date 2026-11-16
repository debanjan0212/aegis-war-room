// The first thing you see: Aegis on standby. Waking it is also what lets the browser speak and play sound,
// which both need a click first.
import { useState } from "react";

type Props = { name: string; known: string; crew: number; onWake: (operator: string) => void };

export default function Boot({ name, known, crew, onWake }: Props) {
  const [operator, setOperator] = useState(known);
  return (
    <div className="fixed inset-0 z-30 flex items-center justify-center bg-void/75 p-4 backdrop-blur-[3px]">
      <form
        className="hud w-full max-w-md min-w-0 p-6 text-center sm:p-7"
        style={{ boxShadow: "0 0 80px -20px #4ff3ff, inset 0 0 50px -30px #4ff3ff" }}
        onSubmit={(event) => {
          event.preventDefault();
          onWake(operator.trim());
        }}
      >
        <p className="hud-label">Incident response system</p>
        <h1 className="boot-flicker mt-3 font-display text-4xl font-black tracking-[0.18em] sm:text-5xl text-aegis glow-text">{name.toUpperCase()}</h1>
        <ul className="mt-5 space-y-1 text-left font-mono text-[13px] text-dim">
          {[
            ["Core", "standby"],
            ["Crew", `${crew} agents asleep`],
            ["Defender", "armed"],
            ["Voice", "standing by"],
          ].map(([what, state]) => (
            <li key={what} className="flex items-end gap-2">
              <span>&gt; {what}</span>
              <span className="mb-1 flex-1 border-b border-dotted border-dim/50" />
              <span className="text-text">{state}</span>
            </li>
          ))}
        </ul>
        <label className="mt-6 block text-left">
          <span className="hud-label">Operator</span>
          <input
            className="hud-input mt-1 block h-12 w-full text-lg"
            value={operator}
            onChange={(event) => setOperator(event.target.value)}
            placeholder="What should I call you?"
            maxLength={40}
            autoFocus
          />
        </label>
        <button type="submit" className="wake mt-6 w-full py-3.5 text-lg">
          Wake {name}
        </button>
        <p className="mt-3 text-sm text-dim">It greets you out loud. Mute it any time from the top bar.</p>
      </form>
    </div>
  );
}
