import type { LogMessageProto } from "@/generated/messages/v1/log";
import type {
  PipelineProto,
  SetPipleineSettingMessageProto,
} from "@/generated/messages/v1/pipeline";
import type { SettingValueProto } from "@/generated/settings/v1/value";
import type {
  CameraID,
  CameraPipelinesMap,
  PipelinesMap,
} from "./dataStractures";

/**
 * Settings waiting to be applied to the pipeline state. The outermost map is
 * keyed by camera, then pipeline index, then setting name so a burst of
 * SET_SETTING messages can be collapsed to one structural patch per frame.
 */
export type PendingSettings = Map<
  CameraID,
  Map<number, Map<string, SettingValueProto>>
>;

/** Tracks log timestamps in O(1) so replayed/duplicate logs are ignored. */
export class LogTimestampIndex {
  private readonly timestamps: Set<number>;

  constructor(existingLogs: LogMessageProto[] = []) {
    this.timestamps = new Set(existingLogs.map((log) => log.timestamp));
  }

  /** Returns true when the timestamp has not been seen before. */
  add(timestamp: number): boolean {
    if (this.timestamps.has(timestamp)) return false;
    this.timestamps.add(timestamp);
    return true;
  }
}

/**
 * Merges a batch of newly received logs into the committed, sorted log list.
 * Incoming logs are sorted once per batch; individual log messages only do
 * O(1) work when they arrive.
 */
export function mergeLogsInOrder(
  existing: LogMessageProto[],
  incoming: LogMessageProto[],
): LogMessageProto[] {
  if (incoming.length === 0) return existing;

  // Always copy: the pending array is reused for the next batch.
  const sortedIncoming = [...incoming].sort(
    (a, b) => a.timestamp - b.timestamp,
  );
  if (existing.length === 0) return sortedIncoming;

  const merged: LogMessageProto[] = new Array(
    existing.length + sortedIncoming.length,
  );
  let i = 0;
  let j = 0;
  let k = 0;

  while (i < existing.length && j < sortedIncoming.length) {
    if (existing[i].timestamp <= sortedIncoming[j].timestamp) {
      merged[k++] = existing[i++];
    } else {
      merged[k++] = sortedIncoming[j++];
    }
  }
  while (i < existing.length) merged[k++] = existing[i++];
  while (j < sortedIncoming.length) merged[k++] = sortedIncoming[j++];

  return merged;
}

/** Records a SET_SETTING message without touching the React state tree. */
export function recordPendingSetting(
  pending: PendingSettings,
  message: SetPipleineSettingMessageProto,
): void {
  if (message.value === undefined) return;

  let cameraChanges = pending.get(message.cameraid);
  if (!cameraChanges) {
    cameraChanges = new Map();
    pending.set(message.cameraid, cameraChanges);
  }

  let pipelineChanges = cameraChanges.get(message.pipelineIndex);
  if (!pipelineChanges) {
    pipelineChanges = new Map();
    cameraChanges.set(message.pipelineIndex, pipelineChanges);
  }

  pipelineChanges.set(message.setting, message.value);
}

/**
 * Applies all pending settings with structural sharing: the pipelines map is
 * cloned once, then only affected camera maps, pipelines and settings objects
 * are replaced. Untouched entries keep their identity.
 */
export function applyPendingSettings(
  pipelines: PipelinesMap,
  pending: PendingSettings,
): PipelinesMap {
  if (pending.size === 0) return pipelines;

  let nextPipelines: PipelinesMap | undefined;

  for (const [cameraId, pipelineChanges] of pending) {
    const cameraPipelines = (nextPipelines ?? pipelines).get(cameraId);
    if (!cameraPipelines) continue;

    let nextCameraPipelines: CameraPipelinesMap | undefined;

    for (const [pipelineIndex, settingChanges] of pipelineChanges) {
      const pipeline = (nextCameraPipelines ?? cameraPipelines).get(
        pipelineIndex,
      );
      if (!pipeline) continue;

      const settingsValues = { ...pipeline.settingsValues };
      for (const [setting, value] of settingChanges) {
        settingsValues[setting] = value;
      }

      if (!nextCameraPipelines) nextCameraPipelines = new Map(cameraPipelines);
      nextCameraPipelines.set(pipelineIndex, {
        ...pipeline,
        settingsValues,
      });
    }

    if (nextCameraPipelines) {
      if (!nextPipelines) nextPipelines = new Map(pipelines);
      nextPipelines.set(cameraId, nextCameraPipelines);
    }
  }

  return nextPipelines ?? pipelines;
}

/** Patches one setting in a camera's pipelines for optimistic UI updates. */
export function patchCameraPipelinesSetting(
  pipelines: CameraPipelinesMap,
  pipeline: PipelineProto,
  setting: string,
  value: SettingValueProto,
): CameraPipelinesMap {
  const current = pipelines.get(pipeline.index) ?? pipeline;
  const next = new Map(pipelines);
  next.set(pipeline.index, {
    ...current,
    settingsValues: { ...current.settingsValues, [setting]: value },
  });
  return next;
}
