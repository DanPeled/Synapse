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
    let timer1: ReturnType<typeof setTimeout>;
    let timer2: ReturnType<typeof setTimeout>;

    if (initialVisible) {
      setRendered(true);
      timer1 = setTimeout(() => setVisible(true), 10);
    } else {
      setVisible(false);
      timer2 = setTimeout(() => {
        setRendered(false);
        onClose?.();
      }, 300);
    }

    return () => {
      clearTimeout(timer1);
      clearTimeout(timer2);
    };
  }, [initialVisible, onClose]);

  if (!rendered) return null;

  return (
    <div
      className={cn(
        "fixed inset-0 z-[1000] flex items-center justify-center bg-black/50 transition-opacity duration-300 ease-in-out",
        visible
          ? "opacity-100 pointer-events-auto"
          : "opacity-0 pointer-events-none",
      )}
      onClick={onClose}
    >
      <div
        className={cn(
          "bg-zinc-900 text-white rounded-lg p-5 min-w-[300px] shadow-xl transform transition-transform duration-300 ease-in-out",
          visible ? "scale-100" : "scale-90", // scale down more on exit for stronger effect
          className,
        )}
        onClick={(e) => e.stopPropagation()}
      >
        {children}
      </div>
    </div>
  );
}
