"use client";

import React, { useMemo, useRef } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { OrbitControls, Grid, Text } from "@react-three/drei";
import { OrbitControls as OrbitControlsImpl } from "three-stdlib";
import * as THREE from "three";
import { Button } from "./button";

export interface Transform3DState {
  rotation: { x: number; y: number; z: number };
  translation: { x: number; y: number; z: number };
}

export interface TransformableObjectState {
  id: string;
  transform: Transform3DState;
  color?: string;
  shape?: React.ReactNode;
  wireframe?: boolean;
}

export interface Transform3DVisualizerProps {
  objects: TransformableObjectState[];
  showReference?: boolean;
  showAxes?: boolean;
  showGrid?: boolean;
  height?: string | number;
  showControls?: boolean;
  controlsRef?: React.RefObject<OrbitControlsImpl | null>;
}

function TransformableObject({
  transform,
  color = "#cbd5e1",
  shape,
  wireframe,
}: {
  transform: Transform3DState;
  color?: string;
  shape?: React.ReactNode;
  wireframe?: boolean;
}) {
  return (
    <group
      rotation={[
        (transform.rotation.x * Math.PI) / 180,
        (transform.rotation.y * Math.PI) / 180,
        (transform.rotation.z * Math.PI) / 180,
      ]}
      position={[
        transform.translation.x,
        transform.translation.z, // converts from WPI pose to THREEJS pose
        transform.translation.y,
      ]}
    >
      {shape ?? (
        <mesh>
          <boxGeometry args={[2.5, 0.5, 2.5]} />
          <meshStandardMaterial color={color} />
        </mesh>
      )}
      {wireframe && (
        <mesh>
          <boxGeometry args={[2.7, 0.7, 2.7]} />
          <meshBasicMaterial color="yellow" wireframe />
        </mesh>
      )}
    </group>
  );
}

function RoundedRectMesh({
  width = 1.5,
  height = 0.5,
  radius = 0.1,
  color = "white",
  opacity = 0.6,
  ...props
}) {
  const shape = useMemo(() => {
    const s = new THREE.Shape();
    s.moveTo(radius, 0);
    s.lineTo(width - radius, 0);
    s.quadraticCurveTo(width, 0, width, radius);
    s.lineTo(width, height - radius);
    s.quadraticCurveTo(width, height, width - radius, height);
    s.lineTo(radius, height);
    s.quadraticCurveTo(0, height, 0, height - radius);
    s.lineTo(0, radius);
    s.quadraticCurveTo(0, 0, radius, 0);
    return s;
  }, [width, height, radius]);

  const geometry = useMemo(() => {
    const geom = new THREE.ShapeGeometry(shape);
    geom.translate(-width / 2, -height / 2, 0);
    return geom;
  }, [shape, width, height]);

  const material = useMemo(
    () => new THREE.MeshBasicMaterial({ color, transparent: true, opacity }),
    [color, opacity]
  );

  return <primitive object={new THREE.Mesh(geometry, material)} {...props} />;
}

export function CoordinateAxes() {
  const axisLineRadius = 0.03;
  const baseLength = 3.8;
  const padding = 0.4;

  const { camera } = useThree();

  // Refs for axes lines
  const xAxisRef = useRef<THREE.Mesh>(null);
  const yAxisRef = useRef<THREE.Mesh>(null);
  const zAxisRef = useRef<THREE.Mesh>(null);

  // Refs for label groups (to lookAt camera)
  const xAxisLabelRef = useRef<THREE.Group>(null);
  const yAxisLabelRef = useRef<THREE.Group>(null);
  const zAxisLabelRef = useRef<THREE.Group>(null);

  useFrame(() => {
    const scale = camera.position.length() / 10;

    // Scale and position axes lines
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

    // Make labels face the camera and scale
    if (xAxisLabelRef.current) {
      xAxisLabelRef.current.lookAt(camera.position);
      xAxisLabelRef.current.position.set(scale * (baseLength + padding), 0, 0);
      xAxisLabelRef.current.scale.setScalar(scale);
    }
    if (yAxisLabelRef.current) {
      yAxisLabelRef.current.lookAt(camera.position);
      yAxisLabelRef.current.position.set(0, 0, -scale * (baseLength + padding));
      yAxisLabelRef.current.scale.setScalar(scale);
    }
    if (zAxisLabelRef.current) {
      zAxisLabelRef.current.lookAt(camera.position);
      zAxisLabelRef.current.position.set(0, scale * (baseLength + padding), 0);
      zAxisLabelRef.current.scale.setScalar(scale);
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

      {/* Labels with rounded background */}
      {/* X Axis Label */}
      <group ref={xAxisLabelRef}>
        <RoundedRectMesh width={1.6} height={0.5} radius={0.15} color="gray" opacity={0.7} />
        <Text
          fontSize={0.3}
          color="#ef4444"
          fontWeight={"bold"}
          position={[0, 0, 0.01]} // slight offset in z to prevent z-fighting
          anchorX="center"
          anchorY="middle"
        >
          X (Front)
        </Text>
      </group>

      {/* Y Axis Label */}
      <group ref={yAxisLabelRef}>
        <RoundedRectMesh width={1.6} height={0.5} radius={0.15} color="gray" opacity={0.7} />
        <Text
          fontSize={0.3}
          color="#22c55e"
          fontWeight={"bold"}
          position={[0, 0, 1]}
          anchorX="center"
          anchorY="middle"
        >
          Y (Left)
        </Text>
      </group>

      {/* Z Axis Label */}
      <group ref={zAxisLabelRef}>
        <RoundedRectMesh width={1.6} height={0.5} radius={0.15} color="gray" opacity={0.7} />
        <Text
          fontSize={0.3}
          color="blue"
          fontWeight={"bold"}
          position={[0, 0, 0.01]}
          anchorX="center"
          anchorY="middle"
        >
          Z (Up)
        </Text>
      </group>
    </group>
  );
}

export function Transform3DVisualizer({
  showReference = true,
  showAxes = true,
  showGrid = true,
  height = "500px",
  showControls = true,
  controlsRef = React.createRef(),
  objects,
}: Transform3DVisualizerProps) {
  const defaultCameraPose: [number, number, number] = [2.2, 2.2, -2.2];

  const resetCameraPose = () => {
    if (!controlsRef.current) return;
    const [x, y, z] = defaultCameraPose;
    controlsRef.current.object.position.set(x, y, z);
    controlsRef.current.target.set(0, 0, 0);
    controlsRef.current.update();
  };

  return (
    <div>
      <Canvas
        camera={{ position: defaultCameraPose, fov: 50 }}
        gl={{ preserveDrawingBuffer: true }}
        onCreated={({ gl }) => gl.setClearColor("#0000")}
        style={{ height }}
      >
        <ambientLight intensity={0.4} />
        <directionalLight position={[10, 10, 5]} intensity={1} />

        {objects.map((obj) => (
          <TransformableObject
            key={obj.id}
            transform={obj.transform}
            color={obj.color}
            shape={obj.shape}
            wireframe={obj.wireframe}
          />
        ))}

        {showAxes && <CoordinateAxes />}
        {showGrid && <Grid args={[20, 20]} sectionColor={"black"} cellColor={"rgba(256,256,256,0.5)"} />}
        <OrbitControls ref={controlsRef} enablePan enableZoom enableRotate />
      </Canvas>
      {
        showControls && (
          <Button
            onClick={resetCameraPose}
          >
            Reset Camera
          </Button>
        )
      }
    </div >
  );
}
