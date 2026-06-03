import { useState, useEffect } from 'react';

export default function CameraFeed({ frameB64 = null }) {
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
            <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" />
            <circle cx="12" cy="13" r="4" />
          </svg>
          Live Optical Stream
        </h3>
      </div>
      
      <div className={`viewport-frame ${!frameB64 ? 'loading' : ''}`}>
        {frameB64 ? (
          <>
            <img
              src={`data:image/jpeg;base64,${frameB64}`}
              alt="annotated camera feed"
              className="feed-img"
            />
            {/* Sci-Fi HUD CCTV Overlays */}
            <div className="cctv-overlay-top">
              <div className="cctv-live-badge">
                <span className="cctv-dot" />
                <span>LIVE</span>
              </div>
              <div className="cctv-meta">CAM-01_INPUT</div>
            </div>
            
            <div className="cctv-overlay-bottom">
              <div className="cctv-timestamp">{timeStr}</div>
              <div className="cctv-rec">SYS_ACTIVE</div>
            </div>
          </>
        ) : (
          <div className="feed-placeholder">
            <div className="loading-ring" />
            <span>Establishing link to camera...</span>
          </div>
        )}
      </div>
    </div>
  );
}
