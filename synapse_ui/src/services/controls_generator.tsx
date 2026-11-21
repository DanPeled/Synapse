import { useEffect, useRef } from "react";
import { ConstraintTypeProto } from "@/generated/settings/v1/constraint_type";
import { SettingMetaProto } from "@/generated/settings/v1/settings";
import { SettingValueProto } from "@/generated/settings/v1/value";
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
import assert from "assert";
import { hasSettingValue } from "./backend/backendContext";
import { PipelineProto } from "@/generated/messages/v1/pipeline";
import {
  CameraPipelinesMap,
  CameraPipelinesSetter,
} from "./backend/dataStractures";
import { patchCameraPipelinesSetting } from "./backend/stateBatching";
import { createSettingSendThrottle } from "./settingThrottle";
import { FileSettingControl } from "@/widgets/fileSetting";
import { RangeSlider } from "@/widgets/range";
import { ListSettingControl } from "@/widgets/listSetting";
import { ValueTypeProto } from "@/generated/settings/v1/value_type";

interface GeneratedSettingControlProps {
  setting: SettingMetaProto;
  selectedPipeline?: PipelineProto;
  setSetting: (
    val: SettingValueProto,
    setting: string,
    pipeline: PipelineProto,
  ) => void;
  setPipelines: CameraPipelinesSetter;
  pipelines: CameraPipelinesMap;
  locked: boolean;
}

function GeneratedSettingControl({
  setting,
  selectedPipeline,
  setPipelines,
  setSetting,
  locked,
}: GeneratedSettingControlProps) {
  const setSettingRef = useRef(setSetting);
  setSettingRef.current = setSetting;
  const selectedPipelineRef = useRef(selectedPipeline);
  selectedPipelineRef.current = selectedPipeline;

  const throttleRef = useRef<ReturnType<
    typeof createSettingSendThrottle
  > | null>(null);
  let throttle = throttleRef.current;
  if (throttle === null) {
    throttle = createSettingSendThrottle((pending) => {
      setSettingRef.current(pending.value, pending.setting, pending.pipeline!);
    });
    throttleRef.current = throttle;
  }

  // Make sure the last value of a drag reaches the backend on unmount.
  useEffect(() => () => throttle?.flush(), []);

  const setValue = (val: SettingValueProto) => {
    if (!hasSettingValue(val)) return;

    const pipeline = selectedPipelineRef.current;
    if (pipeline) {
      setPipelines((prev) =>
        patchCameraPipelinesSetting(prev, pipeline, setting.name, val),
      );
    }
    throttle.enqueue({
      value: val,
      setting: setting.name,
      pipeline,
    });
  };

  return (
    <GenerateControl
      setting={setting}
      setValue={setValue}
      value={
        selectedPipeline?.settingsValues[setting.name] ??
        setting.default ??
        settingValueToProto("")
      }
      defaultValue={setting.default}
      locked={locked}
    />
  );
}

export function generateControlFromSettingMeta({
  setting,
  ...props
}: GeneratedSettingControlProps) {
  return (
    <GeneratedSettingControl
      key={setting.name + setting.category}
      setting={setting}
      {...props}
    />
  );
}
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

  switch (proto.arrayType) {
    case ValueTypeProto.VALUE_TYPE_PROTO_INT:
      return proto.intArrayValue;
    case ValueTypeProto.VALUE_TYPE_PROTO_STRING:
      return proto.stringArrayValue;
    case ValueTypeProto.VALUE_TYPE_PROTO_BOOL:
      return proto.boolArrayValue;
    case ValueTypeProto.VALUE_TYPE_PROTO_FLOAT:
      return proto.floatArrayValue;
    case ValueTypeProto.VALUE_TYPE_PROTO_BYTES:
      return proto.bytesArrayValue;
    case ValueTypeProto.VALUE_TYPE_PROTO_LIST:
      // LIST marks an empty list whose item type is unknown.
      return [];
  }

  if (proto.intValue !== undefined) return proto.intValue;
  if (proto.stringValue !== undefined) return proto.stringValue;
  if (proto.boolValue !== undefined) return proto.boolValue;
  if (proto.floatValue !== undefined) return proto.floatValue;
  if (proto.bytesValue !== undefined && proto.bytesValue.length > 0)
    return proto.bytesValue;
  // Fall back to arrays from older senders that do not set arrayType.
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

export function settingValueToProto(
  val: unknown,
  itemType: ValueTypeProto = ValueTypeProto.VALUE_TYPE_PROTO_UNSPECIFIED,
): SettingValueProto {
  const proto = SettingValueProto.create();

  if (typeof val === "boolean") {
    proto.boolValue = val;
  } else if (typeof val === "number" && Number.isInteger(val)) {
    proto.intValue = val;
  } else if (typeof val === "number") {
    proto.floatValue = val;
  } else if (typeof val === "string") {
    proto.stringValue = val;
  } else if (val instanceof Uint8Array) {
    proto.bytesValue = val;
  } else if (Array.isArray(val)) {
    let resolvedType = itemType;
    if (resolvedType === ValueTypeProto.VALUE_TYPE_PROTO_UNSPECIFIED) {
      if (val.every((v) => typeof v === "boolean")) {
        resolvedType = ValueTypeProto.VALUE_TYPE_PROTO_BOOL;
      } else if (
        val.every((v) => typeof v === "number" && Number.isInteger(v))
      ) {
        resolvedType = ValueTypeProto.VALUE_TYPE_PROTO_INT;
      } else if (val.every((v) => typeof v === "number")) {
        resolvedType = ValueTypeProto.VALUE_TYPE_PROTO_FLOAT;
      } else if (val.every((v) => typeof v === "string")) {
        resolvedType = ValueTypeProto.VALUE_TYPE_PROTO_STRING;
      } else if (val.every((v) => v instanceof Uint8Array)) {
        resolvedType = ValueTypeProto.VALUE_TYPE_PROTO_BYTES;
      } else if (val.length > 0) {
        throw new TypeError("Unsupported array element type");
      } else {
        // An empty array with no item type still needs a marker so it does
        // not look like an unset value on the wire.
        resolvedType = ValueTypeProto.VALUE_TYPE_PROTO_LIST;
      }
    }

    switch (resolvedType) {
      case ValueTypeProto.VALUE_TYPE_PROTO_INT:
        proto.intArrayValue = val as number[];
        break;
      case ValueTypeProto.VALUE_TYPE_PROTO_FLOAT:
        proto.floatArrayValue = val as number[];
        break;
      case ValueTypeProto.VALUE_TYPE_PROTO_STRING:
        proto.stringArrayValue = val as string[];
        break;
      case ValueTypeProto.VALUE_TYPE_PROTO_BOOL:
        proto.boolArrayValue = val as boolean[];
        break;
      case ValueTypeProto.VALUE_TYPE_PROTO_BYTES:
        proto.bytesArrayValue = val as Uint8Array[];
        break;
      case ValueTypeProto.VALUE_TYPE_PROTO_LIST:
        if (val.length > 0) {
          throw new TypeError("Nested arrays are not supported");
        }
        break;
      default:
        throw new TypeError("Unsupported array element type");
    }

    // arrayType marks the value as an array so empty lists survive the wire.
    proto.arrayType = resolvedType;
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
    case ConstraintTypeProto.CONSTRAINT_TYPE_PROTO_BOOLEAN: {
      assert(setting.constraint.constraint?.boolean !== undefined);

      if (!setting.constraint.constraint?.boolean?.renderAsButton) {
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
      } else {
        return (
          <div className="w-max flex items-center justify-center mx-auto">
            <Button
              style={{ color: teamColor }}
              className="hover:bg-zinc-600 cursor-pointer bg-zinc-700 w-100 text-lg"
              onClick={() => {
                setValue(SettingValueProto.create({ boolValue: true }));
              }}
            >
              {settingName}
            </Button>
          </div>
        );
      }
    }
    case ConstraintTypeProto.CONSTRAINT_TYPE_PROTO_STRING: {
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
    }
    case ConstraintTypeProto.CONSTRAINT_TYPE_PROTO_RANGE:
      const arr = val as number[];
      const tuple = arr as [number, number];
      return (
        <LabeledControl label={settingName}>
          <RangeSlider
            step={setting.constraint.constraint?.range?.step ?? 1}
            value={tuple}
            onChange={([l, u]) => {
              setValue(SettingValueProto.create({ floatArrayValue: [l, u] }));
            }}
            min={setting.constraint.constraint?.range?.min}
            max={setting.constraint.constraint?.range?.max}
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
              min={
                setting.constraint.constraint?.numeric?.min ?? Number.MIN_VALUE
              }
              max={
                setting.constraint.constraint?.numeric?.max ?? Number.MAX_VALUE
              }
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
    case ConstraintTypeProto.CONSTRAINT_TYPE_PROTO_FILE: {
      const fileConstraint = setting.constraint.constraint?.file;
      return (
        <LabeledControl label={settingName}>
          <FileSettingControl
            value={typeof val === "string" ? val : ""}
            onChange={(path) => setValue(settingValueToProto(path))}
            basePath={fileConstraint?.path ?? ""}
            fileTypes={fileConstraint?.fileTypes ?? []}
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
      const options =
        setting.constraint.constraint?.enumerated?.options.map((op) => {
          // Extract the actual value from the proto
          const val = op.value?.intValue ?? op.value?.stringValue ?? 0;
          return { label: op.key, value: val };
        }) ?? [];

      // Patterns for "1920x1080" and single numbers like "60"
      const resolutionPattern = /^(\d+)\s*[xX]\s*(\d+)$/;
      const singleNumberPattern = /^\d+$/;

      const allResLike = options.every((opt) =>
        resolutionPattern.test(opt.label),
      );
      const allNumLike = options.every((opt) =>
        singleNumberPattern.test(opt.label),
      );

      let sortedOptions = options;

      if (allResLike) {
        sortedOptions = [...options].sort((a, b) => {
          const [, aw, ah] = a.label.match(resolutionPattern) || [];
          const [, bw, bh] = b.label.match(resolutionPattern) || [];
          return (
            (parseInt(aw) || 0) - (parseInt(bw) || 0) ||
            (parseInt(ah) || 0) - (parseInt(bh) || 0)
          );
        });
      } else if (allNumLike) {
        sortedOptions = [...options].sort(
          (a, b) => parseFloat(a.label) - parseFloat(b.label),
        );
      }

      return (
        <LabeledControl label={settingName}>
          <Dropdown
            label=""
            options={sortedOptions as DropdownOption<string>[]}
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
    case ConstraintTypeProto.CONSTRAINT_TYPE_PROTO_LIST: {
      const listConstraint = setting.constraint.constraint?.list;
      const depth = listConstraint?.depth ?? 1;
      if (depth > 1) {
        // Nested list values cannot be represented by SettingValueProto yet.
        return null;
      }
      const itemType =
        listConstraint?.itemType ?? ValueTypeProto.VALUE_TYPE_PROTO_UNSPECIFIED;
      return (
        <LabeledControl label={settingName}>
          <ListSettingControl
            value={Array.isArray(val) ? val : []}
            itemType={itemType}
            onChange={(values) =>
              setValue(settingValueToProto(values, itemType))
            }
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
