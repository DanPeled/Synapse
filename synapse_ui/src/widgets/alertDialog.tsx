"use client";

import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";

export function AlertDialog({
  visible: initialVisible,
  onClose,
  children,
  className,
}: {
  visible: boolean;
  onClose?: () => void;
  children: React.ReactNode;
  className?: string;
}) {
  const [rendered, setRendered] = useState(initialVisible);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (initialVisible) {
      setRendered(true);
      const timer = setTimeout(() => setVisible(true), 8);
      return () => clearTimeout(timer);
    } else {
      setVisible(false);
      const timer = setTimeout(() => {
        setRendered(false);
        onClose?.();
      }, 300);
      return () => clearTimeout(timer);
    }
  }, [initialVisible, onClose]);

  if (!rendered) return null;

  return (
    <div
      className={cn(
        "fixed inset-0 z-[1000] flex items-center justify-center bg-black/50 transition-opacity duration-300",
        visible
          ? "opacity-100 pointer-events-auto"
          : "opacity-0 pointer-events-none",
      )}
      onClick={onClose}
    >
      <div
        className={cn(
          "bg-zinc-900 text-white rounded-lg p-5 min-w-[300px] shadow-xl transform transition-transform duration-300",
          visible ? "scale-100" : "scale-95",
          className,
        )}
        onClick={(e) => e.stopPropagation()}
      >
        {children}
      </div>
    </div>
  );
}
