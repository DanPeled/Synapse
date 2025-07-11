import React from "react";
import { cn } from "@/lib/utils";
import { Row } from "./containers";

interface LabeledControlProps {
  label: string;
  children: React.ReactNode;
  className?: string;
}

export default function LabeledControl({
  label,
  children,
  className,
}: LabeledControlProps) {
  return (
    <div className={cn("flex items-center gap-4 my-2", className)}>
      <div className="min-w-[150px] text-right font-medium">{label}</div>
      <Row className="flex-1 items-center" gap="gap-3">
        {children}
      </Row>
    </div>
  );
}
