package frc.robot.subsystems.vision;

import java.io.IOException;

import com.fasterxml.jackson.core.JacksonException;
import com.fasterxml.jackson.core.JsonParser;
import com.fasterxml.jackson.databind.DeserializationContext;
import com.fasterxml.jackson.databind.JsonDeserializer;
import com.fasterxml.jackson.databind.JsonNode;

import edu.wpi.first.math.geometry.Pose3d;
import edu.wpi.first.math.geometry.Rotation3d;
import edu.wpi.first.math.geometry.Translation3d;
import edu.wpi.first.math.util.Units;

public class Pose3dDeserializer extends JsonDeserializer<Pose3d> {
  @Override
  public Pose3d deserialize(JsonParser p, DeserializationContext ctxt) throws IOException, JacksonException {
    JsonNode node = p.getCodec().readTree(p);
    double x = node.get("x").asDouble();
    double y = node.get("y").asDouble();
    double z = node.get("z").asDouble();
    double yaw = node.get("yaw").asDouble();
    double pitch = node.get("pitch").asDouble();
    double roll = node.get("roll").asDouble();

    if (node.get("rotation_unit").textValue() == "degrees") {
      return new Pose3d(new Translation3d(x, y, z), new Rotation3d(Units.degreesToRadians(roll),
          Units.degreesToRadians(pitch), Units.degreesToRadians(yaw)));
    } else { // radians
      return new Pose3d(new Translation3d(x, y, z), new Rotation3d(roll,
          pitch, yaw));
    }
  }
}
