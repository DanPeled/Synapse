// SPDX-FileCopyrightText: 2025 Dan Peled
// SPDX-FileCopyrightText: 2026 Dan Peled
//
// SPDX-License-Identifier: GPL-3.0-or-later
//
// Generated from schema/synapse_lib.json. Do not edit by hand.
// Run `python tools/generate_synapse_lib.py` to regenerate.

package synapse.pipelines.apriltag;

import com.fasterxml.jackson.annotation.JsonProperty;
import edu.wpi.first.math.geometry.Pose3d;
import edu.wpi.first.math.geometry.Rotation3d;
import edu.wpi.first.math.geometry.Translation3d;
import java.util.Arrays;

/** Represents the result of detecting AprilTags in a single frame. */
public class ApriltagResult {

  /** The detected AprilTags. */
  public ApriltagDetection[] tags;

  /** The camera pose as [x, y, z, roll, pitch, yaw] in degrees, or null when unavailable. */
  public double[] cameraEstimate_fieldSpace;

  /** The reprojection error of the camera pose estimate. 0.0 when unavailable. */
  @JsonProperty("reprojection_error")
  public double reprojectionError;

  /** Default constructor. */
  public ApriltagResult() {}

  /**
   * Returns the camera's estimated pose in field space as a 3D pose.
   *
   * @return the estimated field-space pose, or {@code null} when no estimate was published
   */
  public Pose3d cameraEstimate_fieldSpace3d() {
    if (cameraEstimate_fieldSpace == null || cameraEstimate_fieldSpace.length < 6) {
      return null;
    }
    return new Pose3d(
        new Translation3d(
            cameraEstimate_fieldSpace[0],
            cameraEstimate_fieldSpace[1],
            cameraEstimate_fieldSpace[2]),
        new Rotation3d(
            Math.toRadians(cameraEstimate_fieldSpace[3]),
            Math.toRadians(cameraEstimate_fieldSpace[4]),
            Math.toRadians(cameraEstimate_fieldSpace[5])));
  }

  @Override
  public boolean equals(Object o) {
    if (this == o) return true;
    if (!(o instanceof ApriltagResult)) return false;
    ApriltagResult that = (ApriltagResult) o;
    return Arrays.equals(tags, that.tags)
        && Arrays.equals(cameraEstimate_fieldSpace, that.cameraEstimate_fieldSpace)
        && Double.compare(reprojectionError, that.reprojectionError) == 0;
  }

  @Override
  public int hashCode() {
    int result = Arrays.hashCode(tags);
    result = 31 * result + Arrays.hashCode(cameraEstimate_fieldSpace);
    result = 31 * result + Double.hashCode(reprojectionError);
    return result;
  }
}
