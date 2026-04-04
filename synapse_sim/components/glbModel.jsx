'use client';

import { useGLTF } from '@react-three/drei';
import { rotationsToEuler, wpiToThree } from './math_util';
import * as THREE from 'three';

export const fieldWidthMeters = 651.220 * 0.0254;
export const fieldLengthMeters = 317.677 * 0.0254;

export function RobotModel({
  modelUrl,
  pose,
  cameraOffsetWpi = { position: [0, 0, 0], rotations: [] }
}) {
  // --- clone the GLB scene for multiple Kitbots ---
  const { scene: originalScene } = useGLTF(modelUrl);
  const scene = originalScene.clone(true);
  centerScene(scene);

  // --- robot position in WPI coordinates ---
  const wpiPosition = [
    -pose.position[0] + fieldWidthMeters / 2,
    -pose.position[1] + fieldLengthMeters / 2,
    pose.position[2],
  ];
  const threePosition = new THREE.Vector3(...wpiToThree(wpiPosition));

  // --- robot rotation ---
  const robotEuler = rotationsToEuler(pose.rotations, [0, -Math.PI / 2, 0]);
  const robotQuat = new THREE.Quaternion().setFromEuler(robotEuler);

  // --- camera offset ---
  const cameraOffsetVec = new THREE.Vector3(
    ...wpiToThree([
      cameraOffsetWpi.position[0],
      -cameraOffsetWpi.position[1],
      cameraOffsetWpi.position[2],
    ])
  );
  cameraOffsetVec.applyQuaternion(robotQuat);
  const cameraWorldPos = threePosition.clone().add(cameraOffsetVec);

  // --- camera rotation ---
  const cameraEuler = rotationsToEuler(cameraOffsetWpi.rotations, [0, 0, 0]);
  const cameraQuat = new THREE.Quaternion().setFromEuler(cameraEuler).multiply(robotQuat);
  const finalCameraEuler = new THREE.Euler().setFromQuaternion(cameraQuat);

  return (
    <>
      {/* robot */}
      <group position={threePosition} rotation={robotEuler}>
        <primitive object={scene} />
      </group>

      {/* camera marker */}
      <group position={cameraWorldPos} rotation={finalCameraEuler}>
        <mesh position={[0, 0, 0]}>
          <boxGeometry args={[0.2, 0.2, 0.2]} />
          <meshBasicMaterial color="red" />
        </mesh>
      </group>
    </>
  );
}

// --- center the cloned scene ---
function centerScene(scene) {
  if (!scene) return;
  const box = new THREE.Box3().setFromObject(scene, true);
  const center = new THREE.Vector3();
  box.getCenter(center);
  scene.position.x -= center.x;
  scene.position.z -= center.z;
}
