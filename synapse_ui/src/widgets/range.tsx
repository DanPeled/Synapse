import React, { useEffect, useState } from "react";
import { Slider as UISlider } from "@/components/ui/slider";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { baseCardColor, teamColor } from "@/services/style";

interface RangeSliderProps {
  min?: number;
  max?: number;
  step?: number;
  value: [number, number];
  label?: string;
  labelGap?: string;
  className?: string;
  onChange?: (value: [number, number]) => void;
  disabled?: boolean;
}

export function RangeSlider({
  min = 0,
  max = 100,
  step = 1,
  value,
  label = "",
  labelGap = "0px",
  className = "",
  onChange,
  disabled = false,
}: RangeSliderProps) {
  const [internalValue, setInternalValue] = useState<[number, number]>(value);

  useEffect(() => {
    setInternalValue(value);
  }, [value]);

  const clamp = (v: number) => Math.min(max, Math.max(min, v));

  const update = (next: [number, number]) => {
    setInternalValue(next);
    onChange?.(next);
  };

  return (
    <div
      className={cn(
        "w-[97%] p-4 rounded-2xl flex items-center gap-4",
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
          disabled={disabled || internalValue[0] <= min}
          onClick={() =>
            update([clamp(internalValue[0] - step), internalValue[1]])
          }
          className="w-8 h-8 rounded-full font-bold text-lg grid place-items-center cursor-pointer hover:bg-stone-900 bg-zinc-800"
          style={{
            borderColor: "rgba(255,255,255,0.2)",
            color: teamColor,
          }}
        >
          <span className="select-none">&minus;</span>
        </Button>

        <p className="italic">{min}</p>

        <UISlider
          value={internalValue}
          min={min}
          max={max}
          step={step}
          disabled={disabled}
          onValueChange={(v) => update(v as [number, number])}
          className="flex-grow"
        />

        <p className="italic">{max}</p>

        <Button
          variant="outline"
          size="sm"
          disabled={disabled || internalValue[1] >= max}
          onClick={() =>
            update([internalValue[0], clamp(internalValue[1] + step)])
          }
          className="w-8 h-8 rounded-full font-bold text-lg grid place-items-center cursor-pointer hover:bg-stone-900 bg-zinc-800"
          style={{
            borderColor: "rgba(255,255,255,0.2)",
            color: teamColor,
          }}
        >
          <span className="select-none">+</span>
        </Button>

        <div className="flex gap-1">
          <input
            type="number"
            value={internalValue[0]}
            min={min}
            max={internalValue[1]}
            step={step}
            disabled={disabled}
            onChange={(e) => {
              const left = clamp(Number(e.target.value));
              update([Math.min(left, internalValue[1]), internalValue[1]]);
            }}
            className="w-15 px-2 py-1 rounded-lg font-semibold text-base text-center border focus:outline-none focus:border-current bg-[rgba(255,255,255,0.08)] border-[rgba(255,255,255,0.2)]"
            style={!disabled ? { color: teamColor } : {}}
          />

          <span className="self-center">-</span>

          <input
            type="number"
            value={internalValue[1]}
            min={internalValue[0]}
            max={max}
            step={step}
            disabled={disabled}
            onChange={(e) => {
              const right = clamp(Number(e.target.value));
              update([internalValue[0], Math.max(right, internalValue[0])]);
            }}
            className="w-15 px-2 py-1 rounded-lg font-semibold text-base text-center border focus:outline-none focus:border-current bg-[rgba(255,255,255,0.08)] border-[rgba(255,255,255,0.2)]"
            style={!disabled ? { color: teamColor } : {}}
          />
        </div>
      </div>
    </div>
  );
}
