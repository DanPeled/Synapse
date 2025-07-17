import React, { useMemo } from "react";
import { LogMessageProto } from "@/proto/v1/log";
import { AlertDialog } from "@/widgets/alertDialog";
import { Button } from "@/widgets/button";
import { Column, Row } from "@/widgets/containers";
import { X } from "lucide-react";

const TAG_STYLES: Record<string, React.CSSProperties> = {
  bold: { fontWeight: "bold" },
  green: { color: "green" },
  red: { color: "red" },
  yellow: { color: "yellow" },
};

function parseStyledMessage(message: string): React.ReactNode[] {
  const stack: string[] = [];
  const output: React.ReactNode[] = [];

  let i = 0;
  let textBuffer = "";

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
            if (stack.length && stack[stack.length - 1] === tagName) {
              stack.pop();
            }
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

interface ProgramLogsDialogProps {
  visible: boolean;
  setVisible: (visible: boolean) => void;
  logs: LogMessageProto[];
}

export function ProgramLogsDialog({
  visible,
  setVisible,
  logs,
}: ProgramLogsDialogProps) {
  const filteredAndParsedLogs = useMemo(() => {
    return logs
      .filter(
        (log) =>
          !/^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\]:\s*$/.test(log.message),
      )
      .map((log) => ({
        key: log.timestamp,
        content: parseStyledMessage(log.message),
      }));
  }, [logs]);

  return (
    <AlertDialog
      visible={visible}
      onClose={() => setVisible(false)}
      className="w-[80vw] h-[80vh]"
      aria-label="Program Logs Dialog"
    >
      <Column className="h-full">
        <Row className="justify-end p-2">
          <Button onClickAction={() => setVisible(false)} className="w-auto">
            <span
              className="flex items-center justify-center gap-2 text-sm"
              aria-label="Close logs dialog"
            >
              <X aria-hidden="true" size={14} />
              Close
            </span>
          </Button>
        </Row>

        {/* Scrollable logs container */}
        <div
          className="flex-grow overflow-y-auto px-4 font-mono scrollbar scrollbar-thumb-gray-500 scrollbar-track-gray-200"
          role="log"
          aria-live="polite"
        >
          {filteredAndParsedLogs.map(({ key, content }) => (
            <div key={key} className="mb-1">
              {content}
            </div>
          ))}
        </div>
      </Column>
    </AlertDialog>
  );
}
