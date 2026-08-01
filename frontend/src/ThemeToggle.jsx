import { Sun, Moon } from 'lucide-react';

export function ThemeToggle({ theme, onToggle }) {
  const isDark = theme === 'dark';
  return (
    <button
      onClick={onToggle}
      aria-label={`Switch to ${isDark ? 'light' : 'dark'} mode`}
      className="relative inline-flex h-8 w-16 items-center rounded-full border-themed surface px-1 transition-colors"
      style={{ borderColor: 'var(--border)' }}
    >
      <span
        className="flex h-6 w-6 items-center justify-center rounded-full transition-transform duration-300 ease-out"
        style={{
          transform: isDark ? 'translateX(0)' : 'translateX(32px)',
          backgroundColor: 'var(--amber)',
          color: 'var(--bg)',
        }}
      >
        {isDark ? <Moon size={14} /> : <Sun size={14} />}
      </span>
    </button>
  );
}