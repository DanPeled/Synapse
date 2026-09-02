package synapse;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.msgpack.jackson.dataformat.MessagePackFactory;

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

    Optional<int[]> results = camera.deserializeResults(new TypeReference<int[]>() {}, serialized);

    assertTrue(results.isPresent());
    assertArrayEquals(new int[] {1, 2, 3}, results.get());
  }

  @Test
  void testGetResultsApriltagResults() throws IOException {
    // TODO
  }
}
