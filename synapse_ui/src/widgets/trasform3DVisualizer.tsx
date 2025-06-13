"use client";

import React from "react";

import { useRef, useState } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { OrbitControls, Grid, Text } from "@react-three/drei";
import { OrbitControls as OrbitControlsImpl } from "three-stdlib";
import * as THREE from "three";
import { Column } from "./containers";
import { Button } from "./button";

class WPIPosition {
  x: number;
  y: number;
  z: number;

  constructor(x: number, y: number, z: number) {
    this.x = x;
    this.y = y;
    this.z = z;
  }

  public toThreeJSPose(): THREE.Vector3 {
    return new THREE.Vector3(this.x, this.z, this.y);
  }
}

interface Transform3DState {
  rotation: {
    x: number;
    y: number;
    z: number;
  };
  translation: {
    x: number;
    y: number;
    z: number;
  };
}

interface Transform3DVisualizerProps {
  /** Initial transformation values */
  initialTransform?: Transform3DState;
  /** Whether to show the original reference shape */
  showReference?: boolean;
  /** Whether to show coordinate axes */
  showAxes?: boolean;
  /** Whether to show the grid */
  showGrid?: boolean;
  /** Custom shape to transform (defaults to box + cone) */
  children?: React.ReactNode;
  /** Callback when transformation changes */
  onTransformChange?: (transform: Transform3DState) => void;
  /** Canvas height */
  height?: string | number;
  /** Whether to show controls */
  showControls?: boolean;
  /** Custom colors for the shapes */
  color?: string;
  /** Translation range limits */
  translationRange?: {
    min: number;
    max: number;
  };
  controlsRef?: React.RefObject<OrbitControlsImpl | null>;
}

function TransformableObject({
  transform,
  children,
  color = "#cbd5e1",
}: {
  transform: Transform3DState;
  children?: React.ReactNode;
  color?: string;
}) {
  const meshRef = useRef<THREE.Group>(null);

  useFrame(() => {
    if (meshRef.current) {
      // Apply rotation
      meshRef.current.rotation.x = (transform.rotation.x * Math.PI) / 180;
      meshRef.current.rotation.y = (transform.rotation.y * Math.PI) / 180;
      meshRef.current.rotation.z = (transform.rotation.z * Math.PI) / 180;

      // Apply translation
      meshRef.current.position.x = transform.translation.x;
      meshRef.current.position.y = transform.translation.y;
      meshRef.current.position.z = transform.translation.z;
    }
  });

  const DefaultShape = () => (
    <>
      <mesh>
        <boxGeometry args={[3, 0.5, 3]} />
        <meshStandardMaterial color={color} />
      </mesh>
    </>
  );

  return (
    <>
      {/* Transformed object */}
      <group ref={meshRef}>{children || <DefaultShape />}</group>
    </>
  );
}

function CoordinateAxes() {
  const axisLineRadius = 0.03;
  const baseLength = 3.8;
  const padding = 0.4;

  const { camera } = useThree();

  const xAxisRef = useRef<THREE.Mesh>(null);
  const yAxisRef = useRef<THREE.Mesh>(null);
  const zAxisRef = useRef<THREE.Mesh>(null);
  const xAxisLabelRef = useRef<THREE.Mesh>(null);
  const zAxisLabelRef = useRef<THREE.Mesh>(null);
  const yAxisLabelRef = useRef<THREE.Mesh>(null);

  useFrame(() => {
    const scale = camera.position.length() / 10;

    // Scale axis meshes
    if (xAxisRef.current) {
      xAxisRef.current.scale.set(1, scale, 1);
      xAxisRef.current.position.set((scale * baseLength) / 2, 0, 0);
    }
    if (yAxisRef.current) {
      yAxisRef.current.scale.set(1, scale, 1);
      yAxisRef.current.position.set(0, (scale * baseLength) / 2, 0);
    }
    if (zAxisRef.current) {
      zAxisRef.current.scale.set(1, scale, 1);
      zAxisRef.current.position.set(0, 0, (-scale * baseLength) / 2);
    }

    // Rotate labels toward camera
    if (xAxisLabelRef.current) {
      xAxisLabelRef.current.lookAt(camera.position);
      xAxisLabelRef.current.position.set(scale * (baseLength + padding), 0, 0);
      xAxisLabelRef.current.scale.setScalar(scale);
    }
    if (zAxisLabelRef.current) {
      zAxisLabelRef.current.lookAt(camera.position);
      zAxisLabelRef.current.position.set(0, scale * (baseLength + padding), 0);
      zAxisLabelRef.current.scale.setScalar(scale);
    }
    if (yAxisLabelRef.current) {
      yAxisLabelRef.current.lookAt(camera.position);
      yAxisLabelRef.current.position.set(0, 0, -scale * (baseLength + padding));
      yAxisLabelRef.current.scale.setScalar(scale);
    }
  });

  return (
    <group>
      {/* X-axis (Red) */}
      <mesh ref={xAxisRef} rotation={[0, 0, -Math.PI / 2]}>
        <cylinderGeometry args={[axisLineRadius, axisLineRadius, baseLength]} />
        <meshBasicMaterial color="red" />
      </mesh>

      {/* Z-axis (Blue) */}
      <mesh ref={yAxisRef} rotation={[0, 0, 0]}>
        <cylinderGeometry args={[axisLineRadius, axisLineRadius, baseLength]} />
        <meshBasicMaterial color="blue" />
      </mesh>

      {/* Y-axis (Green) */}
      <mesh ref={zAxisRef} rotation={[Math.PI * 0.5, 0, 0]}>
        <cylinderGeometry args={[axisLineRadius, axisLineRadius, baseLength]} />
        <meshBasicMaterial color="green" />
      </mesh>

      {/* Labels */}
      <Text
        ref={xAxisLabelRef}
        fontSize={0.3}
        color="#ef4444"
        fontWeight={"bold"}
      >
        X (Front)
      </Text>
      <Text ref={zAxisLabelRef} fontSize={0.3} color="blue" fontWeight={"bold"}>
        Z (Up)
      </Text>
      <Text
        ref={yAxisLabelRef}
        fontSize={0.3}
        color="#22c55e"
        fontWeight={"bold"}
      >
        Y (Left)
      </Text>
    </group>
  );
}

export function Transform3DVisualizer({
  showReference = true,
  showAxes = true,
  showGrid = true,
  children,
  height = "500px",
  showControls = true,
  color: color,
  controlsRef = React.createRef(),
}: Transform3DVisualizerProps) {
  const defaultCameraPose: [x: number, y: number, z: number] = [3, 3, -3];

  const resetCameraPose = () => {
    if (!controlsRef.current) return;

    // Reset camera position (same as initial position in Canvas)
    const [x, y, z] = defaultCameraPose;
    controlsRef.current.object.position.set(x, y, z);

    // Reset the target to origin (or wherever you want)
    controlsRef.current.target.set(0, 0, 0);

    // Must call update after manual changes
    controlsRef.current.update();
  };

  const Scene = () => (
    <Canvas
      camera={{ position: defaultCameraPose, fov: 50 }}
      gl={{ preserveDrawingBuffer: true }}
      onCreated={({ gl }) => {
        gl.setClearColor("#0000");
      }}
    >
      <ambientLight intensity={0.4} />
      <directionalLight position={[10, 10, 5]} intensity={1} />

      <TransformableObject
        transform={{
          rotation: { x: 0, y: 0, z: 0 },
          translation: { x: 0, y: 0, z: 0 },
        }}
        color={color}
      >
        {children}
      </TransformableObject>

      {showAxes && <CoordinateAxes />}
      {showGrid && (
        <Grid
          args={[20, 20, 20]}
          sectionColor={"black"}
          cellColor={"rgba(256,256, 256, 0.5)"}
        />
      )}

      <OrbitControls
        enablePan={true}
        enableZoom={true}
        enableRotate={true}
        ref={controlsRef}
      />
    </Canvas>
  );

  if (!showControls) {
    return (
      <div className="border rounded-lg bg-white" style={{ height }}>
        <Scene />
      </div>
    );
  }

  return (
    <Column>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <div className="border rounded-lg bg-white" style={{ height }}>
            <Scene />
          </div>
          {showReference && (
            <div className="mt-4 flex items-center gap-4"></div>
          )}
        </div>
      </div>
      <Button onClick={resetCameraPose}>Reset Camera Pose</Button>
    </Column>
  );
}
