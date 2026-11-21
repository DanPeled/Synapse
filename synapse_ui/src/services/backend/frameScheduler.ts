export type CancelScheduledFrame = () => void;

/**
 * Runs a batched state update once per frame. The timer fallback keeps the
 * provider working in test environments and on platforms without rAF.
 */
export function scheduleFrame(
  callback: () => void,
  fallbackDelayMs = 16,
): CancelScheduledFrame {
  if (
    typeof requestAnimationFrame === "function" &&
    typeof cancelAnimationFrame === "function"
  ) {
    const handle = requestAnimationFrame(() => callback());
    return () => cancelAnimationFrame(handle);
  }

  const handle = setTimeout(callback, fallbackDelayMs);
  return () => clearTimeout(handle);
}
