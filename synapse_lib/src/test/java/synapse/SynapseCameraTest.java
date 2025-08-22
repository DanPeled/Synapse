package synapse;

import static org.junit.jupiter.api.Assertions.*;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import edu.wpi.first.networktables.*;
import java.io.IOException;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.msgpack.jackson.dataformat.MessagePackFactory;

class SynapseCameraTest {

  private NetworkTableInstance ntInstance;
  private NetworkTable subTable;
  private SynapseCamera camera;

  @BeforeEach
  void setup() {
    camera = new SynapseCamera(0);
  }

  @Test
  void testGetResults() throws IOException {
    byte[] serialized =
        new ObjectMapper(new MessagePackFactory()).writeValueAsBytes(new int[] {1, 2, 3});

    int[] results = camera.getResults(new TypeReference<int[]>() {}, serialized);
    assertArrayEquals(new int[] {1, 2, 3}, results);
  }
}
