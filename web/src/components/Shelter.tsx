// The shelter: Aegis as a living reactor core in the middle, every member of the crew in a bay around it.
// Each agent has its own colour. A beam joins each bay to the core: it flows, with data pulses running in,
// while that agent works, and holds steady once it has reported. Asleep bays are dim and grey.
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
const ORBIT = 345;
const BAY = 54;
const CORE_EDGE = 210;
const ACTIVE = new Set(["working", "done", "yourcall", "blocked"]);

const hex = (x: number, y: number, r: number, turn = -90) =>
  Array.from({ length: 6 }, (_, k) => {
    const a = ((60 * k + turn) * Math.PI) / 180;
    return `${(x + r * Math.cos(a)).toFixed(1)},${(y + r * Math.sin(a)).toFixed(1)}`;
  }).join(" ");

const at = (r: number, degrees: number) => {
  const a = (degrees * Math.PI) / 180;
  return [CX + r * Math.cos(a), CY + r * Math.sin(a)];
};

function Core({ name, line, mood, busy, speaking, onCore }: Pick<Props, "name" | "line" | "mood" | "busy" | "speaking" | "onCore">) {
  return (
    <g className="core core-hit" data-mood={mood} data-busy={busy} data-speaking={speaking} onClick={onCore} role="button" aria-label={`Talk to ${name}`}>
      <defs>
        <radialGradient id="plasma">
          <stop offset="0" stopColor="#ffffff" stopOpacity="0.95" />
          <stop offset="0.22" style={{ stopColor: "var(--tone)", stopOpacity: 0.9 }} />
          <stop offset="0.6" style={{ stopColor: "var(--tone)", stopOpacity: 0.22 }} />
          <stop offset="1" style={{ stopColor: "var(--tone)", stopOpacity: 0 }} />
        </radialGradient>
        <radialGradient id="shell">
          <stop offset="0" style={{ stopColor: "var(--tone)", stopOpacity: 0.16 }} />
          <stop offset="1" stopColor="#040a16" stopOpacity="0.92" />
        </radialGradient>
      </defs>

      {/* A wide bloom behind everything, so the core lights the room. */}
      <circle cx={CX} cy={CY} r={150} style={{ fill: "var(--tone)" }} opacity="0.16" filter="url(#bloom)" />

      {/* Outer instrument rings. */}
      <g className="shelter-rot spin-90">
        {Array.from({ length: 72 }, (_, k) => {
          const long = k % 6 === 0;
          const [x1, y1] = at(long ? 190 : 196, k * 5);
          const [x2, y2] = at(long ? 210 : 204, k * 5);
          return <line key={k} x1={x1} y1={y1} x2={x2} y2={y2} className="core-line-1" strokeWidth={long ? 2 : 1} opacity={long ? 0.8 : 0.45} />;
        })}
      </g>
      <circle className="core-line-1 shelter-rot spin-14" cx={CX} cy={CY} r={184} strokeWidth="4" strokeDasharray="90 40 20 40 140 60 30 50" opacity="0.85" filter="url(#glow)" />
      <circle className="core-line-1 shelter-rot spin-40r" cx={CX} cy={CY} r={174} strokeWidth="1.2" strokeDasharray="2 6" opacity="0.6" />
      <circle className="core-line-1 busy-only shelter-rot spin-5" cx={CX} cy={CY} r={164} strokeWidth="3" strokeDasharray="70 300" filter="url(#glow)" />
      <circle className="core-line-1 busy-only shelter-rot spin-8r" cx={CX} cy={CY} r={157} strokeWidth="2" strokeDasharray="30 160" />

      {/* A ring of level bars: quiet while idle, dancing while Aegis speaks. */}
      <g className="wave">
        {Array.from({ length: 64 }, (_, k) => (
          <g key={k} transform={`rotate(${k * 5.625} ${CX} ${CY})`}>
            <rect x={CX - 1.6} y={CY - 152} width="3.2" height="12" style={{ animationDelay: `${-((k * 37) % 100) / 90}s` }} />
          </g>
        ))}
      </g>

      {/* The shield itself. */}
      <polygon className="core-line-1" points={hex(CX, CY, 132)} strokeWidth="7" opacity="0.5" filter="url(#glow)" />
      <polygon className="core-shell" points={hex(CX, CY, 130)} />
      <polygon className="core-line-1" points={hex(CX, CY, 138)} strokeWidth="1" opacity="0.5" />
      <g className="shelter-rot spin-40r">
        <polygon className="core-line-1" points={hex(CX, CY, 110, 0)} strokeWidth="1.2" opacity="0.55" />
      </g>

      {/* The plasma heart. It breathes, and beats while speaking. */}
      <circle className="plasma" cx={CX} cy={CY} r={98} fill="url(#plasma)" />
      <circle className="core-line-1" cx={CX} cy={CY} r={66} strokeWidth="1.5" opacity="0.8" filter="url(#glow)" />
      <circle className="core-line-1 shelter-rot spin-8r" cx={CX} cy={CY} r={80} strokeWidth="2.5" strokeDasharray="40 22" opacity="0.7" />

      <text className="core-name" x={CX} y={CY + 10} textAnchor="middle" filter="url(#glow)">
        {name.toUpperCase()}
      </text>
      <text className="core-line" x={CX} y={CY + 44} textAnchor="middle">
        {line}
      </text>
    </g>
  );
}

export default function Shelter({ room, name, line, mood, busy, speaking, waking, onCore, onBay }: Props) {
  const states = CREW.map((member) => ({ ...member, ...bayState(member.id, room) }));
  const place = (i: number) => -90 + (i * 360) / CREW.length;

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className={`h-full w-full overflow-visible ${waking ? "waking" : ""} ${mood === "asleep" ? "asleep" : ""}`}
      role="img"
      aria-label={`${name}: ${line}. ${states.map((s) => `${s.name}: ${s.label}`).join(". ")}.`}
    >
      <defs>
        <filter id="glow" x="-60%" y="-60%" width="220%" height="220%">
          <feGaussianBlur stdDeviation="5" result="soft" />
          <feMerge>
            <feMergeNode in="soft" />
            <feMergeNode in="soft" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
        <filter id="bloom" x="-100%" y="-100%" width="300%" height="300%">
          <feGaussianBlur stdDeviation="40" />
        </filter>
        {states.map((member, i) => {
          const [bx, by] = at(ORBIT, place(i));
          const [cx, cy] = at(CORE_EDGE, place(i));
          return (
            <linearGradient key={member.id} id={`beam-${member.id}`} gradientUnits="userSpaceOnUse" x1={bx} y1={by} x2={cx} y2={cy}>
              <stop offset="0" stopColor={member.color} />
              <stop offset="1" stopColor="#4ff3ff" stopOpacity="0.6" />
            </linearGradient>
          );
        })}
      </defs>

      {/* The orbit the crew sits on, a slow ring of satellites, and a radar sweep across the whole shelter. */}
      <circle cx={CX} cy={CY} r={ORBIT} fill="none" stroke="#17345a" strokeWidth="1.5" />
      <circle className="shelter-rot spin-90" cx={CX} cy={CY} r={ORBIT + 22} fill="none" stroke="#4ff3ff" strokeOpacity="0.18" strokeDasharray="1 12" />
      <g className="sweep">
        <path d={`M${CX},${CY} L${at(ORBIT + 60, -26).join(",")} A${ORBIT + 60},${ORBIT + 60} 0 0 1 ${at(ORBIT + 60, 0).join(",")} Z`} fill="#4ff3ff" opacity="0.06" />
        <line x1={CX} y1={CY} x2={at(ORBIT + 60, 0)[0]} y2={at(ORBIT + 60, 0)[1]} stroke="#4ff3ff" strokeOpacity="0.45" strokeWidth="2" filter="url(#glow)" />
      </g>
      <g className="satellites shelter-rot spin-40r">
        {[15, 105, 195, 285].map((degrees) => {
          const [x, y] = at(ORBIT + 22, degrees);
          return <circle key={degrees} cx={x} cy={y} r="4" fill="#4ff3ff" filter="url(#glow)" />;
        })}
      </g>

      {states.map((member, i) => {
        const degrees = place(i);
        const [x, y] = at(ORBIT, degrees);
        const [ex, ey] = at(CORE_EDGE, degrees);
        const cos = Math.cos((degrees * Math.PI) / 180);
        const sin = Math.sin((degrees * Math.PI) / 180);
        const [lx, ly] = at(ORBIT + 88, degrees);
        const anchor = cos > 0.35 ? "start" : cos < -0.35 ? "end" : "middle";
        const nameY = anchor !== "middle" ? ly - 2 : sin < 0 ? ly - 18 : ly + 10;
        const active = ACTIVE.has(member.state);
        const gap = (BAY + 8) / ORBIT;
        const [sx, sy] = [x - (x - CX) * gap, y - (y - CY) * gap];
        return (
          <g
            key={member.id}
            className="bay"
            data-state={member.state}
            style={{ "--agent": member.color, "--i": i } as CSSProperties}
            role="button"
            tabIndex={0}
            aria-label={`${member.name}: ${member.label}. ${member.job}`}
            onClick={() => onBay(member.id)}
            onKeyDown={(event) => (event.key === "Enter" || event.key === " ") && onBay(member.id)}
            cursor="pointer"
          >
            <line className="beam" stroke={`url(#beam-${member.id})`} x1={sx} y1={sy} x2={ex} y2={ey} />
            {member.state === "working" &&
              [0, 0.45].map((delay) => (
                <circle key={delay} r="5" fill={member.color} filter="url(#glow)">
                  <animateMotion dur="0.9s" begin={`${delay}s`} repeatCount="indefinite" path={`M${sx},${sy} L${ex},${ey}`} />
                </circle>
              ))}
            <circle className="bay-ripple" cx={x} cy={y} r={BAY} strokeWidth="2" />
            <polygon className={`bay-cell ${active ? "bay-glow" : ""}`} points={hex(x, y, BAY)} />
            <polygon className="bay-inner" points={hex(x, y, BAY - 9)} />
            <circle className="bay-ring" cx={x} cy={y} r={BAY + 13} strokeWidth="3" strokeDasharray="34 46" />
            <circle className="bay-ring reverse" cx={x} cy={y} r={BAY + 21} strokeWidth="1.5" strokeDasharray="5 9" />
            <g transform={`translate(${x - 22} ${y - 22}) scale(1.85)`} filter={active ? "url(#glow)" : undefined}>
              <path className="bay-icon" d={member.icon} />
            </g>
            <text className="bay-name" x={lx} y={nameY} textAnchor={anchor} filter={active ? "url(#glow)" : undefined}>
              {member.name}
            </text>
            <text className="bay-state" x={lx} y={nameY + (typeof window !== "undefined" && window.innerWidth <= 640 ? 32 : 24)} textAnchor={anchor}>
              {member.label}
            </text>
          </g>
        );
      })}

      <Core name={name} line={line} mood={mood} busy={busy} speaking={speaking} onCore={onCore} />
    </svg>
  );
}
