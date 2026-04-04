'use client';

import { useMemo } from 'react';
import { DoubleSide, CanvasTexture, Euler, Loader } from 'three';
import { Html } from '@react-three/drei';
import * as THREE from 'three';
import { rotationsToEuler, wpiToThree } from './math_util';

const loader = new THREE.TextureLoader();

function createAprilTagTexture(tagId) {
  const id = String(tagId).padStart(5, '0');

  const texture = loader.load(`/apriltags/tag36_11_${id}.png`, (tex) => {
    tex.needsUpdate = true;
  });

  // Make it crisp (no blur)
  texture.minFilter = THREE.NearestFilter;
  texture.magFilter = THREE.NearestFilter;
  texture.generateMipmaps = false;

  return texture;
}


export default function AprilTag({ tag, tagSizeMeters }) {
  const texture = useMemo(() => createAprilTagTexture(tag.id), [tag.id]);
  const euler = useMemo(() => rotationsToEuler(tag.rotations, [0, Math.PI / 2, 0]), [tag.rotations]);
  const threePosition = wpiToThree(tag.position);

  return (
    <group
      position={threePosition}
      rotation={euler}
    >
      {/* AprilTag plane */}
      <mesh>
        <planeGeometry args={[tagSizeMeters, tagSizeMeters]} />
        <meshBasicMaterial map={texture} side={DoubleSide} />
      </mesh>

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
