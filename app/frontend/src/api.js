const jsonHeaders = { "Content-Type": "application/json" };

async function request(path, opts = {}) {
  const res = await fetch(path, opts);
  if (!res.ok) {
    let msg = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail) msg = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      try {
        const text = await res.text();
        if (text) msg = text.slice(0, 400);
      } catch {
        /* ignore */
      }
    }
    throw new Error(msg);
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  health: () => request("/api/health"),
  list: () => request("/api/briefs"),
  get: (id) => request(`/api/briefs/${id}`),
  ingest: (url, whisperModel) =>
    request("/api/ingest", {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify({ url, whisper_model: whisperModel }),
    }),
  ingestBatch: (urls, whisperModel) =>
    request("/api/ingest/batch", {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify({ urls, whisper_model: whisperModel }),
    }),
  resummarize: (id, mode) =>
    request(`/api/briefs/${id}/resummarize`, {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify({ mode }),
    }),
  voices: () => request("/api/voices"),
  setVoice: (voice) =>
    request("/api/settings/voice", { method: "PUT", headers: jsonHeaders, body: JSON.stringify({ voice }) }),
  voice: (id) => request(`/api/briefs/${id}/voice`, { method: "POST" }),
  cancel: (id) => request(`/api/briefs/${id}/cancel`, { method: "POST" }),
  retry: (id) =>
    request(`/api/briefs/${id}/retry`, {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify({}),
    }),
  remove: (id) => request(`/api/briefs/${id}?files=true`, { method: "DELETE" }),
};

export function formatDuration(seconds) {
  if (seconds == null || Number.isNaN(Number(seconds))) return "";
  const total = Math.max(0, Math.round(Number(seconds)));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  if (h) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return `${m}:${String(s).padStart(2, "0")}`;
}

export function stageLabel(stage) {
  return (
    {
      queued: "Queued",
      resolving: "Resolving",
      captions: "Fetching captions",
      downloading: "Downloading",
      transcribing: "Transcribing",
      condensing: "Condensing",
      chapters: "Planning chapters",
      writing: "Writing chapters",
      synthesizing: "Writing summary",
      voicing: "Recording audio",
      done: "Ready",
      error: "Error",
      cancelled: "Cancelled",
      idle: "Idle",
    }[stage] || stage || ""
  );
}
