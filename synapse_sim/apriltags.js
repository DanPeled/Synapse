import {
  CanvasTexture,
  DoubleSide,
  Group,
  Mesh,
  MeshBasicMaterial,
  PlaneGeometry,
  Quaternion,
  Euler,
  Vector3,
} from 'three';

// AprilTag 36h11 encoding - simplified pattern generation
// Real 36h11 tags have specific bit patterns, this generates visual approximations
function generateTagPattern(tagId) {
  // Use tag ID to seed a deterministic pattern
  const seed = tagId * 2654435761;
  const bits = [];
  for (let i = 0; i < 36; i++) {
    bits.push(((seed >> (i % 32)) ^ (seed >> ((i + 7) % 32))) & 1);
  }
  return bits;
}

function createAprilTagTexture(tagId, size = 256) {
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d');
  
  // Fill white background
  ctx.fillStyle = '#FFFFFF';
  ctx.fillRect(0, 0, size, size);
  
  // The tag is 10x10 grid:
  // - Outer 1 cell border is white (already filled)
  // - Next 1 cell border is black
  // - Inner 6x6 is the data region
  
  const cellSize = size / 10;
  
  // Draw black border (1 cell thick, inside the white border)
  ctx.fillStyle = '#000000';
  // Top border
  ctx.fillRect(cellSize, cellSize, cellSize * 8, cellSize);
  // Bottom border
  ctx.fillRect(cellSize, cellSize * 8, cellSize * 8, cellSize);
  // Left border
  ctx.fillRect(cellSize, cellSize, cellSize, cellSize * 8);
  // Right border
  ctx.fillRect(cellSize * 8, cellSize, cellSize, cellSize * 8);
  
  // Generate and draw the 6x6 data pattern
  const pattern = generateTagPattern(tagId);
  
  for (let row = 0; row < 6; row++) {
    for (let col = 0; col < 6; col++) {
      const bitIndex = row * 6 + col;
      const isBlack = pattern[bitIndex] === 1;
      
      ctx.fillStyle = isBlack ? '#000000' : '#FFFFFF';
      ctx.fillRect(
        (col + 2) * cellSize,
        (row + 2) * cellSize,
        cellSize,
        cellSize
      );
    }
  }
  
  return new CanvasTexture(canvas);
}

function createTagIdLabel(tagId, size = 128) {
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size / 2;
  const ctx = canvas.getContext('2d');
  
  // Transparent background
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  
  // Draw text
  ctx.fillStyle = '#FF6600';
  ctx.font = `bold ${size / 3}px Arial`;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(`ID: ${tagId}`, canvas.width / 2, canvas.height / 2);
  
  return new CanvasTexture(canvas);
}

export function createAprilTag(tag, tagSizeMeters) {
  const group = new Group();
  group.name = `apriltag_${tag.ID}`;
  
  // Create the tag plane
  const geometry = new PlaneGeometry(tagSizeMeters, tagSizeMeters);
  const texture = createAprilTagTexture(tag.ID);
  const material = new MeshBasicMaterial({
    map: texture,
    side: DoubleSide,
  });
  
  const tagMesh = new Mesh(geometry, material);
  tagMesh.name = `apriltag_mesh_${tag.ID}`;
  group.add(tagMesh);
  
  // Create ID label above tag
  const labelSize = tagSizeMeters * 0.8;
  const labelGeometry = new PlaneGeometry(labelSize, labelSize / 2);
  const labelTexture = createTagIdLabel(tag.ID);
  const labelMaterial = new MeshBasicMaterial({
    map: labelTexture,
    transparent: true,
    side: DoubleSide,
    depthTest: false,
  });
  
  const labelMesh = new Mesh(labelGeometry, labelMaterial);
  labelMesh.position.set(0, tagSizeMeters * 0.7, 0.01);
  labelMesh.name = `apriltag_label_${tag.ID}`;
  group.add(labelMesh);
  
  // Position from WPI coordinates
  // WPI: X = forward (toward red alliance), Y = left, Z = up
  // Three.js: X = right, Y = up, Z = toward camera
  // Convert: WPI(x,y,z) -> Three.js(y, z, -x) or similar based on field orientation
  
  const translation = tag.pose.translation;
  const rotation = tag.pose.rotation.quaternion;
  
  // WPI coordinate frame: X forward, Y left, Z up
  // Three.js default: X right, Y up, Z out of screen
  // We need to transform coordinates appropriately
  
  // Set position directly in WPI frame first, then rotate the entire group if needed
  // For now, assuming the field model is also in WPI coordinates
  group.position.set(
    translation.x,
    translation.y,
    translation.z
  );
  
  // Apply rotation from quaternion
  // The quaternion from the config represents the tag's orientation
  const quaternion = new Quaternion(
    rotation.X,
    rotation.Y,
    rotation.Z,
    rotation.W
  );
  group.setRotationFromQuaternion(quaternion);
  
  return group;
}

export async function loadAprilTags(scene, configUrl = '/apriltag-config.json') {
  try {
    const response = await fetch(configUrl);
    const config = await response.json();
    
    // Tag size: 6.5 inches in meters
    const tagSizeInches = 6.5;
    const tagSizeMeters = tagSizeInches * 0.0254;
    
    const tagsGroup = new Group();
    tagsGroup.name = 'apriltags';
    
    console.log(`Loading ${config.tags.length} AprilTags...`);
    
    config.tags.forEach((tag) => {
      const tagMesh = createAprilTag(tag, tagSizeMeters);
      tagsGroup.add(tagMesh);
    });
    
    scene.add(tagsGroup);
    
    console.log('AprilTags loaded successfully');
    return tagsGroup;
  } catch (error) {
    console.error('Failed to load AprilTags:', error);
    return null;
  }
}

export function removeAprilTags(scene) {
  const tagsGroup = scene.getObjectByName('apriltags');
  if (tagsGroup) {
    scene.remove(tagsGroup);
    // Dispose geometries and materials
    tagsGroup.traverse((child) => {
      if (child.geometry) child.geometry.dispose();
      if (child.material) {
        if (child.material.map) child.material.map.dispose();
        child.material.dispose();
      }
    });
  }
}
