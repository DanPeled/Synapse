import React, { forwardRef } from "react";
import { cn } from "@/lib/utils";

type Alignment = "start" | "center" | "end" | "baseline" | "stretch";
type Justify = "start" | "center" | "end" | "between" | "around" | "evenly";

interface FlexProps extends React.HTMLAttributes<HTMLDivElement> {
  gap?: string;
  align?: Alignment;
  justify?: Justify;
  wrap?: boolean;
}

export const Row = forwardRef<HTMLDivElement, FlexProps>(function Row(
  { children, className, gap, align, justify, wrap = false, ...props },
  ref,
) {
  const alignClass = align ? `items-${align}` : "";
  const justifyClass = justify ? `justify-${justify}` : "";
  const wrapClass = wrap ? "flex-wrap" : "flex-nowrap";

  return (
    <div
      ref={ref}
      className={cn(
        "flex flex-row flex-wrap",
        "max-sm:flex-col",
        alignClass,
        justifyClass,
        gap,
        wrapClass,
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
});

export const Column = forwardRef<HTMLDivElement, FlexProps>(function Column(
  { children, className, gap = "", align, justify, wrap, ...props },
  ref,
) {
  const alignClass = align ? `items-${align}` : "";
  const justifyClass = justify ? `justify-${justify}` : "";
  const wrapClass = wrap ? "flex-wrap" : "flex-nowrap";

  return (
    <div
      ref={ref}
      className={cn(
        "flex flex-col",
        alignClass,
        justifyClass,
        gap,
        wrapClass,
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
});
