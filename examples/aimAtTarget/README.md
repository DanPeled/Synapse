# AimAtTarget – FRC Differential Drive Robot Example

This project is an **FRC example** demonstrating a differential drive robot with **joystick control**, **simulation support**, and **vision targeting using Synapse cameras** with AprilTag detection.

---

## Features

- **Differential Drive**
  Control a standard two-motor drivetrain using arcade drive (forward/backward + rotation).

- **Joystick Control**
  Drive manually using a joystick connected to the robot.

- **Synapse Vision Integration**
  Detect AprilTags and automatically adjust turning to aim at a specific tag (configured via `TAG_ID`).

- **Simulation Support**
  Simulate the drivetrain and encoders using WPILib's `DifferentialDrivetrainSim` and `EncoderSim`.

- **Field Visualization**
  Visualize robot pose on the SmartDashboard with `Field2d`.

---

## Project Structure

- **`Robot.java`** – Main robot code including teleop control, aiming logic, and simulation updates.
- **`Constants.java`** – Contains motor ports, encoder channels, and other configuration values.
- **Synapse Integration** – Uses `SynapseCamera` and AprilTag pipeline for vision targeting.

---

## Getting Started

### Requirements

- **Java 11+** (compatible with WPILib 2025)
- **WPILib** installed
- **SynapseFRC library**
- **Gradle** build system

### Running on the Robot

1. Connect your robot and deploy code:

   ```bash
   ./gradlew build
   ./gradlew deploy
