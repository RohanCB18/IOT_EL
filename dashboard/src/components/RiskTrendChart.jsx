import {
  ResponsiveContainer, LineChart, Line,
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
      <p className="chart-tooltip-val">R = {payload[0].value?.toFixed(4)}</p>
    </div>
  );
}

export default function RiskTrendChart({ trendData = [] }) {
  return (
    <div className="card chart-card">
      <h3 className="card-title">Risk Trend (last {trendData.length} readings)</h3>
      <ResponsiveContainer width="100%" height={160}>
        <LineChart data={trendData} margin={{ top: 8, right: 12, left: -20, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
          <XAxis
            dataKey="label"
            tick={{ fontSize: 9, fill: '#64748b' }}
            interval="preserveStartEnd"
          />
          <YAxis
            domain={[0, 1]}
            tick={{ fontSize: 9, fill: '#64748b' }}
            tickCount={6}
          />
          <Tooltip content={<CustomTooltip />} />
          <ReferenceLine y={WARN_THRESH} stroke="#f59e0b" strokeDasharray="4 2"
                         label={{ value: 'WARN', position: 'insideTopLeft',
                                  fontSize: 8, fill: '#f59e0b' }} />
          <ReferenceLine y={CRIT_THRESH} stroke="#ef4444" strokeDasharray="4 2"
                         label={{ value: 'CRIT', position: 'insideTopLeft',
                                  fontSize: 8, fill: '#ef4444' }} />
          <Line
            type="monotone"
            dataKey="risk"
            stroke="#6366f1"
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
