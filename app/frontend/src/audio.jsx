import { useEffect, useRef, useState } from "react";
import { formatDuration } from "./api";

const SPEEDS = [1, 1.25, 1.5, 2];

function savedSpeed() {
  try {
    const v = Number(localStorage.getItem("vidbrief.speed"));
    return SPEEDS.includes(v) ? v : 1;
  } catch {
    return 1;
  }
}

/** Listen bar: play/pause, scrub, speed, download. Uses the native <audio> element underneath. */
export default function AudioBar({ brief }) {
  const ref = useRef(null);
  const [playing, setPlaying] = useState(false);
  const [time, setTime] = useState(0);
  const [duration, setDuration] = useState(brief.audio_seconds || 0);
  const [speed, setSpeed] = useState(savedSpeed);
  const src = `/api/briefs/${brief.id}/audio`;

  useEffect(() => {
    const el = ref.current;
    if (!el) return undefined;
    el.playbackRate = speed;
    const onTime = () => setTime(el.currentTime);
    const onMeta = () => setDuration(el.duration || brief.audio_seconds || 0);
    const onPlay = () => setPlaying(true);
    const onPause = () => setPlaying(false);
    el.addEventListener("timeupdate", onTime);
    el.addEventListener("loadedmetadata", onMeta);
    el.addEventListener("play", onPlay);
    el.addEventListener("pause", onPause);
    el.addEventListener("ended", onPause);
    return () => {
      el.removeEventListener("timeupdate", onTime);
      el.removeEventListener("loadedmetadata", onMeta);
      el.removeEventListener("play", onPlay);
      el.removeEventListener("pause", onPause);
      el.removeEventListener("ended", onPause);
    };
  }, [src]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (ref.current) ref.current.playbackRate = speed;
    try {
      localStorage.setItem("vidbrief.speed", String(speed));
    } catch {
      /* private mode */
    }
  }, [speed]);

  useEffect(() => {
    // Control Center / media keys show what's playing.
    if (!("mediaSession" in navigator) || typeof window.MediaMetadata === "undefined") return;
    navigator.mediaSession.metadata = new window.MediaMetadata({
      title: brief.title || "VidBrief",
      artist: brief.uploader || "",
      album: "VidBrief",
    });
  }, [brief.title, brief.uploader]);

  function toggle() {
    const el = ref.current;
    if (!el) return;
    if (el.paused) el.play();
    else el.pause();
  }

  function seek(e) {
    const el = ref.current;
    if (!el) return;
    el.currentTime = Number(e.target.value);
    setTime(el.currentTime);
  }

  const pct = duration ? Math.min(100, (100 * time) / duration) : 0;

  return (
    <div className="listen">
      <audio ref={ref} src={src} preload="metadata" />
      <button type="button" className="listen-play" onClick={toggle} aria-label={playing ? "Pause" : "Listen"}>
        {playing ? (
          <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
            <rect x="6" y="5" width="4" height="14" rx="1" fill="currentColor" />
            <rect x="14" y="5" width="4" height="14" rx="1" fill="currentColor" />
          </svg>
        ) : (
          <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
            <path d="M8 5.5v13a1 1 0 0 0 1.5.86l10.5-6.5a1 1 0 0 0 0-1.72L9.5 4.64A1 1 0 0 0 8 5.5Z" fill="currentColor" />
          </svg>
        )}
      </button>
      <div className="listen-main">
        <div className="listen-label">
          <span>{playing ? "Listening" : time > 0 ? "Paused" : "Listen to this brief"}</span>
          <span className="listen-time">
            {formatDuration(time)} / {formatDuration(duration)}
          </span>
        </div>
        <input
          className="listen-scrub"
          type="range"
          min="0"
          max={duration || 0}
          step="0.1"
          value={time}
          onChange={seek}
          aria-label="Seek"
          style={{ "--pct": `${pct}%` }}
        />
      </div>
      <div className="seg listen-speed" role="radiogroup" aria-label="Playback speed">
        {SPEEDS.map((s) => (
          <button key={s} type="button" role="radio" aria-checked={speed === s} className={speed === s ? "on" : ""}
            onClick={() => setSpeed(s)}>
            {s}×
          </button>
        ))}
      </div>
      <a className="listen-download" href={src} download aria-label="Download audio" title="Download MP3">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2"
          strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M12 4v11M7 10l5 5 5-5M5 20h14" />
        </svg>
      </a>
    </div>
  );
}
