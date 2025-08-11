import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";
import { teamColor } from "@/services/style";
import { SelectGroup } from "@radix-ui/react-select";
import React from "react";

export interface DropdownOption<T> {
  value: T;
  label: React.ReactNode;
}

interface DropdownProps<T> {
  label: string;
  value: T;
  onValueChange: (value: T) => void;
  options: DropdownOption<T>[];
  disabled?: boolean;
  textSize?: string;
}

export function Dropdown<T>({
  label,
  value,
  onValueChange,
  options,
  disabled = false,
  textSize = "text-base",
}: DropdownProps<T>) {
  const stringToValue = new Map<string, T>();
  const valueToString = new Map<T, string>();

  options.forEach((opt, idx) => {
    const str = String(idx); // simple unique string ID
    stringToValue.set(str, opt.value);
    valueToString.set(opt.value, str);
  });

  const selectedKey = valueToString.has(value) ? valueToString.get(value)! : "";

  return (
    <div
      className="flex items-center gap-3 relative transition-colors w-full"
      style={{
        color: teamColor,
        fontWeight: 500,
        opacity: disabled ? 0.5 : 1,
      }}
    >
      <label
        className={cn(
          "min-w-[80px] text font-bold whitespace-nowrap",
          textSize,
        )}
        style={{ color: teamColor }}
      >
        {label}
      </label>
      <div className="flex-1 relative">
        <Select
          value={selectedKey ?? ""}
          onValueChange={(strVal) => {
            const newVal = stringToValue.get(strVal);
            if (newVal !== undefined) onValueChange(newVal);
          }}
          disabled={disabled}
        >
          <SelectTrigger
            className={cn(
              "w-full border rounded-[10px] text-left px-4 py-2 transition-all select-none",
              textSize,
            )}
            style={{
              backgroundColor: "rgb(20, 20, 20)",
              borderColor: "#3a3a3a",
              color: teamColor,
              cursor: disabled ? "not-allowed" : "pointer",
            }}
          >
            <SelectValue className={cn("select-none", textSize)} />
          </SelectTrigger>
          <SelectContent
            className="rounded-[10px] shadow-lg max-h-[220px] overflow-y-auto text-gray-400"
            style={{
              backgroundColor: "#2b2b2b",
              borderColor: "#444",
              zIndex: 9999,
            }}
          >
            <SelectGroup>
              {options.map((opt, idx) => {
                const strKey = String(idx);
                return (
                  <SelectItem
                    key={strKey}
                    value={strKey}
                    className={cn(
                      "px-4 py-2 transition-colors cursor-pointer",
                      textSize,
                    )}
                    style={{
                      color: teamColor,
                      backgroundColor:
                        selectedKey === strKey ? "#333333" : "transparent",
                      fontWeight: selectedKey === strKey ? 600 : 400,
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.backgroundColor = "rgb(30, 30, 30)";
                    }}
                    onMouseLeave={(e) => {
                      if (selectedKey !== strKey) {
                        e.currentTarget.style.backgroundColor = "transparent";
                      }
                    }}
                  >
                    {opt.label}
                  </SelectItem>
                );
              })}
            </SelectGroup>
          </SelectContent>
        </Select>
      </div>
    </div>
  );
}
