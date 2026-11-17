"use client";

import { useGLTF } from "@react-three/drei";
import { useThree } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";

import { rotationsToEuler, wpiToThree } from "./math_util";

export const fieldWidthMeters = 651.22 * 0.0254;
export const fieldLengthMeters = 317.677 * 0.0254;

interface Rotation {
  axis: "x" | "y" | "z";
  degrees: number;
}

interface CameraOffsetWpi {
  position: [number, number, number];
  rotations: Rotation[];
}

interface Pose {
  position: [number, number, number];
  rotations: Rotation[];
}

interface RobotModelProps {
  modelUrl: string;
  pose: Pose;
  cameraOffsetWpi?: CameraOffsetWpi;
}

export function RobotModel({
  modelUrl,
  pose,
  cameraOffsetWpi = {
    position: [0, 0, 0],
    rotations: [],
  },
}: RobotModelProps) {
  const { scene, gl } = useThree();

  const { scene: originalScene } = useGLTF(modelUrl);

  const robotScene = useMemo(() => {
    const clone = originalScene.clone(true);
    centerScene(clone);
    return clone;
  }, [originalScene]);

  const virtualCamera = useRef(
    new THREE.PerspectiveCamera(75, 1280 / 800, 0.01, 100),
  );

  const lastFrameTime = useRef(0);

  //
  // Robot transform
  //

  const wpiPosition = [
    -pose.position[0] + fieldWidthMeters / 2,
    -pose.position[1] + fieldLengthMeters / 2,
    pose.position[2],
  ] as [number, number, number];

  const threePosition = new THREE.Vector3(...wpiToThree(wpiPosition));

  const robotEuler = rotationsToEuler(pose.rotations, [0, -Math.PI / 2, 0]);

  const robotQuat = new THREE.Quaternion().setFromEuler(robotEuler);

  //
  // Camera transform
  //

  const cameraOffset = new THREE.Vector3(
    cameraOffsetWpi.position[0],
    cameraOffsetWpi.position[2],
    -cameraOffsetWpi.position[1],
  );

  cameraOffset.applyQuaternion(robotQuat);

  const cameraWorldPosition = threePosition.clone().add(cameraOffset);

  const cameraRotation = new THREE.Quaternion()
    .setFromEuler(rotationsToEuler(cameraOffsetWpi.rotations, [0, 0, 0]))
    .multiply(robotQuat);

  useEffect(() => {
    const camera = virtualCamera.current;

    camera.position.copy(cameraWorldPosition);
    camera.quaternion.copy(cameraRotation);
  }, [
    cameraWorldPosition.x,
    cameraWorldPosition.y,
    cameraWorldPosition.z,
    cameraRotation.x,
    cameraRotation.y,
    cameraRotation.z,
    cameraRotation.w,
  ]);

  //
  // MJPEG publisher
  //

  useEffect(() => {
    let running = true;

    const FPS = 30;
    const interval = 1000 / FPS;

    function publishFrame() {
      if (!running) return;

      const now = performance.now();

      if (now - lastFrameTime.current >= interval) {
        lastFrameTime.current = now;

        gl.render(scene, virtualCamera.current);

        gl.domElement.toBlob(
          async (blob) => {
            if (!blob) return;

            try {
              await fetch("http://localhost:1181/camera/frame", {
                method: "POST",
                body: blob,
                headers: {
                  "Content-Type": "image/jpeg",
                },
              });
            } catch (err) {
              console.error("Failed publishing camera frame", err);
            }
          },
          "image/jpeg",
          0.85,
        );
      }

      requestAnimationFrame(publishFrame);
    }

    publishFrame();

    return () => {
      running = false;
    };
  }, [scene, gl]);

  return (
    <>
      {/* Robot */}
      <group position={threePosition} rotation={robotEuler}>
        <primitive object={robotScene} />
      </group>

      {/* Camera marker */}
      <mesh position={cameraWorldPosition} quaternion={cameraRotation}>
        <boxGeometry args={[0.05, 0.05, 0.05]} />

        <meshBasicMaterial color="red" />
      </mesh>
    </>
  );
}

function centerScene(scene: THREE.Object3D) {
  const box = new THREE.Box3().setFromObject(scene, true);

  const center = new THREE.Vector3();

  box.getCenter(center);

  scene.position.x -= center.x;
  scene.position.z -= center.z;
}
