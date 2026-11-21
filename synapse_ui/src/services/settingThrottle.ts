import type { PipelineProto } from "@/generated/messages/v1/pipeline";
import type { SettingValueProto } from "@/generated/settings/v1/value";

export interface PendingSettingSend {
  value: SettingValueProto;
  setting: string;
  pipeline?: PipelineProto;
}

export interface SettingSendThrottle {
  enqueue(pending: PendingSettingSend): void;
  flush(): void;
  cancel(): void;
}

/**
 * Leading/trailing throttle for setting writes. The first change is sent
 * immediately, later changes collapse into one send per interval, and the
 * final value is always flushed.
 */
export function createSettingSendThrottle(
  send: (pending: PendingSettingSend) => void,
  intervalMs = 100,
  now: () => number = Date.now,
): SettingSendThrottle {
  let pending: PendingSettingSend | undefined;
  let timer: ReturnType<typeof setTimeout> | undefined;
  let lastSentAt = -Infinity;

  const flush = () => {
    if (timer !== undefined) {
      clearTimeout(timer);
      timer = undefined;
    }
    if (!pending) return;

    const current = pending;
    pending = undefined;
    lastSentAt = now();
    send(current);
  };

  return {
    enqueue(next) {
      pending = next;
      const elapsed = now() - lastSentAt;
      if (elapsed >= intervalMs) {
        flush();
        return;
      }
      if (timer === undefined) {
        timer = setTimeout(flush, intervalMs - elapsed);
      }
    },
    flush,
    cancel() {
      if (timer !== undefined) clearTimeout(timer);
      timer = undefined;
      pending = undefined;
    },
  };
}
