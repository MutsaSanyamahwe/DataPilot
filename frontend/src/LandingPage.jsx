import { ArrowRight, FileSpreadsheet, Layers, Database } from 'lucide-react';
import { Logo } from './Logo';
import { ThemeToggle } from './ThemeToggle';
import { FlightPath } from './FlightPath';

export function Landing({ theme, onToggleTheme, onGetStarted }) {
  return (
    <div className="relative flex min-h-screen flex-col overflow-hidden">
      {/* Background radial glow */}
      <div
        className="pointer-events-none absolute left-1/2 top-[28%] -z-10 h-125 w-175 -translate-x-1/2 -translate-y-1/2 rounded-full glow-radial animate-pulse-glow"
      />

      {/* Nav */}
      <nav className="flex items-center justify-between px-6 py-5 md:px-10">
        <Logo />
        <ThemeToggle theme={theme} onToggle={onToggleTheme} />
      </nav>

      {/* Hero content */}
      <main className="flex flex-1 flex-col items-center justify-center px-6 pb-8">
        <div className="w-full max-w-3xl text-center">
          {/* Eyebrow badge */}
          <div className="mb-5 flex justify-center animate-fade-in">
            <span className="eyebrow">
              <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: 'var(--amber)' }} />
              Autonomous data analysis
            </span>
          </div>

          {/* Headline */}
          <h1 className="font-display text-4xl font-bold leading-[1.1] tracking-tight md:text-6xl animate-fade-in" style={{ animationDelay: '0.1s' }}>
            Plain English in.
            <br />
            Clear answers out.
          </h1>

          {/* Subheading */}
          <p className="mx-auto mt-5 max-w-xl font-body text-base leading-relaxed md:text-lg animate-fade-in" style={{ color: 'var(--muted)', animationDelay: '0.2s' }}>
            Upload your CSVs or spreadsheets, ask questions like you would a colleague, and get back SQL-backed analysis, charts, and a report you can download.
          </p>

          {/* CTA */}
          <div className="mt-8 flex justify-center animate-fade-in" style={{ animationDelay: '0.3s' }}>
            <button
              onClick={onGetStarted}
              className="btn-amber inline-flex items-center gap-2 rounded-xl px-7 py-3.5 font-display text-base font-semibold"
            >
              Get started
              <ArrowRight size={18} strokeWidth={2.5} />
            </button>
          </div>

          {/* Pill badges */}
          <div className="mt-6 flex flex-wrap items-center justify-center gap-2.5 animate-fade-in" style={{ animationDelay: '0.4s' }}>
            <span className="pill">
              <FileSpreadsheet size={13} style={{ color: 'var(--teal)' }} />
              CSV & Excel
            </span>
            <span className="pill">
              <Layers size={13} style={{ color: 'var(--teal)' }} />
              Multi-sheet support
            </span>
            <span className="pill">
              <Database size={13} style={{ color: 'var(--teal)' }} />
              Runs real SQL
            </span>
          </div>
        </div>

        {/* Signature flight path */}
        <div className="mt-4 w-full max-w-2xl animate-fade-in" style={{ animationDelay: '0.5s' }}>
          <FlightPath />
        </div>
      </main>

      {/* Footer */}
      <footer className="px-6 py-5 text-center">
        <p className="font-mono text-xs" style={{ color: 'var(--muted)' }}>
          Your data stays in the session — nothing is stored after you're done.
        </p>
      </footer>
    </div>
  );
}