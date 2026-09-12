import { useRef, type DragEvent, type KeyboardEvent } from "react";

interface Props {
  file: File | null;
  error?: string;
  disabled?: boolean;
  onChange: (file: File | null) => void;
}

export function ModelUploader({ file, error, disabled, onChange }: Props) {
  const input = useRef<HTMLInputElement>(null);
  const choose = () => { if (!disabled) input.current?.click(); };
  const drop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    if (!disabled) onChange(event.dataTransfer.files.item(0));
  };
  const keyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === "Enter" || event.key === " ") { event.preventDefault(); choose(); }
  };

  return (
    <div className="field-group">
      <label id="model-label">3D model <span>Required</span></label>
      <div
        className={`dropzone ${error ? "invalid" : ""}`}
        role="button"
        tabIndex={disabled ? -1 : 0}
        aria-labelledby="model-label"
        aria-describedby={error ? "model-error" : "model-help"}
        aria-disabled={disabled}
        onClick={choose}
        onKeyDown={keyDown}
        onDragOver={event => event.preventDefault()}
        onDrop={drop}
      >
        <strong>{file ? file.name : "Drop a GLB here"}</strong>
        <small>{file ? `${(file.size / 1_000_000).toFixed(2)} MB · Choose another file` : "or choose a file from your computer"}</small>
      </div>
      <input ref={input} className="visually-hidden" type="file" accept=".glb,model/gltf-binary" disabled={disabled}
        onChange={event => onChange(event.target.files?.item(0) ?? null)} />
      <p id={error ? "model-error" : "model-help"} className={error ? "field-error" : "field-help"}>
        {error ?? "GLB only, up to 50 MB."}
      </p>
    </div>
  );
}

