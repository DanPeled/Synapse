import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { SetNetworkSettingsProto } from "@/generated/messages/v1/device";
import {
  MessageProto,
  MessageTypeProto,
} from "@/generated/messages/v1/message";
import { useBackendContext } from "@/services/backend/backendContext";
import { baseCardColor, teamColor } from "@/services/style";
import { AlertDialog } from "@/widgets/alertDialog";
import { Button } from "@/widgets/button";
import { Column, Row } from "@/widgets/containers";
import { Dropdown } from "@/widgets/dropdown";
import TextInput from "@/widgets/textInput";
import ToggleButton from "@/widgets/toggleButtons";
import { Network, TriangleAlert } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

// Keep in sync with synapse_net.devicenetworking.VIRTUAL_INTERFACE_PREFIXES.
const VIRTUAL_INTERFACE_PREFIXES = [
  "lo",
  "docker",
  "veth",
  "br-",
  "virbr",
  "vmnet",
  "tun",
  "tap",
  "wg",
  "tailscale",
  "zt",
  "dummy",
  "can",
  "vcan",
  "bond",
  "team",
  "ppp",
];

function isPhysicalInterface(name: string): boolean {
  return (
    name.length > 0 &&
    !VIRTUAL_INTERFACE_PREFIXES.some((prefix) => name.startsWith(prefix))
  );
}

const ipv4Regex =
  /^(25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)){3}$/;

/**
 * FRC teams use 10.TE.AM.11 for their coprocessors. Team 1234 becomes
 * 10.12.34.11, and team 68 becomes 10.0.68.11.
 */
function suggestedStaticAddress(teamNumber: number): string {
  if (!Number.isInteger(teamNumber) || teamNumber <= 0 || teamNumber > 9999) {
    return "";
  }

  const padded = teamNumber.toString().padStart(4, "0");
  return `10.${padded.slice(0, 2)}.${padded.slice(2)}.11`;
}

export function NetworkSettings({}) {
  const [manageDeviceNetworking, setManageDeviceNetworking] = useState(true);
  const {
    deviceinfo,
    networksettings,
    setNetworksettings,
    connection,
    socket,
  } = useBackendContext();

  const physicalInterfaces = useMemo(
    () => deviceinfo.networkInterfaces.filter(isPhysicalInterface),
    [deviceinfo.networkInterfaces],
  );

  const [selectedNetworkInterface, setSelectedNetworkInterface] = useState("");
  const [teamNumber, setTeamNumber] = useState(networksettings.teamNumber);
  const [hostname, setPropHostname] = useState(deviceinfo.hostname);
  const [networkTable, setNetworkTable] = useState(
    networksettings.networkTable,
  );
  const [staticEnabled, setStaticEnabled] = useState(false);
  const [staticIPAddr, setStaticIPAddr] = useState("");
  const [prefixLength, setPrefixLength] = useState("24");
  const [confirmOpen, setConfirmOpen] = useState(false);

  const teamNumberRegex = "\\d+";
  const suggestedAddress = suggestedStaticAddress(teamNumber);

  useEffect(() => {
    if (connection.backend) {
      setPropHostname(networksettings.hostname);
      setTeamNumber(networksettings.teamNumber);
      setNetworkTable(networksettings.networkTable);
      setPrefixLength(
        networksettings.prefixLength > 0
          ? networksettings.prefixLength.toString()
          : "24",
      );

      const configuredAddress = ipv4Regex.test(networksettings.ip)
        ? networksettings.ip
        : "";
      setStaticIPAddr(configuredAddress);
      setStaticEnabled(configuredAddress !== "");

      if (physicalInterfaces.includes(networksettings.networkInterface)) {
        setSelectedNetworkInterface(networksettings.networkInterface);
      } else {
        setSelectedNetworkInterface(physicalInterfaces.at(0) ?? "");
      }
    }
  }, [deviceinfo, connection, networksettings, physicalInterfaces]);

  const validate = (): string | null => {
    if (!hostname.trim()) {
      return "Hostname cannot be empty.";
    }

    if (!staticEnabled) {
      return null;
    }

    if (!selectedNetworkInterface) {
      return "Select a network interface for the static address.";
    }

    if (!ipv4Regex.test(staticIPAddr)) {
      return "Enter a valid IPv4 address, for example 10.12.34.11.";
    }

    const prefix = Number(prefixLength);
    if (!Number.isInteger(prefix) || prefix < 1 || prefix > 32) {
      return "Prefix length must be a whole number between 1 and 32.";
    }

    return null;
  };

  const applySettings = () => {
    const error = validate();
    if (error) {
      toast.error(error);
      return;
    }

    const networkSettings = SetNetworkSettingsProto.create({
      ip: staticEnabled ? staticIPAddr : "",
      hostname: hostname.trim(),
      networkInterface: staticEnabled ? selectedNetworkInterface : "",
      networkTable: networkTable,
      teamNumber: teamNumber ?? 0,
      prefixLength: staticEnabled ? Number(prefixLength) : 24,
    });

    const payload = MessageProto.create({
      type: MessageTypeProto.MESSAGE_TYPE_PROTO_SET_NETWORK_SETTINGS,
      setNetworkSettings: networkSettings,
    });

    const binary = MessageProto.encode(payload).finish();
    setNetworksettings(networkSettings);
    socket?.sendBinary(binary);

    toast.info(
      staticEnabled
        ? `Applying ${staticIPAddr}/${prefixLength}. DHCP stays enabled, but this connection may briefly drop.`
        : "Removing the static address. DHCP stays enabled, so internet access is unaffected.",
      { duration: 5000 },
    );
    setConfirmOpen(false);
  };

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
            value={teamNumber.toString() ?? ""}
            errorMessage="The NetworkTables Server Address must be a valid Team Number"
            onChange={(val) => {
              setTeamNumber(+val);
            }}
            textSize="text-lg"
          />
          <TextInput
            label="NetworkTable"
            value={networkTable}
            onChange={(val) => {
              setNetworkTable(val);
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
          <ToggleButton
            label="Static Address"
            value={staticEnabled}
            disabled={!manageDeviceNetworking}
            tooltip="Adds a fixed address alongside DHCP so the robot network can always reach this device. DHCP stays on for internet access."
            onToggleAction={(val) => {
              setStaticEnabled(val);
              if (val && !staticIPAddr && suggestedAddress) {
                setStaticIPAddr(suggestedAddress);
              }
            }}
          />
          {staticEnabled ? (
            <Column gap="gap-1">
              <Row className="items-center gap-3" wrap={false}>
                <TextInput
                  label="Static IP"
                  value={staticIPAddr}
                  placeholder="10.12.34.11"
                  errorMessage="Invalid IPv4 Address"
                  onChange={setStaticIPAddr}
                  pattern={ipv4Regex}
                  textSize="text-lg"
                  disabled={!manageDeviceNetworking}
                />
                <TextInput
                  label="/"
                  placeholder="24"
                  errorMessage="Invalid CIDR"
                  maxLength={2}
                  onChange={setPrefixLength}
                  value={prefixLength}
                  textSize="text-lg"
                  disabled={!manageDeviceNetworking}
                  inputWidth="w-14"
                  allowedChars="[0-9]"
                />
              </Row>
              <p className="text-sm text-gray-400">
                DHCP stays enabled, so internet access keeps working.
                {suggestedAddress && suggestedAddress !== staticIPAddr && (
                  <>
                    {" "}
                    Suggested for team {teamNumber}:{" "}
                    <button
                      type="button"
                      className="underline hover:text-white"
                      onClick={() => setStaticIPAddr(suggestedAddress)}
                    >
                      {suggestedAddress}
                    </button>
                  </>
                )}
              </p>
            </Column>
          ) : (
            <p className="text-sm text-gray-400">
              Currently using DHCP ({deviceinfo.ip || "no address yet"}). Turn
              on Static Address to also reach this device at a fixed address.
            </p>
          )}
          <TextInput
            label="Hostname"
            onChange={setPropHostname}
            disabled={!manageDeviceNetworking}
            value={hostname ?? "Unknown"}
            textSize="text-lg"
          />
          <Dropdown<string>
            label="Network Interface"
            value={selectedNetworkInterface}
            options={physicalInterfaces.map((inter) => ({
              label: inter,
              value: inter,
            }))}
            onValueChange={(val) => {
              setSelectedNetworkInterface(val);
            }}
            disabled={!manageDeviceNetworking || !staticEnabled}
            textSize="text-lg"
          />
          <Button
            className="mt-8"
            onClickAction={() => {
              const error = validate();
              if (error) {
                toast.error(error);
                return;
              }
              setConfirmOpen(true);
            }}
            disabled={!connection.backend || !manageDeviceNetworking}
          >
            Save
          </Button>
        </Column>
      </CardContent>
      <AlertDialog visible={confirmOpen} onClose={() => setConfirmOpen(false)}>
        <Column gap="gap-4" className="max-w-[420px]">
          <h3 className="flex items-center gap-2 text-lg font-bold">
            <TriangleAlert className="text-yellow-400" />
            Apply network settings?
          </h3>
          <p className="text-sm text-gray-300">
            {staticEnabled
              ? `The address ${staticIPAddr}/${prefixLength} will be added on ${selectedNetworkInterface} while DHCP stays enabled.`
              : "The static address will be removed while DHCP stays enabled."}{" "}
            Applying changes may briefly drop the connection to this device.
          </p>
          <Row justify="end" gap="gap-3" className="flex-nowrap">
            <Button onClickAction={() => setConfirmOpen(false)}>Cancel</Button>
            <Button onClickAction={applySettings}>Apply</Button>
          </Row>
        </Column>
      </AlertDialog>
    </Card>
  );
}
