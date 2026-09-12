import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { uploadPreview } from "../api";
import type { Geometry, PreviewRecord, PreviewView } from "../contracts";

export const RENDERER_VERSION = "three-r180-v1";
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
  renderer.setClearColor(0xf3f0e8, 1);
  const scene = new THREE.Scene();
  const group = new THREE.Group();
  scene.add(group);
  scene.add(new THREE.HemisphereLight(0xffffff, 0x667069, 2.4));
  const key = new THREE.DirectionalLight(0xffffff, 3.2); key.position.set(2, 3, 4); scene.add(key);
  const fill = new THREE.DirectionalLight(0xc9ddff, 1.2); fill.position.set(-3, 1, -2); scene.add(fill);
  const camera = new THREE.PerspectiveCamera(35, 1, 0.1, Math.max(10000, geometry.preview_camera_distance_mm * 5));
  const target = new THREE.WebGLRenderTarget(SIZE, SIZE, { colorSpace: THREE.SRGBColorSpace });
  renderer.setRenderTarget(target);

  try {
    const gltf = await new GLTFLoader().loadAsync(`/api/assets/${geometry.asset_id}/model.glb`);
    gltf.scene.updateMatrixWorld(true);
    gltf.scene.traverse(object => {
      if (object instanceof THREE.Mesh && (!object.material || (Array.isArray(object.material) && object.material.length === 0))) {
        object.material = new THREE.MeshStandardMaterial({ color: 0x8da897, roughness: 0.72 });
      }
    });
    group.add(gltf.scene);
    group.applyMatrix4(matrixFromRowMajor(geometry.source_to_canonical));
    group.updateMatrixWorld(true);

    const distance = geometry.preview_camera_distance_mm;
    const views: Array<[Exclude<PreviewView, "thumbnail">, THREE.Vector3, THREE.Vector3]> = [
      ["front", new THREE.Vector3(0, 0, distance), new THREE.Vector3(0, 1, 0)],
      ["side", new THREE.Vector3(distance, 0, 0), new THREE.Vector3(0, 1, 0)],
      ["top", new THREE.Vector3(0, distance, 0), new THREE.Vector3(0, 0, -1)],
      ["three_quarter", new THREE.Vector3(distance, distance * .72, distance), new THREE.Vector3(0, 1, 0)],
    ];
    const records: PreviewRecord[] = [];
    for (const [view, position, up] of views) {
      camera.position.copy(position); camera.up.copy(up); camera.lookAt(0, 0, 0); camera.updateMatrixWorld();
      renderer.render(scene, camera);
      verifyNonblank(renderer);
      renderer.setRenderTarget(null); renderer.render(scene, camera);
      const image = await canvasBlob(canvas);
      records.push(await uploadPreview(itemId, geometry.version, view, image));
      renderer.setRenderTarget(target);
    }
    return records;
  } catch (reason) {
    if (reason instanceof PreviewCaptureError) throw reason;
    throw new PreviewCaptureError(reason instanceof Error ? `Preview rendering failed: ${reason.message}` : "Preview rendering failed.");
  } finally {
    dispose(group); target.dispose(); renderer.dispose();
  }
}
