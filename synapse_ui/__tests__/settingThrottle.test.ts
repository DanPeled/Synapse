import type { SettingValueProto } from "@/generated/settings/v1/value";
import {
  createSettingSendThrottle,
  type PendingSettingSend,
} from "@/services/settingThrottle";

function value(n: number): SettingValueProto {
  return { intValue: n } as SettingValueProto;
}

function send(n: number): PendingSettingSend {
  return { value: value(n), setting: "slider" };
}

describe("createSettingSendThrottle", () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it("sends the first change immediately and coalesces later changes", () => {
    let now = 1000;
    const sendMock = jest.fn();
    const throttle = createSettingSendThrottle(sendMock, 100, () => now);

    throttle.enqueue(send(1));
    expect(sendMock).toHaveBeenCalledTimes(1);
    expect(sendMock.mock.calls[0][0].value).toEqual(value(1));

    now = 1010;
    throttle.enqueue(send(2));
    now = 1020;
    throttle.enqueue(send(3));
    expect(sendMock).toHaveBeenCalledTimes(1);

    now = 1110;
    jest.advanceTimersByTime(100);
    expect(sendMock).toHaveBeenCalledTimes(2);
    expect(sendMock.mock.calls[1][0].value).toEqual(value(3));
  });

  it("flush sends the pending value and cancels the scheduled timer", () => {
    let now = 1000;
    const sendMock = jest.fn();
    const throttle = createSettingSendThrottle(sendMock, 100, () => now);

    throttle.enqueue(send(1));
    now = 1010;
    throttle.enqueue(send(2));
    throttle.flush();

    expect(sendMock).toHaveBeenCalledTimes(2);
    expect(sendMock.mock.calls[1][0].value).toEqual(value(2));

    jest.advanceTimersByTime(200);
    expect(sendMock).toHaveBeenCalledTimes(2);
  });

  it("cancel drops a pending change without sending it", () => {
    let now = 1000;
    const sendMock = jest.fn();
    const throttle = createSettingSendThrottle(sendMock, 100, () => now);

    throttle.enqueue(send(1));
    now = 1010;
    throttle.enqueue(send(2));
    throttle.cancel();
    jest.advanceTimersByTime(200);

    expect(sendMock).toHaveBeenCalledTimes(1);
  });
});
