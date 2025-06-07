import React, { useState, useEffect } from "react";

function AlertDialog({ visible: initialVisible, onClose, children, style }) {
  const [rendered, setRendered] = useState(initialVisible);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (initialVisible) {
      setRendered(true); // mount dialog immediately
      // Trigger animation to visible on next tick
      const timer = setTimeout(() => setVisible(true), 8);
      return () => clearTimeout(timer);
    } else {
      // Start fade-out
      setVisible(false);
      // After fade out, unmount and call onClose
      const timer = setTimeout(() => {
        setRendered(false);
        onClose?.();
      }, 300);
      return () => clearTimeout(timer);
    }
  }, [initialVisible, onClose]);

  if (!rendered) return null;

  const styles = {
    overlay: {
      position: "fixed",
      top: 0,
      left: 0,
      width: "100vw",
      height: "100vh",
      backgroundColor: "rgba(0,0,0,0.5)",
      display: "flex",
      justifyContent: "center",
      alignItems: "center",
      zIndex: 1000,
      opacity: visible ? 1 : 0,
      pointerEvents: visible ? "auto" : "none",
      transition: "opacity 300ms ease",
    },
    dialog: {
      backgroundColor: "rgb(20, 20, 20)",
      padding: 20,
      borderRadius: 8,
      minWidth: 300,
      boxShadow: "0 5px 15px rgba(0,0,0,0.3)",
      transform: visible ? "scale(1)" : "scale(0.9)",
      transition: "transform 300ms ease",
      color: "white",
    },
  };

  return (
    <div style={styles.overlay} onClick={onClose}>
      <div
        style={{ ...styles.dialog, ...style }}
        onClick={(e) => e.stopPropagation()}
      >
        {children}
      </div>
    </div>
  );
}

export default AlertDialog;
