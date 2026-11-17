import React from "react";

const TAG_STYLES: Record<string, React.CSSProperties> = {
  bold: { fontWeight: "bold" },
  green: { color: "green" },
  red: { color: "red" },
  yellow: { color: "orange" },
  blue: { color: "blue" },
};

export function parseStyledMessage(message: string): React.ReactNode[] {
  const stack: string[] = [];
  const output: React.ReactNode[] = [];
  let textBuffer = "";
  let i = 0;

  const flushText = () => {
    if (!textBuffer) return;
    let element: React.ReactNode = textBuffer;
    for (let j = stack.length - 1; j >= 0; j--) {
      const style = TAG_STYLES[stack[j]];
      if (style) {
        element = (
          <span style={style} key={`${stack[j]}-${output.length}`}>
            {element}
          </span>
        );
      }
    }
    output.push(
      <span className="whitespace-pre-wrap" key={`text-${output.length}`}>
        {element}
      </span>,
    );
    textBuffer = "";
  };

  while (i < message.length) {
    if (message[i] === "[") {
      const closeIndex = message.indexOf("]", i);
      if (closeIndex !== -1) {
        const tagContent = message.slice(i + 1, closeIndex).trim();
        const isClosing = tagContent.startsWith("/");
        const tagName = isClosing ? tagContent.slice(1) : tagContent;

        if (TAG_STYLES[tagName]) {
          flushText();
          if (isClosing) {
            if (stack.length && stack[stack.length - 1] === tagName)
              stack.pop();
          } else {
            stack.push(tagName);
          }
          i = closeIndex + 1;
          continue;
        }
      }
    }
    textBuffer += message[i];
    i++;
  }
  flushText();
  return output;
}
