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

type Device = {
  hostname: string;
  address: string;
};

const devices: Device[] = [
  {
    hostname: "limelight",
    address: "10.44.81.11",
  },
  {
    hostname: "coprocessor",
    address: "localhost",
  },
];

export default function DeviceTable() {
  return (
    <div className="ml-5 mt-5 overflow-hidden rounded-2xl bg-[#1f1f1f] shadow-sm">
      <Table className="overflow-hidden rounded-2xl">
        <TableHeader>
          <TableRow className="bg-[#0f0f0f] text-xl hover:bg-[#0f0f0f]">
            <TableHead className="text-[#ff66c4] first:rounded-tl-2xl">
              Hostname
            </TableHead>

            <TableHead className="text-[#ff66c4] last:rounded-tr-2xl">
              Address
            </TableHead>
            <TableHead className="text-[#ff66c4] last:rounded-tr-2xl"></TableHead>
          </TableRow>
        </TableHeader>

        <TableBody>
          {devices.map((device, index) => (
            <TableRow
              key={device.address}
              className="
                text-xl text-[#ff66c4]
                transition-colors
                hover:bg-[#2b2a2a]
                border-none
              "
            >
              <TableCell
                className={index === devices.length - 1 ? "rounded-bl-2xl" : ""}
              >
                {device.hostname}
              </TableCell>

              <TableCell
                className={index === devices.length - 1 ? "rounded-br-2xl" : ""}
              >
                {device.address}
              </TableCell>
              <TableCell
                className={index === devices.length - 1 ? "rounded-br-2xl" : ""}
              >
                <div className="row gap-5">
                  {" "}
                  <button
                    onClick={() => {
                      openWindow({ label: "processor" });
                    }}
                  >
                    <Info />
                  </button>
                  <button>
                    <Upload />
                  </button>
                  <button
                    onClick={() => {
                      openWindow({
                        label: `SynapseDashboard${device.hostname}`,
                        url: `http://${device.address}:3000`,
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
