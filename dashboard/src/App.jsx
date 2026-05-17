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
      {connected ? 'MQTT Connected' : 'Connecting...'}
    </div>
  );
}

export default function App() {
  const { connected, metrics, heatmapB64, actuation, alerts, trendData } = useMqtt();

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-left">
          <span className="header-icon">🏟️</span>
          <div>
            <h1 className="header-title">Crowd Safety Oracle</h1>
            <p className="header-sub">Real-time density and risk monitoring</p>
          </div>
        </div>
        <ConnectionBadge connected={connected} />
      </header>

      <MetricsBar metrics={metrics} />

      <main className="main-grid">
        <section className="col-left">
          <div className="card gauge-card">
            <h3 className="card-title">Risk Score</h3>
            <RiskGauge
              riskScore={metrics.risk_score}
              alertLevel={metrics.alert_level}
            />
          </div>
          <GateStatus command={actuation.command} />
        </section>

        <section className="col-centre">
          <DensityHeatmap heatmapB64={heatmapB64} />
          <CameraFeed frameB64={null} />
        </section>

        <section className="col-right">
          <RiskTrendChart trendData={trendData} />
          <FlowVectorOverlay flowData={null} />
          <AlertLog alerts={alerts} />
        </section>
      </main>

      <footer className="app-footer">
        IOT_EL - Oracle Pipeline - Phase 4
      </footer>
    </div>
  );
}
