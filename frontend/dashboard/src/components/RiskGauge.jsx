import { useMemo } from 'react';

const R      = 75;   // arc radius
const CX     = 100;  // SVG centre X
const CY     = 95;   // SVG centre Y
const START  = Math.PI;          // left  (180°)
const END    = 0;                // right (0°)
const RANGE  = Math.PI;          // half-circle

const ZONES = [
  { lo: 0.00, hi: 0.55, colour: '#10b981', label: 'SAFE'     },
  { lo: 0.55, hi: 0.75, colour: '#f59e0b', label: 'WARNING'  },
  { lo: 0.75, hi: 1.00, colour: '#ef4444', label: 'CRITICAL' },
];

function polar(cx, cy, r, angle) {
  return [cx + r * Math.cos(angle), cy - r * Math.sin(angle)];
}

function arcPath(cx, cy, r, startAngle, endAngle) {
  const [x1, y1] = polar(cx, cy, r, startAngle);
  const [x2, y2] = polar(cx, cy, r, endAngle);
  const large = endAngle - startAngle > Math.PI ? 1 : 0;
  return `M ${x1} ${y1} A ${r} ${r} 0 ${large} 1 ${x2} ${y2}`;
}

function valueToAngle(v) {
  return START - v * RANGE;
}

export default function RiskGauge({ riskScore = 0, alertLevel = 'SAFE' }) {
  const clampedScore = Math.max(0, Math.min(1, riskScore));

  const zoneArcs = useMemo(() =>
    ZONES.map(({ lo, hi, colour }) => ({
      d: arcPath(CX, CY, R, valueToAngle(lo), valueToAngle(hi)),
      colour,
    })),
  []);

  const needleAngle = valueToAngle(clampedScore);
  const [nx, ny]    = polar(CX, CY, R - 14, needleAngle);

  const levelColour = ZONES.find(z => clampedScore >= z.lo && clampedScore < z.hi)?.colour
    ?? ZONES[ZONES.length - 1].colour;

  return (
    <div className="card gauge-card">
      <div className="card-header-row" style={{ width: '100%' }}>
        <h3 className="card-title">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.5">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
            <line x1="12" y1="9" x2="12" y2="13"/>
            <line x1="12" y1="17" x2="12.01" y2="17"/>
          </svg>
          Risk Indicator
        </h3>
      </div>
      <div className="gauge-wrap">
        <svg viewBox="0 0 200 136" width="100%" style={{ maxWidth: 280, filter: 'drop-shadow(0 4px 12px rgba(0, 0, 0, 0.4))' }}>
          <defs>
            <filter id="gauge-glow" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
            {/* Subtle inner grid pattern */}
            <pattern id="gauge-grid" width="10" height="10" patternUnits="userSpaceOnUse">
              <path d="M 10 0 L 0 0 0 10" fill="none" stroke="rgba(255,255,255,0.02)" strokeWidth="0.5"/>
            </pattern>
          </defs>

          {/* Grid Background */}
          <path d={arcPath(CX, CY, R + 10, START, END)} fill="url(#gauge-grid)" />

          {/* Track background */}
          <path
            d={arcPath(CX, CY, R, START, END)}
            fill="none" stroke="rgba(31, 41, 55, 0.6)" strokeWidth={14}
            strokeLinecap="round"
          />

          {/* Coloured zone arcs with hover indicator */}
          {zoneArcs.map(({ d, colour }, i) => (
            <path
              key={i}
              d={d}
              fill="none"
              stroke={colour}
              strokeWidth={14}
              opacity={clampedScore >= ZONES[i].lo && clampedScore <= ZONES[i].hi ? 0.85 : 0.25}
              strokeLinecap="butt"
              style={{ transition: 'opacity 0.4s ease' }}
            />
          ))}

          {/* Glowing indicator arc up to current value */}
          <path
            d={arcPath(CX, CY, R, START, needleAngle)}
            fill="none"
            stroke={levelColour}
            strokeWidth={4}
            opacity={0.8}
            filter="url(#gauge-glow)"
            style={{ transition: 'stroke 0.4s, d 0.4s' }}
          />

          {/* Needle indicator */}
          <g style={{ transition: 'transform 0.4s cubic-bezier(0.34, 1.56, 0.64, 1)', transformOrigin: `${CX}px ${CY}px` }}>
            <line
              x1={CX} y1={CY}
              x2={nx} y2={ny}
              stroke={levelColour}
              strokeWidth={3}
              strokeLinecap="round"
              filter="url(#gauge-glow)"
            />
            <circle cx={CX} cy={CY} r={6} fill={levelColour} stroke="#030712" strokeWidth={2} />
          </g>

          {/* Score text readout */}
          <text
            x={CX} y={CY + 23}
            textAnchor="middle"
            fontSize={24}
            fontWeight="bold"
            fontFamily="var(--font-heading)"
            fill={levelColour}
            style={{ transition: 'fill 0.4s' }}
          >
            {clampedScore.toFixed(3)}
          </text>
          <text x={CX} y={CY + 35} textAnchor="middle" fontSize={8} fontWeight="700" fill="var(--text-secondary)" letterSpacing={1.2}>
            RISK ASSESSMENT
          </text>

          {/* Zone labels */}
          <text x={20}  y={102} fontSize={8} fontWeight="700" fill="#10b981" opacity={0.8}>SAFE</text>
          <text x={100} y={14}  fontSize={8} fontWeight="700" fill="#f59e0b" opacity={0.8} textAnchor="middle">WARN</text>
          <text x={180} y={102} fontSize={8} fontWeight="700" fill="#ef4444" opacity={0.8} textAnchor="end">CRIT</text>
        </svg>
        <div className={`alert-badge alert-${alertLevel.toLowerCase()}`}>
          {alertLevel}
        </div>
      </div>
    </div>
  );
}
