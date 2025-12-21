package synapse;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.msgpack.jackson.dataformat.MessagePackFactory;
import synapse.pipelines.apriltag.ApriltagDetection;
import synapse.pipelines.apriltag.ApriltagResult;

class SynapseCameraTest {

  private SynapseCamera camera;

  @BeforeEach
  void setup() {
    camera = new SynapseCamera("TestCamera");
  }

  @Test
  void testGetResultsIntArray() throws IOException {
    byte[] serialized =
        new ObjectMapper(new MessagePackFactory()).writeValueAsBytes(new int[] {1, 2, 3});

    Optional<int[]> results = camera.getResults(new TypeReference<int[]>() {}, serialized);

    assertTrue(results.isPresent());
    assertArrayEquals(new int[] {1, 2, 3}, results.get());
  }

  @Test
  void testGetResultsApriltagResults() throws IOException {
    ObjectMapper mapper = new ObjectMapper(new MessagePackFactory());

    ApriltagResult original = new ApriltagResult();
    original.cameraEstimate_fieldSpace = new double[] {1, 2, 3};
    original.tags = new ApriltagDetection[] {new ApriltagDetection()};
    original.tags[0].hamming = 2;
    original.tags[0].tagID = 7;
    original.tags[0].cameraPose_fieldSpace = new double[] {1, 2, 3, 4, 5, 6};

    byte[] serialized = mapper.writeValueAsBytes(original);

    Optional<ApriltagResult> results =
        camera.getResults(new TypeReference<ApriltagResult>() {}, serialized);

    assertTrue(results.isPresent());
    assertEquals(results.get(), original);
  }
}
