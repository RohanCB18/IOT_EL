import { useEffect, useRef, useState, useCallback } from 'react';
import mqtt from 'mqtt';

const BROKER_URL = 'ws://localhost:9001';
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
  const [actuation,  setActuation]  = useState(DEFAULT_ACTUATION);
  const [alerts,     setAlerts]     = useState([]);
  const [trendData,  setTrendData]  = useState([]);

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
      client.subscribe('oracle/#', { qos: 0 });
    });

    client.on('disconnect', () => setConnected(false));
    client.on('offline',    () => setConnected(false));
    client.on('error',      (err) => console.error('[MQTT]', err.message));

    client.on('message', (topic, payload) => {
      try {
        const raw = payload.toString();

        if (topic === 'oracle/node1/heatmap') {
          setHeatmapB64(raw);
          return;
        }

        const data = JSON.parse(raw);

        if (topic === 'oracle/node1/metrics') {
          setMetrics(data);
          setTrendData((prev) => {
            const point = {
              time:  data.timestamp,
              risk:  data.risk_score,
              label: new Date(data.timestamp).toLocaleTimeString(),
            };
            return [...prev, point].slice(-MAX_TREND_POINTS);
          });
        } else if (topic === 'oracle/node1/actuation') {
          setActuation(data);
        } else if (topic === 'oracle/node1/alert') {
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

  return { connected, metrics, heatmapB64, actuation, alerts, trendData };
}
