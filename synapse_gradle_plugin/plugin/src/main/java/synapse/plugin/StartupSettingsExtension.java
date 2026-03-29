package synapse.plugin;

public class StartupSettingsExtension {
    private String projectName;
    private String deviceName;

    public String getDeviceName() {
        return deviceName;
    }

    public void setDeviceName(String name) {
        deviceName = name;
    }

    public String getProjectName() {
        return projectName;
    }

    public void setProjectName(String name) {
        projectName = name;
    }
}
