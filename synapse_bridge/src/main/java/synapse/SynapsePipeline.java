package synapse;

enum SynapsePipeline {
  kApriltag(ApriltagResult.class);

  public final Class<?> clazz;

  SynapsePipeline(Class<?> clazz) {
    this.clazz = clazz;
  }
}
