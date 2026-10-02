import { useEffect, useRef, useState } from "react";
import { api } from "./api";

function label(v) {
  return `${v.name} · ${v.accent} ${v.gender === "female" ? "woman" : "man"}`;
}

/** Default voice for new audio, with a short preview for each voice. */
export default function VoicePicker({ onChange }) {
  const [voices, setVoices] = useState([]);
  const [current, setCurrent] = useState(null);
  const [open, setOpen] = useState(false);
  const [previewing, setPreviewing] = useState(null);
  const [loading, setLoading] = useState(null);
  const player = useRef(null);

  useEffect(() => {
    api.voices().then((r) => {
      setVoices(r.voices);
      setCurrent(r.current);
    }).catch(() => {});
    return () => player.current?.pause();
  }, []);

  async function choose(id) {
    const r = await api.setVoice(id);
    setCurrent(r.current);
    onChange?.(r.current);
  }

  function preview(id) {
    if (player.current) player.current.pause();
    if (previewing === id) {
      setPreviewing(null);
      return;
    }
    const audio = new Audio(`/api/voices/${id}/preview`);
    player.current = audio;
    setLoading(id);
    audio.addEventListener("playing", () => { setLoading(null); setPreviewing(id); });
    audio.addEventListener("ended", () => setPreviewing(null));
    audio.addEventListener("error", () => { setLoading(null); setPreviewing(null); });
    audio.play().catch(() => setLoading(null));
  }

  const selected = voices.find((v) => v.id === current);
  const groups = [
    ["Recommended", voices.filter((v) => v.recommended)],
    ["American", voices.filter((v) => v.accent === "American" && !v.recommended)],
    ["British", voices.filter((v) => v.accent === "British" && !v.recommended)],
  ];

  return (
    <div className="voice">
      <div className="whisper-row">
        <span className="whisper-label">Voice</span>
        <button type="button" className="voice-current" onClick={() => setOpen(!open)} aria-expanded={open}>
          {selected ? label(selected) : "…"}
          <span aria-hidden="true">{open ? "▴" : "▾"}</span>
        </button>
        <span className="whisper-help">Reads each brief aloud. First preview of a voice takes a few seconds.</span>
      </div>
      {open && (
        <div className="voice-panel">
          {groups.map(([name, list]) => list.length > 0 && (
            <div key={name} className="voice-group">
              <div className="section-label">{name}</div>
              <div className="voice-list">
                {list.map((v) => (
                  <div key={v.id} className={`voice-chip${v.id === current ? " on" : ""}`}>
                    <button type="button" className="voice-pick" onClick={() => choose(v.id)} aria-pressed={v.id === current}>
                      <span className="voice-name">{v.name}</span>
                      <span className="voice-meta">{v.accent === "British" ? "UK" : "US"} · {v.gender === "female" ? "woman" : "man"}</span>
                    </button>
                    <button type="button" className="voice-preview" onClick={() => preview(v.id)}
                      aria-label={`Preview ${v.name}`} title="Preview">
                      {loading === v.id ? "…" : previewing === v.id ? "■" : "▶"}
                    </button>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
