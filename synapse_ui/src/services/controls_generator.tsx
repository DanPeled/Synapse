import { ConstraintTypeProto } from "@/proto/settings/v1/constraint_type";
import { SettingMetaProto } from "@/proto/settings/v1/settings";
import { SettingValueProto } from "@/proto/settings/v1/value";
import { Dropdown, DropdownOption } from "@/widgets/dropdown";
import { Slider } from "@/widgets/slider";
import TextInput from "@/widgets/textInput";
import ToggleButton from "@/widgets/toggleButtons";
import { toTitleCase } from "./stringUtil";
import { Placeholder } from "@/widgets/placeholder";

interface ControlGeneratorProps {
  setting: SettingMetaProto;
  setValue: (val: SettingValueProto) => void;
  value: SettingValueProto;
  defaultValue: SettingValueProto | undefined;
}

export function toNumber(val: unknown | undefined): number | undefined {
  if (val === undefined || val === null) return undefined;

  const num = Number(val);
  return isNaN(num) ? undefined : num;
}

export function protoToSettingValue(proto: SettingValueProto): unknown {
  if (proto === undefined) return undefined;

  if (proto.intValue !== undefined) return proto.intValue;
  if (proto.stringValue !== undefined) return proto.stringValue;
  if (proto.boolValue !== undefined) return proto.boolValue;
  if (proto.floatValue !== undefined) return proto.floatValue;
  if (proto.bytesValue !== undefined && proto.bytesValue.length > 0)
    return proto.bytesValue;
  if (proto.intArrayValue.length > 0) return proto.intArrayValue;
  if (proto.stringArrayValue.length > 0) return proto.stringArrayValue;
  if (proto.boolArrayValue.length > 0) return proto.boolArrayValue;
  if (proto.floatArrayValue.length > 0) return proto.floatArrayValue;
  if (proto.bytesArrayValue.length > 0) return proto.bytesArrayValue;

  return undefined;
}

export function settingValueToProto(val: unknown): SettingValueProto {
  const proto = SettingValueProto.create();

  if (typeof val === "number" && Number.isInteger(val)) {
    proto.intValue = val;
  } else if (typeof val === "number") {
    proto.floatValue = val;
  } else if (typeof val === "string") {
    proto.stringValue = val;
  } else if (typeof val === "boolean") {
    proto.boolValue = val;
  } else if (val instanceof Uint8Array) {
    proto.bytesValue = val;
  } else if (Array.isArray(val)) {
    if (val.every((v) => typeof v === "number" && Number.isInteger(v))) {
      proto.intArrayValue = val as number[];
    } else if (val.every((v) => typeof v === "number")) {
      proto.floatArrayValue = val as number[];
    } else if (val.every((v) => typeof v === "string")) {
      proto.stringArrayValue = val as string[];
    } else if (val.every((v) => typeof v === "boolean")) {
      proto.boolArrayValue = val as boolean[];
    } else if (val.every((v) => v instanceof Uint8Array)) {
      proto.bytesArrayValue = val as Uint8Array[];
    } else {
      throw new TypeError("Unsupported array element type");
    }
  } else {
    throw new TypeError("Unsupported setting value type");
  }

  return proto;
}

export function GenerateControl({
  setting,
  setValue,
  value,
  defaultValue,
}: ControlGeneratorProps) {
  const settingName = toTitleCase(setting.name.replaceAll("_", " "));
  switch (setting.constraint?.type) {
    case ConstraintTypeProto.CONSTRAINT_TYPE_PROTO_BOOLEAN:
      return (
        <ToggleButton
          label={settingName}
          value={protoToSettingValue(value) as boolean}
          onToggleAction={(val) => setValue(settingValueToProto(val))}
        />
      );
    case ConstraintTypeProto.CONSTRAINT_TYPE_PROTO_STRING:
      return (
        <TextInput
          label={settingName}
          pattern={setting.constraint.constraint?.string?.pattern}
          maxLength={setting.constraint.constraint?.string?.maxLength}
          onChange={(val) => setValue(settingValueToProto(val))}
        />
      );
    case ConstraintTypeProto.CONSTRAINT_TYPE_PROTO_RANGE:
      return (
        <Slider
          label={settingName}
          min={setting.constraint.constraint?.range?.min}
          max={setting.constraint.constraint?.range?.max}
          step={setting.constraint.constraint?.range?.step}
          value={toNumber(protoToSettingValue(value)) ?? 0}
          onChange={(val) => setValue(settingValueToProto(val))}
        />
      );
    case ConstraintTypeProto.CONSTRAINT_TYPE_PROTO_LIST_OPTIONS:
      if (setting.constraint.constraint?.listOptions?.allowMultiple) {
        return <Placeholder text="TODO: multiple options not implemented" />;
      } else {
        return (
          <Dropdown
            label={settingName}
            options={
              (setting.constraint.constraint?.listOptions?.options.map(
                (op) => ({
                  label: protoToSettingValue(op),
                  value: protoToSettingValue(op),
                }),
              ) as DropdownOption<SettingValueProto>[]) ?? []
            }
            value={protoToSettingValue(value)}
            onValueChange={(val) => setValue(settingValueToProto(val))}
          />
        );
      }
    default:
      return null;
  }
}
