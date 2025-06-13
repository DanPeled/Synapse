import React from "react";
import { teamColor } from "../services/style";

export default function ToggleButton({
  label = "Toggle",
  value = false,
  onToggle = () => { },
  disabled = false,
  labelGap = 12, // New configurable gap
}) {
  const containerStyle = {
    display: "flex",
    alignItems: "center",
    gap: labelGap,
    marginBottom: 12,
    paddingLeft: 30
  };

  const labelStyle = {
    fontWeight: "bold",
    color: teamColor,
    fontSize: 18,
    minWidth: 120,
  };

  const trackStyle = {
    width: 50,
    height: 28,
    borderRadius: 999,
    backgroundColor: value ? "#00bfa5" : "#444",
    position: "relative",
    cursor: disabled ? "not-allowed" : "pointer",
    transition: "background-color 0.2s",
    opacity: disabled ? 0.5 : 1,
  };

  const knobStyle = {
    position: "absolute",
    top: 3,
    left: value ? 26 : 3,
    width: 22,
    height: 22,
    borderRadius: "50%",
    backgroundColor: "white",
    transition: "left 0.2s",
  };

  return (
    <div style={containerStyle}>
      <label style={labelStyle}>{label}</label>
      <div
        style={trackStyle}
        onClick={() => {
          if (!disabled) onToggle(!value);
        }}
      >
        <div style={knobStyle}></div>
      </div>
    </div>
  );
}
