"use client";

import { TriangleAlert } from "lucide-react";
import React, { useState } from "react";
import { iconSize, teamColor } from "../services/style";
import { AlertDialog } from "./alertDialog";

export function Button({
  children,
  onClickAction,
  disabled = false,
  className = "",
  enabledColors = {
    background: "#2A2D34",
    color: teamColor,
    border: "#3F4451",
    hoverBackground: "#3B4050",
    hoverBorder: "#5A6074",
  },
  disabledColors = {
    background: "#4B5060",
    color: "#8A8F9C",
    border: "#5A6074",
  },
}: {
  children: React.ReactNode;
  onClickAction?: () => void;
  disabled?: boolean;
  className?: string;
  enabledColors?: {
    background: string;
    color: string;
    border: string;
    hoverBackground: string;
    hoverBorder: string;
  };
  disabledColors?: {
    background: string;
    color: string;
    border: string;
  };
}) {
  const [isPressed, setIsPressed] = useState(false);

  return (
    <button
      onClick={disabled ? undefined : onClickAction}
      disabled={disabled}
      onMouseDown={() => !disabled && setIsPressed(true)}
      onMouseUp={() => !disabled && setIsPressed(false)}
      onTouchStart={() => !disabled && setIsPressed(true)}
      onTouchEnd={() => !disabled && setIsPressed(false)}
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
        setIsPressed(false);
      }}
      onBlur={(e) => {
        e.currentTarget.style.outline = "none";
      }}
      style={{
        padding: "12px 24px",
        backgroundColor: disabled
          ? disabledColors.background
          : enabledColors.background,
        color: disabled ? disabledColors.color : enabledColors.color,
        border: `2px solid ${disabled ? disabledColors.border : enabledColors.border}`,
        borderRadius: "0.5rem",
        cursor: disabled ? "not-allowed" : "pointer",
        fontSize: "16px",
        fontWeight: 600,
        transition: "all 0.1s ease",
        boxShadow: isPressed
          ? "inset 0 1px 3px rgba(0,0,0,0.7)"
          : "0 2px 6px rgba(0,0,0,0.5)",
        transform: isPressed ? "scale(0.95)" : "scale(1)",
      }}
      className={className}
    >
      {children}
    </button>
  );
}

function ConfirmDialog({
  message,
  onConfirm,
  onCancel,
  visible,
}: {
  message: React.ReactNode;
  onConfirm: () => void;
  onCancel: () => void;
  visible: boolean;
}) {
  return (
    <AlertDialog visible={visible} onClose={onCancel}>
      <div className="mb-5">{message}</div>
      <div className="flex justify-end gap-2">
        <button
          className="bg-gray-300 text-gray-800 px-4 py-2 rounded hover:bg-gray-400 transition cursor-pointer"
          onClick={onCancel}
        >
          Cancel
        </button>
        <button
          className="bg-red-700 text-white font-bold px-4 py-2 rounded hover:bg-red-800 transition cursor-pointer"
          onClick={onConfirm}
        >
          Confirm
        </button>
      </div>
    </AlertDialog>
  );
}

type ColorConfig = {
  background: string;
  color: string;
  border: string;
  hoverBackground: string;
  hoverBorder: string;
} | undefined;

export function DangerButton({
  enabledColors = {
    background: "#cc0c39",
    color: "white",
    border: "#cc0c39",
    hoverBackground: "#91102e",
    hoverBorder: "#b22222",
  },
  disabledColors = {
    background: "#a0522d",
    color: "#ccc",
    border: "#5c2a0e",
    hoverBackground: "#a0522d",
    hoverBorder: "#5c2a0e",
  },
  warning = "",
  onClickAction,
  children,
  className,
  ...props
}: {
  enabledColors?: ColorConfig;
  disabledColors?: ColorConfig;
  warning?: string;
  onClickAction?: () => void;
  className?: string;
  children: React.ReactNode;
}) {
  const [showConfirm, setShowConfirm] = useState(false);

  const handleClick = () => {
    setShowConfirm(true);
  };

  const handleConfirm = () => {
    setShowConfirm(false);
    onClickAction?.();
  };

  const handleCancel = () => {
    setShowConfirm(false);
  };

  return (
    <>
      <Button
        enabledColors={enabledColors}
        disabledColors={disabledColors}
        onClickAction={handleClick}
        className={className}
        {...props}
      >
        {children}
      </Button>
      {showConfirm && (
        <ConfirmDialog
          message={
            <div className="text-center">
              Are you sure you want to proceed?
              <br />
              <span className="text-yellow-400 flex justify-center items-center gap-1 mt-1">
                <TriangleAlert size={iconSize} />
                {warning}
              </span>
            </div>
          }
          onConfirm={handleConfirm}
          onCancel={handleCancel}
          visible={true}
        />
      )}
    </>
  );
}
