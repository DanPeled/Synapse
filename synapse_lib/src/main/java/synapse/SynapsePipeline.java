package synapse;

import com.fasterxml.jackson.core.type.TypeReference;
import synapse.pipelines.apriltag.ApriltagResult;

/**
 * Represents a Synapse pipeline. Each pipeline is associated with a result class that defines the
 * type of data returned.
 *
 * @param <T> the type of result data returned by this pipeline, typically a List or Map of results
 */
public class SynapsePipeline<T> {

  /**
   * The AprilTag pipeline. This pipeline uses the {@link ApriltagResult} class to store the result
   * data.
   */
  public static final SynapsePipeline<ApriltagResult> kApriltag =
      new SynapsePipeline<>(new TypeReference<ApriltagResult>() {}, "ApriltagPipeline");

  /** The TypeReference representing the result type for this pipeline. */
  private final TypeReference<T> typeRef;

  /** The string identifier for this pipeline, used as the topic name. */
  public final String typestring;

  /**
   * Constructor for the SynapsePipeline class.
   *
   * @param typeRef The TypeReference associated with this pipeline's result data.
   * @param typestring The string identifier for this pipeline.
   */
  public SynapsePipeline(TypeReference<T> typeRef, String typestring) {
    this.typeRef = typeRef;
    this.typestring = typestring;
  }

  /**
   * Gets the TypeReference for this pipeline.
   *
   * @return The TypeReference representing the result type {@code T}.
   */
  public TypeReference<T> getTypeReference() {
    return typeRef;
  }
}
