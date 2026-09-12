import * as THREE from "three";
import type { Geometry, Placement, Suitcase } from "../contracts";

export interface SceneContract {
  scale: number;
  outer: THREE.Vector3;
  usable: THREE.Vector3;
  usableOrigin: THREE.Vector3;
  center: THREE.Vector3;
}

export function sceneContract(suitcase: Suitcase): SceneContract {
  const outer = new THREE.Vector3(suitcase.internal_dimensions_mm.width, suitcase.internal_dimensions_mm.height, suitcase.internal_dimensions_mm.depth);
  const usable = outer.clone().subScalar(suitcase.clearance_mm);
  const usableOrigin = new THREE.Vector3().addScalar(suitcase.clearance_mm / 2);
  return { scale: 1 / Math.max(outer.x, outer.y, outer.z), outer, usable, usableOrigin, center: outer.clone().multiplyScalar(.5) };
}

export function placementCenter(placement: Placement, contract: SceneContract): THREE.Vector3 {
  return contract.usableOrigin.clone().add(new THREE.Vector3(...placement.position_mm)).add(new THREE.Vector3(placement.dimensions_mm.width, placement.dimensions_mm.height, placement.dimensions_mm.depth).multiplyScalar(.5));
}

export function sourceModelMatrix(geometry: Geometry, placement: Placement, contract: SceneContract): THREE.Matrix4 {
  const source = new THREE.Matrix4().set(...geometry.source_to_canonical as [number, number, number, number, number, number, number, number, number, number, number, number, number, number, number, number]);
  const m = placement.orientation_matrix.values;
  const orientation = new THREE.Matrix4().set(m[0][0], m[0][1], m[0][2], 0, m[1][0], m[1][1], m[1][2], 0, m[2][0], m[2][1], m[2][2], 0, 0, 0, 0, 1);
  return new THREE.Matrix4().makeScale(contract.scale, contract.scale, contract.scale).multiply(orientation).multiply(source);
}

export function placementInsideSuitcase(placement: Placement, contract: SceneContract, epsilon = 1e-6): boolean {
  const [x, y, z] = placement.position_mm; const d = placement.dimensions_mm;
  return x >= -epsilon && y >= -epsilon && z >= -epsilon && x + d.width <= contract.usable.x + epsilon && y + d.height <= contract.usable.y + epsilon && z + d.depth <= contract.usable.z + epsilon;
}
