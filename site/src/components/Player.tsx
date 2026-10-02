import { useEffect, useRef, useState } from "react";
import { Pause, Play } from "lucide-react";

const SPEEDS = [1, 1.25, 1.5, 2];

function clock(s: number): string {
  if (!Number.isFinite(s)) return "0:00";
  const t = Math.max(0, Math.round(s));
  return `${Math.floor(t / 60)}:${String(t % 60).padStart(2, "0")}`;
}

/** The same Listen bar the app shows, playing a real Kokoro recording. */
export default function Player({ src, label }: { src: string; label: string }) {
  const ref = useRef<HTMLAudioElement>(null);
  const [playing, setPlaying] = useState(false);
  const [time, setTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [speed, setSpeed] = useState(1);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const on = (type: string, fn: () => void) => {
      el.addEventListener(type, fn);
      return () => el.removeEventListener(type, fn);
    };
    const offs = [
      on("timeupdate", () => setTime(el.currentTime)),
      on("loadedmetadata", () => setDuration(el.duration)),
      on("play", () => setPlaying(true)),
      on("pause", () => setPlaying(false)),
      on("ended", () => setPlaying(false)),
    ];
    return () => offs.forEach((off) => off());
  }, []);

  useEffect(() => {
    if (ref.current) ref.current.playbackRate = speed;
  }, [speed]);

  const toggle = () => {
    const el = ref.current;
    if (!el) return;
    if (el.paused) void el.play();
    else el.pause();
  };
  const pct = duration ? (100 * time) / duration : 0;

  return (
    <div className="flex flex-wrap items-center gap-4 rounded-2xl border border-line bg-card p-3 sm:flex-nowrap sm:p-4">
      <audio ref={ref} src={src} preload="metadata" />
      <button
        type="button"
        onClick={toggle}
        aria-label={playing ? "Pause" : "Play sample"}
        className="grid size-12 shrink-0 cursor-pointer place-items-center rounded-full bg-accent text-white transition hover:bg-accent-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
      >
        {playing ? <Pause size={20} fill="currentColor" /> : <Play size={20} fill="currentColor" className="ml-0.5" />}
      </button>
      <div className="min-w-0 flex-1">
        <div className="mb-2 flex justify-between gap-3 text-sm">
          <span className="truncate">{playing ? "Listening" : time > 0 ? "Paused" : label}</span>
          <span className="shrink-0 tabular-nums text-ink-2">
            {clock(time)} / {clock(duration)}
          </span>
        </div>
        <input
          type="range"
          className="scrub w-full"
          min={0}
          max={duration || 0}
          step={0.1}
          value={time}
          aria-label="Seek"
          style={{ ["--pct" as string]: `${pct}%` }}
          onChange={(e) => {
            if (ref.current) ref.current.currentTime = Number(e.target.value);
          }}
        />
      </div>
      <div className="flex shrink-0 gap-0.5 rounded-full bg-raised p-1" role="radiogroup" aria-label="Playback speed">
        {SPEEDS.map((s) => (
          <button
            key={s}
            type="button"
            role="radio"
            aria-checked={speed === s}
            onClick={() => setSpeed(s)}
            className={`cursor-pointer rounded-full px-3 py-1 text-xs font-medium transition ${
              speed === s ? "bg-raised-2 text-ink" : "text-ink-2 hover:text-ink"
            }`}
          >
            {s}×
          </button>
        ))}
      </div>
    </div>
  );
}
