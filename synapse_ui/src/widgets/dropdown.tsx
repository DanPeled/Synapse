import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import { teamColor } from "@/services/style";

export interface DropdownOption {
  value: any;
  label: string;
}

interface DropdownProps {
  label: string;
  value: any;
  onValueChange: (value: any) => void;
  options: DropdownOption[];
  disabled?: boolean;
}

function hexToRgba(hex: string, alpha: number) {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

export function Dropdown({
  label,
  value,
  onValueChange,
  options,
  disabled = false,
}: DropdownProps) {
  const baseBg = "rgb(20, 20, 20)";
  const hoverBg = "rgb(30, 30, 30)";
  const selectedBg = "#333333";

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
        <Select value={value} onValueChange={onValueChange} disabled={disabled}>
          <SelectTrigger
            className="w-full border rounded-[10px] text-left px-4 py-2 transition-all select-none"
            style={{
              backgroundColor: baseBg,
              borderColor: "#3a3a3a",
              color: teamColor,
              cursor: disabled ? "not-allowed" : "pointer",
            }}
          >
            <SelectValue className="select-none" />
          </SelectTrigger>
          <SelectContent
            className="rounded-[10px] shadow-lg max-h-[220px] overflow-y-auto"
            style={{
              backgroundColor: "#2b2b2b",
              borderColor: "#444",
              zIndex: 9999,
            }}
          >
            {options.map((opt) => (
              <SelectItem
                key={opt.value}
                value={opt.value}
                className="px-4 py-2 transition-colors font-normal cursor-pointer"
                style={{
                  color: teamColor,
                  backgroundColor:
                    value === opt.value ? selectedBg : "transparent",
                  fontWeight: value === opt.value ? 600 : 400,
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = hoverBg;
                }}
                onMouseLeave={(e) => {
                  if (value !== opt.value) {
                    e.currentTarget.style.backgroundColor = "transparent";
                  }
                }}
              >
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
    </div>
  );
}
