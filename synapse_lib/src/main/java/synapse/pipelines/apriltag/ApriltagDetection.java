// SPDX-FileCopyrightText: 2025 Dan Peled
// SPDX-FileCopyrightText: 2026 Dan Peled
//
// SPDX-License-Identifier: GPL-3.0-or-later
//
// Generated from schema/synapse_lib.json. Do not edit by hand.
// Run `python tools/generate_synapse_lib.py` to regenerate.

package synapse.pipelines.apriltag;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.Arrays;

/** Represents a single detected AprilTag, including its screen-space position. */
public class ApriltagDetection {

  /** The unique ID of the detected AprilTag. */
  @JsonProperty("tag_id")
  public int tagID;

  /** The Hamming distance of the detection. Lower values are more accurate. */
  public int hamming;

  /** The center of the tag in screen space, as [x, y] pixels. */
  public double[] tagPose_screenSpace;

  /** Default constructor. */
  public ApriltagDetection() {}

  /**
   * Returns the tag's horizontal position in screen space.
   *
   * @return the tag's horizontal screen-space position
   */
  public double tx() {
    return tagPose_screenSpace[0];
  }

  /**
   * Returns the tag's vertical position in screen space.
   *
   * @return the tag's vertical screen-space position
   */
  public double ty() {
    return tagPose_screenSpace[1];
  }

  @Override
  public boolean equals(Object o) {
    if (this == o) return true;
    if (!(o instanceof ApriltagDetection)) return false;
    ApriltagDetection that = (ApriltagDetection) o;
    return tagID == that.tagID
        && hamming == that.hamming
        && Arrays.equals(tagPose_screenSpace, that.tagPose_screenSpace);
  }

  @Override
  public int hashCode() {
    int result = tagID;
    result = 31 * result + hamming;
    result = 31 * result + Arrays.hashCode(tagPose_screenSpace);
    return result;
  }
}
