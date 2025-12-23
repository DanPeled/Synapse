package synapse.pipelines.color;

import java.util.Arrays;
import java.util.Objects;

/**
 * Represents the result of a color detection pipeline. Contains bounding box, center coordinates,
 * and area of the detected color region.
 */
public class ColorDetection {
  /** Bounding box of the detected color region as [x, y, width, height]. */
  public float[] bbox;

  /** Center of the detected color region as [x, y]. */
  public float[] center;

  /** Area of the detected color region in pixels squared. */
  public float area;

  /** Default constructor. */
  public ColorDetection() {}

  /**
   * Computes a hash code for this ColorResult.
   *
   * @return hash code based on bbox, center, and area.
   */
  @Override
  public int hashCode() {
    int result = Objects.hash(area);
    result = 31 * result + Arrays.hashCode(bbox);
    result = 31 * result + Arrays.hashCode(center);
    return result;
  }

  /**
   * Compares this ColorResult to another object for equality. Two ColorResult objects are equal if
   * their bbox, center, and area are all equal.
   *
   * @param obj the object to compare to
   * @return true if equal, false otherwise
   */
  @Override
  public boolean equals(Object obj) {
    if (this == obj) return true;
    if (!(obj instanceof ColorDetection)) return false;
    ColorDetection other = (ColorDetection) obj;
    return Float.compare(area, other.area) == 0
        && Arrays.equals(bbox, other.bbox)
        && Arrays.equals(center, other.center);
  }
}
