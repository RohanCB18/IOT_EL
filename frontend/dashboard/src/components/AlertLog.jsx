import { useEffect, useRef } from 'react';

const LEVEL_COLOUR = {
  CRITICAL: '#ef4444',
  WARNING:  '#f59e0b',
  SAFE:     '#22c55e',
};

function fmt(ts) {
  if (!ts) return '—';
  return new Date(ts).toLocaleTimeString();
}

export default function AlertLog({ alerts = [] }) {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [alerts.length]);

  return (
    <div className="card alert-card">
      <h3 className="card-title">
        Alert Log
        <span className="alert-count">{alerts.length}</span>
      </h3>
      <div className="alert-list">
        {alerts.length === 0 && (
          <p className="alert-empty">No alerts yet — system nominal.</p>
        )}
        {alerts.map((a) => (
          <div key={a.id} className="alert-item"
               style={{ borderLeftColor: LEVEL_COLOUR[a.level] ?? '#64748b' }}>
            <span className="alert-time">{fmt(a.timestamp)}</span>
            <span className="alert-level"
                  style={{ color: LEVEL_COLOUR[a.level] ?? '#94a3b8' }}>
              {a.level}
            </span>
            <span className="alert-msg">{a.message}</span>
            {a.predicted_time_to_critical != null && (
              <span className="alert-ttc">
                TTC: {Number(a.predicted_time_to_critical).toFixed(1)}s
              </span>
            )}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
