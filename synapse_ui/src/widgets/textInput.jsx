import React, { useState, useEffect } from "react";
import { styled } from "styled-components";
import { lighten, darken } from "polished";
import { getDivColor, teamColor } from "../services/style";
import Tooltip from "./tooltip";

// Styled Components
const Container = styled.div`
  box-sizing: border-box;
  width: ${(props) => props.$width || "95%"};
  max-width: 100%;
  opacity: ${(props) => (props.$disabled ? 0.5 : 1)};
  pointer-events: ${(props) => (props.$disabled ? "none" : "auto")};
  display: flex;
  flex-direction: column;
  overflow: visible;
`;

const InputWrapper = styled.div`
  box-sizing: border-box;
  width: 100%;
  background-color: ${darken(0.05, getDivColor())};
  border-radius: 12px;
  padding: 0px 14px;
  color: #eee;
  font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
  font-weight: 600;
  user-select: none;

  display: flex;
  align-items: center;
  gap: 12px;
  position: relative;
`;

const Label = styled.label`
  min-width: 0px;
  font-size: 18px;
  color: ${teamColor};
`;

const StyledInput = styled.input`
  box-sizing: border-box;
  min-width: 0;
  flex-grow: 1;
  background-color: ${lighten(0.15, getDivColor())};
  color: ${(props) => (props.$invalid ? "#ff6b6b" : "white")};
  padding: 8px 12px;
  border: none;
  border-radius: 8px;
  font-size: 18px;
  cursor: ${(props) => (props.disabled ? "not-allowed" : "text")};

  &:focus {
    outline: 2px solid ${lighten(0.15, getDivColor())};
    background-color: ${lighten(0.2, getDivColor())};
  }
`;

const ErrorText = styled.span`
  color: #ff6b6b;
  font-size: 14px;
  margin-top: 6px;
  user-select: none;
`;

export default function TextInput({
  label = "Input",
  initialValue = "",
  onChange = (_) => {},
  placeholder = "",
  pattern = "^.*$",
  errorMessage = "Invalid input",
  allowedChars = null,
  width,
  disabled = false,
  maxLength = null,
  tooltip = null,
}) {
  const [value, setValue] = useState(initialValue);
  const [invalid, setInvalid] = useState(false);
  const [hovered, setHovered] = useState(false);

  function handleChange(e) {
    let val = e.target.value;

    if (allowedChars) {
      const regex = new RegExp(allowedChars);
      val = [...val].filter((ch) => regex.test(ch)).join("");
    }

    if (maxLength !== null && val.length > maxLength) {
      val = val.slice(0, maxLength);
    }

    setValue(val);

    const patternRegex =
      pattern instanceof RegExp ? pattern : new RegExp(pattern);
    const isInvalid = val !== "" && !patternRegex.test(val);
    setInvalid(isInvalid);

    if (!isInvalid) {
      onChange(val);
    }
  }

  useEffect(() => {
    const regex = pattern instanceof RegExp ? pattern : new RegExp(pattern);
    setInvalid(value !== "" && !regex.test(value));
  }, [value, pattern]);

  return (
    <Container $width={width} $disabled={disabled}>
      <InputWrapper
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
      >
        {tooltip && <Tooltip visible={hovered}>{tooltip}</Tooltip>}
        <Label>{label}</Label>
        <StyledInput
          type="text"
          value={value}
          onChange={handleChange}
          placeholder={placeholder}
          $invalid={invalid}
          disabled={disabled}
          maxLength={maxLength}
        />
      </InputWrapper>
      {invalid && <ErrorText>{errorMessage}</ErrorText>}
    </Container>
  );
}
