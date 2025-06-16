import React, { useState } from "react";
import styled from "styled-components";
import { lighten } from "polished";
import { getDivColor, teamColor } from "../services/style";

const baseColor = getDivColor();

const SliderWrapper = styled.div`
  width: 97%;
  padding: 16px 20px;
  border-radius: 16px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  display: flex;
  align-items: center;
  gap: 16px;
  color: ${lighten(0.8, baseColor)};
`;

const SliderLabel = styled.label`
  font-weight: 600;
  font-size: 16px;
  min-width: 80px;
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
  background: ${lighten(0.1, baseColor)};
  border: 1px solid ${lighten(0.2, baseColor)};
  color: ${teamColor};
  font-weight: 700;
  font-size: 18px;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  cursor: pointer;
  transition: all 0.2s ease;
  display: grid;
  place-items: center;

  &:hover {
    background: ${lighten(0.15, baseColor)};
  }

  &:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
`;

const StyledInput = styled.input`
  -webkit-appearance: none;
  flex-grow: 1;
  height: 6px;
  border-radius: 5px;
  background: linear-gradient(
    to right,
    ${teamColor} 0%,
    ${teamColor} ${(props) => props.valuePercent}%,
    ${lighten(0.2, baseColor)} ${(props) => props.valuePercent}%,
    ${lighten(0.2, baseColor)} 100%
  );
  outline: none;
  cursor: pointer;
  transition: background 0.3s ease;

  &::-webkit-slider-thumb {
    -webkit-appearance: none;
    appearance: none;
    width: 18px;
    height: 18px;
    background: ${teamColor};
    border-radius: 50%;
    border: 2px solid white;
    box-shadow: 0 0 4px rgba(0, 0, 0, 0.25);
    transition: background 0.3s ease;
  }

  &::-moz-range-thumb {
    width: 18px;
    height: 18px;
    background: ${teamColor};
    border-radius: 50%;
    border: 2px solid white;
    box-shadow: 0 0 4px rgba(0, 0, 0, 0.25);
  }

  &:hover::-webkit-slider-thumb {
    background: ${lighten(0.1, teamColor)};
  }
`;

const ValueInput = styled.input`
  width: 60px;
  padding: 8px;
  background: ${lighten(0.08, baseColor)};
  border: 1px solid ${lighten(0.2, baseColor)};
  border-radius: 8px;
  color: ${teamColor};
  font-weight: 600;
  text-align: center;
  font-size: 16px;
  transition: all 0.2s ease;

  &:focus {
    outline: none;
    border-color: ${teamColor};
    background: ${lighten(0.05, baseColor)};
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
  onChange = (val) => { },
}) {
  const [value, setValue] = useState(initial);
  const valuePercent = ((value - min) / (max - min)) * 100;

  const clampValue = (val) => Math.min(max, Math.max(min, val));

  const handleSliderChange = (e) => {
    const val = clampValue(Number(e.target.value));
    setValue(val);
    onChange(val);
  };

  const handleInputChange = (e) => {
    const val = e.target.value;
    if (val === "") {
      setValue("");
      return;
    }
    const num = Number(val);
    if (!isNaN(num)) {
      const clamped = clampValue(num);
      setValue(clamped);
      onChange(clamped);
    }
  };

  const handleInputBlur = () => {
    if (value === "" || isNaN(value)) {
      setValue(min);
    }
  };

  const increment = () => {
    const clamped = clampValue(Number(value) + step);
    setValue(clamped);
    onChange(clamped);
  };

  const decrement = () => {
    const clamped = clampValue(Number(value) - step);
    setValue(clamped);
    onChange(clamped);
  };

  return (
    <SliderWrapper className={className}>
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
