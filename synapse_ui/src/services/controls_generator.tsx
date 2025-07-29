import { ConstraintTypeProto } from "@/proto/settings/v1/constraint_type";
import { SettingMetaProto } from "@/proto/settings/v1/settings";
import { SettingValueProto } from "@/proto/settings/v1/value";
import { Dropdown, DropdownOption } from "@/widgets/dropdown";
import { Slider } from "@/widgets/slider";
import TextInput from "@/widgets/textInput";
import ToggleButton from "@/widgets/toggleButtons";
import { toTitleCase } from "./stringUtil";
import { NumberInput } from "@/widgets/numberInput";
import LabeledControl from "@/widgets/labeledControl";
import { Button } from "@/components/ui/button";
import { teamColor } from "./style";
import { RefreshCcw } from "lucide-react";

interface ControlGeneratorProps {
  setting: SettingMetaProto;
  setValue: (val: SettingValueProto) => void;
  value: SettingValueProto;
  defaultValue: SettingValueProto | undefined;
  locked: boolean;
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

function ResetToDefaultButton({
  defaultValue,
  setValue,
  disabled,
}: {
  defaultValue?: SettingValueProto;
  setValue: (val: SettingValueProto) => void;
  disabled: boolean;
}) {
  return defaultValue !== undefined ? (
    <Button
      size="sm"
      style={{ color: teamColor }}
      className="hover:bg-zinc-700 cursor-pointer"
      onClick={() => {
        setValue(defaultValue);
      }}
      disabled={disabled}
    >
      <RefreshCcw />
    </Button>
  ) : null;
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
  locked,
}: ControlGeneratorProps) {
  const settingName = toTitleCase(setting.name.replaceAll("_", " "));
  const val = protoToSettingValue(value);

  switch (setting.constraint?.type) {
    case ConstraintTypeProto.CONSTRAINT_TYPE_PROTO_BOOLEAN:
      return (
        <LabeledControl label={settingName}>
          <ToggleButton
            value={val as boolean}
            onToggleAction={(val) => setValue(settingValueToProto(val))}
            disabled={locked}
          />
          <ResetToDefaultButton
            defaultValue={defaultValue}
            setValue={setValue}
            disabled={locked}
          />
        </LabeledControl>
      );
    case ConstraintTypeProto.CONSTRAINT_TYPE_PROTO_STRING:
      return (
        <LabeledControl label={settingName}>
          <TextInput
            value={String(val)}
            pattern={setting.constraint.constraint?.string?.pattern}
            maxLength={setting.constraint.constraint?.string?.maxLength}
            onChange={(val) => setValue(settingValueToProto(val))}
            disabled={locked}
          />
          <ResetToDefaultButton
            defaultValue={defaultValue}
            setValue={setValue}
            disabled={locked}
          />
        </LabeledControl>
      );
    case ConstraintTypeProto.CONSTRAINT_TYPE_PROTO_NUMBER:
      if (setting.constraint.constraint?.numeric?.max) {
        return (
          <LabeledControl label={settingName}>
            <Slider
              min={setting.constraint.constraint?.numeric?.min}
              max={setting.constraint.constraint?.numeric?.max}
              step={setting.constraint.constraint?.numeric?.step}
              value={toNumber(val) ?? 0}
              onChange={(val) => setValue(settingValueToProto(val))}
              disabled={locked}
            />
            <ResetToDefaultButton
              defaultValue={defaultValue}
              setValue={setValue}
              disabled={locked}
            />
          </LabeledControl>
        );
      } else {
        return (
          <LabeledControl label={settingName}>
            <NumberInput
              value={val as number}
              onChange={(val) => setValue(settingValueToProto(val))}
              disabled={locked}
            />
            <ResetToDefaultButton
              defaultValue={defaultValue}
              setValue={setValue}
              disabled={locked}
            />
          </LabeledControl>
        );
      }
    case ConstraintTypeProto.CONSTRAINT_TYPE_PROTO_ENUMERATED: {
      return (
        <LabeledControl label={settingName}>
          <Dropdown
            label=""
            options={
              (setting.constraint.constraint?.enumerated?.options.map((op) => ({
                label: protoToSettingValue(op),
                value: protoToSettingValue(op),
              })) as DropdownOption<SettingValueProto>[]) ?? []
            }
            value={val}
            onValueChange={(val) => setValue(settingValueToProto(val))}
            disabled={locked}
          />
          <ResetToDefaultButton
            defaultValue={defaultValue}
            setValue={setValue}
            disabled={locked}
          />
        </LabeledControl>
      );
    }
    default:
      return null;
  }
}
