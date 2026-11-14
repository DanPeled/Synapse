// SPDX-FileCopyrightText: 2026 Dan Peled
//
// SPDX-License-Identifier: GPL-3.0-or-later
//
// Generated from schema/synapse_lib.json. Do not edit by hand.
// Run `python tools/generate_synapse_lib.py` to regenerate.

package synapse.generated;

/** NetworkTables paths and pipeline type strings used by SynapseLib. */
public final class SynapseApi {
  /** The settings NetworkTables subtable. */
  public static final String SETTINGS_TABLE = "settings";

  /** The data NetworkTables subtable. */
  public static final String DATA_TABLE = "data";

  /** The selected pipeline index. */
  public static final String PIPELINE = "pipeline";

  /** The camera recording state. */
  public static final String RECORD = "record";

  /** The selected pipeline's type string. */
  public static final String PIPELINE_TYPE = "pipeline_type";

  /** The latest pipeline results, serialized with MessagePack. */
  public static final String RESULTS = "results";

  /** The latest capture latency, in seconds. */
  public static final String CAPTURE_LATENCY = "captureLatency";

  /** The latest processing latency, in seconds. */
  public static final String PROCESS_LATENCY = "processLatency";

  /** The camera view ID. */
  public static final String VIEW_ID = "view_id";

  /** Camera brightness. */
  public static final String BRIGHTNESS_SETTING = "brightness";

  /** Camera gain. */
  public static final String GAIN_SETTING = "gain";

  /** Camera exposure. */
  public static final String EXPOSURE_SETTING = "exposure";

  /** Camera orientation in degrees (0, 90, 180, or 270). */
  public static final String ORIENTATION_SETTING = "orientation";

  /** Camera contrast. */
  public static final String CONTRAST_SETTING = "contrast";

  /** Camera saturation. */
  public static final String SATURATION_SETTING = "saturation";

  /** Camera hue. */
  public static final String HUE_SETTING = "hue";

  /** Camera white balance temperature. */
  public static final String WHITE_BALANCE_TEMPERATURE_SETTING = "white_balance_temperature";

  /** Camera sharpness. */
  public static final String SHARPNESS_SETTING = "sharpness";

  /** AprilTag detection and field-space pose estimation. */
  public static final String APRILTAG_PIPELINE = "ApriltagPipeline";

  /** Color-region detection. */
  public static final String COLOR_PIPELINE = "ColorPipeline";

  private SynapseApi() {}
}
