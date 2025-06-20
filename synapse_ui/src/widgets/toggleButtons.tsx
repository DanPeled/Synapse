"use client";

import React from "react";
import { cn } from "@/lib/utils";
import { teamColor } from "../services/style";

export default function ToggleButton({
  label = "Toggle",
  value = false,
  onToggleAction = () => {},
  disabled = false,
  labelGap = 3, // Tailwind spacing scale (12px ≈ gap-3)
}: {
  label?: string;
  value?: boolean;
  onToggleAction?: (val: boolean) => void;
  disabled?: boolean;
  labelGap?: number;
}) {
  return (
    <div className={cn("flex items-center mb-3 pl-4", `gap-${labelGap}`)}>
      <label className="font-bold min-w-[120px]" style={{ color: teamColor }}>
        {label}
      </label>
      <div
        className={cn(
          "relative w-[50px] h-[28px] rounded-full transition-colors cursor-pointer",
          value ? "bg-teal-500" : "bg-gray-700",
          disabled && "opacity-50 cursor-not-allowed",
        )}
        onClick={() => {
          if (!disabled) onToggleAction(!value);
        }}
      >
        <div
          className={cn(
            "absolute top-[3px] w-[22px] h-[22px] bg-white rounded-full transition-all",
            value ? "left-[26px]" : "left-[3px]",
          )}
        />
      </div>
    </div>
  );
}
