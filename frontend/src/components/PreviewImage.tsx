import { useEffect, useState } from "react";

export function PreviewImage({ src, alt, className }: { src: string; alt: string; className?: string }) {
  const [state, setState] = useState<"loading" | "loaded" | "failed">("loading");
  useEffect(() => setState("loading"), [src]);
  return <div className={`preview-image ${className ?? ""}`} data-state={state}>
    {state === "loading" && <span className="preview-image-status">Loading preview…</span>}
    {state === "failed" && <span className="preview-image-status error">Preview unavailable</span>}
    <img src={src} alt={alt} hidden={state === "failed"} onLoad={() => setState("loaded")} onError={() => setState("failed")} />
  </div>;
}
