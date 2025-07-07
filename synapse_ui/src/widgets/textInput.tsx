import React, { useState, useEffect, useId } from "react";
import { cn } from "@/lib/utils";
import { teamColor } from "../services/style";

interface TextInputProps {
  label?: string;
  value: string;
  onChange?: (value: string) => void;
  placeholder?: string;
  pattern?: string | RegExp;
  errorMessage?: string;
  allowedChars?: string | null | RegExp;
  disabled?: boolean;
  maxLength?: number | null;
  textColor?: string;
  labelColor?: string;
  textSize?: string;
  inputWidth?: string;
}

export default function TextInput({
  label = "",
  value,
  onChange,
  placeholder = "",
  pattern = "^.*$",
  allowedChars = null,
  disabled = false,
  maxLength = null,
  labelColor = teamColor,
  textSize = "text-base",
  inputWidth = "",
}: TextInputProps) {
  const [invalid, setInvalid] = useState(false);
  const id = useId();

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    let val = e.target.value;

    if (allowedChars) {
      const regex = new RegExp(allowedChars);
      val = [...val].filter((ch) => regex.test(ch)).join("");
    }

    if (maxLength !== null && val.length > maxLength) {
      val = val.slice(0, maxLength);
    }

    const patternRegex =
      pattern instanceof RegExp ? pattern : new RegExp(pattern);
    const isInvalid = val !== "" && !patternRegex.test(val);
    setInvalid(isInvalid);

    onChange?.(val);
  };

  useEffect(() => {
    const regex = pattern instanceof RegExp ? pattern : new RegExp(pattern);
    setInvalid(value !== "" && !regex.test(value));
  }, [value, pattern]);

  return (
    <div
      className={cn(disabled ? "opacity-50 pointer-events-none" : "", textSize)}
    >
      <div className="flex items-center gap-3 py-2 rounded-xl relative bg-[rgba(50, 50, 50, 1)]">
        <label
          htmlFor={id}
          className="min-w-0 text font-semibold"
          style={{ color: labelColor }}
        >
          {label}
        </label>
        <input
          id={id}
          type="text"
          value={value}
          onChange={handleChange}
          placeholder={placeholder}
          disabled={disabled}
          maxLength={maxLength ?? undefined}
          className={cn(
            "text-white rounded-md flex-1 py-2 px-2",
            invalid ? "text-red-400" : "",
            "focus:outline-none focus:ring-2 focus:ring-[rgba(0,0,0,0.15)] selection:bg-[rgba(0,0,200,0.5)] bg-zinc-800",
            textSize,
            inputWidth,
          )}
        />
      </div>
    </div>
  );
}
