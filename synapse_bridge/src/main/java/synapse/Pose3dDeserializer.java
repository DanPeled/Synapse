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
 * A custom Jackson deserializer for {@link Pose3d} objects.
 *
 * <p>This deserializer converts a JSON object into a {@code Pose3d} instance, extracting the
 * position (x, y, z) and orientation (yaw, pitch, roll) values. It handles rotation units,
 * automatically converting from degrees to radians when specified.
 */
public class Pose3dDeserializer extends JsonDeserializer<Pose3d> {

  /**
   * Deserializes a JSON object into a {@link Pose3d} instance.
   *
   * <p>This method reads the position and rotation values from the JSON node and converts them into
   * a {@code Pose3d} object. It checks if the rotation is in degrees and converts it to radians if
   * needed.
   *
   * @param p the JSON parser used to parse the input JSON
   * @param ctxt the deserialization context provided by Jackson
   * @return a new {@code Pose3d} instance based on the parsed JSON data
   * @throws IOException if an I/O error occurs during parsing
   * @throws JacksonException if an error occurs while parsing the JSON structure
   */
  @Override
  public Pose3d deserialize(JsonParser p, DeserializationContext ctxt)
      throws IOException, JacksonException {
    JsonNode node = p.getCodec().readTree(p);

    // Extracting the position (x, y, z) and rotation (yaw, pitch, roll) values
    double x = node.get("x").asDouble();
    double y = node.get("y").asDouble();
    double z = node.get("z").asDouble();
    double yaw = node.get("yaw").asDouble();
    double pitch = node.get("pitch").asDouble();
    double roll = node.get("roll").asDouble();

    // Check if the rotation is specified in degrees and convert it if necessary
    if ("degrees".equals(node.get("rotation_unit").textValue())) {
      return new Pose3d(
          new Translation3d(x, y, z),
          new Rotation3d(
              Units.degreesToRadians(roll),
              Units.degreesToRadians(pitch),
              Units.degreesToRadians(yaw)));
    } else { // Default to radians if rotation_unit is not "degrees"
      return new Pose3d(new Translation3d(x, y, z), new Rotation3d(roll, pitch, yaw));
    }
  }

  /**
   * Default constructor for the Pose3dDeserializer.
   *
   * <p>This constructor is provided to allow Jackson to instantiate the deserializer as needed.
   */
  public Pose3dDeserializer() {}
}
