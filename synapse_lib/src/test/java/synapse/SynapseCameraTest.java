package synapse;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.msgpack.jackson.dataformat.MessagePackFactory;
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

    int[] results = camera.getResults(new TypeReference<int[]>() {}, serialized);
    assertArrayEquals(new int[] {1, 2, 3}, results);
  }

  @Test
  void testGetResultsApriltagResults() throws IOException {
    ObjectMapper mapper = new ObjectMapper(new MessagePackFactory());

    ApriltagResult original = new ApriltagResult();
    original.hamming = 2;
    original.tagID = 7;
    original.robotPose_fieldSpace = new double[] {1, 2, 3, 4, 5, 6};

    byte[] serialized = mapper.writeValueAsBytes(original);

    ApriltagResult results = camera.getResults(new TypeReference<ApriltagResult>() {}, serialized);

    assertEquals(results, original);
  }
}
