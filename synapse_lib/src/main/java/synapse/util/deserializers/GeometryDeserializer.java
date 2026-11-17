package synapse.util.deserializers;

import com.fasterxml.jackson.core.JsonParser;
import com.fasterxml.jackson.databind.DeserializationContext;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.deser.std.StdDeserializer;
import edu.wpi.first.math.geometry.*;
import java.io.IOException;
import java.util.HashMap;
import java.util.Map;
import java.util.function.Function;

/**
 * Generic deserializer for WPILib geometry classes such as Translation2d, Rotation2d, Pose2d,
 * Transform2d, Twist2d, and their 3D counterparts.
 *
 * <p>Synapse serializes geometry as plain arrays, for example:
 *
 * <pre>
 * [1.0, 2.0]
 * </pre>
 *
 * <p>For backwards compatibility, the older tagged representation is also accepted:
 *
 * <pre>
 * {
 *   "type": "Translation2d",
 *   "value": [1.0, 2.0]
 * }
 * </pre>
 *
 * <p>Angles are serialized in degrees, while WPILib's Java constructors take radians, so rotation
 * components are converted here.
 *
 * @param <T> the type of WPILib geometry object to deserialize
 */
public class GeometryDeserializer<T> extends StdDeserializer<T> {

  /** Map linking geometry classes to deserialization functions. */
  private static final Map<Class<?>, Function<JsonNode, ?>> DESERIALIZERS = new HashMap<>();

  /** Map storing the simple class names of the supported geometry types. */
  private static final Map<Class<?>, String> TYPE_NAMES = new HashMap<>();

  static {
    // 2D geometry deserializers
    DESERIALIZERS.put(
        Translation2d.class, node -> new Translation2d(component(node, 0), component(node, 1)));
    DESERIALIZERS.put(
        Rotation2d.class,
        node -> new Rotation2d(toRadians(node.isArray() ? component(node, 0) : node.asDouble())));
    DESERIALIZERS.put(
        Pose2d.class,
        node ->
            new Pose2d(
                new Translation2d(component(node, 0), component(node, 1)),
                new Rotation2d(toRadians(component(node, 2)))));
    DESERIALIZERS.put(
        Transform2d.class,
        node ->
            new Transform2d(
                new Translation2d(component(node, 0), component(node, 1)),
                new Rotation2d(toRadians(component(node, 2)))));
    DESERIALIZERS.put(
        Twist2d.class,
        node -> new Twist2d(component(node, 0), component(node, 1), component(node, 2)));

    // 3D geometry deserializers
    DESERIALIZERS.put(
        Translation3d.class,
        node -> new Translation3d(component(node, 0), component(node, 1), component(node, 2)));
    DESERIALIZERS.put(
        Rotation3d.class,
        node ->
            new Rotation3d(
                toRadians(component(node, 0)),
                toRadians(component(node, 1)),
                toRadians(component(node, 2))));
    DESERIALIZERS.put(
        Pose3d.class,
        node ->
            new Pose3d(
                new Translation3d(component(node, 0), component(node, 1), component(node, 2)),
                new Rotation3d(
                    toRadians(component(node, 3)),
                    toRadians(component(node, 4)),
                    toRadians(component(node, 5)))));
    DESERIALIZERS.put(
        Transform3d.class,
        node ->
            new Transform3d(
                new Translation3d(component(node, 0), component(node, 1), component(node, 2)),
                new Rotation3d(
                    toRadians(component(node, 3)),
                    toRadians(component(node, 4)),
                    toRadians(component(node, 5)))));
    DESERIALIZERS.put(
        Twist3d.class,
        node ->
            new Twist3d(
                component(node, 0),
                component(node, 1),
                component(node, 2),
                component(node, 3),
                component(node, 4),
                component(node, 5)));

    // Store simple class names for optional type verification
    for (Class<?> cls : DESERIALIZERS.keySet()) {
      TYPE_NAMES.put(cls, cls.getSimpleName());
    }
  }

  /** The target geometry class to deserialize. */
  private final Class<T> targetClass;

  /**
   * Constructs a GeometryDeserializer for a specific WPILib geometry type.
   *
   * @param targetClass the geometry class that this deserializer will handle
   */
  public GeometryDeserializer(Class<T> targetClass) {
    super(targetClass);
    this.targetClass = targetClass;
  }

  private static double toRadians(double degrees) {
    return Math.toRadians(degrees);
  }

  private static double component(JsonNode node, int index) {
    JsonNode value = node.get(index);
    if (value == null || !value.isNumber()) {
      throw new IllegalArgumentException(
          "Expected numeric geometry component at index " + index + ", got " + node);
    }
    return value.asDouble();
  }

  /**
   * Deserializes a JSON array (or legacy tagged object) into the target WPILib geometry type.
   *
   * @param p the {@link JsonParser} instance providing the JSON data
   * @param ctxt the deserialization context
   * @return an instance of the target geometry type populated with values from JSON
   * @throws IOException if there is a problem reading from the parser
   * @throws IllegalArgumentException if the JSON type does not match the target class or the
   *     payload has the wrong shape
   */
  @SuppressWarnings("unchecked")
  @Override
  public T deserialize(JsonParser p, DeserializationContext ctxt) throws IOException {
    JsonNode node = p.getCodec().readTree(p);

    JsonNode value = node;
    if (node.isObject()) {
      String type = node.path("type").asText(null);
      value = node.get("value");
      String expectedType = TYPE_NAMES.get(targetClass);
      if (type != null && expectedType != null && !expectedType.equals(type)) {
        throw new IllegalArgumentException(
            "Type mismatch: expected " + expectedType + " but got " + type);
      }
      if (value == null) {
        throw new IllegalArgumentException("Tagged geometry object is missing a 'value' field");
      }
    }

    Function<JsonNode, ?> func = DESERIALIZERS.get(targetClass);
    if (func == null) {
      throw new IllegalArgumentException("No deserializer for class " + targetClass.getName());
    }

    return (T) func.apply(value);
  }
}
