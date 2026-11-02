'use client';

import { useMemo } from 'react';
import { Html } from '@react-three/drei';
import { TAG_SIZE_METERS, createAprilTagMesh } from './apriltag-three';
import { rotationsToEuler, wpiToThree } from './math_util';

export default function AprilTag({ tag, tagSizeMeters = TAG_SIZE_METERS }) {
  const mesh = useMemo(
    () => createAprilTagMesh(tag, tagSizeMeters),
    [tag, tagSizeMeters],
  );
  const euler = useMemo(
    () => rotationsToEuler(tag.rotations, [0, Math.PI / 2, 0]),
    [tag.rotations],
  );
  const threePosition = wpiToThree(tag.position);

  return (
    <group position={threePosition} rotation={euler}>
      {/* AprilTag plane */}
      <primitive object={mesh} />

      {/* ID Label */}
      <Html
        position={[0, tagSizeMeters * 0.6, 0.01]}
        center
        distanceFactor={1}
        style={{
          color: '#FF6600',
          fontSize: '12px',
          fontWeight: 'bold',
          fontFamily: 'monospace',
          background: 'rgba(0,0,0,0.7)',
          padding: '2px 6px',
          borderRadius: '3px',
          whiteSpace: 'nowrap',
          pointerEvents: 'none',
        }}
      >
        ID: {tag.id}
      </Html>
    </group>
  );
}
