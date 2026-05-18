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

import {
  Globe,
  Hash,
  Info,
  Laptop,
  LayoutDashboard,
  Link,
  ShieldCheck,
  Tag,
  Terminal,
  Upload,
} from "lucide-react";
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
                <div className="flex items-center gap-2">
                  <Tag className="w-4 h-4" />
                  Nickname
                </div>
              </TableHead>

              <TableHead className="text-[#ff66c4]">
                <div className="flex items-center gap-2">
                  <Globe className="w-4 h-4" />
                  Address
                </div>
              </TableHead>

              <TableHead className="text-[#ff66c4]"></TableHead>
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

          {selectedDevice && <DeviceDialog device={selectedDevice} />}
        </DialogContent>
      </Dialog>
    </>
  );
}

function DeviceDialog({ device }: { device: DiscoveryResponse }) {
  return (
    <div className="space-y-3 text-xl min-w-0">
      <p className="flex items-center gap-2">
        <Laptop className="w-5 h-5 text-[#ff66c4]" />
        <strong>Hostname:</strong>
        <span className="break-all">{device.hostname}</span>
      </p>

      <p className="flex items-center gap-2">
        <Globe className="w-5 h-5 text-[#ff66c4]" />
        <strong>IP:</strong>
        <span className="break-all">{device.ip}</span>
      </p>

      <p className="flex items-center gap-2">
        <Tag className="w-5 h-5 text-[#ff66c4]" />
        <strong>Nickname:</strong>
        <span>{device.nickname}</span>
      </p>

      <p className="flex items-center gap-2">
        <Hash className="w-5 h-5 text-[#ff66c4]" />
        <strong>Team:</strong>
        <span>{device.team_number}</span>
      </p>

      <p className="flex items-center gap-2">
        <ShieldCheck className="w-5 h-5 text-[#ff66c4]" />
        <strong>Version:</strong>
        <span>{device.version}</span>
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
  );
}
