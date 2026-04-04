'use client';

import { Suspense, useState, useEffect, useRef } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, useGLTF, Html } from '@react-three/drei';
import AprilTag from './apriltag';
import { fieldLengthMeters, RobotModel, fieldWidthMeters } from './glbModel';

// Tag size: 6.5 inches in meters
const TAG_SIZE_METERS = 10.5 * 0.0254;

/** Field model */
function FieldModel({ url }) {
  const { scene } = useGLTF(url);
  return <primitive object={scene} />;
}

/** AprilTags group */
function AprilTags({ config, visible }) {
  if (!visible || !config?.aprilTags) return null;
  return (
    <group name="apriltags">
      {config.aprilTags.map((tag) => (
        <AprilTag key={tag.id} tag={tag} tagSizeMeters={TAG_SIZE_METERS} />
      ))}
    </group>
  );
}

/** Loading overlay */
function LoadingScreen() {
  return (
    <Html center>
      <div
        style={{
          color: 'white',
          fontSize: '18px',
          fontFamily: 'system-ui',
          background: 'rgba(0,0,0,0.8)',
          padding: '20px 40px',
          borderRadius: '8px',
        }}
      >
        Loading field...
      </div>
    </Html>
  );
}

function Kitbot() {
  return (
    <RobotModel
      modelUrl="/kitbot2026.glb"
      pose={{
        position: [fieldWidthMeters / 2, fieldLengthMeters / 2, 0.05],
        rotations: [{ axis: 'z', degrees: 0 }],
      }}
      cameraOffsetWpi={
        {
          position: [0, 0, 0.2],
          rotations: [{
            "axis": "x", "degrees": 90
          }, {
            "axis": "y", "degrees": 0
          }, {
            "axis": "z", "degrees": 0
          },
          ]
        }
      }
    />
  );
}

/** Main viewer */
export default function FieldViewer({
  fieldModelUrl = '/field.glb',
  aprilTagConfigUrl = '/apriltag-config.json',
}) {
  const [aprilTagConfig, setAprilTagConfig] = useState(null);
  const controlsRef = useRef();

  useEffect(() => {
    fetch(aprilTagConfigUrl)
      .then((res) => res.json())
      .then(setAprilTagConfig)
      .catch((err) => console.error('Failed to load AprilTag config:', err));
  }, [aprilTagConfigUrl]);

  return (
    <div className="relative w-full h-screen bg-neutral-900">
      <div className="absolute bottom-4 left-4 z-10 bg-black/70 px-3 py-2 rounded text-white font-mono text-xs">
        <span>WPI Coordinate Frame | Tag Size: 6.5in</span>
      </div>

      <Canvas
        camera={{ position: [10, 10, 10], fov: 60, near: 0.01, far: 1000 }}
        gl={{ antialias: true }}
      >
        <Suspense fallback={<LoadingScreen />}>
          <FieldModel url={fieldModelUrl} />
          <AprilTags config={aprilTagConfig} visible />
          <Kitbot />
        </Suspense>

        <ambientLight intensity={1} />
        <directionalLight position={[0, 100, 5]} intensity={50} />

        {/* OrbitControls with ref */}
        <OrbitControls ref={controlsRef} enablePan enableZoom enableRotate maxDistance={100} minDistance={0.5} />
      </Canvas>
    </div>
  );
}
