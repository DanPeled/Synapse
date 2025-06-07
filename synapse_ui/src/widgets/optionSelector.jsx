import React, { useState } from "react";
import Tooltip from "./tooltip";

export default function OptionSelector({
  label = "Choose an option",
  labelTooltip = "", // tooltip text for the label
  options = [], // Array of { label, value, tooltip? }
  value,
  onChange = () => {},
  disabled = false,
}) {
  const [hoveredOption, setHoveredOption] = useState(null);
  const [labelHovered, setLabelHovered] = useState(false);

  return (
    <div
      style={{
        marginBottom: 12,
        display: "flex",
        alignItems: "flex-start",
        opacity: disabled ? 0.5 : 1,
        pointerEvents: disabled ? "none" : "auto",
        userSelect: disabled ? "none" : "auto",
      }}
    >
      <div
        style={{ position: "relative", marginRight: 12 }}
        onMouseEnter={() => setLabelHovered(true)}
        onMouseLeave={() => setLabelHovered(false)}
      >
        <label
          style={{
            fontWeight: "bold",
            color: "white",
            fontSize: 18,
            minWidth: 120,
            pointerEvents: "none",
            userSelect: "none",
            cursor: labelTooltip ? "help" : "default",
          }}
        >
          {label}
        </label>
        {labelTooltip && labelHovered && (
          <Tooltip visible={true} style={{ top: "100%", left: "0" }}>
            {labelTooltip}
          </Tooltip>
        )}
      </div>

      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 8,
          marginLeft: 300,
          position: "relative",
        }}
      >
        {options.map((opt) => {
          const isSelected = value === opt.value;
          return (
            <div key={opt.value} style={{ position: "relative" }}>
              <button
                onClick={() => onChange(opt.value)}
                disabled={disabled}
                style={{
                  padding: "6px 12px",
                  borderRadius: 6,
                  border: "1px solid #00bfa5",
                  backgroundColor: isSelected ? "#00bfa5" : "transparent",
                  color: "white",
                  cursor: disabled ? "not-allowed" : "pointer",
                  transition: "all 0.2s",
                  fontSize: 16,
                  userSelect: "none",
                }}
                onMouseEnter={() => {
                  if (!disabled) setHoveredOption(opt.value);
                }}
                onMouseLeave={() => {
                  if (!disabled) setHoveredOption(null);
                }}
              >
                {opt.label}
              </button>
              {opt.tooltip && hoveredOption === opt.value && (
                <Tooltip visible={true}>{opt.tooltip}</Tooltip>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
