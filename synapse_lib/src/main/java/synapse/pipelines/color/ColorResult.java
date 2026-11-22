// SPDX-FileCopyrightText: 2025 Dan Peled
// SPDX-FileCopyrightText: 2026 Dan Peled
//
// SPDX-License-Identifier: GPL-3.0-or-later
//
// Generated from schema/synapse_lib.json. Do not edit by hand.
// Run `python tools/generate_synapse_lib.py` to regenerate.

package synapse.pipelines.color;

import java.util.Arrays;
import java.util.Objects;

/** Represents the result of a color detection pipeline run. */
public class ColorResult {

  /** The timestamp in seconds when the frame was processed. */
  public double timestamp;

  /** All detected color regions. */
  public ColorDetection[] detections;

  /** The primary detection, or null when no regions were detected. */
  public ColorDetection main_detection;

  /** Default constructor. */
  public ColorResult() {}

  @Override
  public boolean equals(Object o) {
    if (this == o) return true;
    if (!(o instanceof ColorResult)) return false;
    ColorResult that = (ColorResult) o;
    return Double.compare(timestamp, that.timestamp) == 0
        && Arrays.equals(detections, that.detections)
        && Objects.equals(main_detection, that.main_detection);
  }

  @Override
  public int hashCode() {
    int result = Double.hashCode(timestamp);
    result = 31 * result + Arrays.hashCode(detections);
    result = 31 * result + Objects.hashCode(main_detection);
    return result;
  }
}
