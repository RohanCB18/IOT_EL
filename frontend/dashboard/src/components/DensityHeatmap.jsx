import { useState, useEffect } from 'react';

export default function DensityHeatmap({ heatmapB64 = null }) {
  const [timeStr, setTimeStr] = useState('');

  useEffect(() => {
    const updateTime = () => {
      const d = new Date();
      setTimeStr(d.toLocaleTimeString() + '.' + String(d.getMilliseconds()).padStart(3, '0'));
    };
    updateTime();
    const interval = setInterval(updateTime, 100);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="card video-card">
      <div className="card-header-row">
        <h3 className="card-title">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
            <path d="M8 3v18M16 3v18M3 8h18M3 16h18" strokeWidth="1" strokeDasharray="3 3" opacity="0.3" />
            <circle cx="12" cy="12" r="3" fill="currentColor" />
          </svg>
          Density Heatmap
        </h3>
      </div>
      
      <div className={`viewport-frame ${!heatmapB64 ? 'loading' : ''}`}>
        {heatmapB64 ? (
          <>
            <img
              src={`data:image/jpeg;base64,${heatmapB64}`}
              alt="density heatmap"
              className="feed-img"
            />
            {/* Sci-Fi HUD CCTV Overlays */}
            <div className="cctv-overlay-top">
              <div className="cctv-live-badge" style={{ color: 'var(--color-primary)' }}>
                <span className="cctv-dot" style={{ backgroundColor: 'var(--color-primary)', boxShadow: '0 0 8px var(--color-primary)' }} />
                <span>THERMAL</span>
              </div>
              <div className="cctv-meta">NODE_01_HEAT</div>
            </div>
            
            <div className="cctv-overlay-bottom">
              <div className="cctv-timestamp">{timeStr}</div>
              <div className="cctv-rec" style={{ color: 'var(--color-primary)' }}>PROCESS_LIVE</div>
            </div>
          </>
        ) : (
          <div className="feed-placeholder">
            <div className="loading-ring" style={{ borderTopColor: 'var(--color-secondary)' }} />
            <span>Establishing link to thermal grid...</span>
          </div>
        )}
      </div>
    </div>
  );
}
