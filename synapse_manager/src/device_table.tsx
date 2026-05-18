import { useState } from "react";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "./components/ui/table";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "./components/ui/dialog";

import { Info, LayoutDashboard, Link, Terminal, Upload } from "lucide-react";
import { openWindow } from "./lib/utils";
import { DiscoveryResponse } from "./udp";

export default function DeviceTable({
  devices,
}: {
  devices: DiscoveryResponse[];
}) {
  const [selectedDevice, setSelectedDevice] =
    useState<DiscoveryResponse | null>(null);

  return (
    <>
      <div className="ml-5 mt-5 overflow-hidden rounded-2xl bg-[#1f1f1f] shadow-sm">
        <Table className="overflow-hidden rounded-2xl">
          <TableHeader>
            <TableRow className="bg-[#0f0f0f] text-xl hover:bg-[#0f0f0f]">
              <TableHead className="text-[#ff66c4] first:rounded-tl-2xl">
                Nickname
              </TableHead>

              <TableHead className="text-[#ff66c4]">Address</TableHead>

              <TableHead className="text-[#ff66c4]" />
            </TableRow>
          </TableHeader>

          <TableBody>
            {devices.map((device, index) => (
              <TableRow
                key={device.ip}
                className="text-xl text-[#ff66c4] hover:bg-[#2b2a2a]"
              >
                <TableCell
                  className={
                    index === devices.length - 1 ? "rounded-bl-2xl" : ""
                  }
                >
                  {device.nickname}
                </TableCell>

                <TableCell>{device.ip}</TableCell>

                <TableCell
                  className={
                    index === devices.length - 1 ? "rounded-br-2xl" : ""
                  }
                >
                  <div className="flex gap-5">
                    <button onClick={() => setSelectedDevice(device)}>
                      <Info />
                    </button>

                    <button>
                      <Upload />
                    </button>

                    <button
                      title="Open Dashboard"
                      onClick={() => {
                        openWindow({
                          label: `SynapseDashboard${device.hostname}`,
                          url: `http://${device.ip}:3000`,
                        });
                      }}
                    >
                      <LayoutDashboard />
                    </button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <Dialog
        open={selectedDevice !== null}
        onOpenChange={(open) => {
          if (!open) {
            setSelectedDevice(null);
          }
        }}
      >
        <DialogContent className="border-[#2b2a2a] bg-[#1f1f1f] text-[#ff66c4] w-full max-w-[80vh]">
          <DialogHeader>
            <DialogTitle className="text-2xl">Device Info</DialogTitle>
          </DialogHeader>

          {selectedDevice && (
            <div className="space-y-2 text-xl min-w-0">
              <p>
                <strong>Hostname:</strong>{" "}
                <span className="break-all">{selectedDevice.hostname}</span>
              </p>
              <p>
                <strong>IP:</strong>{" "}
                <span className="break-all">{selectedDevice.ip}</span>
              </p>
              <p>
                <strong>Nickname:</strong> {selectedDevice.nickname}
              </p>
              <p>
                <strong>Team:</strong> {selectedDevice.team_number}
              </p>
              <p>
                <strong>Version:</strong> {selectedDevice.version}
              </p>
              <div className="row space-x-2 mt-15">
                <button title="Link To Project">
                  <Link />
                </button>
                <button title="Open Terminal" disabled>
                  <Terminal />
                </button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
