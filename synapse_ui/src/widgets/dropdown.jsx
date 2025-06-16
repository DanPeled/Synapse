import React, { useState, useRef, useEffect } from "react";
import ReactDOM from "react-dom";
import { lighten, darken } from "polished";
import { getDivColor, teamColor } from "../services/style";
import { styled } from "styled-components";
import Tooltip from "./tooltip";

const DropdownWrapper = styled.div`
  width: ${(props) => props.$width || "95%"};
  color: ${teamColor};
  font-family: "Inter", "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px;
  position: relative;
  transition: background-color 0.2s ease;
`;

const Label = styled.label`
  min-width: 80px;
  font-size: 18px;
  color: ${teamColor};
  opacity: ${(props) => (props.disabled ? 0.5 : 0.9)};
  font-weight: bold;
`;

const DropdownButton = styled.button`
  flex-grow: 1;
  width: 100%;
  background-color: ${(props) =>
    props.disabled ? darken(0.02, getDivColor()) : darken(0.1, getDivColor())};
  color: ${teamColor};
  padding: 10px 14px;
  border: 1px solid ${lighten(0.1, getDivColor())};
  border-radius: 10px;
  text-align: left;
  font-size: 16px;
  cursor: ${(props) => (props.disabled ? "not-allowed" : "pointer")};
  transition: all 0.2s ease;

  &:hover {
    background-color: ${(props) =>
    props.disabled
      ? darken(0.02, getDivColor())
      : darken(0.12, getDivColor())};
  }

  &:focus {
    outline: none;
    box-shadow: 0 0 0 2px ${lighten(0.2, getDivColor())};
  }
`;

const DropdownList = styled.ul`
  position: absolute;
  background-color: ${lighten(0.1, getDivColor())};
  border: 1px solid ${lighten(0.2, getDivColor())};
  border-radius: 10px;
  max-height: 220px;
  overflow-y: auto;
  padding: 4px 0;
  margin: 0;
  z-index: 9999;
  list-style: none;
  animation: fadeIn 0.15s ease-out;
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.15);

  @keyframes fadeIn {
    from {
      opacity: 0;
      transform: translateY(-5px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }
`;

const DropdownItem = styled.li`
  padding: 10px 14px;
  cursor: pointer;
  font-size: 15px;
  font-weight: ${(props) => (props.selected ? 600 : 400)};
  background: ${(props) => (props.selected ? darken(0.15, getDivColor()) : "transparent")};
  color: ${teamColor};
  transition: background 0.15s ease;

  &:hover {
    background-color: ${darken(0.2, getDivColor())};
  }
`;

const DropdownArrow = styled.span`
  position: absolute;
  right: 14px;
  top: 50%;
  transform: translateY(-50%)
    rotate(${(props) => (props.$open ? "180deg" : "0deg")});
  transition: transform 0.3s ease;
  pointer-events: none;
  font-size: 14px;
`;

function Dropdown({
  options,
  label = "Select",
  onChange = (val) => { },
  width = "auto",
  tooltip = "",
  disabled = false,
  initialValue = options[0].value
}) {
  const [selected, setSelected] = useState(
    initialValue,
  );
  const [open, setOpen] = useState(false);
  const [hovered, setHovered] = useState(false);
  const wrapperRef = useRef(null);
  const buttonRef = useRef(null);
  const [dropdownStyles, setDropdownStyles] = useState({});

  const handleSelect = (value) => {
    if (options.map((option) => option.value).includes(value)) {
      setSelected(value);
      setOpen(false);
      if (onChange) onChange(value);
    }
  };

  // Close dropdown if disabled while open
  useEffect(() => {
    if (disabled && open) {
      setOpen(false);
    }
  }, [disabled, open]);

  // Detect clicks outside the dropdown
  useEffect(() => {
    function handleClickOutside(event) {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  // Update dropdown position when opened
  useEffect(() => {
    if (open && buttonRef.current) {
      const rect = buttonRef.current.getBoundingClientRect();
      const dropdownMaxHeight = 200; // max-height in px
      const spaceBelow = window.innerHeight - rect.bottom;
      const spaceAbove = rect.top;
      let top, bottom;

      if (spaceBelow >= dropdownMaxHeight + 8) {
        top = rect.bottom + window.scrollY + 8 + "px"; // 8px gap
        bottom = "auto";
      } else if (spaceAbove >= dropdownMaxHeight + 8) {
        top = "auto";
        bottom = window.innerHeight - rect.top + window.scrollY + 8 + "px"; // 8px gap
      } else if (spaceBelow >= spaceAbove) {
        top = rect.bottom + window.scrollY + 8 + "px";
        bottom = "auto";
      } else {
        top = "auto";
        bottom = window.innerHeight - rect.top + window.scrollY + 8 + "px";
      }

      setDropdownStyles({
        left: rect.left + window.scrollX + "px",
        width: rect.width + "px",
        top,
        bottom,
        maxHeight: dropdownMaxHeight + "px",
        overflowY: "auto",
      });
    }
  }, [open]);

  const selectedLabel =
    options.find((opt) => (opt.value ?? opt) === selected)?.label ?? selected;

  return (
    <DropdownWrapper $width={width} ref={wrapperRef}>
      <Label disabled={disabled}>{label}</Label>
      <div style={{ position: "relative", flexGrow: 1 }}>
        <DropdownButton
          ref={buttonRef}
          onClick={() => {
            if (!disabled) setOpen((o) => !o);
          }}
          aria-haspopup="listbox"
          aria-expanded={open}
          onMouseEnter={() => !disabled && setHovered(true)}
          onMouseLeave={() => !disabled && setHovered(false)}
          disabled={disabled}
        >
          {selectedLabel}
          <DropdownArrow $open={open}>▾</DropdownArrow>
          {tooltip && <Tooltip visible={hovered}>{tooltip}</Tooltip>}
        </DropdownButton>
      </div>
      {open &&
        ReactDOM.createPortal(
          <DropdownList
            role="listbox"
            style={dropdownStyles}
            onMouseDown={(e) => e.stopPropagation()}
          >
            {options.map((opt, i) => {
              const val = opt.value ?? opt;
              const lbl = opt.label ?? opt;
              return (
                <DropdownItem
                  key={i}
                  onClick={() => handleSelect(val)}
                  role="option"
                  aria-selected={val === selected}
                  selected={val === selected}
                >
                  {lbl}
                </DropdownItem>
              );
            })}
          </DropdownList>,
          document.body,
        )}
    </DropdownWrapper>
  );
}

export default Dropdown;
