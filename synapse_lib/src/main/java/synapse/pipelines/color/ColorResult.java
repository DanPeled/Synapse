package synapse.pipelines.color;

import java.util.Arrays;
import java.util.Objects;

/**
 * Represents the result of a color detection pipeline run.
 *
 * <p>This object contains all detected color targets for a single frame, along with a designated
 * primary detection (if one exists) and the timestamp at which the frame was processed.
 */
public class ColorResult {

  /**
   * Timestamp (in seconds) at which this result was captured or processed. This is typically
   * synchronized to the coprocessor or camera clock.
   */
  public float timestamp;

  /** All color detections found in the frame. This may be empty if no targets were detected. */
  public ColorDetection[] detections;

  /**
   * The primary or best color detection for this frame. This is usually selected based on criteria
   * such as size, confidence, or proximity, and may be {@code null} if no detections are present.
   */
  public ColorDetection main_detection;

  /**
   * Compares this {@link ColorResult} to another object for equality.
   *
   * <p>Two {@code ColorResult} instances are considered equal if they have the same timestamp,
   * identical detection arrays (by contents), and equal primary detections.
   *
   * @param obj the object to compare against
   * @return {@code true} if the objects are equal, {@code false} otherwise
   */
  @Override
  public boolean equals(Object obj) {
    if (this == obj) {
      return true;
    }
    if (!(obj instanceof ColorResult)) {
      return false;
    }

    ColorResult other = (ColorResult) obj;
    return Float.compare(timestamp, other.timestamp) == 0
        && Arrays.equals(detections, other.detections)
        && Objects.equals(main_detection, other.main_detection);
  }

  /**
   * Computes a hash code for this {@link ColorResult}.
   *
   * <p>The hash code is derived from the timestamp, detection array contents, and primary
   * detection, and is consistent with {@link #equals(Object)}.
   *
   * @return a hash code value for this object
   */
  @Override
  public int hashCode() {
    int result = Objects.hash(timestamp, main_detection);
    result = 31 * result + Arrays.hashCode(detections);
    return result;
  }
}
