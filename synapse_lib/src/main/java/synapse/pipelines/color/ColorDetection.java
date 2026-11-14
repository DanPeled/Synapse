// SPDX-FileCopyrightText: 2025 Dan Peled
// SPDX-FileCopyrightText: 2026 Dan Peled
//
// SPDX-License-Identifier: GPL-3.0-or-later
//
// Generated from schema/synapse_lib.json. Do not edit by hand.
// Run `python tools/generate_synapse_lib.py` to regenerate.

package synapse.pipelines.color;

import java.util.Arrays;

/** Represents a detected color region. */
public class ColorDetection {

  /** The bounding box as [x, y, width, height]. */
  public double[] bbox;

  /** The center of the region as [x, y]. */
  public double[] center;

  /** The area of the region in pixels squared. */
  public double area;

  /** Default constructor. */
  public ColorDetection() {}

  @Override
  public boolean equals(Object o) {
    if (this == o) return true;
    if (!(o instanceof ColorDetection)) return false;
    ColorDetection that = (ColorDetection) o;
    return Arrays.equals(bbox, that.bbox)
        && Arrays.equals(center, that.center)
        && Double.compare(area, that.area) == 0;
  }

  @Override
  public int hashCode() {
    int result = Arrays.hashCode(bbox);
    result = 31 * result + Arrays.hashCode(center);
    result = 31 * result + Double.hashCode(area);
    return result;
  }
}
