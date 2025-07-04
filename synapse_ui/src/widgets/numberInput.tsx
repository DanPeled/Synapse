import React, { useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import { baseCardColor, teamColor } from "@/services/style";

interface NumberInputProps {
  min?: number;
  max?: number;
  step?: number;
  value: number;
  label?: string;
  labelGap?: string;
  className?: string;
  onChange?: (value: number) => void;
}

export function NumberInput({
  min = 0,
  max = 100,
  step = 1,
  value,
  label = "",
  labelGap = "0px",
  className = "",
  onChange,
}: NumberInputProps) {
  const [internalValue, setInternalValue] = useState<number | "">(value);

  useEffect(() => {
    if (internalValue !== value) {
      setInternalValue(value);
    }
  }, [value]);

  const clampValue = (val: number) => Math.min(max, Math.max(min, val));

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    if (val === "") {
      setInternalValue("");
      return;
    }
    const num = Number(val);
    if (!isNaN(num)) {
      const clamped = clampValue(num);
      setInternalValue(clamped);
      onChange?.(clamped);
    }
  };

  const handleInputBlur = () => {
    if (internalValue === "" || isNaN(Number(internalValue))) {
      setInternalValue(min);
      onChange?.(min);
    }
  };

  return (
    <div
      className={cn(
        "w-[97%] p-4 rounded-2xl shadow-md flex items-center gap-4",
        "text-[rgba(255,255,255,0.85)]",
        className,
      )}
      style={{ backgroundColor: baseCardColor, color: teamColor }}
    >
      <label
        className="font-semibold text-base min-w-[80px]"
        style={{ marginRight: labelGap, color: teamColor }}
      >
        {label}
      </label>

      <input
        type="number"
        value={internalValue}
        min={min}
        max={max}
        step={step}
        onChange={handleInputChange}
        onBlur={handleInputBlur}
        className="w-20 px-2 py-1 rounded-lg font-semibold text-base text-center bg-[rgba(255,255,255,0.08)] border border-[rgba(255,255,255,0.2)] focus:outline-none focus:border-current"
        style={{ color: teamColor }}
      />
    </div>
  );
}
