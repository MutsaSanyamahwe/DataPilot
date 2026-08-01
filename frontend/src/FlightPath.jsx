import { Upload, MessageSquare, BarChart3 } from 'lucide-react';

const waypoints = [
    { label: 'Upload', icon: Upload },
    { label: 'Ask', icon: MessageSquare },
    { label: 'Answer', icon: BarChart3 },
];

export function FlightPath() {
    return (
        <div className="relative mx-auto w-full max-w-2xl py-8">
            {/* Dashed path line */}
            <div className="relative h-12">
                <div
                    className="absolute left-0 right-0"
                    style={{
                        top: '50%',
                        height: '2px',
                        transform: 'translateY(-50%)',
                        backgroundImage: `repeating-linear-gradient(90deg, var(--border) 0, var(--border) 8px, transparent 8px, transparent 16px)`,
                    }}
                />

                {/* Waypoint dots */}
                <div className="absolute inset-0 flex items-center justify-between">
                    {waypoints.map((wp) => {
                        const Icon = wp.icon;
                        return (
                            <div
                                key={wp.label}
                                className="flex h-12 w-12 items-center justify-center rounded-full surface"
                                style={{
                                    borderColor: 'var(--border)',
                                    color: 'var(--amber)',
                                    boxShadow: '0 0 0 5px var(--bg), 0 4px 14px var(--amber-soft)',
                                }}
                            >
                                <Icon size={20} strokeWidth={1.75} />
                            </div>
                        );
                    })}
                </div>

                {/* Animated paper plane */}
                <div
                    className="absolute top-1/2"
                    style={{
                        left: 0,
                        transform: 'translateY(-50%)',
                        animation: 'fly-x 5s ease-in-out infinite',
                    }}
                >
                    <PaperPlane />
                </div>
            </div>

            {/* Waypoint labels */}
            <div className="mt-3 flex items-center justify-between">
                {waypoints.map((wp, i) => (
                    <div key={wp.label} className="flex flex-col items-center gap-0.5">
                        <span className="font-mono text-[10px] uppercase tracking-widest" style={{ color: 'var(--muted)' }}>
                            Step {i + 1}
                        </span>
                        <span className="font-display text-sm font-semibold" style={{ color: 'var(--text)' }}>
                            {wp.label}
                        </span>
                    </div>
                ))}
            </div>
        </div>
    );
}

function PaperPlane() {
    return (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" style={{ filter: 'drop-shadow(0 2px 4px var(--amber-soft))' }}>
            <path
                d="M2 12 L22 3 L18 21 L11 14 L2 12 Z"
                fill="var(--amber)"
                stroke="var(--amber)"
                strokeWidth="1"
                strokeLinejoin="round"
            />
            <path d="M11 14 L22 3" stroke="var(--bg)" strokeWidth="1" strokeLinecap="round" opacity="0.4" />
        </svg>
    );
}
