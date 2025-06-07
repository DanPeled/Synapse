import React from "react";
import { styled } from "styled-components";
import { darken } from "polished";
import { getDivColor } from "../services/style";

const TooltipWrapper = styled.div`
  position: absolute;
  bottom: 100%;
  left: 50%;
  transform: translateX(-50%) translateY(-8px);
  background-color: ${darken(0.2, getDivColor())};
  color: #eee;
  padding: 6px 10px;
  border-radius: 8px;
  font-size: 14px;
  white-space: nowrap;
  pointer-events: none;
  user-select: none;
  opacity: 0;
  transition: opacity 0.15s ease-in-out;
  z-index: 10000;

  &::after {
    content: "";
    position: absolute;
    top: 100%;
    left: 50%;
    margin-left: -6px;
    border-width: 6px;
    border-style: solid;
    border-color: ${darken(0.2, getDivColor())} transparent transparent
      transparent;
  }

  &.visible {
    opacity: 1;
  }
`;

export default function Tooltip({ children, visible }) {
  return (
    <TooltipWrapper className={visible ? "visible" : ""}>
      {children}
    </TooltipWrapper>
  );
}
