import React from "react";
import {
  BotOff,
  Camera,
  LayoutDashboard,
  ServerOff,
  Settings,
} from "lucide-react";
import "./Sidebar.css";
import PropTypes from "prop-types";

const icons = [
  { icon: <LayoutDashboard />, label: "Dashboard", url: "dashboard" },
  { icon: <Camera />, label: "Camera", url: "camera" },
  { icon: <Settings />, label: "Settings", url: "settings" },
];

function NavigationIcon(key, icon, label, url) {
  return (
    <div key={key} style={{ margin: "10px 0" }}>
      <a href={`#/${url}`} className="icon-wrapper-nav">
        {icon}{" "}
      </a>
      <span className="tooltip" style={{ zIndex: 999 }}>
        {label}
      </span>
    </div>
  );
}

NavigationIcon.propTypes = {
  key: PropTypes.string,
  icon: PropTypes.element,
  label: PropTypes.string,
  url: PropTypes.string
}

export default function Sidebar() {
  return (
    <div className="sidebar">
      {icons.map(({ icon, label, url }, i) => (
        <div key={i} className="icon-wrapper-nav">
          {NavigationIcon(i, icon, label, url)}
        </div>
      ))}

      <div className="network-group">
        <div className="icon-wrapper-nav network-icon-wrapper ">
          <BotOff />
          <span className="tooltip">NetworkTables Disconnected</span>
        </div>
        <div className="icon-wrapper-nav backend-icon-wrapper">
          <ServerOff />
          <span className="tooltip">Backend Disconnected</span>
        </div>
      </div>
    </div>
  );
}
