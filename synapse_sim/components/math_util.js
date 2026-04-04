import { Euler } from "three";

export function wpiToThree(position) {
  const [x, y, z] = position;

  // WPI -> Three.js
  let tx = -y;
  let ty = z;
  let tz = -x;

  // field yaw +90°
  const rx = -tz;
  const ry = ty;
  const rz = tx;

  return [rx, ry, rz];
}

// Convert axis-angle rotations to Euler angles
export function rotationsToEuler(rotations, offset = [0, 0, 0]) {
  let x = 0, y = 0, z = 0;

  if (rotations) {
    for (const rot of rotations) {
      const r = (rot.degrees * Math.PI) / 180;

      switch (rot.axis) {
        case 'x':
          z += r;
          break;
        case 'y':
          x += r;
          break;
        case 'z':
          y -= r;
          break;
      }
    }
  }

  return new Euler(x + offset[0], -y + offset[1], -z + offset[2], 'XYZ'); // Axis are CCW+ in WPILib
}
