function Metric({ label, value, unit = '' }) {
  return (
    <div className="metric-item">
      <span className="metric-val">{value}{unit}</span>
      <span className="metric-label">{label}</span>
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
    <div className="metrics-bar">
      <Metric label="People"    value={count} />
      <Metric label="Density"   value={density.toFixed(2)}   unit=" p/m²" />
      <Metric label="Flow"      value={flow_mag.toFixed(2)}  unit=" px/f" />
      <Metric label="Divergence" value={divergence.toFixed(3)} />
      <Metric label="Chaos σθ"  value={chaos.toFixed(3)}    unit=" rad" />
    </div>
  );
}
