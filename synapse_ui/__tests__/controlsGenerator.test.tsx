import { fireEvent, render, screen } from "@testing-library/react";
import type { PipelineProto } from "@/generated/messages/v1/pipeline";
import type { SettingMetaProto } from "@/generated/settings/v1/settings";
import { generateControlFromSettingMeta } from "@/services/controls_generator";

let mockSliderValue = 0;

jest.mock("@/services/backend/backendContext", () => ({
  hasSettingValue: () => true,
}));

jest.mock("@/widgets/slider", () => ({
  Slider: ({ onChange }: { onChange: (value: number) => void }) => (
    <button onClick={() => onChange(++mockSliderValue)}>increase</button>
  ),
}));

const setting = {
  name: "gain",
  category: "test",
  constraint: {
    type: 1, // CONSTRAINT_TYPE_PROTO_NUMBER
    constraint: { numeric: { min: 0, max: 100, step: 1 } },
  },
} as unknown as SettingMetaProto;

function pipeline(): PipelineProto {
  return { index: 0, cameraid: 0, name: "p", type: "t", settingsValues: {} };
}

describe("generateControlFromSettingMeta", () => {
  beforeEach(() => {
    mockSliderValue = 0;
    jest.useFakeTimers();
  });
  afterEach(() => jest.useRealTimers());

  it("updates local state immediately and throttles network sends", () => {
    const selectedPipeline = pipeline();
    const setPipelines = jest.fn();
    const setSetting = jest.fn();

    render(
      generateControlFromSettingMeta({
        setting,
        selectedPipeline,
        pipelines: new Map([[0, selectedPipeline]]),
        setPipelines,
        setSetting,
        locked: false,
      }),
    );

    const increase = screen.getByRole("button", { name: "increase" });
    fireEvent.click(increase);
    fireEvent.click(increase);
    fireEvent.click(increase);

    expect(setPipelines).toHaveBeenCalledTimes(3);
    expect(setSetting).toHaveBeenCalledTimes(1);
    expect(setSetting.mock.calls[0][1]).toBe("gain");

    // The functional update is applied optimistically without mutating state.
    const nextPipelines = setPipelines.mock.calls[2][0](
      new Map([[0, selectedPipeline]]),
    );
    expect(nextPipelines.get(0).settingsValues.gain.intValue).toBe(3);
    expect(selectedPipeline.settingsValues).toEqual({});

    jest.advanceTimersByTime(100);
    expect(setSetting).toHaveBeenCalledTimes(2);
    expect(setSetting.mock.calls[1][0].intValue).toBe(3);
  });
});
