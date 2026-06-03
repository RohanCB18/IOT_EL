
const LEVEL_COLOUR = {
  CRITICAL: 'var(--color-critical)',
  WARNING:  'var(--color-warning)',
  SAFE:     'var(--color-safe)',
};

function fmt(ts) {
  if (!ts) return '—';
  const date = new Date(ts);
  return date.toLocaleTimeString([], { hour12: false });
}

export default function AlertLog({ alerts = [] }) {
  return (
    <div className="card alert-card" style={{ flex: 1 }}>
      <div className="card-header-row">
        <h3 className="card-title">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="4 17 10 11 15 16 20 9" />
            <path d="M13 9h7v7" />
          </svg>
          Telemetry Event Log
        </h3>
        <span className="alert-count">{alerts.length} EVENTS</span>
      </div>
      
      <div className="alert-list">
        {alerts.length === 0 ? (
          <div className="alert-empty">
            <svg viewBox="0 0 24 24" width="36" height="36" fill="none" stroke="var(--color-safe)" strokeWidth="1.5" opacity="0.6">
              <circle cx="12" cy="12" r="10" />
              <polyline points="22 4 12 14.01 9 11.01" strokeWidth="2" />
            </svg>
            <span style={{ fontSize: '11px', letterSpacing: '0.8px', color: 'var(--color-safe)', fontWeight: 'bold' }}>
              ALL SYSTEMS OPERATIONS NOMINAL
            </span>
          </div>
        ) : (
          alerts.map((a) => {
            const lowerLevel = (a.level || 'SAFE').toLowerCase();
            return (
              <div
                key={a.id}
                className="alert-item"
                style={{ borderLeftColor: LEVEL_COLOUR[a.level] ?? 'var(--text-muted)' }}
              >
                <span className="alert-time">{fmt(a.timestamp)}</span>
                
                <span className={`alert-level-badge level-${lowerLevel}-badge`}>
                  {a.level}
                </span>
                
                <span className="alert-msg" title={a.message}>
                  {a.message}
                </span>
                
                {a.predicted_time_to_critical != null && (
                  <span className="alert-ttc">
                    TTC: {Number(a.predicted_time_to_critical).toFixed(1)}s
                  </span>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
