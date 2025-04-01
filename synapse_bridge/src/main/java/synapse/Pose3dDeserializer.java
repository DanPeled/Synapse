package synapse;

import com.fasterxml.jackson.core.JacksonException;
import com.fasterxml.jackson.core.JsonParser;
import com.fasterxml.jackson.databind.DeserializationContext;
import com.fasterxml.jackson.databind.JsonDeserializer;
import com.fasterxml.jackson.databind.JsonNode;
import edu.wpi.first.math.geometry.Pose3d;
import edu.wpi.first.math.geometry.Rotation3d;
import edu.wpi.first.math.geometry.Translation3d;
import edu.wpi.first.math.util.Units;
import java.io.IOException;

/**
 * A custom Jackson deserializer for {@link Pose3d} objects. This class deserializes a JSON object
 * into a {@code Pose3d} instance, handling both degrees and radians for rotation.
 */
public class Pose3dDeserializer extends JsonDeserializer<Pose3d> {

  /**
   * Deserializes a JSON object into a {@link Pose3d} instance.
   *
   * @param p the JSON parser
   * @param ctxt the deserialization context
   * @return a new {@code Pose3d} instance based on the parsed JSON
   * @throws IOException if an I/O error occurs
   * @throws JacksonException if JSON parsing fails
   */
  @Override
  public Pose3d deserialize(JsonParser p, DeserializationContext ctxt)
      throws IOException, JacksonException {
    JsonNode node = p.getCodec().readTree(p);
    double x = node.get("x").asDouble();
    double y = node.get("y").asDouble();
    double z = node.get("z").asDouble();
    double yaw = node.get("yaw").asDouble();
    double pitch = node.get("pitch").asDouble();
    double roll = node.get("roll").asDouble();

    // Check if the rotation is specified in degrees and convert if necessary
    if ("degrees".equals(node.get("rotation_unit").textValue())) {
      return new Pose3d(
          new Translation3d(x, y, z),
          new Rotation3d(
              Units.degreesToRadians(roll),
              Units.degreesToRadians(pitch),
              Units.degreesToRadians(yaw)));
    } else { // Default to radians
      return new Pose3d(new Translation3d(x, y, z), new Rotation3d(roll, pitch, yaw));
    }
  }
}
