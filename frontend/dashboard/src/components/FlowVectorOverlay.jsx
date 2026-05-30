const ARROW_COUNT = 8;

function FlowArrow({ x, y, angle, magnitude, maxMag }) {
  const len    = 10 + (magnitude / maxMag) * 20;
  const rad    = angle;
  const ex     = x + len * Math.cos(rad);
  const ey     = y + len * Math.sin(rad);
  const alpha  = 0.4 + 0.6 * (magnitude / maxMag);

  return (
    <g opacity={alpha}>
      <line x1={x} y1={y} x2={ex} y2={ey}
            stroke="#6366f1" strokeWidth={1.5} markerEnd="url(#arrow)" />
    </g>
  );
}

export default function FlowVectorOverlay({ flowData = null }) {
  if (!flowData || !flowData.length) {
    return (
      <div className="card flow-card">
        <h3 className="card-title">Flow Vectors</h3>
        <div className="heatmap-placeholder"><span>No flow data</span></div>
      </div>
    );
  }

  const maxMag = Math.max(...flowData.map(d => d.magnitude), 1);
  const W = 200, H = 150;

  return (
    <div className="card flow-card">
      <h3 className="card-title">Flow Vectors</h3>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ background: '#0f172a', borderRadius: 8 }}>
        <defs>
          <marker id="arrow" markerWidth="5" markerHeight="5"
                  refX="3" refY="2.5" orient="auto">
            <path d="M0,0 L0,5 L5,2.5 Z" fill="#6366f1" />
          </marker>
        </defs>
        {flowData.map((d, i) => (
          <FlowArrow key={i} x={d.x} y={d.y}
                     angle={d.angle} magnitude={d.magnitude} maxMag={maxMag} />
        ))}
      </svg>
    </div>
  );
}
