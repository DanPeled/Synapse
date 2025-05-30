package synapse;

/**
 * Enum representing the different Synapse pipelines. Each pipeline is associated with a result
 * class that defines the type of data returned.
 */
enum SynapsePipeline {

  /**
   * The AprilTag pipeline. This pipeline uses the ApriltagResult class to store the result data.
   */
  kApriltag(ApriltagResult.class);

  /** The class that represents the result type for this pipeline. */
  public final Class<?> clazz;

  /**
   * Constructor for the SynapsePipeline enum.
   *
   * @param clazz The class associated with this pipeline's result data.
   */
  SynapsePipeline(Class<?> clazz) {
    this.clazz = clazz;
  }
}
