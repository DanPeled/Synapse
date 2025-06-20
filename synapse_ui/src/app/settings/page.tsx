"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useBackendContext } from "@/services/backend/backendContext";
import {
  background,
  baseCardColor,
  iconSize,
  teamColor,
} from "@/services/style";
import { createMessage } from "@/services/websocket";
import { AlertDialog } from "@/widgets/alertDialog";
import { Button, DangerButton } from "@/widgets/button";
import { Column, Row } from "@/widgets/containers";
import { Dropdown } from "@/widgets/dropdown";
import OptionSelector from "@/widgets/optionSelector";
import TextInput from "@/widgets/textInput";
import ToggleButton from "@/widgets/toggleButtons";
import {
  AlertTriangle,
  ChartColumnBig,
  Clock,
  Computer,
  Download,
  Eye,
  Import,
  ListRestart,
  Network,
  RotateCcw,
  Skull,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";

enum IPMode {
  static = "Static",
  dhcp = "DHCP",
}

function NetworkSettings({}) {
  const [manageDeviceNetworking, setManageDeviceNetworking] = useState(true);
  const {
    deviceinfo,
    setDeviceinfo,
    networktable,
    setNetworktable,
    connection,
    socket,
    networkTablesServer,
    setNetworkTablesServer,
  } = useBackendContext();
  const [networkInterface, setNetworkInterface] = useState(
    deviceinfo.networkInterfaces[0],
  );
  const [hostname, setPropHostname] = useState(deviceinfo.hostname);
  const [ipMode, setIpMode] = useState(IPMode.dhcp.valueOf());
  const [staticIPAddr, setStaticIPAddr] = useState(deviceinfo.ip);

  const teamNumberRegex = "\\d+(\\.\\d+)?";
  const ipAddressRegex =
    "((25[0-5]|2[0-4]\\d|1\\d{2}|[1-9]?\\d)(\\.(?!$)|$)){4}";
  const teamNumberOrIPRegex = new RegExp(
    `^(${teamNumberRegex}|${ipAddressRegex})$`,
  );

  useEffect(() => {
    if (hostname == null) {
      setPropHostname(deviceinfo.hostname);
    }
  }, [deviceinfo]);

  useEffect(() => {
    if (ipMode === IPMode.static && staticIPAddr == null) {
      setStaticIPAddr(deviceinfo.ip);
    }
  }, [ipMode]);

  return (
    <Card
      style={{ backgroundColor: baseCardColor, color: teamColor }}
      className="border-gray-700 min-w-[450px]"
    >
      <CardHeader className="pb-0">
        <CardTitle className="flex items-center gap-2 text-lg">
          <Network />
          Network Settings
        </CardTitle>
      </CardHeader>
      <CardContent>
        <Column gap="gap-3">
          <TextInput
            label="Team Number / NetworkTables Server Address"
            pattern={teamNumberOrIPRegex}
            errorMessage="The NetworkTables Server Address must be a valid Team Number or IP address"
            onChange={(val) => {
              setNetworkTablesServer(val);
            }}
          />
          <TextInput
            label="NetworkTable"
            initialValue={networktable}
            onChange={(val) => {
              setNetworktable(val);
            }}
          />
          <ToggleButton
            label="Manage Device Networking"
            value={manageDeviceNetworking}
            onToggleAction={(val) => {
              setManageDeviceNetworking(val);
            }}
          />
          <Row className="items-center gap-4">
            <TextInput
              label={
                ipMode === IPMode.static ? "Static IP" : "Current IP (DHCP)"
              }
              initialValue={deviceinfo.ip?.valueOf() ?? "127.0.0.1"}
              pattern={ipAddressRegex}
              errorMessage="Invalid IPv4 Address"
              onChange={(val) => {
                setStaticIPAddr(val);
              }}
              disabled={!manageDeviceNetworking || ipMode === IPMode.dhcp}
              allowedChars={"[\\d.]+"}
            />
            {ipMode === IPMode.static && (
              <TextInput
                label="/"
                placeholder="24"
                errorMessage="Invalid CIDR"
                maxLength={2}
                onChange={(val) => {
                  return val;
                }}
                initialValue="24"
                disabled={
                  !manageDeviceNetworking || ipMode === IPMode.dhcp.valueOf()
                }
                allowedChars={"[0-9]"}
              />
            )}
            <OptionSelector
              label=""
              options={[
                {
                  label: IPMode.dhcp,
                  value: IPMode.dhcp,
                  tooltip:
                    "Router will automatically assign an IP address that changes across reboots",
                },
                {
                  label: IPMode.static,
                  value: IPMode.static,
                  tooltip: "User-picked IP address that doesn't change",
                },
              ]}
              onChange={(val) => setIpMode(val.toString())}
              value={ipMode}
              disabled={!manageDeviceNetworking}
            />
          </Row>
          <TextInput
            label="Hostname"
            onChange={setPropHostname}
            disabled={!manageDeviceNetworking}
            initialValue={deviceinfo.hostname ?? "Unknown"}
          />
          <Dropdown
            label="NetworkManager Interface"
            value={networkInterface}
            options={deviceinfo.networkInterfaces.map((inter) => ({
              label: inter,
              value: inter,
            }))}
            onValueChange={(val) => {
              setNetworkInterface(val);
            }}
            disabled={!manageDeviceNetworking}
          />
          <Button
            onClickAction={() => {
              socket?.send(
                createMessage("set_network_config", {
                  ip: ipMode == IPMode.static ? staticIPAddr : null,
                  networkInterface: networkInterface,
                  hostname: hostname,
                  networkTable: networktable ?? "Synapse",
                  networkTablesServer: networkTablesServer,
                }),
              );
            }}
            disabled={!connection.backend || !manageDeviceNetworking}
          >
            Save
          </Button>
        </Column>
      </CardContent>
    </Card>
  );
}

function DeviceInfo({}) {
  const { hardwaremetrics, deviceinfo } = useBackendContext();

  return (
    <Card
      style={{ backgroundColor: baseCardColor, color: teamColor }}
      className="border-gray-700"
    >
      <CardHeader className="pb-0">
        <Row className="items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-lg">
            <ChartColumnBig className="w-5 h-5" />
            Device Status
          </CardTitle>
          <Row gap="gap-2" className="items-center">
            <Badge variant="secondary" className="bg-gray-400">
              <Clock className="w-3 h-3 mr-1" /> {""}
              Last Fetched: {hardwaremetrics.last_fetched}
            </Badge>
          </Row>
        </Row>
      </CardHeader>
      <CardContent>
        <Column gap="gap-4">
          <h2 className="font-bold">Device Info</h2>
          <Table className="w-full border rounded-lg text-center text-lg">
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead className="text-center">Version</TableHead>
                <TableHead className="text-center">Platform</TableHead>
                <TableHead className="text-center">IP Address</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow className="hover:bg-transparent">
                <TableCell className="text-center">Unknown</TableCell>
                <TableCell className="text-center">
                  {deviceinfo.platform}
                </TableCell>
                <TableCell className="text-center">
                  {deviceinfo.ip ?? "127.0.0.1"}
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
          <h2 className="font-bold">Hardware Metrics</h2>
          <Table className="w-full border rounded-lg text-center text-lg">
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead className="text-center">CPU Temp</TableHead>
                <TableHead className="text-center">CPU Usage</TableHead>
                <TableHead className="text-center">Memory Usage</TableHead>
                <TableHead className="text-center">Uptime</TableHead>
                <TableHead className="text-center">Disk Usage</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow className="hover:bg-transparent">
                <TableCell className="text-center">
                  {hardwaremetrics.cpu_temp > 0
                    ? `${hardwaremetrics.cpu_temp}°`
                    : "---"}
                </TableCell>
                <TableCell className="text-center">
                  {hardwaremetrics.cpu_usage > 0
                    ? `${hardwaremetrics.cpu_usage}%`
                    : "---"}
                </TableCell>
                <TableCell className="text-center">
                  {hardwaremetrics.ram_usage > 0
                    ? `${hardwaremetrics.ram_usage}%`
                    : "---"}
                </TableCell>
                <TableCell className="text-center">
                  {hardwaremetrics.uptime > 0
                    ? `${hardwaremetrics.uptime}s`
                    : "---"}
                </TableCell>
                <TableCell className="text-center">
                  {hardwaremetrics.disk_usage > 0
                    ? `${hardwaremetrics.disk_usage}%`
                    : "---"}
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </Column>
      </CardContent>
    </Card>
  );
}

function DangerZone() {
  return (
    <Column gap="gap-5">
      <h2 className="text-yellow-400 text-lg flex gap-2 items-center">
        <AlertTriangle /> Danger Zone
      </h2>
      <Row gap="gap-4">
        <DangerButton
          warning="Restarting Synapse will restart all runtime processes. Proceed only if necessary."
          className="w-full"
        >
          <span className="flex items-center justify-center gap-2">
            <RotateCcw size={iconSize} />
            Restart Synapse
          </span>
        </DangerButton>
        <DangerButton
          warning="Restarting the device will stop all processes. Make sure to save your work."
          className="w-full"
        >
          <span className="flex items-center justify-center gap-2">
            <ListRestart size={iconSize} />
            Restart Device
          </span>
        </DangerButton>
      </Row>

      <DangerButton
        warning="WARNING: This action will factory reset the device and permanently delete all saved data. This cannot be undone."
        className="w-full"
      >
        <span className="flex items-center justify-center gap-2">
          <Skull size={iconSize} />
          Factory Reset Synapse & Delete Everything
        </span>
      </DangerButton>
    </Column>
  );
}

function DeviceControls({}) {
  const { connection } = useBackendContext();
  const [programLogsVisible, setProgramLogsVisible] = useState(false);

  return (
    <Card
      style={{ backgroundColor: baseCardColor, color: teamColor }}
      className="border-gray-700"
    >
      <CardHeader className="pb-0">
        <CardTitle className="flex items-center gap-2 text-lg">
          <Computer className="w-5 h-5" />
          Device Control
        </CardTitle>
      </CardHeader>
      <CardContent>
        <Column gap="gap-4">
          <Row gap="gap-6">
            <Button className="w-full">
              <span className="flex items-center justify-center gap-2">
                <Import size={iconSize} />
                Import Settings
              </span>
            </Button>
            <Button className="w-full">
              <span className="flex items-center justify-center gap-2">
                <Download size={iconSize} />
                Export Settings
              </span>
            </Button>
          </Row>
          <Row gap="gap-6">
            <Button className="w-full">
              <span className="flex items-center justify-center gap-2">
                <Download size={iconSize} />
                Download Logs
              </span>
            </Button>
            <Button
              onClickAction={() => setProgramLogsVisible(true)}
              className="w-full"
            >
              <span className="flex items-center justify-center gap-2">
                <Eye size={iconSize} />
                View Program Logs
              </span>
            </Button>
          </Row>
          <DangerZone />
        </Column>

        {programLogsVisible && (
          <AlertDialog
            visible={programLogsVisible}
            onClose={() => setProgramLogsVisible(false)}
            className="w-[80vw] h-[80vh]"
          >
            <Button
              onClickAction={() => setProgramLogsVisible(false)}
              className="w-auto"
            >
              <span className="flex items-center justify-center gap-2">
                <X />
                Close
              </span>
            </Button>
          </AlertDialog>
        )}
      </CardContent>
    </Card>
  );
}

export default function Settings({}) {
  return (
    <div
      className="w-full min-h-screen text-pink-600"
      style={{ backgroundColor: background, color: teamColor }}
    >
      <div
        className="max-w-8xl mx-auto"
        style={{
          backgroundColor: background,
          borderRadius: "12px",
          padding: "10px",
        }}
      >
        <Row gap="gap-2" className="h-full">
          <Column className="flex-[1.5] space-y-2 h-full">
            <DeviceInfo />
            <DeviceControls />
          </Column>

          <Column className="flex-[1.2] space-y-2 h-full">
            <NetworkSettings />
          </Column>
        </Row>
      </div>
    </div>
  );
}
