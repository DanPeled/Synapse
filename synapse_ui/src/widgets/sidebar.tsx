"use client";

import { useBackendContext } from "@/services/backend/backendContext";
import { baseCardColor, teamColor } from "@/services/style";
import {
  Camera,
  LayoutDashboard,
  Settings,
  BotOff,
  ServerOff,
  Bot,
  Server,
} from "lucide-react";
import Link from "next/link";

export function Sidebar({ compact }: { compact: boolean }) {
  const { connection } = useBackendContext();

  return (
    <div
      className={`fixed top-0 left-0 h-screen transition-all duration-300 text-white flex flex-col justify-between ${compact ? "w-15" : "w-64"} z-50`}
      style={{ backgroundColor: baseCardColor, color: teamColor }}
    >
      {/* Top icons */}
      <div className="p-4">
        <ul className={`space-y-6 text-[${teamColor}]`}>
          {[
            { Icon: LayoutDashboard, label: "Dashboard", link: "/dashboard" },
            { Icon: Camera, label: "Camera", link: "/camera" },
            { Icon: Settings, label: "Settings", link: "/settings" },
          ].map(({ Icon, label, link }) => (
            <li
              key={label}
              className="relative group flex items-center justify-center cursor-pointer"
            >
              <Link href={link}>
                <Icon fontSize={18} />
              </Link>
              {/* Tooltip */}
              <span className="absolute left-full top-1/2 -translate-y-1/2 ml-2 w-max rounded bg-gray-800 px-2 py-1 text-sm text-center opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none select-none whitespace-nowrap z-10">
                {label}
              </span>
            </li>
          ))}
        </ul>
      </div>

      {/* Bottom icons */}
      <div className="p-4">
        <ul className={`space-y-6 text-[${teamColor}]`}>
          {[
            {
              Icon: connection.networktables ? Bot : BotOff,
              label:
                "NetworkTables " +
                (connection.networktables ? "Connected" : "Disconnected"),
            },
            {
              Icon: connection.backend ? Server : ServerOff,
              label:
                "Backend " +
                (connection.backend ? "Connected" : "Disconnected"),
            },
          ].map(({ Icon, label }) => (
            <li
              key={label}
              className="relative group flex items-center justify-center"
            >
              <Icon fontSize={18} />
              {/* Tooltip */}
              <span className="absolute left-full top-1/2 -translate-y-1/2 ml-2 w-max rounded bg-gray-800 px-2 py-1 text-sm text-center opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none select-none whitespace-nowrap z-10">
                {label}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
