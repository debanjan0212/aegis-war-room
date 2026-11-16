// The shelter: Aegis in the middle, every member of the crew in a bay around it.
// A beam runs from each bay to the core; it flows while that agent works and stays lit once it has reported.
import type { CSSProperties } from "react";
import { CREW, bayState, type Room } from "../stations";

export type Mood = "asleep" | "idle" | "yourcall" | "resolved" | "blocked";

type Props = {
  room: Room;
  name: string;
  line: string;
  mood: Mood;
  busy: boolean;
  speaking: boolean;
  waking: boolean;
  onCore: () => void;
  onBay: (id: string) => void;
};

const W = 1200;
const H = 1000;
const CX = W / 2;
const CY = H / 2;
const ORBIT = 330;
const BAY = 54;

const hex = (x: number, y: number, r: number) =>
  Array.from({ length: 6 }, (_, k) => {
    const a = ((60 * k - 90) * Math.PI) / 180;
    return `${(x + r * Math.cos(a)).toFixed(1)},${(y + r * Math.sin(a)).toFixed(1)}`;
  }).join(" ");

export default function Shelter({ room, name, line, mood, busy, speaking, waking, onCore, onBay }: Props) {
  const states = CREW.map((member) => ({ ...member, ...bayState(member.id, room) }));
  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className={`h-full w-full ${waking ? "waking" : ""}`}
      role="img"
      aria-label={`${name}: ${line}. ${states.map((s) => `${s.name}: ${s.label}`).join(". ")}.`}
    >
      <circle cx={CX} cy={CY} r={ORBIT} fill="none" stroke="var(--color-glass)" strokeWidth="1" />

      {states.map((member, i) => {
        const angle = ((-90 + (i * 360) / CREW.length) * Math.PI) / 180;
        const cos = Math.cos(angle);
        const sin = Math.sin(angle);
        const x = CX + ORBIT * cos;
        const y = CY + ORBIT * sin;
        const lx = CX + (ORBIT + 82) * cos;
        const ly = CY + (ORBIT + 82) * sin;
        const anchor = cos > 0.35 ? "start" : cos < -0.35 ? "end" : "middle";
        const nameY = anchor !== "middle" ? ly - 4 : sin < 0 ? ly - 16 : ly + 8;
        return (
          <g
            key={member.id}
            className="bay"
            data-state={member.state}
            data-you={member.id === "human"}
            style={{ "--i": i } as CSSProperties}
            role="button"
            tabIndex={0}
            aria-label={`${member.name}: ${member.label}. ${member.job}`}
            onClick={() => onBay(member.id)}
            onKeyDown={(event) => (event.key === "Enter" || event.key === " ") && onBay(member.id)}
            cursor="pointer"
          >
            <line className="beam" x1={x - (BAY + 8) * cos} y1={y - (BAY + 8) * sin} x2={CX + 168 * cos} y2={CY + 168 * sin} />
            <polygon className="bay-cell" points={hex(x, y, BAY)} />
            <circle className="bay-orbit" cx={x} cy={y} r={BAY + 12} />
            <g transform={`translate(${x - 21} ${y - 21}) scale(1.75)`}>
              <path className="bay-icon" d={member.icon} />
            </g>
            <text className="bay-name" x={lx} y={nameY} textAnchor={anchor}>
              {member.name}
            </text>
            <text className="bay-state" x={lx} y={nameY + (typeof window !== "undefined" && window.innerWidth <= 640 ? 34 : 23)} textAnchor={anchor}>
              {member.label}
            </text>
          </g>
        );
      })}

      <g className="core core-hit" data-mood={mood} data-busy={busy} data-speaking={speaking} onClick={onCore} role="button" aria-label={`Talk to ${name}`}>
        <defs>
          <radialGradient id="heart">
            <stop offset="0" style={{ stopColor: "var(--tone)", stopOpacity: mood === "asleep" ? 0.15 : 0.55 }} />
            <stop offset="0.6" style={{ stopColor: "var(--tone)", stopOpacity: mood === "asleep" ? 0.04 : 0.12 }} />
            <stop offset="1" style={{ stopColor: "var(--tone)", stopOpacity: 0 }} />
          </radialGradient>
        </defs>
        <circle className="core-spin" cx={CX} cy={CY} r={186} />
        <circle className="core-spin reverse" cx={CX} cy={CY} r={198} />
        <polygon className="core-ring" points={hex(CX, CY, 172)} strokeDasharray="4 10" />
        <polygon className="core-shell" points={hex(CX, CY, 150)} />
        <polygon className="core-ring" points={hex(CX, CY, 128)} />
        <circle className="core-heart" cx={CX} cy={CY} r={118} />
        <text className="core-name" x={CX} y={CY + 4} textAnchor="middle">
          {name}
        </text>
        <text className="core-line" x={CX} y={CY + 40} textAnchor="middle">
          {line}
        </text>
      </g>
    </svg>
  );
}
