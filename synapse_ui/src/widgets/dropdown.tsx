import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import { teamColor } from "@/services/style";

export interface DropdownOption<T> {
  value: T;
  label: string;
}

interface DropdownProps<T> {
  label: string;
  value: T;
  onValueChange: (value: T) => void;
  options: DropdownOption<T>[];
  disabled?: boolean;
}

export function Dropdown<T>({
  label,
  value,
  onValueChange,
  options,
  disabled = false,
}: DropdownProps<T>) {
  const stringToValue = new Map<string, T>();
  const valueToString = new Map<T, string>();

  options.forEach((opt, idx) => {
    const str = String(idx); // simple unique string ID
    stringToValue.set(str, opt.value);
    valueToString.set(opt.value, str);
  });

  const selectedKey = valueToString.get(value);

  return (
    <div
      className="flex items-center gap-3 px-3 py-2 relative transition-colors w-full"
      style={{
        color: teamColor,
        fontFamily: '"Inter", "Segoe UI", Tahoma, Geneva, Verdana, sans-serif',
        fontWeight: 500,
        opacity: disabled ? 0.5 : 1,
      }}
    >
      <label
        className="min-w-[80px] text font-bold whitespace-nowrap"
        style={{ color: teamColor }}
      >
        {label}
      </label>
      <div className="flex-1 relative">
        <Select
          value={selectedKey}
          onValueChange={(strVal) => {
            const newVal = stringToValue.get(strVal);
            if (newVal !== undefined) onValueChange(newVal);
          }}
          disabled={disabled}
        >
          <SelectTrigger className="w-full border rounded-[10px] text-left px-4 py-2 transition-all select-none"
            style={{
              backgroundColor: "rgb(20, 20, 20)",
              borderColor: "#3a3a3a",
              color: teamColor,
              cursor: disabled ? "not-allowed" : "pointer",
            }}>
            <SelectValue className="select-none" />
          </SelectTrigger>
          <SelectContent className="rounded-[10px] shadow-lg max-h-[220px] overflow-y-auto"
            style={{ backgroundColor: "#2b2b2b", borderColor: "#444", zIndex: 9999 }}>
            {options.map((opt, idx) => {
              const strKey = String(idx);
              return (
                <SelectItem
                  key={strKey}
                  value={strKey}
                  className="px-4 py-2 transition-colors font-normal cursor-pointer"
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
          </SelectContent>
        </Select>
      </div>
    </div>
  );
}
