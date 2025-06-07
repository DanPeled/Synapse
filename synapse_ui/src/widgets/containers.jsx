import React from "react";

/**
 * A flex container that arranges its children horizontally in a row.
 * Supports wrapping of children onto multiple lines and spacing between them.
 *
 * @param {object} props
 * @param {React.ReactNode} props.children - The content to be rendered inside the row.
 * @param {React.CSSProperties} [props.style={}] - Optional additional inline styles to apply.
 * @param {object} [rest] - Other props passed to the container div.
 */
export function Row({ children, style = {}, fitMaxWidth = false, ...props }) {
  // If fitMaxWidth is true, clone children to add flex: 1 style
  const childrenWithFlex = fitMaxWidth
    ? React.Children.map(children, (child) => {
      if (React.isValidElement(child)) {
        // Merge child's existing style with flex: 1
        const childStyle = { ...(child.props.style || {}), flex: 1 };
        return React.cloneElement(child, { style: childStyle });
      }
      return child;
    })
    : children;

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "row",
        alignItems: "flex-start",
        width: "100%",
        height: "auto",
        gap: 12,
        ...style,
      }}
      {...props}
    >
      {childrenWithFlex}
    </div>
  );
}

/**
 * A flex container that arranges its children vertically in a column.
 * Supports wrapping of children and spacing between them.
 *
 * @param {object} props
 * @param {React.ReactNode} props.children - The content to be rendered inside the column.
 * @param {React.CSSProperties} [props.style={}] - Optional additional inline styles to apply.
 * @param {object} [rest] - Other props passed to the container div.
 */
export function Column({ children, style = {}, ...props }) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 12,
        ...style,
      }}
      {...props}
    >
      {children}
    </div>
  );
}
