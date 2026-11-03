import * as THREE from "three";

export interface CameraOffsetWpi {
  position: [number, number, number];
  rotations: number[];
}

export class VirtualCamera {
  public camera: THREE.PerspectiveCamera;

  private renderer: THREE.WebGLRenderer;
  private scene: THREE.Scene;

  private streamUrl: string;
  private interval?: number;

  constructor(
    scene: THREE.Scene,
    renderer: THREE.WebGLRenderer,
    streamUrl: string,
    fov = 70,
    resolution: [number, number] = [1080, 720],
  ) {
    this.scene = scene;
    this.renderer = renderer;
    this.streamUrl = streamUrl;

    this.camera = new THREE.PerspectiveCamera(
      fov,
      resolution[0] / resolution[1],
      0.01,
      100,
    );
  }

  updateTransform(
    robotPosition: THREE.Vector3,
    robotRotation: THREE.Quaternion,
    offset: CameraOffsetWpi,
  ) {
    const cameraOffset = new THREE.Vector3(
      offset.position[0],
      -offset.position[1],
      offset.position[2],
    );

    cameraOffset.applyQuaternion(robotRotation);

    this.camera.position.copy(robotPosition.clone().add(cameraOffset));

    const cameraRotation = new THREE.Quaternion()
      .setFromEuler(
        new THREE.Euler(
          offset.rotations[0] ?? 0,
          offset.rotations[1] ?? 0,
          offset.rotations[2] ?? 0,
        ),
      )
      .multiply(robotRotation);

    this.camera.quaternion.copy(cameraRotation);
  }

  start(fps = 30) {
    this.interval = window.setInterval(() => this.captureFrame(), 1000 / fps);
  }

  stop() {
    if (this.interval) clearInterval(this.interval);
  }

  private captureFrame() {
    this.renderer.render(this.scene, this.camera);

    this.renderer.domElement.toBlob(
      async (blob) => {
        if (!blob) return;

        await fetch(this.streamUrl, {
          method: "POST",
          headers: {
            "Content-Type": "image/jpeg",
          },
          body: blob,
        });
      },
      "image/jpeg",
      0.85,
    );
  }
}
