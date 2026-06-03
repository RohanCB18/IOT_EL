import { useState, useEffect } from 'react';
import './App.css';
import { useMqtt }       from './hooks/useMqtt';
import RiskGauge         from './components/RiskGauge';
import RiskTrendChart    from './components/RiskTrendChart';
import DensityHeatmap    from './components/DensityHeatmap';
import CameraFeed        from './components/CameraFeed';
import GateStatus        from './components/GateStatus';
import AlertLog          from './components/AlertLog';
import MetricsBar        from './components/MetricsBar';
import FlowVectorOverlay from './components/FlowVectorOverlay';

function ConnectionBadge({ connected }) {
  return (
    <div className={`conn-badge ${connected ? 'conn-ok' : 'conn-off'}`}>
      <span className="conn-dot" />
      {connected ? 'BROKER CONNECTED' : 'BROKER DISCONNECTED'}
    </div>
  );
}

export default function App() {
  const { connected, metrics, heatmapB64, cameraB64, actuation, alerts, trendData, flowData } = useMqtt();
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-left">
          <div className="header-icon-wrap">
            <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              <path d="M12 8v4" />
              <path d="M12 16h.01" />
            </svg>
          </div>
          <div>
            <h1 className="header-title">Crowd Safety Oracle</h1>
            <p className="header-sub">
              <span>Node: Edge-RPI-01</span>
              <span className="header-meta-dot"></span>
              <span>North Gate Entrance</span>
              <span className="header-meta-dot"></span>
              <span>Mode: Autonomous Safety</span>
            </p>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div className="cctv-meta" style={{ padding: '6px 14px', fontSize: '11px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2.5">
              <circle cx="12" cy="12" r="10" />
              <polyline points="12 6 12 12 16 14" />
            </svg>
            <span>{time.toLocaleDateString()} {time.toLocaleTimeString()}</span>
          </div>
          <ConnectionBadge connected={connected} />
        </div>
      </header>

      <MetricsBar metrics={metrics} />

      <main className="main-grid">
        <section className="col-left">
          <RiskGauge
            riskScore={metrics.risk_score}
            alertLevel={metrics.alert_level}
          />
          <GateStatus command={actuation.command} />
        </section>

        <section className="col-centre">
          <DensityHeatmap heatmapB64={heatmapB64} />
          <CameraFeed frameB64={cameraB64} />
        </section>

        <section className="col-right">
          <RiskTrendChart trendData={trendData} />
          <FlowVectorOverlay flowData={flowData} />
          <AlertLog alerts={alerts} />
        </section>
      </main>

      <footer className="app-footer">
        CROWD SAFETY ORACLE SYSTEM • EDGE PIPELINE PIPELINE PHASE IV • AUTONOMOUS GATE CONTROL
      </footer>
    </div>
  );
}
