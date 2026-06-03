import {
  ResponsiveContainer, AreaChart, Area,
  XAxis, YAxis, CartesianGrid, Tooltip,
  ReferenceLine,
} from 'recharts';

const WARN_THRESH = 0.55;
const CRIT_THRESH = 0.75;

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="chart-tooltip">
      <p className="chart-tooltip-time">{label}</p>
      <p className="chart-tooltip-val">
        <span style={{ color: 'var(--text-secondary)', marginRight: '6px', fontWeight: '500' }}>Risk:</span>
        {(payload[0].value ?? 0).toFixed(4)}
      </p>
    </div>
  );
}

export default function RiskTrendChart({ trendData = [] }) {
  return (
    <div className="card chart-card">
      <div className="card-header-row">
        <h3 className="card-title">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="23 6 13.5 15.5 8.5 10.5 1 18" />
            <polyline points="17 6 23 6 23 12" />
          </svg>
          Risk Telemetry History
        </h3>
        <span className="cctv-meta" style={{ fontSize: '9px', fontWeight: 'bold' }}>
          {trendData.length} SEC WINDOW
        </span>
      </div>
      
      <ResponsiveContainer width="100%" height={160}>
        <AreaChart data={trendData} margin={{ top: 12, right: 8, left: -22, bottom: 0 }}>
          <defs>
            {/* Smooth glowing area fill gradient */}
            <linearGradient id="riskGlow" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="var(--color-primary)" stopOpacity={0.35}/>
              <stop offset="95%" stopColor="var(--color-primary)" stopOpacity={0.0}/>
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255, 255, 255, 0.03)" />
          
          <XAxis
            dataKey="label"
            tick={{ fontSize: 9, fill: 'var(--text-secondary)', fontFamily: 'monospace' }}
            tickLine={{ stroke: 'rgba(255, 255, 255, 0.05)' }}
            axisLine={{ stroke: 'rgba(255, 255, 255, 0.05)' }}
            interval="preserveStartEnd"
          />
          <YAxis
            domain={[0, 1]}
            tick={{ fontSize: 9, fill: 'var(--text-secondary)', fontFamily: 'monospace' }}
            tickCount={6}
            tickLine={{ stroke: 'rgba(255, 255, 255, 0.05)' }}
            axisLine={{ stroke: 'rgba(255, 255, 255, 0.05)' }}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ stroke: 'rgba(99, 102, 241, 0.15)', strokeWidth: 1.5 }} />
          
          {/* Reference thresholds */}
          <ReferenceLine
            y={WARN_THRESH}
            stroke="var(--color-warning)"
            strokeDasharray="4 4"
            opacity={0.6}
            label={{
              value: 'WARNING LEVEL (0.55)',
              position: 'insideBottomRight',
              fontSize: 7,
              fontWeight: '700',
              fill: 'var(--color-warning)',
              style: { letterSpacing: '0.5px' }
            }}
          />
          <ReferenceLine
            y={CRIT_THRESH}
            stroke="var(--color-critical)"
            strokeDasharray="4 4"
            opacity={0.6}
            label={{
              value: 'CRITICAL LEVEL (0.75)',
              position: 'insideTopRight',
              fontSize: 7,
              fontWeight: '700',
              fill: 'var(--color-critical)',
              style: { letterSpacing: '0.5px' }
            }}
          />
          
          <Area
            type="monotone"
            dataKey="risk"
            stroke="var(--color-primary)"
            strokeWidth={2}
            fillOpacity={1}
            fill="url(#riskGlow)"
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
