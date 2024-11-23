package frc.robot.subsystems.vision;

import java.util.HashMap;
import java.util.Map;
import java.util.Optional;
import java.util.Optional;

import edu.wpi.first.networktables.NetworkTable;
import edu.wpi.first.networktables.NetworkTableInstance;

public class Synapse {
  private static Map<String, Synapse> m_instances = new HashMap<>();
  private NetworkTable m_table = NetworkTableInstance.getDefault().getTable("Synapse");

  public static Synapse createInstance(String tableName) {
    Synapse s = new Synapse();

    s.setTableName(tableName);
    m_instances.put(tableName, s);
    return s;
  }

  public static Optional<Synapse> getInstance(String name) {
    return Optional.<Synapse>of(m_instances.get(name));
  }

  public void setTableName(String newTableName) {
    m_table = NetworkTableInstance.getDefault().getTable(newTableName);
  }

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
