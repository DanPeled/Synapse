# Getting Target Data

## Constructing a SynapseCamera

#### What is a SynapseCamera?

**`SynapseCamera`** is a class in Synapse that provides a simple and consistent interface for interacting with a camera connected to a Synapse coprocessor. It exposes commonly used vision data, including pipeline results, latency, and [other metadata](../../additional-resources/networktables-api.md) published by Synapse.

The **`SynapseCamera`** class provides two constructors:

* A constructor that takes only the camera name. This version automatically uses the default Synapse coprocessor name, making it convenient when your setup only includes one coprocessor or when you want to rely on the standard configuration.
* A constructor that accepts both a coprocessor name and a camera name. This allows you to explicitly specify which coprocessor the camera belongs to, which is helpful in systems with multiple coprocessors or custom naming schemes.

In both cases, the camera name must match the camera’s configured name in the Synapse web UI to ensure proper communication over NetworkTables.

{% tabs %}
{% tab title="Java" %}
```java
// Change this to match the name of your camera and coprocessor
SynapseCamera camera = new SynapseCamera("camera1", "OrangePiSynapse");
```
{% endtab %}

{% tab title="Python" %}
```py
# Change this to match the name of your camera and coprocessor
self.camera = SynapseCamera("camera1", "OrangePiSynapse")
```
{% endtab %}
{% endtabs %}

## Getting The Pipeline Results

Use the `getResults(SynapsePipelineType<T> t)` to obtain the latest pipeline results. This method returns an `Optional<T>` where T is the result type of the passed pipleine (will return `Optional.empty()` if the camera is not currently using the same pipeline type as the passed one of there are no results)

{% tabs %}
{% tab title="Java" %}
```java
Optional<ApriltagResult> results = Optional.empty();
// Query the latest apriltag results from camera
results = camera.getResults(SynapsePipelineType.kApriltag);
```
{% endtab %}

{% tab title="Python" %}
```python
# Query latest apriltag results from self.camera
results = self.camera.getResults(SynapsePipelineType.kApriltag);
```
{% endtab %}
{% endtabs %}

### Apriltag Results



### Color Detection Results

