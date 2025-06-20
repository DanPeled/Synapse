import React, { useState, useEffect, useId } from "react";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { teamColor } from "../services/style";

interface TextInputProps {
  label?: string;
  initialValue?: string;
  onChange?: (value: string) => void;
  placeholder?: string;
  pattern?: string | RegExp;
  errorMessage?: string;
  allowedChars?: string | null;
  disabled?: boolean;
  maxLength?: number | null;
  textColor?: string;
}

export default function TextInput({
  label = "Input",
  initialValue = "",
  onChange,
  placeholder = "",
  pattern = "^.*$",
  allowedChars = null,
  disabled = false,
  maxLength = null,
  textColor = teamColor,
}: TextInputProps) {
  const [value, setValue] = useState(initialValue);
  const [invalid, setInvalid] = useState(false);

  const id = useId();

  useEffect(() => {
    setValue(initialValue);
  }, [initialValue]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    let val = e.target.value;

    if (allowedChars) {
      const regex = new RegExp(allowedChars);
      val = [...val].filter((ch) => regex.test(ch)).join("");
    }

    if (maxLength !== null && val.length > maxLength) {
      val = val.slice(0, maxLength);
    }

    setValue(val);

    const patternRegex =
      pattern instanceof RegExp ? pattern : new RegExp(pattern);
    const isInvalid = val !== "" && !patternRegex.test(val);
    setInvalid(isInvalid);

    if (!isInvalid) {
      onChange?.(val);
    }
  };

  useEffect(() => {
    const regex = pattern instanceof RegExp ? pattern : new RegExp(pattern);
    setInvalid(value !== "" && !regex.test(value));
  }, [value, pattern]);

  return (
    <div
      className={cn(
        "flex flex-col",
        disabled ? "opacity-50 pointer-events-none" : "",
      )}
    >
      <div className="flex items-center gap-3 px-4 py-2 rounded-xl relative bg-[rgba(50, 50, 50, 1)]">
        <label
          htmlFor={id}
          className="min-w-0 text font-semibold"
          style={{ color: textColor }}
        >
          {label}
        </label>
        <Input
          id={id}
          type="text"
          value={disabled ? initialValue : value}
          onChange={handleChange}
          placeholder={placeholder}
          disabled={disabled}
          maxLength={maxLength ?? undefined}
          className={cn(
            "bg-[rgb(30,30,30)] text-white rounded-md text-base flex-1",
            invalid ? "text-red-400" : "",
            "focus:outline-none focus:ring-2 focus:ring-[rgba(0,0,0,0.15)] border-none selection:bg-[rgba(0,0,200,0.5)]",
          )}
        />
      </div>
    </div>
  );
}
