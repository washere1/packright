import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import type { LibraryItem, Placement, Suitcase } from "../contracts";
import { placementCenter, sceneContract, sourceModelMatrix } from "./sceneContract";

function disposeObject(root: THREE.Object3D) { root.traverse(child => { const mesh = child as THREE.Mesh; mesh.geometry?.dispose(); const material = mesh.material; if (Array.isArray(material)) material.forEach(value => value.dispose()); else material?.dispose(); }); }
function clearGroup(group: THREE.Group) { for (const child of [...group.children]) { group.remove(child); disposeObject(child); } }
interface Runtime { renderer: THREE.WebGLRenderer; scene: THREE.Scene; camera: THREE.PerspectiveCamera; controls: OrbitControls; suitcase: THREE.Group; items: THREE.Group; frame: number; observer: ResizeObserver }

export function PackingScene({ placements, suitcase, catalog, colors, xray, detailedMeshes, showShell, showClearance, showCom, resetToken, onMeshFailure, onSelect }: {
  placements: Placement[]; suitcase: Suitcase; catalog: LibraryItem[]; colors: Map<string, string>; xray: boolean; detailedMeshes: boolean; showShell: boolean; showClearance: boolean; showCom: boolean; resetToken: number; onMeshFailure: (message: string) => void; onSelect: (instanceId: string) => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null); const runtimeRef = useRef<Runtime | null>(null); const loadGeneration = useRef(0);
  const [webglFailure, setWebglFailure] = useState(false); const failureRef = useRef(onMeshFailure); failureRef.current = onMeshFailure; const selectRef = useRef(onSelect); selectRef.current = onSelect;
  const resetCamera = () => { const runtime = runtimeRef.current; if (!runtime) return; const c = sceneContract(suitcase); runtime.controls.target.copy(c.center.multiplyScalar(c.scale)); runtime.camera.position.set(1.35, 1.05, 1.45); runtime.camera.lookAt(runtime.controls.target); runtime.controls.update(); };

  useEffect(() => {
    const canvas = canvasRef.current; if (!canvas) return; let renderer: THREE.WebGLRenderer;
    try { renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true }); } catch { setWebglFailure(true); return; }
    const scene = new THREE.Scene(); scene.background = new THREE.Color("#f7f5ef"); const camera = new THREE.PerspectiveCamera(35, 1, .001, 100); const controls = new OrbitControls(camera, canvas); controls.enableDamping = true; controls.enablePan = false;
    scene.add(new THREE.HemisphereLight("#ffffff", "#756d62", 2.5)); const key = new THREE.DirectionalLight("#ffffff", 2); key.position.set(2, 3, 4); scene.add(key);
    const suitcaseGroup = new THREE.Group(), items = new THREE.Group(); scene.add(suitcaseGroup, items);
    const resize = () => { const width = Math.max(320, canvas.clientWidth || 640), height = Math.max(260, canvas.clientHeight || 420); camera.aspect = width / height; camera.updateProjectionMatrix(); renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2)); renderer.setSize(width, height, false); };
    const observer = new ResizeObserver(resize); observer.observe(canvas); resize();
    const raycaster = new THREE.Raycaster(), pointer = new THREE.Vector2(); const click = (event: MouseEvent) => { const rect = canvas.getBoundingClientRect(); pointer.set((event.clientX - rect.left) / rect.width * 2 - 1, -(event.clientY - rect.top) / rect.height * 2 + 1); raycaster.setFromCamera(pointer, camera); const hit = raycaster.intersectObjects(items.children, true).find(value => value.object.userData.instanceId); if (hit) selectRef.current(hit.object.userData.instanceId as string); }; canvas.addEventListener("click", click);
    const runtime: Runtime = { renderer, scene, camera, controls, suitcase: suitcaseGroup, items, frame: 0, observer }; runtimeRef.current = runtime;
    const animate = () => { runtime.frame = requestAnimationFrame(animate); controls.update(); renderer.render(scene, camera); }; animate(); resetCamera();
    return () => { loadGeneration.current += 1; canvas.removeEventListener("click", click); cancelAnimationFrame(runtime.frame); observer.disconnect(); controls.dispose(); clearGroup(items); clearGroup(suitcaseGroup); renderer.dispose(); runtimeRef.current = null; };
  }, []);

  useEffect(() => {
    const runtime = runtimeRef.current; if (!runtime) return; clearGroup(runtime.suitcase); const c = sceneContract(suitcase), s = c.scale;
    const panelMaterial = new THREE.MeshStandardMaterial({ color: "#64747b", transparent: true, opacity: showShell ? (xray ? .045 : .13) : 0, side: THREE.DoubleSide, depthWrite: false });
    const outer = new THREE.Mesh(new THREE.BoxGeometry(c.outer.x * s, c.outer.y * s, c.outer.z * s), panelMaterial); outer.position.copy(c.center).multiplyScalar(s); outer.visible = showShell; runtime.suitcase.add(outer);
    const outerEdges = new THREE.LineSegments(new THREE.EdgesGeometry(outer.geometry), new THREE.LineBasicMaterial({ color: "#253940", transparent: true, opacity: .9 })); outerEdges.position.copy(outer.position); outerEdges.visible = showShell; runtime.suitcase.add(outerEdges);
    const usableEdges = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(c.usable.x * s, c.usable.y * s, c.usable.z * s)), new THREE.LineDashedMaterial({ color: "#d38a2e", dashSize: .025, gapSize: .012, transparent: true, opacity: .9 })); usableEdges.position.copy(c.usableOrigin.clone().add(c.usable.clone().multiplyScalar(.5))).multiplyScalar(s); usableEdges.visible = showClearance; usableEdges.computeLineDistances(); runtime.suitcase.add(usableEdges);
    const dark = new THREE.MeshStandardMaterial({ color: "#26343a", roughness: .7 }), wheelR = .035;
    [[.12, .12], [.88, .12], [.12, .88], [.88, .88]].forEach(([fx, fz]) => { const wheel = new THREE.Mesh(new THREE.CylinderGeometry(wheelR, wheelR, .035, 20), dark); wheel.rotation.z = Math.PI / 2; wheel.position.set(fx * c.outer.x * s, -.025, fz * c.outer.z * s); runtime.suitcase.add(wheel); });
    const handlePoints = [[.42, 1.025, .5], [.42, 1.16, .5], [.58, 1.16, .5], [.58, 1.025, .5]].map(v => new THREE.Vector3(v[0] * c.outer.x * s, v[1] * c.outer.y * s, v[2] * c.outer.z * s)); runtime.suitcase.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(handlePoints), new THREE.LineBasicMaterial({ color: "#26343a" })));
    const lid = new THREE.Mesh(new THREE.BoxGeometry(c.outer.x * s, .018, c.outer.z * s), panelMaterial.clone()); lid.position.set(c.center.x * s, c.outer.y * s + .12, c.center.z * s); lid.rotation.x = -.22; lid.visible = showShell; runtime.suitcase.add(lid);
    const target = new THREE.Mesh(new THREE.BoxGeometry(c.usable.x * s * .18, c.usable.y * s * .12, c.usable.z * s * .18), new THREE.MeshBasicMaterial({ color: "#bd8b35", wireframe: true, transparent: true, opacity: .75 })); target.position.copy(c.center).multiplyScalar(s); target.visible = showCom; runtime.suitcase.add(target);
  }, [suitcase, xray, showShell, showClearance, showCom]);

  useEffect(() => {
    const runtime = runtimeRef.current; if (!runtime) return; const generation = ++loadGeneration.current; clearGroup(runtime.items); const c = sceneContract(suitcase), items = new Map(catalog.map(item => [item.id, item])), loader = new GLTFLoader(); let weighted = new THREE.Vector3(), total = 0;
    placements.forEach(placement => {
      const center = placementCenter(placement, c), item = items.get(placement.item_id), group = new THREE.Group(); group.position.copy(center).multiplyScalar(c.scale); group.userData.instanceId = placement.instance_id;
      const color = new THREE.Color(colors.get(placement.instance_id) ?? "#5877a8"), d = placement.dimensions_mm; const volume = new THREE.Mesh(new THREE.BoxGeometry(d.width * c.scale, d.height * c.scale, d.depth * c.scale), new THREE.MeshStandardMaterial({ color, transparent: true, opacity: detailedMeshes && item?.geometry ? .2 : .86, roughness: .65 })); volume.userData.instanceId = placement.instance_id; group.add(volume);
      const edges = new THREE.LineSegments(new THREE.EdgesGeometry(volume.geometry), new THREE.LineBasicMaterial({ color: color.clone().multiplyScalar(.62), transparent: true, opacity: .95 })); edges.userData.instanceId = placement.instance_id; group.add(edges); runtime.items.add(group);
      const weight = item?.weight_g ?? 1; weighted.add(center.clone().multiplyScalar(weight)); total += weight;
      if (detailedMeshes && item?.asset_id && item.geometry) loader.load(`/api/assets/${item.asset_id}/model.glb`, gltf => { if (generation !== loadGeneration.current || !runtimeRef.current) return; const model = gltf.scene; model.applyMatrix4(sourceModelMatrix(item.geometry!, placement, c)); model.traverse(child => { const mesh = child as THREE.Mesh; mesh.userData.instanceId = placement.instance_id; if (mesh.material) { const source = Array.isArray(mesh.material) ? mesh.material : [mesh.material]; mesh.material = source.map(material => { const clone = material.clone(); clone.side = THREE.DoubleSide; return clone; }); } }); group.add(model); }, undefined, () => { if (generation === loadGeneration.current) failureRef.current(`${item.name} model could not load; its validated cuboid is still shown.`); });
    });
    if (total && showCom) { weighted.multiplyScalar(1 / total); const marker = new THREE.Mesh(new THREE.SphereGeometry(.018, 18, 18), new THREE.MeshBasicMaterial({ color: "#c53f35" })); marker.position.copy(weighted).multiplyScalar(c.scale); runtime.items.add(marker); }
  }, [placements, suitcase, catalog, colors, detailedMeshes, showCom]);

  useEffect(() => { resetCamera(); }, [resetToken]);
  if (webglFailure) return <div className="packing-scene scene-fallback" role="img" aria-label="3D unavailable"><strong>3D preview unavailable</strong><span>The validated packing instructions and exact coordinates remain available below.</span></div>;
  return <canvas ref={canvasRef} className="packing-scene" aria-label="Orbitable validated suitcase packing scene" />;
}
