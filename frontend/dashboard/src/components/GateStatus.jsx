const GATE_CONFIG = {
  GATE_OPEN: {
    label:    'OPEN',
    angle:    0,
    ledGreen: true,
    ledAmber: false,
    ledRed:   false,
    buzzer:   false,
    colour:   '#10b981',
  },
  GATE_HALF: {
    label:    'HALF-OPEN',
    angle:    45,
    ledGreen: false,
    ledAmber: true,
    ledRed:   false,
    buzzer:   false,
    colour:   '#f59e0b',
  },
  GATE_CLOSE: {
    label:    'CLOSED',
    angle:    90,
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
          background: active ? colour : '#111827',
          borderColor: active ? colour : '#1f2937',
          boxShadow:  active ? `0 0 14px 4px ${colour}77, inset 0 0 4px ${colour}` : 'inset 0 0 4px rgba(0,0,0,0.6)',
        }}
      />
      <span className="led-label">{label}</span>
    </div>
  );
}

function GateMechanism({ angle = 0, colour = '#10b981' }) {
  // Let's render a physical mechanical gate structure inside a clean 100x80 viewbox
  const cx = 35;
  const cy = 55;

  return (
    <svg viewBox="0 0 100 80" width="100" height="80" style={{ filter: 'drop-shadow(0 4px 8px rgba(0, 0, 0, 0.3))' }}>
      <defs>
        {/* Black & Yellow Hazard Stripes Pattern for the Gate Arm */}
        <pattern id="hazard" width="10" height="20" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <rect width="5" height="20" fill="#f59e0b" />
          <rect x="5" width="5" height="20" fill="#111827" />
        </pattern>
        {/* Glowing metal accents */}
        <linearGradient id="metal" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#4b5563" />
          <stop offset="50%" stopColor="#1f2937" />
          <stop offset="100%" stopColor="#111827" />
        </linearGradient>
      </defs>

      {/* Ground/Floor base line */}
      <line x1="10" y1="70" x2="90" y2="70" stroke="#374151" strokeWidth="2" strokeLinecap="round" />

      {/* Servo Housing / Post */}
      <rect x="25" y="40" width="20" height="30" rx="3" fill="url(#metal)" stroke="#4b5563" strokeWidth="1" />
      <rect x="28" y="43" width="14" height="6" rx="1" fill="#030712" opacity="0.6" />

      {/* Dynamic Animated Gate Barrier Arm */}
      <g
        style={{
          transform: `rotate(${-angle}deg)`,
          transformOrigin: `${cx}px ${cy}px`,
          transition: 'transform 0.8s cubic-bezier(0.25, 1, 0.5, 1)',
        }}
      >
        {/* Main gate arm body */}
        <rect x={cx} y={cy - 4} width="52" height="8" rx="2" fill="url(#hazard)" stroke="#111827" strokeWidth="1" />
        {/* Gate tip red warning light indicator */}
        <circle cx={cx + 48} cy={cy} r="2" fill={colour} style={{ transition: 'fill 0.8s' }} />
        {/* Pivot counterweight end */}
        <rect x={cx - 14} y={cy - 5} width="14" height="10" rx="2" fill="#374151" stroke="#1f2937" />
      </g>

      {/* Center Cap/Actuator Gear */}
      <circle cx={cx} cy={cy} r="8" fill="url(#metal)" stroke="#6b7280" strokeWidth="1.5" />
      <circle cx={cx} cy={cy} r="3" fill="#030712" />
    </svg>
  );
}

export default function GateStatus({ command = 'GATE_OPEN' }) {
  const cfg = GATE_CONFIG[command] ?? GATE_CONFIG.GATE_OPEN;

  return (
    <div className="card gate-card">
      <div className="card-header-row">
        <h3 className="card-title">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
            <path d="M7 11V7a5 5 0 0 1 10 0v4" />
          </svg>
          Actuator Control
        </h3>
      </div>
      <div className="gate-body">
        <GateMechanism angle={cfg.angle} colour={cfg.colour} />
        
        <div className="gate-label" style={{ color: cfg.colour, transition: 'color 0.4s' }}>
          {cfg.label}
          {cfg.buzzer && (
            <span className="buzzer-tag">
              <svg viewBox="0 0 24 24" width="11" height="11" fill="currentColor" style={{ marginRight: '4px', verticalAlign: 'middle' }}>
                <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9M13.73 21a2 2 0 0 1-3.46 0" />
              </svg>
              BUZZER ACTIVE
            </span>
          )}
        </div>

        <div className="led-row">
          <Led colour="#10b981" active={cfg.ledGreen} label="OPEN" />
          <Led colour="#f59e0b" active={cfg.ledAmber} label="WARN" />
          <Led colour="#ef4444" active={cfg.ledRed}   label="STOP" />
        </div>
      </div>
    </div>
  );
}
