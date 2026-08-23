import {
  ArrowRight,
  FileSpreadsheet,
  Database,
  Upload,
  MessageSquareText,
  LineChart,
  Lock,
  ShieldCheck,
  Zap,
  Sparkles,
  Compass,
} from 'lucide-react';
import { Logo } from './Logo';
import { ThemeToggle } from './ThemeToggle';
import { FlightPath } from './FlightPath';

const STEPS = [
  {
    icon: Upload,
    title: 'Upload your data',
    desc: "Drop a single CSV or Excel file. If it's a multi-sheet workbook, just pick the one sheet you want to analyze.",
  },
  {
    icon: MessageSquareText,
    title: 'Ask in plain English',
    desc: 'Type a question the way you would ask a colleague. No SQL, no formulas, no pivot tables to configure.',
  },
  {
    icon: LineChart,
    title: 'Get answers & charts',
    desc: 'DataPilot figures out the right analysis, runs it directly against your data, and explains what it finds — with charts when useful, plus a downloadable report you can share.',
  },
];

const FEATURES = [
  {
    icon: Database,
    title: 'No hallucinated numbers',
    desc: 'The AI decides what to analyze; a fixed set of tested operations actually computes it — never arbitrary code, never a made-up figure.',
  },
  {
    icon: Compass,
    title: 'Guided starting point',
    desc: "Not sure what to ask? Explore hands you ready-made questions tailored to your exact dataset's columns before you type a thing.",
  },
  {
    icon: LineChart,
    title: 'Charts that match the question',
    desc: 'Bar, line, scatter, or table — the visualization is chosen to fit the answer, not the other way around.',
  },
  {
    icon: FileSpreadsheet,
    title: 'CSV & Excel, no cleanup',
    desc: 'Messy headers, blank rows, and mixed types are handled on import. Your file works as-is.',
  },
  {
    icon: Zap,
    title: 'Instant results',
    desc: 'Most questions return in seconds. Iterate on follow-ups without re-uploading or re-explaining.',
  },
  {
    icon: ShieldCheck,
    title: 'Private by default',
    desc: 'Your file lives in your session and is deleted the moment you leave — or automatically if you walk away. Nothing lingers, nothing is trained on.',
  },
];

const EXAMPLES = [
  {
    tag: 'Sales',
    question: 'Which region grew fastest last quarter?',
    answer: 'West region, up 23% QoQ — driven by enterprise renewals.',
  },
  {
    tag: 'Operations',
    question: 'Where are our fulfillment delays concentrated?',
    answer: '62% of late shipments originate from two warehouses in the Midwest.',
  },
  {
    tag: 'Finance',
    question: 'What is our average contract value by tier?',
    answer: 'Enterprise $48k, Growth $12k, Starter $1.8k — median across the last 90 days.',
  },
];

export function Landing({ theme, onToggleTheme, onGetStarted }) {
  return (
    <div className="relative flex min-h-screen flex-col overflow-hidden">
      {/* Background radial glow */}
      <div
        className="pointer-events-none absolute left-1/2 top-[18%] -z-10 h-125 w-175 -translate-x-1/2 -translate-y-1/2 rounded-full glow-radial animate-pulse-glow"
      />

      {/* Nav */}
      <nav className="flex items-center justify-between px-6 py-5 md:px-10">
        <Logo />
        <div className="flex items-center gap-4">
          <a
            href="#how"
            className="hidden font-body text-sm md:inline-block"
            style={{ color: 'var(--muted)' }}
          >
            How it works
          </a>
          <ThemeToggle theme={theme} onToggle={onToggleTheme} />
        </div>
      </nav>

      {/* Hero content */}
      <main className="flex flex-1 flex-col items-center px-6 pb-8">
        <div className="w-full max-w-3xl pt-10 text-center md:pt-16">
          {/* Eyebrow badge */}
          <div className="mb-5 flex justify-center animate-fade-in">
            <span className="eyebrow">Your AI data analyst</span>
          </div>

          {/* Headline */}
          <h1
            className="font-display text-4xl font-bold leading-[1.1] tracking-tight md:text-6xl animate-fade-in"
            style={{ animationDelay: '0.1s' }}
          >
            Upload a spreadsheet.
            <br />
            Ask it anything.
          </h1>

          {/* Subheading */}
          <p
            className="mx-auto mt-5 max-w-xl font-body text-base leading-relaxed md:text-lg animate-fade-in"
            style={{ color: 'var(--muted)', animationDelay: '0.2s' }}
          >
            Drop in a CSV or Excel file, type a question the way you'd ask a
            colleague, and DataPilot figures out the right analysis, runs it
            directly against your data, and hands you back an answer —
            charts and a downloadable report included.
          </p>

          {/* CTA */}
          <div
            className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row animate-fade-in"
            style={{ animationDelay: '0.3s' }}
          >
            <button
              onClick={onGetStarted}
              className="btn-amber inline-flex items-center gap-2 rounded-xl px-7 py-3.5 font-display text-base font-semibold"
            >
              Get started
              <ArrowRight size={18} strokeWidth={2.5} />
            </button>
            <a
              href="#how"
              className="inline-flex items-center gap-2 rounded-xl border-themed surface px-6 py-3.5 font-display text-base font-semibold"
              style={{ borderColor: 'var(--border)' }}
            >
              See how it works
            </a>
          </div>

          {/* Pill badges */}
          <div
            className="mt-6 flex flex-wrap items-center justify-center gap-2.5 animate-fade-in"
            style={{ animationDelay: '0.4s' }}
          >
            <span className="pill">
              <FileSpreadsheet size={13} style={{ color: 'var(--teal)' }} />
              CSV & Excel
            </span>
            <span className="pill">
              <Compass size={13} style={{ color: 'var(--teal)' }} />
              Guided suggestions
            </span>
            <span className="pill">
              <Database size={13} style={{ color: 'var(--teal)' }} />
              Grounded answers
            </span>
            <span className="pill">
              <Sparkles size={13} style={{ color: 'var(--teal)' }} />
              Completely free
            </span>
          </div>
        </div>

        {/* Signature flight path with caption */}
        <div
          className="mt-10 w-full max-w-2xl animate-fade-in"
          style={{ animationDelay: '0.5s' }}
        >
          <FlightPath />
          <p
            className="mt-2 text-center font-mono text-[11px] tracking-wide"
            style={{ color: 'var(--muted)' }}
          >
            DataPilot traces your question → analysis → result
          </p>
        </div>

        {/* How it works */}
        <section id="how" className="mt-24 w-full max-w-5xl scroll-mt-24">
          <div className="mb-10 text-center">
            <span className="eyebrow">How it works</span>
            <h2 className="mt-3 font-display text-3xl font-bold tracking-tight md:text-4xl">
              From file to answer in three steps
            </h2>
            <p
              className="mx-auto mt-3 max-w-lg font-body text-base"
              style={{ color: 'var(--muted)' }}
            >
              No setup, no schema to define, no SQL to write. Just upload and
              ask.
            </p>
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            {STEPS.map((step, i) => {
              const Icon = step.icon;
              return (
                <div
                  key={step.title}
                  className="surface animate-fade-in rounded-2xl border-themed p-6 text-left transition-transform duration-300 ease-out hover:-translate-y-1"
                  style={{
                    borderColor: 'var(--border)',
                    animationDelay: `${0.6 + i * 0.1}s`,
                  }}
                >
                  <div className="mb-4 flex items-center gap-2">
                    <span
                      className="flex h-9 w-9 items-center justify-center rounded-lg"
                      style={{
                        backgroundColor: 'var(--amber)',
                        color: 'var(--bg)',
                      }}
                    >
                      <Icon size={18} strokeWidth={2.25} />
                    </span>
                    <span
                      className="font-mono text-xs"
                      style={{ color: 'var(--muted)' }}
                    >
                      {String(i + 1).padStart(2, '0')}
                    </span>
                  </div>
                  <h3 className="font-display text-lg font-semibold">
                    {step.title}
                  </h3>
                  <p
                    className="mt-2 font-body text-sm leading-relaxed"
                    style={{ color: 'var(--muted)' }}
                  >
                    {step.desc}
                  </p>
                </div>
              );
            })}
          </div>
        </section>

        {/* Features grid */}
        <section className="mt-24 w-full max-w-5xl">
          <div className="mb-10 text-center">
            <span className="eyebrow">Features</span>
            <h2 className="mt-3 font-display text-3xl font-bold tracking-tight md:text-4xl">
              Built for people who think in spreadsheets
            </h2>
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((f, i) => {
              const Icon = f.icon;
              return (
                <div
                  key={f.title}
                  className="surface animate-fade-in rounded-2xl border-themed p-6 text-left transition-transform duration-300 ease-out hover:-translate-y-1"
                  style={{
                    borderColor: 'var(--border)',
                    animationDelay: `${0.7 + i * 0.08}s`,
                  }}
                >
                  <span
                    className="mb-4 flex h-9 w-9 items-center justify-center rounded-lg"
                    style={{
                      backgroundColor: 'var(--amber)',
                      color: 'var(--bg)',
                    }}
                  >
                    <Icon size={18} strokeWidth={2.25} />
                  </span>
                  <h3 className="font-display text-base font-semibold">
                    {f.title}
                  </h3>
                  <p
                    className="mt-2 font-body text-sm leading-relaxed"
                    style={{ color: 'var(--muted)' }}
                  >
                    {f.desc}
                  </p>
                </div>
              );
            })}
          </div>
        </section>

        {/* Example Q&A */}
        <section className="mt-24 w-full max-w-5xl">
          <div className="mb-10 text-center">
            <span className="eyebrow">Examples</span>
            <h2 className="mt-3 font-display text-3xl font-bold tracking-tight md:text-4xl">
              Ask like a human, get a real answer
            </h2>
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            {EXAMPLES.map((ex, i) => (
              <div
                key={ex.question}
                className="surface animate-fade-in rounded-2xl border-themed p-6 text-left transition-transform duration-300 ease-out hover:-translate-y-1"
                style={{
                  borderColor: 'var(--border)',
                  animationDelay: `${0.7 + i * 0.1}s`,
                }}
              >
                <span
                  className="mb-3 inline-block rounded-md px-2 py-0.5 font-mono text-[11px] font-semibold"
                  style={{
                    backgroundColor: 'var(--amber)',
                    color: 'var(--bg)',
                  }}
                >
                  {ex.tag}
                </span>
                <p className="font-display text-sm font-semibold leading-snug">
                  {ex.question}
                </p>
                <p
                  className="mt-2 font-body text-sm leading-relaxed"
                  style={{ color: 'var(--muted)' }}
                >
                  {ex.answer}
                </p>
              </div>
            ))}
          </div>
        </section>

        {/* Final CTA */}
        <section className="mt-24 w-full max-w-5xl">
          <div
            className="surface animate-fade-in rounded-3xl border-themed px-8 py-14 text-center transition-transform duration-300 ease-out hover:-translate-y-1"
            style={{ borderColor: 'var(--border)', animationDelay: '0.8s' }}
          >
            <Sparkles
              size={28}
              className="mx-auto mb-4"
              style={{ color: 'var(--amber)' }}
            />
            <h2 className="font-display text-3xl font-bold tracking-tight md:text-4xl">
              Your next report is one question away
            </h2>
            <p
              className="mx-auto mt-3 max-w-md font-body text-base"
              style={{ color: 'var(--muted)' }}
            >
              Upload a file and ask away. Completely free, no sign-up —
              your file is deleted the moment you're done.
            </p>
            <button
              onClick={onGetStarted}
              className="btn-amber mt-7 inline-flex items-center gap-2 rounded-xl px-7 py-3.5 font-display text-base font-semibold"
            >
              Get started
              <ArrowRight size={18} strokeWidth={2.5} />
            </button>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer
        className="px-6 py-8 text-center"
        style={{ borderTop: '1px solid var(--border)' }}
      >
        <div className="mx-auto flex max-w-5xl flex-col items-center justify-between gap-4 md:flex-row">
          <div className="flex items-center gap-2">
            <Logo />
          </div>
          <p
            className="inline-flex items-center gap-1.5 font-mono text-xs"
            style={{ color: 'var(--muted)' }}
          >
            <Lock size={11} />
            Your file is deleted the moment you leave — or automatically after a short period of inactivity.
          </p>
          <p
            className="font-mono text-xs"
            style={{ color: 'var(--muted)' }}
          >
            © {new Date().getFullYear()} DataPilot
          </p>
        </div>
      </footer>
    </div>
  );
}