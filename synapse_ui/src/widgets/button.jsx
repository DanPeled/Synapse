import { TriangleAlert } from "lucide-react";
import React, { useState } from "react";
import { iconSize } from "../services/style";
import AlertDialog from "./alert";

export function Button({
  children,
  onClick,
  disabled = false,
  style,
  enabledColors = {
    background: "#2A2D34", // dark gray-blue
    color: "#E0E3E7", // light gray
    border: "#3F4451", // slightly lighter border
    hoverBackground: "#3B4050", // a bit lighter and bluish on hover
    hoverBorder: "#5A6074", // lighter blue-gray border on hover
  },
  disabledColors = {
    background: "#4B5060", // muted gray-blue
    color: "#8A8F9C", // muted light gray
    border: "#5A6074", // same as hover border but dimmer
  },
}) {
  const [isPressed, setIsPressed] = useState(false);

  const handlePressStart = () => {
    if (!disabled) setIsPressed(true);
  };

  const handlePressEnd = () => {
    if (!disabled) setIsPressed(false);
  };

  return (
    <button
      onClick={disabled ? undefined : onClick}
      disabled={disabled}
      onMouseDown={handlePressStart}
      onMouseUp={handlePressEnd}
      onTouchStart={handlePressStart}
      onTouchEnd={handlePressEnd}
      style={{
        padding: "12px 24px",
        backgroundColor: disabled
          ? disabledColors.background
          : enabledColors.background,
        color: disabled ? disabledColors.color : enabledColors.color,
        border: `2px solid ${disabled ? disabledColors.border : enabledColors.border
          }`,
        borderRadius: "8px",
        cursor: disabled ? "not-allowed" : "pointer",
        fontSize: "16px",
        fontWeight: "600",
        transition: "all 0.1s ease",
        boxShadow: isPressed
          ? "0 1px 3px rgba(0,0,0,0.7) inset"
          : "0 2px 6px rgba(0,0,0,0.5)",
        transform: isPressed ? "scale(0.95)" : "scale(1)",
        ...style,
      }}
      onMouseEnter={(e) => {
        if (!disabled && !isPressed) {
          e.currentTarget.style.backgroundColor = enabledColors.hoverBackground;
          e.currentTarget.style.borderColor = enabledColors.hoverBorder;
        }
      }}
      onMouseLeave={(e) => {
        if (!disabled && !isPressed) {
          e.currentTarget.style.backgroundColor = enabledColors.background;
          e.currentTarget.style.borderColor = enabledColors.border;
        }
        handlePressEnd();
      }}
      onBlur={(e) => {
        e.currentTarget.style.outline = "none";
      }}
    >
      {children}
    </button>
  );
}

function ConfirmDialog({ message, onConfirm, onCancel, visible }) {
  return (
    <AlertDialog visible={visible} onClose={onCancel}>
      <p style={{ marginBottom: 20 }}>{message}</p>
      <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
        <button
          style={{
            backgroundColor: "#ccc",
            color: "#333",
            border: "none",
            padding: "8px 16px",
            borderRadius: 4,
            cursor: "pointer",
          }}
          onClick={onCancel}
        >
          Cancel
        </button>
        <button
          style={{
            backgroundColor: "#b22222",
            color: "#fff",
            border: "none",
            padding: "8px 16px",
            borderRadius: 4,
            cursor: "pointer",
            fontWeight: "bold",
          }}
          onClick={onConfirm}
        >
          Confirm
        </button>
      </div>
    </AlertDialog>
  );
}

// DangerButton with confirmation dialog
export function DangerButton({
  enabledColors = {
    background: "#b22222",
    color: "#fff",
    border: "#800000",
    hoverBackground: "#800000",
    hoverBorder: "#b22222",
  },
  disabledColors = {
    background: "#a0522d",
    color: "#ccc",
    border: "#5c2a0e",
  },
  warning = "",
  onClick = () => { },
  ...props
}) {
  const [showConfirm, setShowConfirm] = useState(false);

  const handleClick = () => {
    setShowConfirm(true);
  };

  const handleConfirm = () => {
    setShowConfirm(false);
    if (onClick) onClick();
  };

  const handleCancel = () => {
    setShowConfirm(false);
  };

  return (
    <>
      <Button
        enabledColors={enabledColors}
        disabledColors={disabledColors}
        onClick={handleClick}
        {...props}
      />
      {showConfirm && (
        <ConfirmDialog
          message={
            <p style={{ textAlign: "center" }}>
              Are you sure you want to proceed? <br />
              <span style={{ color: "yellow" }}>
                {" "}
                <TriangleAlert size={iconSize} /> {warning}
              </span>
            </p>
          }
          onConfirm={handleConfirm}
          onCancel={handleCancel}
          visible={true}
        />
      )}
    </>
  );
}
