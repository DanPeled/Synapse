import React from "react";
import {
  Bot,
  BotOff,
  Camera,
  LayoutDashboard,
  Server,
  ServerOff,
  Settings,
} from "lucide-react";
import "./Sidebar.css";
import PropTypes from "prop-types";
import { useBackendContext } from "../services/backend/backendContext";
import { getDivColor, teamColor } from "../services/style";
import { Link } from "react-router-dom";

const icons = [
  { icon: <LayoutDashboard />, label: "Dashboard", url: "/dashboard" },
  { icon: <Camera />, label: "Camera", url: "/camera" },
  { icon: <Settings />, label: "Settings", url: "/settings" },
];

function NavigationIcon({ icon, label, url }) {
  return (
    <div style={{ margin: "10px 0" }}>
      <Link
        to={url}
        className="icon-wrapper-nav"
        style={{ color: teamColor }}
      >
        {icon}
      </Link>
      <span className="tooltip" style={{ zIndex: 999 }}>
        {label}
      </span>
    </div>
  );
}

NavigationIcon.propTypes = {
  icon: PropTypes.element,
  label: PropTypes.string,
  url: PropTypes.string,
};

export default function Sidebar() {
  const { connection } = useBackendContext();

  return (
    <div className="sidebar" style={{ backgroundColor: getDivColor() }}>
      {icons.map(({ icon, label, url }, i) => (
        <NavigationIcon key={i} icon={icon} label={label} url={url} />
      ))}

      <div className="network-group">
        <div
          className="icon-wrapper-nav network-icon-wrapper "
          style={{ color: teamColor }}
        >
          {connection.networktables ? <Bot /> : <BotOff />}
          <span className="tooltip">
            {connection.networktables
              ? "NetworkTables Connected"
              : "NetworkTables Disconnected"}
          </span>
        </div>
        <div
          className="icon-wrapper-nav backend-icon-wrapper"
          style={{ color: teamColor }}
        >
          {connection.backend ? <Server /> : <ServerOff />}
          <span className="tooltip">
            {connection.backend ? "Backend Connected" : "Backend Disconnected"}
          </span>
        </div>
      </div>
    </div>
  );
}
