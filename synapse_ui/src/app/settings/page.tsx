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
import { Button, DangerButton } from "@/widgets/button";
import { Column, Row } from "@/widgets/containers";
import {
  AlertTriangle,
  ChartColumnBig,
  Clock,
  Computer,
  Download,
  Eye,
  Import,
  ListRestart,
  RotateCcw,
  Skull,
} from "lucide-react";
import { useEffect, useState } from "react";
import { ProgramLogsDialog } from "./programLogsDialog";
import { NetworkSettings } from "./network_settings";
import { MessageProto, MessageTypeProto } from "@/proto/v1/message";
import { WebSocketWrapper } from "@/services/websocket";

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
              Last Fetched: {hardwaremetrics.lastFetched}
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
                  {hardwaremetrics.cpuTemp > 0
                    ? `${hardwaremetrics.cpuTemp.toFixed(2)}°c`
                    : "---"}
                </TableCell>
                <TableCell className="text-center">
                  {hardwaremetrics.cpuUsage > 0
                    ? `${hardwaremetrics.cpuUsage.toFixed(2)}%`
                    : "---"}
                </TableCell>
                <TableCell className="text-center">
                  {hardwaremetrics.ramUsage > 0
                    ? `${((hardwaremetrics.ramUsage / hardwaremetrics.memory) * 100).toFixed(2)}%`
                    : "---"}
                </TableCell>
                <TableCell className="text-center">
                  {hardwaremetrics.uptime > 0
                    ? `${Math.floor(hardwaremetrics.uptime)}s`
                    : "---"}
                </TableCell>
                <TableCell className="text-center">
                  {hardwaremetrics.diskUsage > 0
                    ? `${hardwaremetrics.diskUsage.toFixed(2)}%`
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

function DangerZone({ socket }: { socket?: WebSocketWrapper }) {
  return (
    <Column gap="gap-5">
      <h2 className="text-yellow-400 text-lg flex gap-2 items-center">
        <AlertTriangle /> Danger Zone
      </h2>
      <Row gap="gap-4">
        <DangerButton
          warning="Restarting Synapse will restart all runtime processes. Proceed only if necessary."
          className="w-full"
          onClickAction={() => {
            const payload = MessageProto.create({
              type: MessageTypeProto.MESSAGE_TYPE_PROTO_RESTART_SYNAPSE,
              removePipelineIndex: -1,
            });

            const binary = MessageProto.encode(payload).finish();
            socket?.sendBinary(binary);
          }}
          disabled={true}
        >
          <span className="flex items-center justify-center gap-2">
            <RotateCcw size={iconSize} />
            Restart Synapse
          </span>
        </DangerButton>
        <DangerButton
          warning="Restarting the device will stop all processes. Make sure to save your work."
          className="w-full"
          onClickAction={() => {
            const payload = MessageProto.create({
              type: MessageTypeProto.MESSAGE_TYPE_PROTO_REBOOT,
              removePipelineIndex: -1,
            });

            const binary = MessageProto.encode(payload).finish();
            socket?.sendBinary(binary);
          }}
        >
          <span className="flex items-center justify-center gap-2">
            <ListRestart size={iconSize} />
            Restart Device
          </span>
        </DangerButton>
      </Row>

      <DangerButton
        warning="WARNING: This action will factory reset the device and permanently delete all saved data. This cannot be undone. Once this is confirmed the device will restart."
        className="w-full"
        onClickAction={() => {
          const payload = MessageProto.create({
            type: MessageTypeProto.MESSAGE_TYPE_PROTO_FORMAT,
            removePipelineIndex: -1,
          });

          const binary = MessageProto.encode(payload).finish();
          socket?.sendBinary(binary);
        }}
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
  const [programLogsVisible, setProgramLogsVisible] = useState(false);
  const { logs, socket } = useBackendContext();

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
          <DangerZone socket={socket} />
        </Column>

        <ProgramLogsDialog
          visible={programLogsVisible}
          setVisible={setProgramLogsVisible}
          logs={logs}
        />
      </CardContent>
    </Card>
  );
}

export default function Settings({}) {
  useEffect(() => {
    document.title = "Synapse Client";
  }, []);

  return (
    <div
      className="w-full text-pink-600"
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
