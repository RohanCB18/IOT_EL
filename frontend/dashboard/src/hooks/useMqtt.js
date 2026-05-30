import { useEffect, useRef, useState, useCallback } from 'react';
import mqtt from 'mqtt';

const BROKER_URL = 'ws://broker.hivemq.com:8000/mqtt';
const MAX_TREND_POINTS = 120;   // ~60 s at ~2 fps
const MAX_ALERTS       = 50;

const DEFAULT_METRICS = {
  count:       0,
  density:     0,
  risk_score:  0,
  flow_mag:    0,
  divergence:  0,
  chaos:       0,
  alert_level: 'SAFE',
  timestamp:   null,
};

const DEFAULT_ACTUATION = { command: 'GATE_OPEN', timestamp: null };

export function useMqtt(brokerUrl = BROKER_URL) {
  const clientRef = useRef(null);

  const [connected,  setConnected]  = useState(false);
  const [metrics,    setMetrics]    = useState(DEFAULT_METRICS);
  const [heatmapB64, setHeatmapB64] = useState(null);
  const [cameraB64,  setCameraB64]  = useState(null);
  const [actuation,  setActuation]  = useState(DEFAULT_ACTUATION);
  const [alerts,     setAlerts]     = useState([]);
  const [trendData,  setTrendData]  = useState([]);
  const [flowData,   setFlowData]   = useState([]);

  const addAlert = useCallback((payload) => {
    setAlerts((prev) => [
      { ...payload, id: Date.now() + Math.random() },
      ...prev,
    ].slice(0, MAX_ALERTS));
  }, []);

  useEffect(() => {
    const client = mqtt.connect(brokerUrl, {
      reconnectPeriod: 3000,
      connectTimeout:  10000,
      protocolVersion: 4,
    });
    clientRef.current = client;

    client.on('connect', () => {
      setConnected(true);
      client.subscribe('oracle_rohan_123/#', { qos: 0 });
    });

    client.on('disconnect', () => setConnected(false));
    client.on('offline',    () => setConnected(false));
    client.on('error',      (err) => console.error('[MQTT]', err.message));

    client.on('message', (topic, payload) => {
      try {
        const raw = payload.toString();

        if (topic === 'oracle_rohan_123/node1/heatmap') {
          setHeatmapB64(raw);
          return;
        }

        if (topic === 'oracle_rohan_123/node1/camera') {
          setCameraB64(raw);
          return;
        }

        const data = JSON.parse(raw);

        if (topic === 'oracle_rohan_123/node1/metrics') {
          setMetrics(data);
          setTrendData((prev) => {
            const point = {
              time:  data.timestamp,
              risk:  data.risk_score,
              label: new Date(data.timestamp).toLocaleTimeString(),
            };
            return [...prev, point].slice(-MAX_TREND_POINTS);
          });

          // Generate dynamic flow vectors based on live metrics
          setFlowData(generateFlowVectors(data.flow_mag, data.divergence, data.chaos));
        } else if (topic === 'oracle_rohan_123/node1/actuation') {
          setActuation(data);
        } else if (topic === 'oracle_rohan_123/node1/alert') {
          if (data.level !== 'SAFE') addAlert(data);
        }
      } catch (e) {
        console.warn('[MQTT] parse error', e);
      }
    });

    return () => {
      client.end(true);
    };
  }, [brokerUrl, addAlert]);

  return { connected, metrics, heatmapB64, cameraB64, actuation, alerts, trendData, flowData };
}

// --- Dynamic Flow Vector Generator Helper ---
function generateFlowVectors(flowMag, divergence, chaos) {
  const vectors = [];
  const cols = 6;
  const rows = 5;
  const W = 200;
  const H = 150;
  
  const stepX = W / (cols + 1);
  const stepY = H / (rows + 1);
  
  // Base angle representing global motion
  const globalAngle = (Date.now() / 2500) % (2 * Math.PI); // slowly rotating global direction
  
  for (let c = 1; c <= cols; c++) {
    for (let r = 1; r <= rows; r++) {
      const x = c * stepX;
      const y = r * stepY;
      
      // Calculate radial angle relative to center
      const dx = 100 - x;
      const dy = 75 - y;
      const radialAngle = Math.atan2(dy, dx);
      
      // Interpolate base angle based on divergence magnitude
      let baseAngle = globalAngle;
      
      if (divergence < -0.05) {
        // Compress (towards center)
        baseAngle = radialAngle;
      } else if (divergence > 0.05) {
        // Expand (away from center)
        baseAngle = radialAngle + Math.PI;
      }
      
      // Add chaos noise
      const noise = (Math.random() - 0.5) * chaos * 0.8;
      const angle = baseAngle + noise;
      
      // Add magnitude with individual variance
      const magnitude = flowMag * (0.6 + Math.random() * 0.6);
      
      vectors.push({ x, y, angle, magnitude });
    }
  }
  return vectors;
}
