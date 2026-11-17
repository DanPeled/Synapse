package synapse;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import edu.wpi.first.math.geometry.Pose3d;
import edu.wpi.first.math.geometry.Rotation2d;
import edu.wpi.first.math.geometry.Translation3d;
import java.io.IOException;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.msgpack.jackson.dataformat.MessagePackFactory;
import synapse.pipelines.apriltag.ApriltagResult;
import synapse.pipelines.color.ColorResult;

class SynapseCameraTest {

  private SynapseCamera camera;
  private ObjectMapper mapper;

  @BeforeEach
  void setup() {
    camera = new SynapseCamera("TestCamera");
    mapper = new ObjectMapper(new MessagePackFactory());
  }

  @Test
  void testGetResultsIntArray() throws IOException {
    byte[] serialized = mapper.writeValueAsBytes(new int[] {1, 2, 3});

    Optional<int[]> results = camera.deserializeResults(new TypeReference<int[]>() {}, serialized);

    assertTrue(results.isPresent());
    assertArrayEquals(new int[] {1, 2, 3}, results.get());
  }

  @Test
  void testGetResultsApriltagResults() throws IOException {
    // Mirrors the runtime's MessagePack output: integer tag fields, list payloads,
    // and a nullable camera pose.
    Map<String, Object> payload =
        Map.of(
            "cameraEstimate_fieldSpace",
            new double[] {1.0, 2.0, 3.0, 4.0, 5.0, 6.0},
            "tags",
            List.of(
                Map.of(
                    "tag_id", 7,
                    "hamming", 1,
                    "tagPose_screenSpace", new int[] {320, 240})),
            "reprojection_error",
            1.25);

    Optional<ApriltagResult> results =
        camera.deserializeResults(
            new TypeReference<ApriltagResult>() {}, mapper.writeValueAsBytes(payload));

    assertTrue(results.isPresent());
    ApriltagResult result = results.get();
    assertEquals(1, result.tags.length);
    assertEquals(7, result.tags[0].tagID);
    assertEquals(1, result.tags[0].hamming);
    assertArrayEquals(new double[] {320, 240}, result.tags[0].tagPose_screenSpace);
    assertEquals(320, result.tags[0].tx());
    assertEquals(240, result.tags[0].ty());
    assertArrayEquals(
        new double[] {1.0, 2.0, 3.0, 4.0, 5.0, 6.0}, result.cameraEstimate_fieldSpace);
    assertEquals(1.25, result.reprojectionError);
    Pose3d pose = result.cameraEstimate_fieldSpace3d();
    assertNotNull(pose);
    assertEquals(1.0, pose.getX());
    assertEquals(3.0, pose.getZ());
    // The runtime sends roll/pitch/yaw in degrees; the accessor must convert to radians.
    assertEquals(Math.toRadians(4.0), pose.getRotation().getX(), 1e-9);
    assertEquals(Math.toRadians(5.0), pose.getRotation().getY(), 1e-9);
    assertEquals(Math.toRadians(6.0), pose.getRotation().getZ(), 1e-9);
  }

  @Test
  void testApriltagResultWithoutCameraEstimate() throws IOException {
    Map<String, Object> payload = new HashMap<>();
    payload.put("cameraEstimate_fieldSpace", null);
    payload.put("tags", List.of());
    payload.put("reprojection_error", 0.0);

    Optional<ApriltagResult> results =
        camera.deserializeResults(
            new TypeReference<ApriltagResult>() {}, mapper.writeValueAsBytes(payload));

    assertTrue(results.isPresent());
    ApriltagResult result = results.get();
    assertNull(result.cameraEstimate_fieldSpace);
    assertNull(result.cameraEstimate_fieldSpace3d());
    assertEquals(0, result.tags.length);
  }

  @Test
  void testGetResultsColorResults() throws IOException {
    Map<String, Object> detection =
        Map.of("bbox", new int[] {1, 2, 3, 4}, "center", new double[] {2.5, 4.0}, "area", 12.0);
    Map<String, Object> payload =
        Map.of("timestamp", 1.5, "detections", List.of(detection), "main_detection", detection);

    Optional<ColorResult> results =
        camera.deserializeResults(
            new TypeReference<ColorResult>() {}, mapper.writeValueAsBytes(payload));

    assertTrue(results.isPresent());
    ColorResult result = results.get();
    assertEquals(1.5, result.timestamp);
    assertEquals(1, result.detections.length);
    assertArrayEquals(new double[] {1, 2, 3, 4}, result.detections[0].bbox);
    assertArrayEquals(new double[] {2.5, 4.0}, result.detections[0].center);
    assertEquals(12.0, result.detections[0].area);
    assertNotNull(result.main_detection);
  }

  /** Custom result classes can use WPILib geometry directly; Synapse sends plain arrays. */
  static class CustomResult {
    public Pose3d pose;
    public Translation3d translation;
    public Rotation2d rotation;
  }

  @Test
  void testCustomResultWithGeometry() throws IOException {
    Map<String, Object> payload =
        Map.of(
            "pose", new double[] {1, 2, 3, 4, 5, 6},
            "translation", new double[] {7, 8, 9},
            "rotation", 90.0);

    Optional<CustomResult> results =
        camera.deserializeResults(
            new TypeReference<CustomResult>() {}, mapper.writeValueAsBytes(payload));

    assertTrue(results.isPresent());
    CustomResult result = results.get();
    assertEquals(1.0, result.pose.getX());
    assertEquals(3.0, result.pose.getZ());
    assertEquals(Math.toRadians(4.0), result.pose.getRotation().getX(), 1e-9);
    assertEquals(Math.toRadians(5.0), result.pose.getRotation().getY(), 1e-9);
    assertEquals(Math.toRadians(6.0), result.pose.getRotation().getZ(), 1e-9);
    assertEquals(7.0, result.translation.getX());
    assertEquals(9.0, result.translation.getZ());
    // Rotation2d is sent in degrees and must come back as the same angle.
    assertEquals(90.0, result.rotation.getDegrees(), 1e-9);
  }
}
