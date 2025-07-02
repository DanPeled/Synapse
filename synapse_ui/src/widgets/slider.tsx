import React, { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { baseCardColor, teamColor } from "@/services/style";

interface SliderProps {
  min?: number;
  max?: number;
  step?: number;
  value: number;
  label?: string;
  labelGap?: string;
  className?: string;
  onChange?: (value: number) => void;
}

export function Slider({
  min = 0,
  max = 100,
  step = 1,
  value,
  label = "Value",
  labelGap = "0px",
  className = "",
  onChange,
}: SliderProps) {
  const [internalValue, setInternalValue] = useState<number | "">(value);

  useEffect(() => {
    if (internalValue !== value) {
      setInternalValue(value);
    }
  }, [value]);

  const clampValue = (val: number) => Math.min(max, Math.max(min, val));
  const valuePercent =
    (((typeof internalValue === "number" ? internalValue : min) - min) /
      (max - min)) *
    100;

  const handleSliderChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = clampValue(Number(e.target.value));
    setInternalValue(val);
    onChange?.(val);
  };

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

  const increment = () => {
    const clamped = clampValue(Number(value) + step);
    setInternalValue(clamped);
    onChange?.(clamped);
  };

  const decrement = () => {
    const clamped = clampValue(Number(value) - step);
    setInternalValue(clamped);
    onChange?.(clamped);
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

      <div className="flex items-center gap-3 flex-grow">
        <Button
          variant="outline"
          size="sm"
          onClick={decrement}
          disabled={typeof internalValue === "number" && internalValue <= min}
          className="w-8 h-8 rounded-full font-bold text-lg grid place-items-center"
          style={{
            borderColor: "rgba(255,255,255,0.2)",
            backgroundColor: "rgba(255,255,255,0.1)",
            color: teamColor,
          }}
        >
          &minus;
        </Button>

        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={internalValue === "" ? min : internalValue}
          onChange={handleSliderChange}
          className="flex-grow h-1 rounded-md cursor-pointer appearance-none"
          style={{
            background: `linear-gradient(to right, ${teamColor} 0%, ${teamColor} ${valuePercent}%, rgba(255,255,255,0.2) ${valuePercent}%, rgba(255,255,255,0.2) 100%)`,
            outline: "none",
          }}
        />

        <Button
          variant="outline"
          size="sm"
          onClick={increment}
          disabled={typeof internalValue === "number" && internalValue >= max}
          className="w-8 h-8 rounded-full font-bold text-lg grid place-items-center"
          style={{
            borderColor: "rgba(255,255,255,0.2)",
            backgroundColor: "rgba(255,255,255,0.1)",
            color: teamColor,
          }}
        >
          +
        </Button>

        <input
          type="number"
          value={internalValue}
          min={min}
          max={max}
          step={step}
          onChange={handleInputChange}
          onBlur={handleInputBlur}
          className="w-15 px-2 py-1 rounded-lg font-semibold text-base text-center bg-[rgba(255,255,255,0.08)] border border-[rgba(255,255,255,0.2)] focus:outline-none focus:border-current"
          style={{ color: teamColor }}
        />
      </div>
    </div>
  );
}
