// Where you talk to Aegis: type, or press the microphone orb and say it. The chips are things it can do right now.
import { useState } from "react";

type Props = {
  name: string;
  busy: boolean;
  hearing: boolean;
  canListen: boolean;
  suggestions: { label: string; say: string }[];
  onSay: (text: string) => void;
  onMic: () => void;
};

export default function Composer({ name, busy, hearing, canListen, suggestions, onSay, onMic }: Props) {
  const [text, setText] = useState("");
  const send = (said: string) => {
    if (!said.trim()) return;
    onSay(said.trim());
    setText("");
  };
  return (
    <div className="border-t border-line bg-void/85 p-3 backdrop-blur">
      <div className="mb-2.5 flex gap-2 overflow-x-auto pb-1 sm:flex-wrap sm:overflow-visible" aria-label="Things to ask">
        {suggestions.map((suggestion) => (
          <button key={suggestion.label} className="chip" disabled={busy} onClick={() => send(suggestion.say)} title={suggestion.say}>
            {suggestion.label}
          </button>
        ))}
      </div>
      <form
        className="flex items-center gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          send(text);
        }}
      >
        <button
          type="button"
          className="mic-orb grid h-12 w-12 shrink-0 place-items-center"
          aria-pressed={hearing}
          aria-label={hearing ? "Listening" : `Talk to ${name}`}
          title={canListen ? `Talk to ${name}` : "Voice needs Chrome or Edge"}
          disabled={!canListen}
          onClick={onMic}
        >
          <svg viewBox="0 0 24 24" className="h-5 w-5" aria-hidden="true">
            <path d="M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3zM5 11a7 7 0 0 0 14 0M12 18v3" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" />
          </svg>
        </button>
        <input
          className="hud-input h-12 min-w-0 flex-1"
          value={text}
          onChange={(event) => setText(event.target.value)}
          placeholder={hearing ? "Listening…" : busy ? `${name} is thinking…` : `Talk to ${name}…`}
          maxLength={300}
          aria-label={`Message to ${name}`}
        />
        <button type="submit" className="hud-btn h-12 px-5" disabled={busy || !text.trim()}>
          Send
        </button>
      </form>
    </div>
  );
}
