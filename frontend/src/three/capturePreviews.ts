import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { uploadPreview } from "../api";
import type { Geometry, PreviewRecord, PreviewView } from "../contracts";

export const RENDERER_VERSION = "three-r180-v2";
const SIZE = 512;

export class PreviewCaptureError extends Error {
  constructor(message: string) { super(message); this.name = "PreviewCaptureError"; }
}

function matrixFromRowMajor(values: number[]): THREE.Matrix4 {
  const matrix = new THREE.Matrix4();
  matrix.set(...values as [number, number, number, number, number, number, number, number, number, number, number, number, number, number, number, number]);
  return matrix;
}

function dispose(root: THREE.Object3D) {
  root.traverse(object => {
    if (!(object instanceof THREE.Mesh)) return;
    object.geometry.dispose();
    const materials = Array.isArray(object.material) ? object.material : [object.material];
    for (const material of materials) {
      for (const value of Object.values(material)) if (value instanceof THREE.Texture) value.dispose();
      material.dispose();
    }
  });
}

function preparePreviewMaterial(mesh: THREE.Mesh) {
  const source = Array.isArray(mesh.material) ? mesh.material[0] : mesh.material;
  const sourceColor = source && "color" in source ? (source as THREE.MeshStandardMaterial).color : null;
  const tooLight = !sourceColor || sourceColor.r * .2126 + sourceColor.g * .7152 + sourceColor.b * .0722 > .82;
  const material = new THREE.MeshStandardMaterial({
    color: tooLight ? 0x527864 : sourceColor,
    map: source && "map" in source ? (source as THREE.MeshStandardMaterial).map : null,
    roughness: .72,
    metalness: source && "metalness" in source ? Math.min((source as THREE.MeshStandardMaterial).metalness, .35) : .05,
    transparent: false, opacity: 1, side: THREE.DoubleSide,
  });
  const materials = Array.isArray(mesh.material) ? mesh.material : mesh.material ? [mesh.material] : [];
  materials.forEach(value => value.dispose());
  mesh.material = material;
}

function verifyNonblank(renderer: THREE.WebGLRenderer) {
  const pixels = new Uint8Array(SIZE * SIZE * 4);
  renderer.readRenderTargetPixels(renderer.getRenderTarget() as THREE.WebGLRenderTarget, 0, 0, SIZE, SIZE, pixels);
  let min = 255, max = 0;
  for (let index = 0; index < pixels.length; index += 4) {
    min = Math.min(min, pixels[index], pixels[index + 1], pixels[index + 2]);
    max = Math.max(max, pixels[index], pixels[index + 1], pixels[index + 2]);
  }
  if (max - min < 8) throw new PreviewCaptureError("The browser produced a blank preview.");
}

function canvasBlob(canvas: HTMLCanvasElement): Promise<Blob> {
  return new Promise((resolve, reject) => canvas.toBlob(
    blob => blob ? resolve(blob) : reject(new PreviewCaptureError("The preview could not be encoded.")), "image/png",
  ));
}

export async function captureAndUploadPreviews(itemId: string, geometry: Geometry): Promise<PreviewRecord[]> {
  if (!window.WebGLRenderingContext) throw new PreviewCaptureError("WebGL is unavailable; metadata fallback will be used.");
  const canvas = document.createElement("canvas");
  canvas.width = SIZE; canvas.height = SIZE;
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false, preserveDrawingBuffer: true });
  renderer.setSize(SIZE, SIZE, false);
  renderer.setPixelRatio(1);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;
  renderer.setClearColor(0xdde4e0, 1);
  const scene = new THREE.Scene();
  const group = new THREE.Group();
  scene.add(group);
  scene.add(new THREE.HemisphereLight(0xffffff, 0x526159, 1.35));
  const key = new THREE.DirectionalLight(0xffffff, 1.8); key.position.set(2, 3, 4); scene.add(key);
  const fill = new THREE.DirectionalLight(0xbfd6ca, .65); fill.position.set(-3, 1, -2); scene.add(fill);
  const camera = new THREE.PerspectiveCamera(35, 1, 0.1, 10000);
  const target = new THREE.WebGLRenderTarget(SIZE, SIZE, { colorSpace: THREE.SRGBColorSpace });
  renderer.setRenderTarget(target);

  try {
    const gltf = await new GLTFLoader().loadAsync(`/api/assets/${geometry.asset_id}/model.glb`);
    gltf.scene.updateMatrixWorld(true);
    gltf.scene.traverse(object => { if (object instanceof THREE.Mesh) preparePreviewMaterial(object); });
    group.add(gltf.scene);
    group.applyMatrix4(matrixFromRowMajor(geometry.source_to_canonical));
    group.updateMatrixWorld(true);

    const bounds = new THREE.Box3().setFromObject(group);
    if (bounds.isEmpty()) throw new PreviewCaptureError("The transformed model has no visible bounds.");
    const center = bounds.getCenter(new THREE.Vector3());
    const radius = Math.max(bounds.getBoundingSphere(new THREE.Sphere()).radius, 1);
    group.position.sub(center); group.updateMatrixWorld(true);
    const distance = radius / Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)) * 1.3;
    camera.near = Math.max(.1, distance - radius * 2.2); camera.far = distance + radius * 3; camera.updateProjectionMatrix();
    const views: Array<[Exclude<PreviewView, "thumbnail">, THREE.Vector3, THREE.Vector3]> = [
      ["front", new THREE.Vector3(0, 0, distance), new THREE.Vector3(0, 1, 0)],
      ["side", new THREE.Vector3(distance, 0, 0), new THREE.Vector3(0, 1, 0)],
      ["top", new THREE.Vector3(0, distance, 0), new THREE.Vector3(0, 0, -1)],
      ["three_quarter", new THREE.Vector3(distance, distance * .72, distance), new THREE.Vector3(0, 1, 0)],
    ];
    const records: PreviewRecord[] = [];
    for (const [view, position, up] of views) {
      camera.position.copy(position); camera.up.copy(up); camera.lookAt(0, 0, 0); camera.updateMatrixWorld();
      renderer.setRenderTarget(target);
      renderer.render(scene, camera);
      verifyNonblank(renderer);
      renderer.setRenderTarget(null); renderer.render(scene, camera);
      const image = await canvasBlob(canvas);
      records.push(await uploadPreview(itemId, geometry.version, view, image));
    }
    return records;
  } catch (reason) {
    if (reason instanceof PreviewCaptureError) throw reason;
    throw new PreviewCaptureError(reason instanceof Error ? `Preview rendering failed: ${reason.message}` : "Preview rendering failed.");
  } finally {
    dispose(group); target.dispose(); renderer.dispose();
  }
}
