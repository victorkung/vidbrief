import { useEffect, useState } from "react";
import {
  ArrowRight,
  AudioLines,
  Check,
  Clock,
  Copy,
  FileText,
  Github,
  Headphones,
  Layers,
  Link2,
  ListChecks,
  Lock,
  SlidersHorizontal,
  Sparkles,
  Zap,
} from "lucide-react";
import Markdown from "./components/Markdown";
import Player from "./components/Player";
import karpathy from "./content/karpathy.md?raw";

const GITHUB = "https://github.com/victorkung/vidbrief";
const SAMPLE_VIDEO = "https://www.youtube.com/watch?v=LCEmiRjPEtQ";
const QUICKSTART = `brew install python yt-dlp ffmpeg node espeak-ng
git clone https://github.com/victorkung/vidbrief.git
cd vidbrief && ./scripts/setup.sh && ./scripts/dev.sh`;

function Wordmark() {
  return (
    <span className="font-display text-[28px] leading-none tracking-tight">
      Vid<em className="gold-text">Brief</em>
    </span>
  );
}

function Nav() {
  return (
    <header className="sticky top-0 z-20 border-b border-line/70 bg-root/80 backdrop-blur">
      <nav className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6" aria-label="Main">
        <a href="#top" aria-label="VidBrief home"><Wordmark /></a>
        <div className="hidden items-center gap-7 text-sm text-ink-2 md:flex">
          <a className="hover:text-ink" href="#how">How it works</a>
          <a className="hover:text-ink" href="#sample">Sample</a>
          <a className="hover:text-ink" href="#features">Features</a>
          <a className="hover:text-ink" href="#faq">FAQ</a>
        </div>
        <a
          href={GITHUB}
          className="inline-flex items-center gap-2 rounded-full border border-line bg-raised px-4 py-2 text-sm font-medium hover:bg-raised-2"
        >
          <Github size={16} /> <span className="hidden sm:inline">View on</span> GitHub
        </a>
      </nav>
    </header>
  );
}

function Hero() {
  return (
    <section id="top" className="hero-aura relative">
      <div className="mx-auto max-w-6xl px-4 pt-16 pb-12 text-center sm:px-6 sm:pt-24">
        <p className="mx-auto mb-6 inline-flex items-center gap-2 rounded-full border border-line bg-card px-3 py-1 text-xs text-ink-2">
          <Sparkles size={13} className="text-gold" /> Free and open source · runs on your Mac
        </p>
        <h1 className="font-display text-6xl leading-[0.95] tracking-tight sm:text-8xl">
          Any video, <em className="gold-text pr-2">briefed.</em>
        </h1>
        <p className="mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-ink-2 sm:text-xl">
          Paste a YouTube or X link. VidBrief writes a tight, timestamped brief, and reads it to you, entirely on
          your Mac. No API keys, no subscriptions, nothing sent to the cloud.
        </p>
        <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
          <a href={GITHUB} className="gold-bg glow inline-flex items-center gap-2 rounded-full px-6 py-3 font-bold text-black hover:brightness-105">
            <Github size={18} /> Get it on GitHub
          </a>
          <a href="#sample" className="inline-flex items-center gap-2 rounded-full border border-line bg-raised px-6 py-3 font-medium hover:bg-raised-2">
            See a sample <ArrowRight size={16} />
          </a>
        </div>
        <div className="mx-auto mt-14 max-w-5xl overflow-hidden rounded-2xl border border-line bg-card shadow-[0_30px_80px_rgba(0,0,0,0.6)]">
          <div className="flex items-center gap-1.5 border-b border-line px-4 py-3" aria-hidden="true">
            <span className="size-2.5 rounded-full bg-raised-2" />
            <span className="size-2.5 rounded-full bg-raised-2" />
            <span className="size-2.5 rounded-full bg-raised-2" />
            <span className="ml-3 text-xs text-ink-3">127.0.0.1:5174</span>
          </div>
          <img
            src="/img/brief.webp"
            width={2560}
            height={2200}
            alt="A VidBrief brief of Andrej Karpathy's talk: overview, context, timestamped chapters, and a Listen bar"
            className="block h-auto w-full"
            fetchPriority="high"
          />
        </div>
      </div>
      <div className="border-y border-line bg-card/60">
        <ul className="mx-auto grid max-w-6xl grid-cols-2 gap-4 px-4 py-5 text-sm text-ink-2 sm:px-6 md:grid-cols-4">
          {["Free forever", "No API keys", "Nothing leaves your Mac", "Open source (MIT)"].map((t) => (
            <li key={t} className="flex items-center justify-center gap-2">
              <Check size={16} className="text-gold" /> {t}
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

const STEPS = [
  { icon: Link2, title: "Paste links", body: "One YouTube or X link, or a whole list. They queue up and run one at a time." },
  { icon: FileText, title: "Get the transcript", body: "YouTube captions in seconds. No captions? Whisper transcribes on your Mac." },
  { icon: Layers, title: "Write the brief", body: "A local model condenses the talk, plans chapters by topic, and writes each one. Code assembles the structure." },
  { icon: Headphones, title: "Listen", body: "A natural open-source voice (Kokoro) reads the brief aloud. Play at up to 2× or download the MP3." },
];

function HowItWorks() {
  return (
    <section id="how" className="section-anchor mx-auto max-w-6xl px-4 py-24 sm:px-6">
      <h2 className="font-display text-5xl tracking-tight sm:text-6xl">How it works</h2>
      <p className="mt-4 max-w-2xl text-lg text-ink-2">
        Four small steps, each sized for a model that runs on a laptop.
      </p>
      <ol className="mt-12 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {STEPS.map(({ icon: Icon, title, body }, i) => (
          <li key={title} className="rounded-2xl border border-line bg-card p-6">
            <div className="flex items-center justify-between">
              <span className="grid size-10 place-items-center rounded-xl bg-raised text-gold"><Icon size={20} /></span>
              <span className="font-display text-3xl text-ink-3">{i + 1}</span>
            </div>
            <h3 className="mt-5 text-lg font-semibold">{title}</h3>
            <p className="mt-2 leading-relaxed text-ink-2">{body}</p>
          </li>
        ))}
      </ol>
      <p className="mt-6 text-sm text-ink-3">
        One model runs at a time and unloads after each step, so it all fits on a 16 GB Mac.
      </p>
    </section>
  );
}

function Sample() {
  return (
    <section id="sample" className="section-anchor border-y border-line bg-card/40">
      <div className="mx-auto grid max-w-6xl gap-12 px-4 py-24 sm:px-6 lg:grid-cols-[1fr_1.15fr] [&>*]:min-w-0">
        <div>
          <h2 className="font-display text-5xl tracking-tight sm:text-6xl">A real brief</h2>
          <p className="mt-4 text-lg leading-relaxed text-ink-2">
            Andrej Karpathy's 40-minute talk <em>Software Is Changing (Again)</em>, briefed in about four minutes
            on a MacBook. Untouched output: read it, or press play to hear the voice.
          </p>
          <div className="mt-8">
            <Player src="/sample/karpathy.mp3" label="Listen to this brief" />
          </div>
          <div className="mt-8 grid grid-cols-2 gap-3">
            <figure className="overflow-hidden rounded-xl border border-line">
              <img src="/img/library.webp" width={2560} height={1520} loading="lazy" alt="Library with a queue of videos" className="aspect-[4/3] w-full object-cover object-top" />
              <figcaption className="px-3 py-2 text-xs text-ink-3">Queue several videos at once</figcaption>
            </figure>
            <figure className="overflow-hidden rounded-xl border border-line">
              <img src="/img/key-points.webp" width={2560} height={2000} loading="lazy" alt="Key points grouped by chapter" className="aspect-[4/3] w-full object-cover object-top" />
              <figcaption className="px-3 py-2 text-xs text-ink-3">Every key point, by chapter</figcaption>
            </figure>
          </div>
        </div>
        <article className="max-h-[760px] overflow-y-auto rounded-2xl border border-line bg-root p-6 sm:p-8" aria-label="Sample brief">
          <Markdown text={karpathy} videoUrl={SAMPLE_VIDEO} />
        </article>
      </div>
    </section>
  );
}

const FEATURES = [
  { icon: ListChecks, title: "Chapters with timestamps", body: "Topic-based chapters, each bullet linked to the exact moment in the video." },
  { icon: AudioLines, title: "28 voices", body: "American and British voices. Preview them, pick one, listen at 1–2×." },
  { icon: Layers, title: "Batch it", body: "Paste a list of links before bed. They queue and process one at a time." },
  { icon: SlidersHorizontal, title: "You decide what matters", body: "A plain-English priorities file tells the model what to keep and what to skip." },
  { icon: Lock, title: "Private by design", body: "Transcripts, briefs, and audio stay on your Mac. No accounts, no telemetry." },
  { icon: Zap, title: "Fast enough", body: "About five minutes to summarize an hour-long video on an M5 with 16 GB." },
];

function Features() {
  return (
    <section id="features" className="section-anchor mx-auto max-w-6xl px-4 py-24 sm:px-6">
      <h2 className="font-display text-5xl tracking-tight sm:text-6xl">Built for staying current</h2>
      <p className="mt-4 max-w-2xl text-lg text-ink-2">
        Founder interviews, market roundups, conference talks: get the actionable parts without the two hours.
      </p>
      <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {FEATURES.map(({ icon: Icon, title, body }) => (
          <div key={title} className="rounded-2xl border border-line bg-card p-6">
            <Icon size={22} className="text-gold" />
            <h3 className="mt-4 text-lg font-semibold">{title}</h3>
            <p className="mt-2 leading-relaxed text-ink-2">{body}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

function Why() {
  return (
    <section className="border-y border-line bg-card/40">
      <div className="mx-auto max-w-3xl px-4 py-24 sm:px-6">
        <h2 className="font-display text-5xl tracking-tight sm:text-6xl">Why I built it</h2>
        <div className="mt-8 space-y-5 text-lg leading-relaxed text-ink-2">
          <p>
            I built <a className="text-gold hover:underline" href="https://podbrief.io">PodBrief</a> to turn podcasts
            and videos into written and audio briefs. It runs on commercial APIs for transcription, summaries and
            voice, and I loved using it. But every brief costs money and sends content to someone else's servers.
          </p>
          <p>
            Open-source models have gotten good enough to do the same job on a laptop. VidBrief is that: the brief
            format I refined in PodBrief, rebuilt on Whisper, a local language model and Kokoro, running entirely
            on your Mac. It's free, it's private, and the code is yours to change.
          </p>
        </div>
      </div>
    </section>
  );
}

function GetStarted() {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    await navigator.clipboard.writeText(QUICKSTART);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  return (
    <section id="start" className="section-anchor mx-auto max-w-6xl px-4 py-24 sm:px-6">
      <div className="grid gap-10 lg:grid-cols-[1fr_1.3fr] lg:items-start [&>*]:min-w-0">
        <div>
          <h2 className="font-display text-5xl tracking-tight sm:text-6xl">Get started</h2>
          <ul className="mt-6 space-y-3 text-ink-2">
            {[
              "Mac with Apple Silicon (M1 or later)",
              "16 GB memory recommended",
              "About 8 GB of disk for models",
              "Homebrew installed",
            ].map((t) => (
              <li key={t} className="flex items-center gap-3"><Check size={18} className="text-gold" /> {t}</li>
            ))}
          </ul>
        </div>
        <div>
          <div className="overflow-hidden rounded-2xl border border-line bg-card">
            <div className="flex items-center justify-between border-b border-line px-4 py-2.5 text-xs text-ink-3">
              <span>Terminal</span>
              <button type="button" onClick={copy} className="inline-flex cursor-pointer items-center gap-1.5 rounded-full px-2 py-1 hover:bg-raised hover:text-ink">
                {copied ? <Check size={14} /> : <Copy size={14} />} {copied ? "Copied" : "Copy"}
              </button>
            </div>
            <pre className="overflow-x-auto p-5 text-sm leading-7"><code>{QUICKSTART}</code></pre>
          </div>
          <p className="mt-4 flex items-center gap-2 text-sm text-ink-2">
            <Clock size={15} className="text-gold" /> First setup downloads about 7.8 GB of models, then opens at
            127.0.0.1:5174.{" "}
            <a className="text-gold hover:underline" href={`${GITHUB}#quick-start`}>Full instructions</a>
          </p>
        </div>
      </div>
    </section>
  );
}

const FAQS = [
  ["Does it cost anything?", "No. It's free and open source (MIT). Everything runs on your own Mac, so there are no API bills or subscriptions."],
  ["Which Macs does it run on?", "Apple Silicon Macs (M1 or later). 16 GB of memory is recommended; the default model peaks at about 6.7 GB."],
  ["Windows or Linux?", "Not yet. VidBrief uses MLX, Apple's machine learning framework, which runs only on Apple Silicon."],
  ["What can I summarize?", "YouTube and X (Twitter) video links today, including long podcasts and livestream recordings."],
  ["How accurate is it?", "Briefs use only what's said in the video, and every timestamp is checked against the transcript. A local model is less polished than the biggest cloud models, and names can occasionally be misheard, so treat it as a fast first read."],
  ["What data leaves my Mac?", "Only what's needed to fetch the video, its captions and its title, plus a one-time model download. Transcripts, briefs and audio never leave your machine."],
  ["Can I change the voice or what it focuses on?", "Yes. Pick any of 28 voices in the app. Edit one plain-English file to tell it what's important to you, and override any prompt."],
];

function FAQ() {
  return (
    <section id="faq" className="section-anchor border-t border-line">
      <div className="mx-auto max-w-3xl px-4 py-24 sm:px-6">
        <h2 className="font-display text-5xl tracking-tight sm:text-6xl">Questions</h2>
        <div className="mt-10 divide-y divide-line border-y border-line">
          {FAQS.map(([q, a]) => (
            <details key={q} className="group py-5">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 text-lg font-medium">
                {q}
                <span className="text-gold transition group-open:rotate-45" aria-hidden="true">+</span>
              </summary>
              <p className="mt-3 leading-relaxed text-ink-2">{a}</p>
            </details>
          ))}
        </div>
      </div>
    </section>
  );
}

function Footer() {
  return (
    <footer className="border-t border-line">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-6 px-4 py-10 text-sm text-ink-3 sm:flex-row sm:px-6">
        <div className="flex items-center gap-3"><Wordmark /> <span>Any video, briefed.</span></div>
        <div className="flex flex-wrap items-center justify-center gap-5">
          <a className="hover:text-ink" href={GITHUB}>GitHub</a>
          <a className="hover:text-ink" href="https://podbrief.io">PodBrief</a>
          <span>MIT license</span>
        </div>
      </div>
    </footer>
  );
}

export default function App() {
  // The page renders after load, so the browser's own jump to #anchor finds nothing; do it here.
  useEffect(() => {
    if (window.location.hash) document.querySelector(window.location.hash)?.scrollIntoView();
  }, []);
  return (
    <>
      <Nav />
      <main>
        <Hero />
        <HowItWorks />
        <Sample />
        <Features />
        <Why />
        <GetStarted />
        <FAQ />
      </main>
      <Footer />
    </>
  );
}
