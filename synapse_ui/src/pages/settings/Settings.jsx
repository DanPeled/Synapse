import { React, useState } from "react";
import {
  iconColor,
  styles,
  iconSize,
  getDivColor,
  setDivColor,
  teamColor,
} from "../../services/style";
import {
  ChartColumnBig,
  Computer,
  Download,
  Eye,
  Import,
  ListRestart,
  Network,
  RotateCcw,
  Skull,
  TriangleAlert,
  Palette,
  X,
} from "lucide-react";
import TextInput from "../../widgets/textInput";
import OptionSelector from "../../widgets/optionSelector";
import { Column, Row } from "../../widgets/containers";
import { Button, DangerButton } from "../../widgets/button";
import AlertDialog from "../../widgets/alert";
import ToggleButton from "../../widgets/toggle";
import Dropdown from "../../widgets/dropdown.jsx";
import { useBackendContext } from "../../services/backend/backendContext";

const teamNumberRegex = "\\d+(\\.\\d+)?";
const ipAddressRegex = "((25[0-5]|2[0-4]\\d|1\\d{2}|[1-9]?\\d)(\\.(?!$)|$)){4}";
const teamNumberOrIPRegex = new RegExp(
  `^(${teamNumberRegex}|${ipAddressRegex})$`,
);

const settingsStyles = {
  statsCard: {
    height: "400px",
    maxWidth: "50%",
    flexShrink: 0, // prevent shrinking smaller than content
  },
};

const IPMode = Object.freeze({
  dhcp: "DHCP",
  static: "Static",
});

function Stats() {
  return (
    <div
      style={{
        ...styles.card,
        ...settingsStyles.statsCard,
        height: 420,
        width: "100%",
      }}
    >
      <h2
        style={{
          display: "flex",
          alignItems: "center",
          gap: "0.5em",
          color: teamColor
        }}
      >
        <ChartColumnBig stroke={iconColor} size={24} fill="none" />
        Stats
      </h2>

      <div style={styles.section}>
        <h3>General Metrics</h3>
        <div style={styles.scrollContainer}>
          <table style={styles.table}>
            <thead>
              <tr>
                <th style={styles.th}>Version</th>
                <th style={styles.th}>Platform</th>
                <th style={styles.th}>IP Address</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td style={styles.td}>Unknown</td>
                <td style={styles.td}>Unknown</td>
                <td style={styles.td}>Unknown</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div style={styles.section}>
        <h3>Hardware Metrics</h3>
        <div style={styles.scrollContainer}>
          <table style={{ ...styles.table }}>
            <thead>
              <tr>
                <th style={styles.th}>CPU Temp</th>
                <th style={styles.th}>CPU Usage</th>
                <th style={styles.th}>Memory Usage</th>
                <th style={styles.th}>CPU Throttling</th>
                <th style={styles.th}>Uptime</th>
                <th style={styles.th}>Disk Usage</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td style={styles.td}>---</td>
                <td style={styles.td}>---</td>
                <td style={styles.td}>---</td>
                <td style={styles.td}>---</td>
                <td style={styles.td}>---</td>
                <td style={styles.td}>---</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function NetworkSettings({
  ipMode,
  setIPMode,
  setNetworkTablesAddr,
  setHostname: setPropHostname,
  setStaticIPAddr,
}) {
  const [manageDeviceNetworking, setManageDeviceNetworking] = useState(true);
  const { deviceIP, setDeviceIP, hostname, setHostname: contextSetHostname } = useBackendContext();


  return (
    <Column
      style={{
        ...styles.placeholderCard,
        gap: "10px",
        flex: 1, // add this instead so it fills parent's flex space
        padding: "10px 10px",
        color: teamColor
      }}
    >
      <h2
        style={{
          display: "flex",
          alignItems: "center",
          gap: "0.5em",
        }}
      >
        <Network stroke={iconColor} size={24} fill="none" />
        Network Settings
      </h2>
      <TextInput
        label={
          <p>
            Team Number / <br /> NetworkTables Server Address
          </p>
        }
        pattern={teamNumberOrIPRegex}
        errorMessage="The NetworkTables Server Address must be a valid Team Number or IP address"
        onChange={(val) => {
          setNetworkTablesAddr(val);
        }}
      />
      <div style={{ height: "12px" }}></div>
      <ToggleButton
        label="Manage Device Networking"
        labelGap={"30%"}
        value={manageDeviceNetworking}
        onToggle={(val) => setManageDeviceNetworking(val)}
      />
      <div style={{ display: "flex", alignItems: "flex-end", gap: "8px" }}>
        <Row style={{ width: "600px", flexDirection: "row" }}>
          <TextInput
            label={ipMode == IPMode.static ? "Static IP" : "Current IP (DHCP)"}
            placeholder={deviceIP.valueOf()}
            pattern={ipAddressRegex}
            errorMessage="Invalid IPv4 Address"
            onChange={(val) => {
              setStaticIPAddr(val);
            }}
            disabled={!manageDeviceNetworking || ipMode == IPMode.dhcp}
            width="500px"
            allowedChars={"[\\d.]+"}
          />
          {ipMode == IPMode.static && (
            <TextInput
              label="/"
              placeholder="24"
              errorMessage="Invalid CIDR"
              onChange={(val) => {
                return val;
              }}
              disabled={!manageDeviceNetworking || ipMode == IPMode.dhcp}
              style={{ width: "4rem" }}
              width="100px"
              maxLength={2}
              allowedChars={"[0-9]"}
            />
          )}
        </Row>
        <OptionSelector
          gap={0}
          label=""
          options={[
            {
              label: IPMode.dhcp,
              value: IPMode.dhcp,
              tooltip: (
                <p style={{ textAlign: "center" }}>
                  Router will automatically assign an IP address <br /> that
                  changes across reboots
                </p>
              ),
            },
            {
              label: IPMode.static,
              value: IPMode.static,
              tooltip: "User-picked IP address that doesn't change",
            },
          ]}
          onChange={(val) => setIPMode(val)}
          value={ipMode}
          disabled={!manageDeviceNetworking}
        />
      </div>
      <TextInput
        label="Hostname"
        onChange={setPropHostname}
        disabled={!manageDeviceNetworking}
        initialValue={hostname}
      />
      <Dropdown
        label="NetworkManager Interface"
        tooltip={
          "Name of the interface Synapse should manage the IP address of"
        }
        options={[
          {
            label: "eth0",
            value: "eth0",
          },
        ]}
        onChange={(val) => { }}
        disabled={!manageDeviceNetworking}
      />
      <hr style={{ width: "98%", border: "1px solid rgba(20,20,20,0.5)" }} />
      <Button
        onClick={() => {
          // TODO
        }}
        disabled={true}
      >
        Save
      </Button>
    </Column>
  );
}

function DeviceControl() {
  const [programLogsVisible, setProgramLogsVisible] = useState(false);

  const buttonContentStyle = {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: "0.5em",
    width: "100%",
    height: "100%",
  };

  return (
    <>
      <Column
        style={{ ...styles.card, height: "405px", gap: "15px", width: "50%" }}
      >
        <h2 style={{ display: "flex", alignItems: "center", gap: "0.5em", color: teamColor }}>
          <Computer stroke={iconColor} size={24} fill="none" />
          Device Control
        </h2>

        <Row fitMaxWidth={true} style={{ gap: "10px" }}>
          <Button>
            <span style={buttonContentStyle}>
              <Import size={iconSize} />
              Import Settings
            </span>
          </Button>
          <Button>
            <span style={buttonContentStyle}>
              <Download size={iconSize} />
              Export Settings
            </span>
          </Button>
        </Row>

        <Row fitMaxWidth={true} style={{ gap: "10px" }}>
          <Button>
            <span style={buttonContentStyle}>
              <Download size={iconSize} />
              Download Logs
            </span>
          </Button>
          <Button onClick={() => setProgramLogsVisible(true)}>
            <span style={buttonContentStyle}>
              <Eye size={iconSize} />
              View Program Logs
            </span>
          </Button>
        </Row>

        <h2
          style={{
            color: "yellow",
            display: "flex",
            alignItems: "center",
            gap: "0.5em",
          }}
        >
          <TriangleAlert />
          Danger Zone
        </h2>

        <Row fitMaxWidth={true}>
          <DangerButton warning="Restarting Synapse will restart all runtime processes. Proceed only if necessary.">
            <span style={buttonContentStyle}>
              <RotateCcw size={iconSize} />
              Restart Synapse
            </span>
          </DangerButton>
          <DangerButton warning="Restarting the device will stop all processes. Make sure to save your work.">
            <span style={buttonContentStyle}>
              <ListRestart size={iconSize} />
              Restart Device
            </span>
          </DangerButton>
        </Row>

        <DangerButton warning="WARNING: This action will factory reset the device and permanently delete all saved data. This cannot be undone.">
          <span style={buttonContentStyle}>
            <Skull size={iconSize} />
            Factory Reset Synapse & Delete Everything
          </span>
        </DangerButton>
      </Column>

      {programLogsVisible && (
        <AlertDialog
          visible={programLogsVisible}
          onClose={() => setProgramLogsVisible(false)}
          style={{ width: "80%", height: "80%" }}
        >
          <Button onClick={() => setProgramLogsVisible(false)}>
            <span style={buttonContentStyle}>
              <X />
              Close
            </span>
          </Button>
        </AlertDialog>
      )}
    </>
  );
}

export default function Settings() {
  const [ipMode, setIPMode] = useState(IPMode.dhcp);
  const [networkTablesAddr, setNetworkTablesAddr] = useState(null);
  const [hostname, setHostname] = useState(null);
  const [staticIPAddr, setStaticIPAddr] = useState(null);

  return (
    <Row style={{ gap: "0px" }}>
      <Column style={{ flex: 3, gap: "8px" }}>
        <div style={{ width: "190%" }}>
          {" "}
          {/*Only god knows why this works */}
          <Stats />
        </div>
        <div style={{ width: "190%" }}>
          <DeviceControl />
        </div>
      </Column>
      <Column style={{ flex: 2 }}>
        <NetworkSettings
          setIPMode={setIPMode}
          ipMode={ipMode}
          setNetworkTablesAddr={setNetworkTablesAddr}
          setHostname={setHostname}
          setStaticIPAddr={setStaticIPAddr}
        />
      </Column>
    </Row>
  );
}
