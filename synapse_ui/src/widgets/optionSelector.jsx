import React, { useState, useRef, useEffect } from "react";
import Tooltip from "./tooltip";
import { teamColor } from "../services/style";

export default function OptionSelector({
  label = "IP Mode",
  labelTooltip = "",
  options = [],
  value,
  onChange = () => {},
  disabled = false,
}) {
  const [hoveredOption, setHoveredOption] = useState(null);
  const [labelHovered, setLabelHovered] = useState(false);
  const [tooltipPos, setTooltipPos] = useState({
    top: 0,
    left: 0,
    visible: false,
  });

  const buttonRefs = useRef({});
  const tooltipRef = useRef(null);

  useEffect(() => {
    if (!hoveredOption || !tooltipRef.current) {
      setTooltipPos((pos) => ({ ...pos, visible: false }));
      return;
    }

    const button = buttonRefs.current[hoveredOption];
    const tooltip = tooltipRef.current;
    if (!button) return;

    const btnRect = button.getBoundingClientRect();
    const tooltipWidth = tooltip.offsetWidth;
    const tooltipHeight = tooltip.offsetHeight;

    const fitsBelow = window.innerHeight > btnRect.bottom + tooltipHeight + 8;
    const fitsRight = window.innerWidth > btnRect.right + tooltipWidth + 8;

    const top = fitsBelow
      ? btnRect.bottom + 4
      : btnRect.top - tooltipHeight - 4;
    const left = fitsBelow ? btnRect.left : btnRect.right + 4;

    setTooltipPos({
      top: Math.max(0, top),
      left: Math.max(0, left),
      visible: true,
    });
  }, [hoveredOption]);

  return (
    <div
      style={{
        marginBottom: 12,
        display: "flex",
        alignItems: "center",
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

      <div style={{ display: "flex", gap: 8 }}>
        {options.map((opt) => {
          const isSelected = value === opt.value;
          return (
            <div
              key={opt.value}
              style={{ position: "relative" }}
              ref={(el) => (buttonRefs.current[opt.value] = el)}
              onMouseEnter={() => {
                if (!disabled) setHoveredOption(opt.value);
              }}
              onMouseLeave={() => {
                if (!disabled) setHoveredOption(null);
              }}
            >
              <button
                onClick={() => onChange(opt.value)}
                disabled={disabled}
                style={{
                  padding: "6px 12px",
                  borderRadius: 6,
                  border: "1px solid #00bfa5",
                  backgroundColor: isSelected
                    ? "rgb(50, 50, 50)"
                    : "transparent",
                  color: teamColor,
                  fontWeight: "bold",
                  cursor: disabled ? "not-allowed" : "pointer",
                  transition: "all 0.2s",
                  fontSize: 16,
                  userSelect: "none",
                }}
              >
                {opt.label}
              </button>
            </div>
          );
        })}
      </div>

      {tooltipPos.visible &&
        hoveredOption &&
        options.find((o) => o.value === hoveredOption)?.tooltip && (
          <Tooltip
            ref={tooltipRef}
            visible={true}
            style={{
              position: "fixed",
              top: tooltipPos.top,
              left: tooltipPos.left,
              zIndex: 1000,
              whiteSpace: "nowrap",
              backgroundColor: "rgba(0,0,0,0.85)",
              color: "white",
              padding: "6px 10px",
              borderRadius: 6,
              fontSize: 14,
              maxWidth: 300,
            }}
          >
            {options.find((o) => o.value === hoveredOption)?.tooltip}
          </Tooltip>
        )}
    </div>
  );
}
