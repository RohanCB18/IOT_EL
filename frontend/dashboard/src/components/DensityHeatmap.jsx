export default function DensityHeatmap({ heatmapB64 = null }) {
  return (
    <div className="card heatmap-card">
      <h3 className="card-title">Density Heatmap</h3>
      <div className="heatmap-frame">
        {heatmapB64 ? (
          <img
            src={`data:image/jpeg;base64,${heatmapB64}`}
            alt="density heatmap"
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
