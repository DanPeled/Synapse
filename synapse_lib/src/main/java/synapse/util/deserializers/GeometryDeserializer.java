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
 * Transform2d, and their 3D counterparts.
 *
 * <p>This deserializer expects a JSON object with:
 *
 * <ul>
 *   <li>{@code "type"}: the simple class name of the geometry type (e.g., "Translation2d")
 *   <li>{@code "value"}: an array of numeric components used to construct the geometry object
 * </ul>
 *
 * <p>Example JSON:
 *
 * <pre>
 * {
 *   "type": "Translation2d",
 *   "value": [1.0, 2.0]
 * }
 * </pre>
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
        Translation2d.class,
        node -> new Translation2d(node.get(0).asDouble(), node.get(1).asDouble()));
    DESERIALIZERS.put(Rotation2d.class, node -> new Rotation2d(node.get(0).asDouble()));
    DESERIALIZERS.put(
        Pose2d.class,
        node ->
            new Pose2d(
                new Translation2d(node.get(0).asDouble(), node.get(1).asDouble()),
                new Rotation2d(node.get(2).asDouble())));
    DESERIALIZERS.put(
        Transform2d.class,
        node ->
            new Transform2d(
                new Translation2d(node.get(0).asDouble(), node.get(1).asDouble()),
                new Rotation2d(node.get(2).asDouble())));

    // 3D geometry deserializers
    DESERIALIZERS.put(
        Translation3d.class,
        node ->
            new Translation3d(
                node.get(0).asDouble(), node.get(1).asDouble(), node.get(2).asDouble()));
    DESERIALIZERS.put(
        Rotation3d.class,
        node ->
            new Rotation3d(node.get(0).asDouble(), node.get(1).asDouble(), node.get(2).asDouble()));
    DESERIALIZERS.put(
        Pose3d.class,
        node ->
            new Pose3d(
                new Translation3d(
                    node.get(0).asDouble(), node.get(1).asDouble(), node.get(2).asDouble()),
                new Rotation3d(
                    node.get(3).asDouble(), node.get(4).asDouble(), node.get(5).asDouble())));
    DESERIALIZERS.put(
        Transform3d.class,
        node ->
            new Transform3d(
                new Translation3d(
                    node.get(0).asDouble(), node.get(1).asDouble(), node.get(2).asDouble()),
                new Rotation3d(
                    node.get(3).asDouble(), node.get(4).asDouble(), node.get(5).asDouble())));

    // Store simple class names for type verification
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

  /**
   * Deserializes a JSON object into the target WPILib geometry type.
   *
   * <p>The JSON must contain both a {@code "type"} field matching the class name of the target
   * geometry type and a {@code "value"} array of numeric components.
   *
   * @param p the {@link JsonParser} instance providing the JSON data
   * @param ctxt the deserialization context
   * @return an instance of the target geometry type populated with values from JSON
   * @throws IOException if there is a problem reading from the parser
   * @throws IllegalArgumentException if the JSON type does not match the target class
   */
  @SuppressWarnings("unchecked")
  @Override
  public T deserialize(JsonParser p, DeserializationContext ctxt) throws IOException {
    JsonNode node = p.getCodec().readTree(p);
    String type = node.get("type").asText();
    JsonNode value = node.get("value");

    String expectedType = TYPE_NAMES.get(targetClass);
    if (!expectedType.equals(type)) {
      throw new IllegalArgumentException(
          "Type mismatch: expected " + expectedType + " but got " + type);
    }

    Function<JsonNode, ?> func = DESERIALIZERS.get(targetClass);
    if (func == null) {
      throw new IllegalArgumentException("No deserializer for class " + targetClass.getName());
    }

    return (T) func.apply(value);
  }
}
