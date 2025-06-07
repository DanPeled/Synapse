import React, { useState, useRef, useEffect } from "react";
import ReactDOM from "react-dom";
import { Menu } from "lucide-react";
import PropTypes from "prop-types";

export default function IconMenu({ icon = <Menu />, options = [] }) {
  const [open, setOpen] = useState(false);
  const [menuVisible, setMenuVisible] = useState(false);
  const [renderMenu, setRenderMenu] = useState(false);
  const iconRef = useRef(null);
  const [menuPosition, setMenuPosition] = useState({ top: 0, right: 0 });

  useEffect(() => {
    function handleClickOutside(e) {
      if (
        iconRef.current &&
        !iconRef.current.contains(e.target) &&
        !document.getElementById("icon-menu-portal")?.contains(e.target)
      ) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Animate menu mount/unmount
  useEffect(() => {
    if (open) {
      setRenderMenu(true);
      requestAnimationFrame(() => setMenuVisible(true));
    } else {
      setMenuVisible(false);
      setTimeout(() => setRenderMenu(false), 150);
    }
  }, [open]);

  // Update menu position when opened
  useEffect(() => {
    if (renderMenu && iconRef.current) {
      const rect = iconRef.current.getBoundingClientRect();
      setMenuPosition({
        top: rect.bottom + window.scrollY - 15,
        right: window.innerWidth - (rect.right) + 20,
      });
    }
  }, [renderMenu]);

  const menu = (
    <div
      id="icon-menu-portal"
      style={{
        position: "absolute",
        top: menuPosition.top,
        right: menuPosition.right,
        backgroundColor: "#121212",
        borderRadius: "10px",
        boxShadow: "0 8px 20px rgba(0,0,0,0.6)",
        padding: "10px",
        display: "flex",
        flexDirection: "column",
        gap: "8px",
        zIndex: 10000,
        transform: menuVisible ? "scale(1)" : "scale(0.95)",
        opacity: menuVisible ? 1 : 0,
        transition: "transform 150ms ease, opacity 150ms ease",
        transformOrigin: "top right",
      }}
      onMouseDown={(e) => e.stopPropagation()}
    >
      {options.map(({ icon, onClick, tooltip }, idx) => (
        <div
          key={idx}
          style={{ position: "relative", display: "inline-block" }}
        >
          <button
            onClick={() => {
              onClick?.();
              setOpen(false);
            }}
            style={{
              padding: "10px 14px",
              backgroundColor: "#761a53",
              border: "none",
              borderRadius: "6px",
              color: "white",
              textAlign: "left",
              cursor: "pointer",
              transition: "background-color 0.2s",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = "#a02978";
              const tooltipEl = e.currentTarget.nextSibling;
              if (tooltipEl) tooltipEl.style.opacity = 1;
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = "#761a53";
              const tooltipEl = e.currentTarget.nextSibling;
              if (tooltipEl) tooltipEl.style.opacity = 0;
            }}
          >
            {icon}
          </button>
          {tooltip && (
            <div
              style={{
                position: "absolute",
                top: "50%",
                right: "105%",
                transform: "translateY(-50%)",
                backgroundColor: "#222",
                color: "white",
                padding: "4px 8px",
                borderRadius: "4px",
                whiteSpace: "nowrap",
                fontSize: "12px",
                opacity: 0,
                pointerEvents: "none",
                transition: "opacity 0.2s",
                zIndex: 10001,
              }}
            >
              {tooltip}
            </div>
          )}
        </div>
      ))}
    </div>
  );

  return (
    <>
      <a
        ref={iconRef}
        onClick={() => setOpen(!open)}
        style={{
          display: "inline-block",
          borderRadius: "50%",
          padding: "10px",
          transition: "background-color 0.2s",
          cursor: "pointer",
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.backgroundColor = "rgba(138, 30, 96, 0.2)";
        }}
        onMouseLeave={(e) => {
          if (!open) e.currentTarget.style.backgroundColor = "transparent";
        }}
      >
        {icon}
      </a>
      {renderMenu && ReactDOM.createPortal(menu, document.body)}
    </>
  );
}

IconMenu.propTypes = {
  icon: PropTypes.node,
  options: PropTypes.arrayOf(
    PropTypes.shape({
      icon: PropTypes.node.isRequired,
      onClick: PropTypes.func,
      tooltip: PropTypes.string,
    }),
  ),
};
