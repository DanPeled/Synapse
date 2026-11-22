import type { LogMessageProto } from "@/generated/messages/v1/log";
import type {
  PipelineProto,
  SetPipleineSettingMessageProto,
} from "@/generated/messages/v1/pipeline";
import type { SettingValueProto } from "@/generated/settings/v1/value";
import {
  applyPendingSettings,
  LogTimestampIndex,
  mergeLogsInOrder,
  patchCameraPipelinesSetting,
  recordPendingSetting,
} from "@/services/backend/stateBatching";

function log(timestamp: number, message = `log-${timestamp}`): LogMessageProto {
  return { timestamp, message, level: 2 } as LogMessageProto;
}

function value(n: number): SettingValueProto {
  return { intValue: n } as SettingValueProto;
}

function pipeline(index: number, cameraid = 0): PipelineProto {
  return {
    name: `pipeline-${index}`,
    index,
    cameraid,
    type: "test",
    settingsValues: {},
  } as PipelineProto;
}

function settingMessage(
  cameraid: number,
  pipelineIndex: number,
  setting: string,
  val: SettingValueProto | undefined,
): SetPipleineSettingMessageProto {
  return {
    cameraid,
    pipelineIndex,
    setting,
    value: val,
  } as SetPipleineSettingMessageProto;
}

describe("mergeLogsInOrder", () => {
  it("keeps committed logs sorted when a batch arrives out of order", () => {
    const existing = [log(10), log(30)];
    const incoming = [log(40), log(20), log(5)];

    const merged = mergeLogsInOrder(existing, incoming);

    expect(merged.map((entry) => entry.timestamp)).toEqual([5, 10, 20, 30, 40]);
    expect(existing.map((entry) => entry.timestamp)).toEqual([10, 30]);
    expect(incoming.map((entry) => entry.timestamp)).toEqual([40, 20, 5]);
  });

  it("returns the original array when there is nothing to merge", () => {
    const existing = [log(1)];
    expect(mergeLogsInOrder(existing, [])).toBe(existing);
  });
});

describe("LogTimestampIndex", () => {
  it("deduplicates timestamps seen in previous and pending batches", () => {
    const index = new LogTimestampIndex([log(1), log(3)]);

    expect(index.add(1)).toBe(false);
    expect(index.add(2)).toBe(true);
    expect(index.add(2)).toBe(false);
    expect(index.add(3)).toBe(false);
  });
});

describe("applyPendingSettings", () => {
  it("patches only the affected pipelines with structural sharing", () => {
    const camera0Pipelines = new Map([
      [0, pipeline(0, 0)],
      [1, pipeline(1, 0)],
    ]);
    const untouchedCameraPipelines = new Map([[0, pipeline(0, 1)]]);
    const pipelines = new Map([
      [0, camera0Pipelines],
      [1, untouchedCameraPipelines],
    ]);
    const pending = new Map();

    recordPendingSetting(pending, settingMessage(0, 0, "exposure", value(10)));
    recordPendingSetting(pending, settingMessage(0, 0, "gain", value(20)));
    recordPendingSetting(pending, settingMessage(0, 99, "ignored", value(1)));
    recordPendingSetting(pending, settingMessage(99, 0, "ignored", value(1)));
    recordPendingSetting(pending, settingMessage(0, 0, "empty", undefined));

    const next = applyPendingSettings(pipelines, pending);

    expect(next).not.toBe(pipelines);
    expect(next.get(1)).toBe(untouchedCameraPipelines);
    expect(next.get(0)).not.toBe(camera0Pipelines);
    expect(next.get(0)?.get(1)).toBe(camera0Pipelines.get(1));
    expect(next.get(0)?.get(0)).not.toBe(camera0Pipelines.get(0));
    expect(next.get(0)?.get(0)?.settingsValues).toEqual({
      exposure: value(10),
      gain: value(20),
    });
    expect(camera0Pipelines.get(0)?.settingsValues).toEqual({});
  });

  it("does not clone the map when no settings are pending", () => {
    const pipelines = new Map([[0, new Map([[0, pipeline(0)]])]]);
    expect(applyPendingSettings(pipelines, new Map())).toBe(pipelines);
  });
});

describe("patchCameraPipelinesSetting", () => {
  it("copies only the changed pipeline and its settings object", () => {
    const unchanged = pipeline(1);
    const pipelines = new Map([
      [0, pipeline(0)],
      [1, unchanged],
    ]);

    const next = patchCameraPipelinesSetting(
      pipelines,
      pipelines.get(0)!,
      "brightness",
      value(7),
    );

    expect(next).not.toBe(pipelines);
    expect(next.get(1)).toBe(unchanged);
    expect(next.get(0)?.settingsValues.brightness).toEqual(value(7));
    expect(pipelines.get(0)?.settingsValues).toEqual({});
  });
});
