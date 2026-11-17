package synapse.util.deserializers;

import com.fasterxml.jackson.databind.module.SimpleModule;
import edu.wpi.first.math.geometry.*;

/**
 * Jackson module that registers deserializers for WPILib geometry classes.
 *
 * <p>This module provides support for deserializing 2D and 3D geometry types such as Translation2d,
 * Rotation2d, Pose2d, Transform2d, and their 3D counterparts using the {@link GeometryDeserializer}
 * class.
 *
 * <p>Once registered with an ObjectMapper, this module allows Jackson to automatically convert JSON
 * (or MessagePack) arrays into WPILib geometry objects.
 */
public class WPILibGeometryModule extends SimpleModule {

  /**
   * Constructs a new WPILibGeometryModule and registers deserializers for all supported WPILib
   * geometry types.
   */
  public WPILibGeometryModule() {
    super("WPILibGeometryModule");

    // Register generic deserializer for all 2D geometry classes
    addDeserializer(Translation2d.class, new GeometryDeserializer<>(Translation2d.class));
    addDeserializer(Rotation2d.class, new GeometryDeserializer<>(Rotation2d.class));
    addDeserializer(Pose2d.class, new GeometryDeserializer<>(Pose2d.class));
    addDeserializer(Transform2d.class, new GeometryDeserializer<>(Transform2d.class));

    // Register generic deserializer for all 3D geometry classes
    addDeserializer(Translation3d.class, new GeometryDeserializer<>(Translation3d.class));
    addDeserializer(Rotation3d.class, new GeometryDeserializer<>(Rotation3d.class));
    addDeserializer(Pose3d.class, new GeometryDeserializer<>(Pose3d.class));
    addDeserializer(Transform3d.class, new GeometryDeserializer<>(Transform3d.class));
  }
}
