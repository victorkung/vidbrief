const TS = /^\[?(\d{1,2}:\d{2}(?::\d{2})?)\]?$/;

function seconds(ts) {
  return ts.split(":").map(Number).reduce((acc, n) => acc * 60 + n, 0);
}

// YouTube links jump to the moment; other sources just highlight the time.
function timeLink(url, ts) {
  if (!url || !/youtube\.com|youtu\.be/.test(url)) return null;
  return `${url}${url.includes("?") ? "&" : "?"}t=${seconds(ts)}s`;
}

function Timestamp({ ts, url }) {
  const href = timeLink(url, ts);
  return href ? (
    <a className="ts" href={href} target="_blank" rel="noreferrer">[{ts}]</a>
  ) : (
    <span className="ts">[{ts}]</span>
  );
}

function inline(text, url) {
  const parts = [];
  const re = /(\*\*\[\d{1,2}:\d{2}(?::\d{2})?\]\*\*|\[\d{1,2}:\d{2}(?::\d{2})?\]|\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g;
  let last = 0;
  let m;
  let key = 0;
  while ((m = re.exec(text))) {
    if (m.index > last) parts.push(text.slice(last, m.index));
    const tok = m[0];
    const bare = tok.replace(/\*\*/g, "");
    if (TS.test(bare) && bare.startsWith("[")) {
      parts.push(<Timestamp key={key++} ts={bare.slice(1, -1)} url={url} />);
    } else if (tok.startsWith("**")) {
      parts.push(<strong key={key++}>{tok.slice(2, -2)}</strong>);
    } else if (tok.startsWith("*")) {
      parts.push(<em key={key++}>{tok.slice(1, -1)}</em>);
    } else {
      parts.push(
        <code key={key++} className="md-code">
          {tok.slice(1, -1)}
        </code>,
      );
    }
    last = m.index + tok.length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

export default function Markdown({ text, sourceUrl }) {
  const lines = String(text || "").replace(/\r\n/g, "\n").split("\n");
  const blocks = [];
  let i = 0;
  let k = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) {
      i += 1;
      continue;
    }
    if (line.startsWith("### ")) {
      blocks.push(
        <h3 key={k++} >
          {inline(line.slice(4), sourceUrl)}
        </h3>,
      );
      i += 1;
      continue;
    }
    if (line.startsWith("## ")) {
      blocks.push(
        <h2 key={k++} >
          {inline(line.slice(3), sourceUrl)}
        </h2>,
      );
      i += 1;
      continue;
    }
    if (/^\s*[-*]\s+/.test(line)) {
      const items = [];
      while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) {
        items.push(
          <li key={items.length}>{inline(lines[i].replace(/^\s*[-*]\s+/, ""), sourceUrl)}</li>,
        );
        i += 1;
      }
      blocks.push(
        <ul key={k++} >
          {items}
        </ul>,
      );
      continue;
    }
    const para = [];
    while (
      i < lines.length &&
      lines[i].trim() &&
      !lines[i].startsWith("##") &&
      !/^\s*[-*]\s+/.test(lines[i])
    ) {
      para.push(lines[i]);
      i += 1;
    }
    blocks.push(
      <p key={k++} >
        {inline(para.join(" "), sourceUrl)}
      </p>,
    );
  }
  return <div className="prose">{blocks}</div>;
}
