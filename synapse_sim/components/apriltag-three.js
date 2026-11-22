// SPDX-FileCopyrightText: 2026 Dan Peled
//
// SPDX-License-Identifier: GPL-3.0-or-later

// AprilTag rendering shared by the interactive viewer and the headless camera
// renderer used by `synapse --sim`.

import * as THREE from "three";

// The tag PNGs contain the 10x10 tag image, including the one-cell white quiet
// zone. The black square is the inner 8x8 cells, so the plane has to be 10/8
// larger than the physical black square.
export const TAG_BLACK_SIZE_METERS = 0.1651;
export const TAG_TEXTURE_CELLS = 10;
export const TAG_BLACK_CELLS = 8;
export const TAG_SIZE_METERS =
  (TAG_BLACK_SIZE_METERS * TAG_TEXTURE_CELLS) / TAG_BLACK_CELLS;

const loader = new THREE.TextureLoader();
const textureCache = new Map();

export function aprilTagUrl(tagId, baseUrl = "/apriltags") {
  const id = String(tagId).padStart(5, "0");
  return `${baseUrl}/tag36_11_${id}.png`;
}

function configureTexture(texture) {
  // Keep the tag sharp and avoid mipmap blur at oblique angles.
  texture.minFilter = THREE.NearestFilter;
  texture.magFilter = THREE.NearestFilter;
  texture.generateMipmaps = false;
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.needsUpdate = true;
  return texture;
}

export function createAprilTagTexture(tagId, baseUrl = "/apriltags") {
  const url = aprilTagUrl(tagId, baseUrl);
  const cached = textureCache.get(url);
  if (cached) {
    return cached;
  }

  const texture = configureTexture(loader.load(url));
  textureCache.set(url, texture);
  return texture;
}

export async function loadAprilTagTexture(tagId, baseUrl = "/apriltags") {
  const url = aprilTagUrl(tagId, baseUrl);
  const cached = textureCache.get(url);
  if (cached) {
    return cached;
  }

  const texture = configureTexture(await loader.loadAsync(url));
  textureCache.set(url, texture);
  return texture;
}

export function createAprilTagMesh(
  tag,
  tagSizeMeters = TAG_SIZE_METERS,
  baseUrl = "/apriltags",
  texture = null,
) {
  const mesh = new THREE.Mesh(
    new THREE.PlaneGeometry(tagSizeMeters, tagSizeMeters),
    new THREE.MeshBasicMaterial({
      map: texture ?? createAprilTagTexture(tag.id, baseUrl),
      side: THREE.DoubleSide,
      // Tags sit directly on the field walls; offset their depth so they do
      // not z-fight with the wall geometry.
      polygonOffset: true,
      polygonOffsetFactor: -2,
      polygonOffsetUnits: -2,
    }),
  );
  mesh.name = `apriltag_${tag.id}`;
  return mesh;
}
