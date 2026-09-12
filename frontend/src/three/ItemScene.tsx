import type { Geometry, PreviewRecord } from "../contracts";

const labels = { front: "Front", side: "Side", top: "Top", three_quarter: "Three-quarter" } as const;

export function ItemScene({ geometry, previews, renderingFailed }: { geometry: Geometry; previews: PreviewRecord[]; renderingFailed: boolean }) {
  const actual = previews.filter(preview => preview.view !== "thumbnail");
  if (actual.length) return (
    <section className="preview-card" aria-label="Canonical model previews">
      <h2>Model views</h2>
      <div className="preview-grid">{actual.map(preview => <figure key={preview.id}>
        <img src={`/api/previews/${preview.id}`} alt={`${labels[preview.view as keyof typeof labels]} view of the uploaded model`} />
        <figcaption>{labels[preview.view as keyof typeof labels]}</figcaption>
      </figure>)}</div>
    </section>
  );
  const dimensions = geometry.canonical_dimensions_mm;
  return (
    <section className="preview-card cuboid-fallback" aria-label="Dimension fallback">
      <h2>Dimension preview</h2>
      <div className="cuboid" aria-hidden="true"><span /></div>
      <p>{dimensions.width.toFixed(1)} × {dimensions.height.toFixed(1)} × {dimensions.depth.toFixed(1)} mm</p>
      <small>{renderingFailed ? "The uploaded model could not be rendered here. This is a labeled bounding-box fallback, not an actual scan." : "Preparing model views…"}</small>
    </section>
  );
}
