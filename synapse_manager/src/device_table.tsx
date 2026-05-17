import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "./components/ui/table";

import { Info, LayoutDashboard, Upload } from "lucide-react";
import { openWindow } from "./lib/utils";
import { DiscoveryResponse } from "./udp";

export default function DeviceTable({
  devices,
}: {
  devices: DiscoveryResponse[];
}) {
  return (
    <div className="ml-5 mt-5 overflow-hidden rounded-2xl bg-[#1f1f1f] shadow-sm">
      <Table className="overflow-hidden rounded-2xl">
        <TableHeader>
          <TableRow className="bg-[#0f0f0f] text-xl hover:bg-[#0f0f0f]">
            <TableHead className="text-[#ff66c4] first:rounded-tl-2xl">
              Hostname
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
                className={index === devices.length - 1 ? "rounded-bl-2xl" : ""}
              >
                {device.hostname}
              </TableCell>

              <TableCell>{device.ip}</TableCell>

              <TableCell
                className={index === devices.length - 1 ? "rounded-br-2xl" : ""}
              >
                <div className="flex gap-5">
                  <button onClick={() => openWindow({ label: "processor" })}>
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
  );
}
