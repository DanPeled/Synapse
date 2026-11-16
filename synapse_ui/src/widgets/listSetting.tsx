import { cn } from "@/lib/utils";
import { ValueTypeProto } from "@/generated/settings/v1/value_type";
import { baseCardColor, teamColor } from "@/services/style";
import { useEffect, useState } from "react";

interface ListSettingControlProps {
  value: unknown[];
  itemType: ValueTypeProto;
  onChange: (value: unknown[]) => void;
  disabled?: boolean;
}

const INT_PATTERN = /^[+-]?\d+$/;

function parseBoolean(token: string): boolean {
  const lowered = token.toLowerCase();
  if (["true", "1", "yes", "on"].includes(lowered)) return true;
  if (["false", "0", "no", "off"].includes(lowered)) return false;
  throw new Error(`"${token}" is not a boolean`);
}

function parseNumber(token: string): number {
  const number = Number(token);
  if (token === "" || !Number.isFinite(number)) {
    throw new Error(`"${token}" is not a number`);
  }
  return number;
}

function inferToken(token: string): unknown {
  const lowered = token.toLowerCase();
  if (["true", "false", "yes", "no", "on", "off"].includes(lowered)) {
    return parseBoolean(token);
  }
  if (INT_PATTERN.test(token)) return Number(token);
  if (Number.isFinite(Number(token))) return Number(token);
  return token;
}

function inferListType(values: unknown[]): ValueTypeProto {
  if (values.length === 0) return ValueTypeProto.VALUE_TYPE_PROTO_UNSPECIFIED;
  if (values.every((value) => typeof value === "boolean")) {
    return ValueTypeProto.VALUE_TYPE_PROTO_BOOL;
  }
  if (values.every((value) => typeof value === "string")) {
    return ValueTypeProto.VALUE_TYPE_PROTO_STRING;
  }
  if (values.every((value) => typeof value === "number")) {
    return values.every((value) => Number.isInteger(value))
      ? ValueTypeProto.VALUE_TYPE_PROTO_INT
      : ValueTypeProto.VALUE_TYPE_PROTO_FLOAT;
  }
  throw new Error("All list items must have the same type");
}

export function parseListText(
  text: string,
  itemType: ValueTypeProto,
): unknown[] {
  const tokens = text
    .split(",")
    .map((token) => token.trim())
    .filter((token) => token.length > 0);

  if (tokens.length === 0) return [];

  switch (itemType) {
    case ValueTypeProto.VALUE_TYPE_PROTO_INT:
      return tokens.map((token) => {
        if (!INT_PATTERN.test(token)) {
          throw new Error(`"${token}" is not an integer`);
        }
        return Number(token);
      });
    case ValueTypeProto.VALUE_TYPE_PROTO_FLOAT:
      return tokens.map(parseNumber);
    case ValueTypeProto.VALUE_TYPE_PROTO_BOOL:
      return tokens.map(parseBoolean);
    case ValueTypeProto.VALUE_TYPE_PROTO_STRING:
      return tokens;
    case ValueTypeProto.VALUE_TYPE_PROTO_BYTES:
    case ValueTypeProto.VALUE_TYPE_PROTO_LIST:
      throw new Error("This list type cannot be edited as text");
    case ValueTypeProto.VALUE_TYPE_PROTO_UNSPECIFIED:
    default: {
      const values = tokens.map(inferToken);
      inferListType(values);
      return values;
    }
  }
}

export function formatListValue(values: unknown[]): string {
  return values
    .map((value) =>
      typeof value === "boolean" ? (value ? "true" : "false") : String(value),
    )
    .join(", ");
}

export function ListSettingControl({
  value,
  itemType,
  onChange,
  disabled = false,
}: ListSettingControlProps) {
  const [text, setText] = useState(() => formatListValue(value));
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setText(formatListValue(value));
    setError(null);
  }, [value]);

  const commit = () => {
    try {
      const parsed = parseListText(text, itemType);
      setError(null);
      setText(formatListValue(parsed));
      onChange(parsed);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Invalid list value");
    }
  };

  return (
    <div
      className={cn(
        "w-[97%] px-4 py-3 rounded-2xl shadow-md flex flex-col gap-1",
        "text-[rgba(255,255,255,0.85)]",
        disabled ? "opacity-50 pointer-events-none" : "",
      )}
      style={{ backgroundColor: baseCardColor, color: teamColor }}
    >
      <input
        type="text"
        value={text}
        placeholder="Comma-separated values, e.g. 1, 2, 3"
        disabled={disabled}
        onChange={(e) => setText(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            commit();
          }
        }}
        className={cn(
          "w-full px-3 py-2 rounded-lg font-semibold text-base bg-[rgba(255,255,255,0.08)]",
          "border focus:outline-none focus:border-current bg-zinc-800",
          error ? "border-red-400" : "border-[rgba(255,255,255,0.2)]",
        )}
        style={{ color: teamColor }}
      />
      {error && <p className="text-red-400 text-sm">{error}</p>}
    </div>
  );
}
