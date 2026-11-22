// SPDX-FileCopyrightText: 2026 Dan Peled
//
// SPDX-License-Identifier: GPL-3.0-or-later

// Builds the Three.js field scene that both the interactive viewer and the
// headless simulated camera use. Keeping the scene here means `synapse --sim`
// renders exactly the same field model and AprilTags as the viewer.

import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";

import {
  TAG_SIZE_METERS,
  createAprilTagMesh,
  loadAprilTagTexture,
} from "./apriltag-three";
import { rotationsToEuler, wpiToThree } from "./math_util";

export const FIELD_LENGTH_METERS = 651.22 * 0.0254;
export const FIELD_WIDTH_METERS = 317.677 * 0.0254;

export async function loadAprilTagConfig(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to load AprilTag config ${url}: ${response.status}`);
  }
  return response.json();
}

export async function createFieldScene({
  fieldUrl = "/field.glb",
  configUrl = "/apriltag-config.json",
  tagBaseUrl = "/apriltags",
} = {}) {
  const [config, gltf] = await Promise.all([
    loadAprilTagConfig(configUrl),
    new GLTFLoader().loadAsync(fieldUrl),
  ]);

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x191919);

  // Match the lighting in components/field-viewer.jsx.
  scene.add(new THREE.AmbientLight(0xffffff, 1));
  const sun = new THREE.DirectionalLight(0xffffff, 50);
  sun.position.set(0, 100, 5);
  scene.add(sun);

  scene.add(gltf.scene);

  const tags = new THREE.Group();
  tags.name = "apriltags";
  const tagObjects = await Promise.all(
    (config.aprilTags ?? []).map(async (tag) => {
      const texture = await loadAprilTagTexture(tag.id, tagBaseUrl);

      const group = new THREE.Group();
      group.name = `apriltag_${tag.id}`;
      // The tag config uses field-centered coordinates, which is the same
      // frame as the field model.
      group.position.fromArray(wpiToThree(tag.position));
      group.rotation.copy(
        rotationsToEuler(tag.rotations, [0, Math.PI / 2, 0]),
      );
      group.add(createAprilTagMesh(tag, TAG_SIZE_METERS, tagBaseUrl, texture));
      return group;
    }),
  );
  tags.add(...tagObjects);
  scene.add(tags);

  return { scene, config, tags, field: gltf.scene };
}
