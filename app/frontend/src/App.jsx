import { useCallback, useEffect, useState } from "react";
import { api, formatDuration, stageLabel } from "./api";
import Markdown from "./markdown.jsx";

const ACTIVE = new Set(["queued", "running", "pending"]);

function routeFromHash() {
  const m = (window.location.hash || "#/").replace(/^#/, "").match(/^\/b\/([^/]+)/);
  return m ? { name: "brief", id: m[1] } : { name: "home" };
}

function go(hash) {
  window.location.hash = hash;
}

function shortModel(id) {
  return String(id || "").split("/").pop();
}

const LINK_RE = /https?:\/\/[^\s,<>"']+/g;

function extractLinks(text) {
  return [...new Set(String(text || "").match(LINK_RE) || [])];
}

function plural(n, word) {
  return `${n} ${word}${n === 1 ? "" : "s"}`;
}

function formatPublished(iso) {
  if (!iso) return "";
  const d = new Date(`${iso}T12:00:00`);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function formatBytes(n) {
  if (!n) return "0 MB";
  return n >= 1e9 ? `${(n / 1e9).toFixed(1)} GB` : `${Math.max(0.1, n / 1e6).toFixed(n >= 1e7 ? 0 : 1)} MB`;
}

function words(text) {
  return (String(text || "").match(/\S+/g) || []).length;
}

function statusClass(b) {
  if (b.status === "ready") return "status-ready";
  if (b.status === "error") return "status-error";
  if (ACTIVE.has(b.status)) return "status-running";
  return "";
}

function StatsLine({ brief }) {
  const s = brief.llm_stats;
  if (!s) return null;
  const llmSecs = s.seconds || 0;
  const tps = (s.condense || s.single_pass)?.generation_tps;
  const parts = [
    brief.transcript_source?.startsWith("youtube") ? "YouTube captions"
      : brief.stt_seconds != null && `Whisper ${formatDuration(brief.stt_seconds)}`,
    `${shortModel(s.model)} ${formatDuration(llmSecs)}`,
    tps && `${tps} tok/s`,
    s.chapters?.chapters && `${s.chapters.chapters} chapters`,
    s.mode === "single_pass" ? "single pass" : "chaptered",
    "$0",
  ].filter(Boolean);
  return <div className="meta">{parts.map((p) => <span key={p}>{p}</span>)}</div>;
}

export default function App() {
  const [route, setRoute] = useState(routeFromHash);
  const [health, setHealth] = useState(null);
  const [briefs, setBriefs] = useState([]);
  const [url, setUrl] = useState("");
  const [whisper, setWhisper] = useState("small");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [detail, setDetail] = useState(null);
  const [tab, setTab] = useState("brief");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    const onHash = () => {
      setRoute(routeFromHash());
      setTab("brief");
      setError("");
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const refreshList = useCallback(async () => {
    try {
      setBriefs(await api.list());
    } catch (err) {
      setError(err.message);
    }
  }, []);

  useEffect(() => {
    api.health().then((h) => {
      setHealth(h);
      if (h?.whisper_model) setWhisper(h.whisper_model);
    }).catch(() => setHealth({ ok: false }));
    refreshList();
  }, [refreshList]);

  const running = Boolean(detail && ACTIVE.has(detail.status));
  const listRunning = briefs.some((b) => ACTIVE.has(b.status));
  const queueLength = briefs.filter((b) => b.queue_position).length;
  const linkCount = extractLinks(url).length;

  useEffect(() => {
    if (route.name !== "home") return undefined;
    const id = setInterval(refreshList, listRunning ? 2000 : 15000);
    return () => clearInterval(id);
  }, [route, listRunning, refreshList]);

  useEffect(() => {
    if (route.name !== "brief") {
      setDetail(null);
      return undefined;
    }
    let stop = false;
    const load = async () => {
      try {
        const data = await api.get(route.id);
        if (!stop) setDetail(data);
      } catch (err) {
        if (!stop) setError(err.message);
      }
    };
    load();
    const id = setInterval(load, running ? 1500 : 10000);
    return () => {
      stop = true;
      clearInterval(id);
    };
  }, [route, running]);

  async function act(fn) {
    setError("");
    try {
      await fn();
      if (route.name === "brief") setDetail(await api.get(route.id));
      await refreshList();
    } catch (err) {
      setError(err.message);
    }
  }

  async function onDelete(b) {
    if (!window.confirm(`Delete "${b.title || b.url}" and its local files?`)) return;
    setError("");
    try {
      const res = await api.remove(b.id);
      setNotice(`Deleted · freed ${formatBytes(res?.freed_bytes)}`);
      setTimeout(() => setNotice(""), 4000);
      await refreshList();
      if (route.name === "brief") go("#/");
    } catch (err) {
      setError(err.message);
    }
  }

  async function onAdd(e) {
    e.preventDefault();
    const links = extractLinks(url);
    if (!links.length) {
      setError("Paste a YouTube or X video link.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      if (links.length === 1) {
        const created = await api.ingest(links[0], whisper);
        setUrl("");
        await refreshList();
        go(`#/b/${created.id}`);
        return;
      }
      // Several links: queue them all and stay on the library; they run one at a time.
      const res = await api.ingestBatch(links, whisper);
      setUrl("");
      const counts = {};
      for (const s of res.skipped) counts[s.reason] = (counts[s.reason] || 0) + 1;
      const parts = [`Queued ${plural(res.queued.length, "video")}`, ...Object.entries(counts).map(([r, n]) => `${n} ${r}`)];
      setNotice(parts.join(" · "));
      setTimeout(() => setNotice(""), 6000);
      await refreshList();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function onCopy(text) {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  const toolsOk = health?.ok && health?.yt_dlp && health?.ffmpeg;
  const tabs = [
    detail?.brief_md && ["brief", "Brief", detail.brief_md],
    detail?.condensed_md && ["condensed", "Key points", detail.condensed_md],
    detail?.transcript && ["transcript", "Transcript", detail.transcript],
  ].filter(Boolean);
  const current = tabs.find((t) => t[0] === tab) || tabs[0];

  return (
    <div className="app">
      <header className="top">
        <button type="button" className="brand" onClick={() => go("#/")}>
          <span className="brand-name">Vid<em>Brief</em></span>
        </button>
        <div className="top-meta">
          <span className={toolsOk ? "chip" : "chip warn"}>
            <i className="dot" />
            {health == null ? "connecting…" : toolsOk ? "local" : "API offline or tools missing"}
          </span>
          {queueLength > 0 && <span className="chip">{queueLength} in queue</span>}
          {health?.llm_model && <span className="chip">{shortModel(health.llm_model)}</span>}
        </div>
      </header>

      {route.name === "home" ? (
        <main className="home">
          <h1>
            Any video, <em>briefed</em>.
          </h1>
          <p className="lede">
            Paste a YouTube or X link. Whisper transcribes it and an open-source model writes the brief, all on
            this Mac. Free and private.
          </p>
          <form className="ingest" onSubmit={onAdd}>
            <textarea
              value={url}
              rows={Math.min(8, Math.max(1, url.split("\n").length))}
              onChange={(e) => setUrl(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) onAdd(e);
              }}
              placeholder="Paste one or more YouTube or X links"
              aria-label="Video links"
              autoFocus
            />
            <select value={whisper} onChange={(e) => setWhisper(e.target.value)} title="Whisper model">
              <option value="small">Whisper small · fast</option>
              <option value="medium">Whisper medium</option>
              <option value="turbo">Whisper turbo · accurate</option>
            </select>
            <button type="submit" className="btn primary" disabled={busy || !linkCount}>
              {busy ? "Adding…" : linkCount > 1 ? `Brief ${linkCount} videos` : "Brief it"}
            </button>
          </form>
          {error && <p className="hint danger-text">{error}</p>}
          {notice && <p className="hint ok-text">{notice}</p>}
          <section className="library">
            <h2 className="section-label">Library</h2>
            {briefs.length === 0 ? (
              <p className="empty">No briefs yet.</p>
            ) : (
              <ul>
                {briefs.map((b) => (
                  <li key={b.id} className="card-row">
                    <button type="button" className="card" onClick={() => go(`#/b/${b.id}`)}>
                      <div className="card-title">{b.title && b.title !== "Resolving…" ? b.title : b.url}</div>
                      <div className="meta">
                        <span className={statusClass(b)}>
                          {b.queue_position
                            ? `Queued · #${b.queue_position} in line`
                            : ACTIVE.has(b.status) ? `${stageLabel(b.stage)} ${Math.round(b.percent || 0)}%` : stageLabel(b.stage)}
                        </span>
                        {b.uploader && <span>{b.uploader}</span>}
                        {b.published && <span>{formatPublished(b.published)}</span>}
                        {b.duration != null && <span>{formatDuration(b.duration)}</span>}
                      </div>
                    </button>
                    <button type="button" className="card-delete" title="Delete brief and its files"
                      aria-label={`Delete ${b.title || "brief"}`} onClick={() => onDelete(b)}>
                      <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2"
                        strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                        <path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6M10 11v6M14 11v6" />
                      </svg>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </main>
      ) : (
        <main className="reader">
          <button type="button" className="back" onClick={() => go("#/")}>
            ← Library
          </button>
          <h1>{detail?.title || "Brief"}</h1>
          <div className="meta">
            {detail?.uploader && <span>{detail.uploader}</span>}
            {detail?.published && <span>Published {formatPublished(detail.published)}</span>}
            {detail?.duration != null && <span>{formatDuration(detail.duration)}</span>}
            {detail?.url && (
              <a href={detail.url} target="_blank" rel="noreferrer">
                Source ↗
              </a>
            )}
          </div>
          {detail?.status === "ready" && <div style={{ marginTop: 6 }}><StatsLine brief={detail} /></div>}

          <div className="reader-actions">
            {running && (
              <button type="button" className="btn small" onClick={() => act(() => api.cancel(detail.id))}>
                Cancel
              </button>
            )}
            {(detail?.status === "error" || detail?.status === "cancelled") && (
              <button type="button" className="btn small primary" onClick={() => act(() => api.retry(detail.id))}>
                Retry
              </button>
            )}
            {detail?.status === "ready" && (
              <>
                <button type="button" className="btn small" onClick={() => act(() => api.resummarize(detail.id, "chaptered"))}>
                  Re-summarize
                </button>
                <button type="button" className="btn small" onClick={() => act(() => api.resummarize(detail.id, "single_pass"))}>
                  Re-summarize (single pass)
                </button>
              </>
            )}
            {detail && !running && (
              <button
                type="button"
                className="btn small"
                onClick={() => onDelete(detail)}
              >
                Delete
              </button>
            )}
          </div>

          {detail && detail.status !== "ready" && (
            <div className="progress">
              <div className="progress-bar">
                <i style={{ width: `${Math.max(2, Number(detail.percent) || 0)}%` }} />
              </div>
              <div className="progress-label">
                {stageLabel(detail.stage)}
                {detail.detail ? ` · ${detail.detail}` : ""}
              </div>
              {detail.error && <p className="hint danger-text">{detail.error}</p>}
            </div>
          )}

          {error && <p className="hint danger-text">{error}</p>}

          {current && (
            <>
              <div className="tabs">
                {tabs.map(([key, label]) => (
                  <button key={key} type="button" className={current[0] === key ? "on" : ""} onClick={() => setTab(key)}>
                    {label}
                  </button>
                ))}
              </div>
              <div className="tab-bar">
                <div className="meta">
                  <span>{Math.max(1, Math.round(words(current[2]) / 230))} min read</span>
                  <span>{words(current[2]).toLocaleString()} words</span>
                </div>
                <button type="button" className="btn small" onClick={() => onCopy(current[2])}>
                  {copied ? "Copied" : `Copy ${current[1].toLowerCase()}`}
                </button>
              </div>
              {current[0] === "transcript" ? (
                <pre className="transcript">{current[2]}</pre>
              ) : (
                <Markdown text={current[2]} sourceUrl={detail?.url} />
              )}
            </>
          )}
        </main>
      )}
    </div>
  );
}
