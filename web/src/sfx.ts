// Interface sounds, made on the spot by the browser: no sound files. Quiet on purpose, and silent when voice is off.
let audio: AudioContext | null = null;
let enabled = false;

export const setSounds = (on: boolean) => {
  enabled = on;
  if (on && !audio) audio = new AudioContext();
};

function tone(freq: number, seconds: number, type: OscillatorType = "sine", gain = 0.04, delay = 0, slideTo?: number) {
  if (!enabled || !audio) return;
  const start = audio.currentTime + delay;
  const osc = audio.createOscillator();
  const level = audio.createGain();
  osc.type = type;
  osc.frequency.setValueAtTime(freq, start);
  if (slideTo) osc.frequency.exponentialRampToValueAtTime(slideTo, start + seconds);
  level.gain.setValueAtTime(0, start);
  level.gain.linearRampToValueAtTime(gain, start + 0.01);
  level.gain.exponentialRampToValueAtTime(0.0001, start + seconds);
  osc.connect(level).connect(audio.destination);
  osc.start(start);
  osc.stop(start + seconds + 0.05);
}

export const sfx = {
  /** Powering up: a rising sweep and a soft chord. */
  boot: () => {
    tone(90, 1.1, "sawtooth", 0.025, 0, 720);
    [392, 523, 784].forEach((f, i) => tone(f, 1.2, "sine", 0.03, 0.9 + i * 0.05));
  },
  /** One bay coming online during the roll call. */
  online: (i: number) => tone(480 + i * 45, 0.09, "triangle", 0.03),
  /** A report arriving from the crew. */
  blip: () => tone(1320, 0.07, "sine", 0.022),
  /** You sent a message. */
  send: () => tone(880, 0.05, "sine", 0.02, 0, 1200),
  /** Your decision is needed. */
  alert: () => {
    tone(660, 0.16, "square", 0.025);
    tone(880, 0.22, "square", 0.025, 0.2);
  },
  /** Resolved. */
  resolved: () => [523, 659, 784, 1046].forEach((f, i) => tone(f, 0.25, "triangle", 0.035, i * 0.09)),
  /** Blocked, refused or failed. */
  blocked: () => tone(170, 0.32, "sawtooth", 0.03),
};
