export default function CameraFeed({ frameB64 = null }) {
  return (
    <div className="card feed-card">
      <h3 className="card-title">Camera Feed</h3>
      <div className="heatmap-frame">
        {frameB64 ? (
          <img
            src={`data:image/jpeg;base64,${frameB64}`}
            alt="annotated camera feed"
            className="heatmap-img"
          />
        ) : (
          <div className="heatmap-placeholder">
            <span>Waiting for feed…</span>
          </div>
        )}
      </div>
    </div>
  );
}
