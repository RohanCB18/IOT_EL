import { useMemo } from 'react';

const R      = 80;   // arc radius
const CX     = 100;  // SVG centre X
const CY     = 100;  // SVG centre Y (arc sits above this)
const START  = Math.PI;          // left  (180°)
const END    = 0;                // right (0°)
const RANGE  = Math.PI;          // half-circle

const ZONES = [
  { lo: 0.00, hi: 0.55, colour: '#22c55e', label: 'SAFE'     },
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
  const [nx, ny]    = polar(CX, CY, R - 12, needleAngle);

  const levelColour = ZONES.find(z => clampedScore >= z.lo && clampedScore < z.hi)?.colour
    ?? ZONES[ZONES.length - 1].colour;

  return (
    <div className="gauge-wrap">
      <svg viewBox="0 0 200 115" width="100%" style={{ maxWidth: 280 }}>
        {/* Track */}
        <path
          d={arcPath(CX, CY, R, START, END)}
          fill="none" stroke="#1e293b" strokeWidth={18}
        />
        {/* Coloured zone arcs */}
        {zoneArcs.map(({ d, colour }, i) => (
          <path key={i} d={d} fill="none" stroke={colour}
                strokeWidth={18} strokeLinecap="butt" opacity={0.35} />
        ))}
        {/* Needle */}
        <line
          x1={CX} y1={CY}
          x2={nx} y2={ny}
          stroke={levelColour} strokeWidth={3} strokeLinecap="round"
        />
        <circle cx={CX} cy={CY} r={5} fill={levelColour} />
        {/* Score text */}
        <text x={CX} y={CY + 22} textAnchor="middle"
              fontSize={22} fontWeight="bold" fill={levelColour}>
          {clampedScore.toFixed(3)}
        </text>
        <text x={CX} y={CY + 36} textAnchor="middle"
              fontSize={9} fill="#94a3b8" letterSpacing={1}>
          RISK SCORE
        </text>
        {/* Zone labels */}
        <text x={16}  y={108} fontSize={7} fill="#22c55e">SAFE</text>
        <text x={84}  y={20}  fontSize={7} fill="#f59e0b" textAnchor="middle">WARN</text>
        <text x={175} y={108} fontSize={7} fill="#ef4444" textAnchor="end">CRIT</text>
      </svg>
      <div className={`alert-badge alert-${alertLevel.toLowerCase()}`}>
        {alertLevel}
      </div>
    </div>
  );
}
