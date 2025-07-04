import React, { useState, useRef, useEffect } from "react";
import { cn } from "@/lib/utils";
import { teamColor } from "../services/style";

type Option = {
  label: string;
  value: string | number;
  tooltip?: string;
};

interface OptionSelectorProps {
  label?: string;
  labelTooltip?: string;
  options: Option[];
  value: string | number;
  onChange?: (val: string | number) => void;
  disabled?: boolean;
}

export default function OptionSelector({
  label = "IP Mode",
  options,
  value,
  onChange = () => {},
  disabled = false,
}: OptionSelectorProps) {
  const [hoveredOption, setHoveredOption] = useState<string | number | null>(
    null,
  );
  const [tooltipPos, setTooltipPos] = useState({
    top: 0,
    left: 0,
    visible: false,
  });

  const buttonRefs = useRef<Record<string | number, HTMLDivElement | null>>({});
  const tooltipRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!hoveredOption || !tooltipRef.current) {
      setTooltipPos((pos) => ({ ...pos, visible: false }));
      return;
    }

    const button = buttonRefs.current[hoveredOption];
    const tooltip = tooltipRef.current;
    if (!button) return;

    const btnRect = button.getBoundingClientRect();
    const tooltipHeight = tooltip.offsetHeight;

    const fitsBelow = window.innerHeight > btnRect.bottom + tooltipHeight + 8;
    const top = fitsBelow
      ? btnRect.bottom + 4
      : btnRect.top - tooltipHeight - 4;
    const left = btnRect.left;

    setTooltipPos({
      top: Math.max(0, top),
      left: Math.max(0, left),
      visible: true,
    });
  }, [hoveredOption]);

  return (
    <div
      className={cn(
        "mb-3 flex items-center",
        disabled ? "opacity-50 pointer-events-none select-none" : "",
      )}
    >
      <span>{label}</span>
      <div className="flex gap-2">
        {options.map((opt) => {
          const isSelected = value === opt.value;
          return (
            <div
              key={opt.value}
              className="relative"
              ref={(el) => {
                buttonRefs.current[opt.value] = el;
              }}
              onMouseEnter={() => !disabled && setHoveredOption(opt.value)}
              onMouseLeave={() => !disabled && setHoveredOption(null)}
            >
              <button
                onClick={() => onChange(opt.value)}
                disabled={disabled}
                className={cn(
                  "px-3 py-1.5 rounded border font-bold text-base transition-all select-none",
                  isSelected ? "bg-neutral-800" : "bg-transparent",
                  "border-teal-500",
                  disabled ? "cursor-not-allowed" : "cursor-pointer",
                )}
                style={{ color: teamColor }}
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
          <div
            ref={tooltipRef}
            className="fixed z-[1000] whitespace-nowrap rounded bg-black/85 text-white text-sm px-2.5 py-1.5 max-w-[300px]"
            style={{ top: tooltipPos.top, left: tooltipPos.left }}
          >
            {options.find((o) => o.value === hoveredOption)?.tooltip}
          </div>
        )}
    </div>
  );
}
