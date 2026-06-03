function MetricCard({ label, value, unit = '', icon }) {
  return (
    <div className="metric-card">
      <div className="metric-icon-box">
        {icon}
      </div>
      <div className="metric-info">
        <span className="metric-val">{value}<span style={{ fontSize: '12px', color: 'var(--text-secondary)', marginLeft: '2px' }}>{unit}</span></span>
        <span className="metric-label">{label}</span>
      </div>
    </div>
  );
}

export default function MetricsBar({ metrics }) {
  const {
    count       = 0,
    density     = 0,
    flow_mag    = 0,
    divergence  = 0,
    chaos       = 0,
  } = metrics ?? {};

  return (
    <div className="metrics-row">
      <MetricCard
        label="People Count"
        value={count}
        unit="px"
        icon={
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
            <circle cx="9" cy="7" r="4" />
            <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
            <path d="M16 3.13a4 4 0 0 1 0 7.75" />
          </svg>
        }
      />
      <MetricCard
        label="Crowd Density"
        value={density.toFixed(2)}
        unit="p/m²"
        icon={
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
            <rect x="7" y="7" width="3" height="3" fill="currentColor" opacity="0.4" />
            <rect x="14" y="7" width="3" height="3" fill="currentColor" opacity="0.4" />
            <rect x="7" y="14" width="3" height="3" fill="currentColor" opacity="0.4" />
            <rect x="14" y="14" width="3" height="3" fill="currentColor" opacity="0.8" />
            <path d="M9 3v18M15 3v18M3 9h18M3 15h18" strokeWidth="1" strokeDasharray="2 2" />
          </svg>
        }
      />
      <MetricCard
        label="Flow Velocity"
        value={flow_mag.toFixed(2)}
        unit="px/f"
        icon={
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
            <path d="M18 6l4 6-4 6" />
          </svg>
        }
      />
      <MetricCard
        label="Divergence"
        value={divergence.toFixed(3)}
        icon={
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10" />
            <path d="M12 12L8 8M12 12l4 4M12 12l4-4M12 12l-4 4" />
            <path d="M8 6h-2v2M18 6h2v2M6 18H8v-2M18 18h-2v-2" strokeWidth="2.5" />
          </svg>
        }
      />
      <MetricCard
        label="Chaos σθ"
        value={chaos.toFixed(3)}
        unit="rad"
        icon={
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7z" />
            <circle cx="12" cy="12" r="3" />
            <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" strokeWidth="1.5" strokeDasharray="3 3" />
          </svg>
        }
      />
    </div>
  );
}
