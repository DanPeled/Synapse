import React, { useState, useRef, useEffect } from "react";
import ReactDOM from "react-dom";
import { lighten, darken } from "polished";
import { getDivColor, teamColor } from "../services/style";
import { styled } from "styled-components";
import Tooltip from "./tooltip";

const DropdownWrapper = styled.div`
  width: ${(props) => props.$width || "95%"};
  background-color: ${lighten(0.1, getDivColor())};
  border-radius: 12px;
  padding: 10px 14px;
  color: ${teamColor};
  font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
  font-weight: 600;
  user-select: none;

  display: flex;
  align-items: center;
  gap: 12px;
  position: relative;
`;

const Label = styled.label`
  min-width: 80px;
  font-size: 18px;
  color: ${(props) => teamColor};
  opacity: ${(props) => (props.disabled ? 0.5 : 1)};
`;

const DropdownButton = styled.button`
  flex-grow: 1;
  width: 100%;
  background-color: ${(props) =>
    props.disabled ? darken(0.05, getDivColor()) : darken(0.15, getDivColor())};
  color: ${teamColor};
  padding: 8px 12px;
  border: none;
  border-radius: 8px;
  text-align: left;
  font-size: 18px;
  cursor: ${(props) => (props.disabled ? "not-allowed" : "pointer")};
  position: relative;
  opacity: ${(props) => (props.disabled ? 0.5 : 1)};

  &:focus {
    outline: ${(props) =>
      props.disabled ? "none" : `2px solid ${lighten(0.15, getDivColor())}`};
    background-color: ${(props) =>
      props.disabled
        ? darken(0.05, getDivColor())
        : darken(0.2, getDivColor())};
  }
`;

const DropdownList = styled.ul`
  position: absolute;
  background-color: ${lighten(0.15, getDivColor())};
  border-radius: 8px;
  max-height: 200px;
  overflow-y: auto;
  padding: 0;
  margin: 0;
  z-index: 9999;
  list-style: none;
  animation: fadeIn 0.2s ease-out;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
  color: ${teamColor};

  @keyframes fadeIn {
    from {
      opacity: 0;
      transform: scaleY(0.95);
    }
    to {
      opacity: 1;
      transform: scaleY(1);
    }
  }
`;

const DropdownItem = styled.li`
  padding: 10px 12px;
  cursor: pointer;
  color: ${teamColor};
  font-weight: ${(props) => (props.selected ? "bold" : "normal")};

  &:hover {
    background-color: ${darken(0.25, getDivColor())};
  }
`;

const DropdownArrow = styled.span`
  position: absolute;
  right: 12px;
  top: 50%;
  pointer-events: none;
  transition: transform 0.3s ease;
  transform-origin: center;
  transform: translateY(-50%)
    rotate(${(props) => (props.$open ? "180deg" : "0deg")});
`;

// Component

function Dropdown({
  options,
  label = "Select",
  onChange,
  width,
  tooltip,
  disabled = false,
}) {
  const [selected, setSelected] = useState(
    options.length > 0 ? (options[0].value ?? options[0]) : "",
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
