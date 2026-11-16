// The first thing you see: Aegis asleep. Waking it is also what lets the browser speak, which needs a click first.
import { useState } from "react";

type Props = { name: string; known: string; onWake: (operator: string) => void };

export default function Boot({ name, known, onWake }: Props) {
  const [operator, setOperator] = useState(known);
  return (
    <div className="fixed inset-0 z-20 flex items-center justify-center bg-night/70 p-4 backdrop-blur-[2px]">
      <form
        className="glass w-full max-w-md p-6 text-center"
        onSubmit={(event) => {
          event.preventDefault();
          onWake(operator.trim());
        }}
      >
        <h1 className="font-display text-4xl font-bold tracking-wide">{name} is asleep</h1>
        <p className="mt-3 text-dim">
          Your incident room. When something breaks, a crew of agents investigates, a defender checks their plan, and nothing is changed until
          you say go.
        </p>
        <label className="mt-5 block text-left text-sm text-dim">
          What should I call you?
          <input
            className="control mt-1 block w-full text-lg text-text"
            value={operator}
            onChange={(event) => setOperator(event.target.value)}
            maxLength={40}
            autoFocus
          />
        </label>
        <button type="submit" className="mt-5 w-full rounded-xl bg-aegis py-3 font-display text-xl font-bold text-night shadow-[0_0_40px_-10px_var(--color-aegis)]">
          Wake {name}
        </button>
        <p className="mt-3 text-sm text-dim">It will greet you out loud. Mute it any time from the top bar.</p>
      </form>
    </div>
  );
}
