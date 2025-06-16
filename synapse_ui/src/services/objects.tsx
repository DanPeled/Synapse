import * as THREE from "three";

export namespace Models {
  export interface RobotModelConfig {
    width: number;
    length: number;
    height: number;
    color: string;
  }

  export const kRobotDefaults: RobotModelConfig = {
    width: 2.5,
    length: 2.5,
    height: 0.32,
    color: "rgb(170, 170, 170)"
  };


  export function createRobotModel(config: RobotModelConfig = kRobotDefaults) {
    const wheelRadius = 0.3;
    const wheelThickness = 0.2;

    const halfW = config.width / 2;
    const halfL = config.length / 2;
    const baseY = -config.height / 2;

    // Adjusted wheel positions inside chassis
    const wheelPositions: [number, number, number][] = [
      [-halfW + wheelRadius, baseY - wheelThickness / 2, -halfL + wheelRadius],  // Front Left
      [halfW - wheelRadius, baseY - wheelThickness / 2, -halfL + wheelRadius],   // Front Right
      [-halfW + wheelRadius, baseY - wheelThickness / 2, halfL - wheelRadius],   // Back Left
      [halfW - wheelRadius, baseY - wheelThickness / 2, halfL - wheelRadius],    // Back Right
    ];

    // Bumper dimensions
    const bumperThickness = 0.1;  // thickness of the bumper
    const bumperHeight = 0.3;    // height of the bumper above the baseY

    return (
      <>
        {/* Outline */}
        <mesh scale={[1.05, 1.05, 1.05]}>
          <boxGeometry args={[config.width, config.height, config.length]} />
          <meshBasicMaterial color="black" side={THREE.BackSide} />
        </mesh>

        {/* Main Chassis */}
        <mesh>
          <boxGeometry args={[config.width, config.height, config.length]} />
          <meshStandardMaterial color={config.color} />
        </mesh>

        {/* Bumper */}
        <mesh position={[0, 0, 0]}>
          <boxGeometry
            args={[config.width + bumperThickness * 2, bumperHeight, config.length + bumperThickness * 2]}
          />
          <meshStandardMaterial color="orange" />
        </mesh>

        {/* Swerve Modules */}
        {wheelPositions.map(([x, y, z], i) => (
          <group key={i} position={[x, y, z]} rotation={[0, 0, 0]}>
            <mesh rotation={[Math.PI / 2, 0, 0]}>
              <cylinderGeometry args={[wheelRadius, wheelRadius, wheelThickness, 20]} />
              <meshStandardMaterial color="gray" />
            </mesh>
          </group>
        ))}
      </>
    );
  }
}
