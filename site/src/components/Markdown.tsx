import type { ReactNode } from "react";

const TOKEN = /(\[\d{1,2}:\d{2}(?::\d{2})?\]|\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g;

function seconds(ts: string): number {
  return ts.split(":").map(Number).reduce((acc, n) => acc * 60 + n, 0);
}

function inline(text: string, videoUrl?: string): ReactNode[] {
  const out: ReactNode[] = [];
  let last = 0;
  let key = 0;
  for (const m of text.matchAll(TOKEN)) {
    const tok = m[0];
    const at = m.index ?? 0;
    if (at > last) out.push(text.slice(last, at));
    if (tok.startsWith("[")) {
      const ts = tok.slice(1, -1);
      out.push(
        videoUrl ? (
          <a key={key++} className="ts" href={`${videoUrl}&t=${seconds(ts)}s`} target="_blank" rel="noreferrer">
            {tok}
          </a>
        ) : (
          <span key={key++} className="ts">{tok}</span>
        ),
      );
    } else if (tok.startsWith("**")) out.push(<strong key={key++}>{tok.slice(2, -2)}</strong>);
    else if (tok.startsWith("`")) out.push(<code key={key++}>{tok.slice(1, -1)}</code>);
    else out.push(<em key={key++}>{tok.slice(1, -1)}</em>);
    last = at + tok.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

/** Just enough markdown for a VidBrief brief: ##/### headings, bullets, paragraphs, inline marks. */
export default function Markdown({ text, videoUrl }: { text: string; videoUrl?: string }) {
  const lines = text.replace(/\r\n/g, "\n").split("\n");
  const blocks: ReactNode[] = [];
  let i = 0;
  let k = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) {
      i += 1;
    } else if (line.startsWith("### ")) {
      blocks.push(<h3 key={k++}>{inline(line.slice(4), videoUrl)}</h3>);
      i += 1;
    } else if (line.startsWith("## ")) {
      blocks.push(<h2 key={k++}>{inline(line.slice(3), videoUrl)}</h2>);
      i += 1;
    } else if (/^\s*[-*]\s+/.test(line)) {
      const items: ReactNode[] = [];
      while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) {
        items.push(<li key={items.length}>{inline(lines[i].replace(/^\s*[-*]\s+/, ""), videoUrl)}</li>);
        i += 1;
      }
      blocks.push(<ul key={k++}>{items}</ul>);
    } else {
      const para: string[] = [];
      while (i < lines.length && lines[i].trim() && !lines[i].startsWith("#") && !/^\s*[-*]\s+/.test(lines[i])) {
        para.push(lines[i]);
        i += 1;
      }
      const joined = para.join(" ");
      const isMeta = blocks.length === 0 && /^\*.*·.*\*$/.test(joined);
      blocks.push(<p key={k++} className={isMeta ? "meta" : undefined}>{inline(isMeta ? joined.slice(1, -1) : joined, videoUrl)}</p>);
    }
  }
  return <div className="prose-brief">{blocks}</div>;
}
