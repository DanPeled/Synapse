package synapse;

/**
 * This annotation is used to mark classes that represent a specific type of result to be registered
 * with Synapse.
 *
 * <p>The {@code type} value defines the type associated with the result, which can later be used
 * for validation, mapping, or processing within the system.
 *
 * <p>Classes annotated with this annotation must provide the {@code type} field, which is a string
 * representing the result type. This is necessary for ensuring that the correct result type is
 * registered and handled appropriately within the framework.
 */
public @interface RegisterSynapseResult {

  /**
   * The type associated with the result. This type will be used for matching and registration
   * purposes in the Synapse system.
   *
   * @return the type of the result
   */
  String type();
}
