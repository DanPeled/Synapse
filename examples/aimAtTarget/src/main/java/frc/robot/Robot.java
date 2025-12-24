package frc.robot;

import edu.wpi.first.math.geometry.Pose2d;
import edu.wpi.first.wpilibj.Encoder;
import edu.wpi.first.wpilibj.Joystick;
import edu.wpi.first.wpilibj.RobotController;
import edu.wpi.first.wpilibj.TimedRobot;
import edu.wpi.first.wpilibj.drive.DifferentialDrive;
import edu.wpi.first.wpilibj.motorcontrol.PWMSparkMax;
import edu.wpi.first.wpilibj.simulation.DifferentialDrivetrainSim;
import edu.wpi.first.wpilibj.simulation.EncoderSim;
import edu.wpi.first.wpilibj.smartdashboard.Field2d;
import edu.wpi.first.wpilibj.smartdashboard.SmartDashboard;
import java.util.Optional;
import synapse.SynapseCamera;
import synapse.SynapsePipelineType;
import synapse.pipelines.apriltag.ApriltagResult;

public class Robot extends TimedRobot {
  // ID of the AprilTag we want to target
  public static final int TAG_ID = 1;

  // Motor controllers for left and right sides
  private final PWMSparkMax leftMotor = new PWMSparkMax(Constants.LEFT_MOTOR_PORT);
  private final PWMSparkMax rightMotor = new PWMSparkMax(Constants.RIGHT_MOTOR_PORT);

  // Differential drive object for arcade or tank drive
  private final DifferentialDrive drive = new DifferentialDrive(leftMotor, rightMotor);

  // Joystick for manual control
  private final Joystick stick = new Joystick(Constants.JOYSTICK_PORT);

  // Wheel encoders for distance and velocity feedback
  private final Encoder leftEncoder =
      new Encoder(Constants.LEFT_ENCODER_A, Constants.LEFT_ENCODER_B);
  private final Encoder rightEncoder =
      new Encoder(Constants.RIGHT_ENCODER_A, Constants.RIGHT_ENCODER_B);

  // Simulation objects (for testing without a real robot)
  private final DifferentialDrivetrainSim driveSim =
      DifferentialDrivetrainSim.createKitbotSim(
          DifferentialDrivetrainSim.KitbotMotor.kDualCIMPerSide,
          DifferentialDrivetrainSim.KitbotGearing.k10p71,
          DifferentialDrivetrainSim.KitbotWheelSize.kSixInch,
          null);

  private final EncoderSim leftEncoderSim = new EncoderSim(leftEncoder);
  private final EncoderSim rightEncoderSim = new EncoderSim(rightEncoder);

  // Field2d object for visualizing robot on the dashboard
  private final Field2d field = new Field2d();

  // Synapse camera for vision processing
  private final SynapseCamera camera =
      new SynapseCamera(SynapseConstants.CAMERA_NAME, SynapseConstants.PROCESSOR_NAME);

  @Override
  public void robotInit() {
    // Invert right side motors (depends on wiring/gearbox)
    rightMotor.setInverted(true);

    // Add Field2d to SmartDashboard for visualization
    SmartDashboard.putData("Field", field);

    // Configure encoder distance per pulse (wheel circumference / pulses per
    // revolution)
    leftEncoder.setDistancePerPulse(Constants.DISTANCE_PER_PULSE);
    rightEncoder.setDistancePerPulse(Constants.DISTANCE_PER_PULSE);
  }

  @Override
  public void teleopPeriodic() {
    // Get joystick inputs for driving
    double forward = -stick.getY(); // forward/backward
    double turn = stick.getX(); // left/right rotation

    // AIM-TO-TAG LOGIC
    if (camera.getPipelineType() == SynapsePipelineType.kApriltag.typestring) {
      Optional<ApriltagResult> results = camera.getResults(SynapsePipelineType.kApriltag);

      if (results.isPresent()) { // Check if we have any detected tags
        for (var tag : results.get().tags) {
          if (tag.tagID == TAG_ID) { // Only target our specific tag
            double screenX = tag.tagPose_screenSpace[0]; // X position, 0 = center of screen

            // Deadband: if tag is close enough to center, don't turn
            double deadband = 0.05;
            if (Math.abs(screenX) > deadband) {
              // Proportional control to turn toward tag
              double AIM_AT_TARGET_KP = 0.8; // tuning constant, adjust for smoothness
              turn = AIM_AT_TARGET_KP * screenX;
            } else {
              turn = 0; // inside deadband, no turning
            }

            break; // stop after first matching tag
          }
        }
      }
    }

    // Drive the robot with joystick + aiming adjustment
    drive.arcadeDrive(forward, turn);
  }

  @Override
  public void simulationPeriodic() {
    // Apply motor voltages to drivetrain simulation
    driveSim.setInputs(
        leftMotor.get() * RobotController.getBatteryVoltage(),
        rightMotor.get() * RobotController.getBatteryVoltage());

    driveSim.update(0.02); // Advance simulation by 20ms (match TimedRobot period)

    // Update simulated encoders with positions and velocities from drivetrain sim
    leftEncoderSim.setDistance(driveSim.getLeftPositionMeters());
    leftEncoderSim.setRate(driveSim.getLeftVelocityMetersPerSecond());
    rightEncoderSim.setDistance(driveSim.getRightPositionMeters());
    rightEncoderSim.setRate(driveSim.getRightVelocityMetersPerSecond());

    // Update robot pose on Field2d for visualization
    Pose2d pose = driveSim.getPose();
    field.setRobotPose(pose);
  }
}
