import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { SetNetworkSettingsProto } from "@/proto/v1/device";
import { MessageProto, MessageTypeProto } from "@/proto/v1/message";
import { useBackendContext } from "@/services/backend/backendContext";
import { baseCardColor, teamColor } from "@/services/style";
import { Button } from "@/widgets/button";
import { Column, Row } from "@/widgets/containers";
import { Dropdown } from "@/widgets/dropdown";
import OptionSelector from "@/widgets/optionSelector";
import TextInput from "@/widgets/textInput";
import ToggleButton from "@/widgets/toggleButtons";
import { Network } from "lucide-react";
import { useEffect, useState } from "react";

export enum IPMode {
  static = "Static",
  dhcp = "DHCP",
}

export function NetworkSettings({}) {
  const [manageDeviceNetworking, setManageDeviceNetworking] = useState(true);
  const {
    deviceinfo,
    networktable,
    setNetworktable,
    connection,
    teamnumber,
    setTeamnumber,
    socket,
  } = useBackendContext();
  const [selectedNetworkInterface, setSelectedNetworkInterface] = useState(
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
  const ipv4Regex = /^((25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)(\.|$)){4}$/;

  useEffect(() => {
    if (connection.backend) {
      setPropHostname(deviceinfo.hostname);
      setStaticIPAddr(deviceinfo.ip);
      setSelectedNetworkInterface(deviceinfo.networkInterfaces.at(0) ?? "");
    }
  }, [deviceinfo, connection]);

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
        <Column gap="gap-3 text-lg">
          <TextInput
            label="Team Number"
            pattern={teamNumberRegex}
            value={teamnumber.toString() ?? ""}
            errorMessage="The NetworkTables Server Address must be a valid Team Number"
            onChange={(val) => {
              setTeamnumber(+val);
            }}
            textSize="text-lg"
          />
          <TextInput
            label="NetworkTable"
            value={networktable}
            onChange={(val) => {
              setNetworktable(val);
            }}
            textSize="text-lg"
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
              value={staticIPAddr ?? "127.0.0.1"}
              errorMessage="Invalid IPv4 Address"
              onChange={(val) => {
                setStaticIPAddr(val);
              }}
              pattern={ipv4Regex}
              textSize="text-lg"
              disabled={!manageDeviceNetworking || ipMode === IPMode.dhcp}
            />
            {ipMode === IPMode.static && (
              <TextInput
                label="/"
                placeholder="24"
                errorMessage="Invalid CIDR"
                maxLength={2}
                onChange={(_) => {}}
                value="24"
                textSize="text-lg"
                disabled={
                  !manageDeviceNetworking || ipMode === IPMode.dhcp.valueOf()
                }
                inputWidth="w-10"
                allowedChars={"[0-9]"}
              />
            )}
            <div className="ml-auto pr-8">
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
            </div>
          </Row>
          <TextInput
            label="Hostname"
            onChange={setPropHostname}
            disabled={!manageDeviceNetworking}
            value={hostname ?? "Unknown"}
            textSize="text-lg"
          />
          <Dropdown<string>
            label="NetworkManager Interface"
            value={selectedNetworkInterface}
            options={deviceinfo.networkInterfaces.map((inter) => ({
              label: inter,
              value: inter,
            }))}
            onValueChange={(val) => {
              setSelectedNetworkInterface(val);
            }}
            disabled={!manageDeviceNetworking}
            textSize="text-lg"
          />
          <Button
            className="mt-8"
            onClickAction={() => {
              const payload = MessageProto.create({
                type: MessageTypeProto.MESSAGE_TYPE_PROTO_SET_NETWORK_SETTINGS,
                setNetworkSettings: SetNetworkSettingsProto.create({
                  ip: staticIPAddr,
                  hostname: hostname,
                  networkInterface: selectedNetworkInterface,
                  networkTable: networktable,
                  teamNumber: teamnumber ?? 0,
                }),
              });

              const binary = MessageProto.encode(payload).finish();
              socket?.sendBinary(binary);
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
