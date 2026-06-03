const W = 200;
const H = 150;

function FlowArrow({ x, y, angle, magnitude, maxMag }) {
  const ratio = magnitude / maxMag;
  // Dynamic sizing based on magnitude ratio
  const len = 8 + ratio * 16;
  const rad = angle;
  const ex = x + len * Math.cos(rad);
  const ey = y + len * Math.sin(rad);
  const alpha = 0.35 + ratio * 0.65;
  
  // Highlight fast vectors in purple/amber, slow in indigo
  const strokeColor = ratio > 0.7 ? '#c084fc' : ratio > 0.4 ? '#6366f1' : '#3b82f6';

  return (
    <g opacity={alpha}>
      <line
        x1={x} y1={y}
        x2={ex} y2={ey}
        stroke={strokeColor}
        strokeWidth={1.5}
        markerEnd={`url(#arrow-${ratio > 0.7 ? 'fast' : ratio > 0.4 ? 'medium' : 'slow'})`}
      />
      <circle cx={x} cy={y} r="1" fill={strokeColor} opacity={0.5} />
    </g>
  );
}

export default function FlowVectorOverlay({ flowData = null }) {
  const hasData = flowData && flowData.length > 0;
  const maxMag = hasData ? Math.max(...flowData.map(d => d.magnitude), 1) : 1;

  return (
    <div className="card flow-card">
      <div className="card-header-row">
        <h3 className="card-title">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
            <polyline points="3.27 6.96 12 12.01 20.73 6.96" />
            <line x1="12" y1="22.08" x2="12" y2="12" />
          </svg>
          Optical Motion Fields
        </h3>
      </div>
      
      <div className="viewport-frame" style={{ aspectRatio: '4/3', display: 'block', height: 'auto' }}>
        {hasData ? (
          <svg viewBox={`0 0 ${W} ${H}`} width="100%" height="100%" style={{ background: 'transparent', display: 'block' }}>
            <defs>
              {/* Radar Coordinate Grid Backdrop */}
              <pattern id="matrix-grid" width="20" height="20" patternUnits="userSpaceOnUse">
                <path d="M 20 0 L 0 0 0 20" fill="none" stroke="rgba(99, 102, 241, 0.04)" strokeWidth="0.5"/>
                <circle cx="20" cy="20" r="0.7" fill="rgba(99, 102, 241, 0.15)" />
              </pattern>
              
              {/* Color-coded Arrow Markers */}
              <marker id="arrow-slow" markerWidth="4" markerHeight="4" refX="2.5" refY="2" orient="auto">
                <path d="M0,0 L0,4 L4,2 Z" fill="#3b82f6" />
              </marker>
              <marker id="arrow-medium" markerWidth="4" markerHeight="4" refX="2.5" refY="2" orient="auto">
                <path d="M0,0 L0,4 L4,2 Z" fill="#6366f1" />
              </marker>
              <marker id="arrow-fast" markerWidth="4" markerHeight="4" refX="2.5" refY="2" orient="auto">
                <path d="M0,0 L0,4 L4,2 Z" fill="#c084fc" />
              </marker>
            </defs>
            
            {/* Grid Pattern overlay */}
            <rect width={W} height={H} fill="url(#matrix-grid)" />
            
            {/* Center target indicator lines */}
            <line x1={W/2} y1="0" x2={W/2} y2={H} stroke="rgba(255, 255, 255, 0.02)" strokeWidth="1" strokeDasharray="3 3" />
            <line x1="0" y1={H/2} x2={W} y2={H/2} stroke="rgba(255, 255, 255, 0.02)" strokeWidth="1" strokeDasharray="3 3" />
            
            {/* Live Flow Vectors */}
            {flowData.map((d, i) => (
              <FlowArrow key={i} x={d.x} y={d.y}
                         angle={d.angle} magnitude={d.magnitude} maxMag={maxMag} />
            ))}
          </svg>
        ) : (
          <div className="feed-placeholder" style={{ height: '100%', justifyContent: 'center' }}>
            <div className="loading-ring" style={{ width: '24px', height: '24px', borderTopColor: 'var(--color-primary)' }} />
            <span>Awaiting telemetry stream...</span>
          </div>
        )}
      </div>
    </div>
  );
}
