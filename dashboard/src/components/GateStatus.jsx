const GATE_CONFIG = {
  GATE_OPEN: {
    label:    'OPEN',
    angle:    0,
    ledGreen: true,
    ledAmber: false,
    ledRed:   false,
    buzzer:   false,
    colour:   '#22c55e',
  },
  GATE_HALF: {
    label:    'HALF',
    angle:    90,
    ledGreen: false,
    ledAmber: true,
    ledRed:   false,
    buzzer:   false,
    colour:   '#f59e0b',
  },
  GATE_CLOSE: {
    label:    'CLOSED',
    angle:    180,
    ledGreen: false,
    ledAmber: false,
    ledRed:   true,
    buzzer:   true,
    colour:   '#ef4444',
  },
};

function Led({ colour, active, label }) {
  return (
    <div className="led-wrap">
      <div
        className="led"
        style={{
          background: active ? colour : '#1e293b',
          boxShadow:  active ? `0 0 10px 3px ${colour}88` : 'none',
        }}
      />
      <span className="led-label">{label}</span>
    </div>
  );
}

function ServoArc({ angle = 0, colour = '#22c55e' }) {
  const rad    = (angle * Math.PI) / 180;
  const cx     = 40;
  const cy     = 40;
  const r      = 28;
  const endX   = cx + r * Math.sin(rad);
  const endY   = cy - r * Math.cos(rad);
  const large  = angle > 180 ? 1 : 0;
  const arcD   = `M ${cx} ${cy - r} A ${r} ${r} 0 ${large} 1 ${endX} ${endY}`;

  return (
    <svg viewBox="0 0 80 80" width={80} height={80}>
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="#1e293b" strokeWidth={6} />
      <path d={arcD} fill="none" stroke={colour} strokeWidth={6} strokeLinecap="round" />
      <line x1={cx} y1={cy} x2={endX} y2={endY}
            stroke={colour} strokeWidth={3} strokeLinecap="round" />
      <circle cx={cx} cy={cy} r={4} fill={colour} />
      <text x={cx} y={cy + 16} textAnchor="middle" fontSize={9} fill="#94a3b8">{angle}°</text>
    </svg>
  );
}

export default function GateStatus({ command = 'GATE_OPEN' }) {
  const cfg = GATE_CONFIG[command] ?? GATE_CONFIG.GATE_OPEN;

  return (
    <div className="card gate-card">
      <h3 className="card-title">Gate Status</h3>
      <div className="gate-body">
        <ServoArc angle={cfg.angle} colour={cfg.colour} />
        <div className="gate-label" style={{ color: cfg.colour }}>
          {cfg.label}
          {cfg.buzzer && <span className="buzzer-tag"> 🔔 BUZZER</span>}
        </div>
        <div className="led-row">
          <Led colour="#22c55e" active={cfg.ledGreen} label="GRN" />
          <Led colour="#f59e0b" active={cfg.ledAmber} label="AMB" />
          <Led colour="#ef4444" active={cfg.ledRed}   label="RED" />
        </div>
      </div>
    </div>
  );
}
