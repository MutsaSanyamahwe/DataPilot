export function Logo({ onClick }) {
    return (
        <button
            onClick={onClick}
            className="font-display text-xl font-bold tracking-tight transition-opacity hover:opacity-80"
            style={{ color: 'var(--text)' }}
        >
            Data<span style={{ color: 'var(--amber)' }}>Pilot</span>
        </button>
    );
}