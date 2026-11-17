package frc.robot;

import edu.wpi.first.math.kinematics.DifferentialDriveKinematics;

public final class Constants {

  // Motor ports
  public static final int LEFT_MOTOR_PORT = 0;
  public static final int RIGHT_MOTOR_PORT = 1;

  // Joystick port
  public static final int JOYSTICK_PORT = 0;

  // Encoder ports
  public static final int LEFT_ENCODER_A = 0;
  public static final int LEFT_ENCODER_B = 1;
  public static final int RIGHT_ENCODER_A = 2;
  public static final int RIGHT_ENCODER_B = 3;

  // Robot physical constants
  public static final double WHEEL_RADIUS_METERS = 0.0762; // 6 inches in meters
  public static final int ENCODER_CPR = 1024;

  // Encoder distance per pulse
  public static final double DISTANCE_PER_PULSE = 2 * Math.PI * WHEEL_RADIUS_METERS / ENCODER_CPR;

  // Differential drive kinematics
  public static final double TRACK_WIDTH_METERS = 0.6; // distance between left and right wheels
  public static final DifferentialDriveKinematics KINEMATICS =
      new DifferentialDriveKinematics(TRACK_WIDTH_METERS);
}
