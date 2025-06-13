import React, { useState } from "react";
import styled from "styled-components";
import { lighten } from "polished";
import { getDivColor, teamColor } from "../services/style";

const baseColor = getDivColor();

const SliderWrapper = styled.div`
  width: 98%;
  padding: 20px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  gap: 12px;
  color: ${lighten(0.8, baseColor)};
`;

const SliderLabel = styled.label`
  font-weight: 600;
  flex-shrink: 0;
  min-width: 70px;
  color: ${teamColor};
`;

const SliderContent = styled.div`
  display: flex;
  align-items: center;
  gap: 12px;
  flex-grow: 1;
  margin-left: ${(props) => props.labelGap || "0px"};
`;

const StepButton = styled.button`
  background: ${lighten(0.2, baseColor)};
  border: none;
  color: ${lighten(0.4, baseColor)};
  font-weight: 700;
  font-size: 20px;
  width: 36px;
  height: 24px;
  border-radius: 8px;
  cursor: pointer;
  user-select: none;
  transition: background-color 0.2s ease;

  &:hover {
    background: ${lighten(0.1, baseColor)};
  }

  &:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
`;

const StyledInput = styled.input`
  -webkit-appearance: none;
  flex-grow: 1;
  height: 8px;
  border-radius: 5px;
  background: linear-gradient(
    to right,
    ${lighten(0.2, baseColor)} 0%,
    ${lighten(0.2, baseColor)} ${(props) => props.valuePercent}%,
    ${lighten(0.15, baseColor)} ${(props) => props.valuePercent}%,
    ${lighten(0.15, baseColor)} 100%
  );
  outline: none;
  cursor: pointer;
  transition: background 0.3s ease;

  &::-webkit-slider-thumb {
    -webkit-appearance: none;
    appearance: none;
    width: 20px;
    height: 20px;
    background: ${lighten(0.3, baseColor)};
    border-radius: 50%;
    cursor: pointer;
    border: 3px solid ${lighten(0.4, baseColor)};
    box-shadow: 0 0 8px ${lighten(0.3, baseColor)};
    margin-top: -7px;
    transition: background 0.3s ease;
  }
  &::-moz-range-thumb {
    width: 20px;
    height: 20px;
    background: ${lighten(0.3, baseColor)};
    border-radius: 50%;
    cursor: pointer;
    border: 3px solid ${lighten(0.4, baseColor)};
    box-shadow: 0 0 8px ${lighten(0.3, baseColor)};
    transition: background 0.3s ease;
  }

  &:hover::-webkit-slider-thumb {
    background: ${lighten(0.4, baseColor)};
  }
`;

const ValueInput = styled.input`
  width: 50px;
  background: ${lighten(0.2, baseColor)};
  border: none;
  border-radius: 6px;
  color: ${teamColor};
  font-weight: 600;
  text-align: center;
  font-size: 16px;
  padding: 6px 0;
  user-select: text;

  &:focus {
    outline: 2px solid ${lighten(0.3, baseColor)};
    background: ${lighten(0.1, baseColor)};
  }

  &::-webkit-inner-spin-button,
  &::-webkit-outer-spin-button {
    -webkit-appearance: none;
    margin: 0;
  }
  -moz-appearance: textfield;
`;

function Slider({
  min = 0,
  max = 100,
  step = 1,
  initial = 50,
  label = "Value",
  labelGap = "0px",
  className = "",
  onChange = (val) => {},
}) {
  const [value, setValue] = useState(initial);
  const valuePercent = ((value - min) / (max - min)) * 100;

  const clampValue = (val) => Math.min(max, Math.max(min, val));

  const handleSliderChange = (e) => {
    setValue(clampValue(Number(e.target.value)));
  };

  const handleInputChange = (e) => {
    const val = e.target.value;
    if (val === "") {
      setValue("");
      return;
    }
    const num = Number(val);
    if (!isNaN(num)) {
      setValue(clampValue(num));
      onChange(clampValue(num));
    }
  };

  const handleInputBlur = () => {
    if (value === "" || isNaN(value)) {
      setValue(min);
    }
  };

  const increment = () => setValue((v) => clampValue(Number(v) + step));
  const decrement = () => setValue((v) => clampValue(Number(v) - step));

  return (
    <SliderWrapper>
      <SliderLabel>{label}</SliderLabel>
      <SliderContent labelGap={labelGap}>
        <StepButton onClick={decrement} disabled={value <= min}>
          &minus;
        </StepButton>
        <StyledInput
          type="range"
          min={min}
          max={max}
          step={step}
          value={value === "" ? min : value}
          valuePercent={valuePercent}
          onChange={handleSliderChange}
        />
        <StepButton onClick={increment} disabled={value >= max}>
          +
        </StepButton>
        <ValueInput
          type="number"
          value={value}
          min={min}
          max={max}
          step={step}
          onChange={handleInputChange}
          onBlur={handleInputBlur}
        />
      </SliderContent>
    </SliderWrapper>
  );
}

export default Slider;
