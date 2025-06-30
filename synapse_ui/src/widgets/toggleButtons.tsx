"use client";

import React from "react";
import { cn } from "@/lib/utils";
import { teamColor } from "../services/style";

export default function ToggleButton({
  label = "Toggle",
  value = false,
  onToggleAction,
  disabled = false,
  labelGap = 3,
  tooltip,
}: {
  label?: string;
  value?: boolean;
  onToggleAction?: (val: boolean) => void;
  disabled?: boolean;
  labelGap?: number;
  tooltip?: string;
}) {
  return (
    <div className={cn("flex items-center mb-3 pl-4", `gap-${labelGap}`)}>
      <label
        className="relative group font-bold min-w-[120px]"
        style={{ color: teamColor }}
      >
        {label}
        {tooltip && (
          <div className="absolute left-1/2 -translate-x-1/2 bottom-full mb-1 w-max px-2 py-1 text-xs bg-gray-800 rounded opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10 font-normal">
            {tooltip}
          </div>
        )}
      </label>

      <div
        className={cn(
          "relative w-[50px] h-[28px] rounded-full transition-colors cursor-pointer",
          value ? "bg-teal-500" : "bg-gray-700",
          disabled && "opacity-50 cursor-not-allowed",
        )}
        onClick={() => {
          if (!disabled) onToggleAction?.(!value);
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
