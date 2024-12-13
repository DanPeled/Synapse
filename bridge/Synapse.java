package frc.robot.subsystems.vision;

import java.util.HashMap;
import java.util.Map;
import java.util.Optional;
import java.util.Optional;

import edu.wpi.first.networktables.NetworkTable;
import edu.wpi.first.networktables.NetworkTableInstance;

public class Synapse {
  private NetworkTable m_table = NetworkTableInstance.getDefault().getTable("Synapse");
  
  public Synapse(){}

  public void setPipeline(int cameraIndex, long pipelineIndex) {
    m_table.getEntry(getCameraPipelineTopic(cameraIndex)).setInteger(pipelineIndex);
  }

  public long getPipeline(int cameraIndex) {
    return m_table.getEntry(getCameraPipelineTopic(cameraIndex)).getInteger(0);
  }

  private String getCameraPipelineTopic(int cameraIndex) {
    return String.format("camera%dpipeline", cameraIndex);
  }
}
