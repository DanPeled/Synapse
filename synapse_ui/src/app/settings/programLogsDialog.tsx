import React, { useMemo, useState } from "react";
import { LogMessageProto, LogLevelProto } from "@/proto/v1/log";
import { AlertDialog } from "@/widgets/alertDialog";
import { Button } from "@/widgets/button";
import { Column, Row } from "@/widgets/containers";
import { X, Info, AlertTriangle, XCircle } from "lucide-react";

// Tag styles for [red], [green], [bold], etc.
const TAG_STYLES: Record<string, React.CSSProperties> = {
  bold: { fontWeight: "bold" },
  green: { color: "green" },
  red: { color: "red" },
  yellow: { color: "orange" },
  blue: { color: "blue" },
};

function parseStyledMessage(message: string): React.ReactNode[] {
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

interface ProgramLogsDialogProps {
  visible: boolean;
  setVisible: (visible: boolean) => void;
  logs: LogMessageProto[];
  onClose?: () => void;
}

// Only these log levels
const LOG_LEVELS = [
  LogLevelProto.LOG_LEVEL_PROTO_INFO,
  LogLevelProto.LOG_LEVEL_PROTO_WARNING,
  LogLevelProto.LOG_LEVEL_PROTO_ERROR,
];

// Icons for log levels
const LOG_LEVEL_ICONS: Record<LogLevelProto, React.ReactNode> = {
  [LogLevelProto.UNRECOGNIZED]: <Info size={14} />,
  [LogLevelProto.LOG_LEVEL_PROTO_UNSPECIFIED]: <Info size={14} />,
  [LogLevelProto.LOG_LEVEL_PROTO_INFO]: <Info size={14} />,
  [LogLevelProto.LOG_LEVEL_PROTO_WARNING]: <AlertTriangle size={14} />,
  [LogLevelProto.LOG_LEVEL_PROTO_ERROR]: <XCircle size={14} />,
};

// Colors for log levels
const LOG_LEVEL_COLORS: Record<
  LogLevelProto,
  {
    background: string;
    color: string;
    border: string;
    hoverBackground: string;
    hoverBorder: string;
  }
> = {
  [LogLevelProto.UNRECOGNIZED]: {
    background: "#3B82F6",
    color: "white",
    border: "#2563EB",
    hoverBackground: "#2563EB",
    hoverBorder: "#1D4ED8",
  },
  [LogLevelProto.LOG_LEVEL_PROTO_UNSPECIFIED]: {
    background: "#3B82F6",
    color: "white",
    border: "#2563EB",
    hoverBackground: "#2563EB",
    hoverBorder: "#1D4ED8",
  },
  [LogLevelProto.LOG_LEVEL_PROTO_INFO]: {
    background: "#3B82F6",
    color: "white",
    border: "#2563EB",
    hoverBackground: "#2563EB",
    hoverBorder: "#1D4ED8",
  },
  [LogLevelProto.LOG_LEVEL_PROTO_WARNING]: {
    background: "#FACC15",
    color: "black",
    border: "#EAB308",
    hoverBackground: "#EAB308",
    hoverBorder: "#CA8A04",
  },
  [LogLevelProto.LOG_LEVEL_PROTO_ERROR]: {
    background: "#EF4444",
    color: "white",
    border: "#DC2626",
    hoverBackground: "#DC2626",
    hoverBorder: "#B91C1C",
  },
};

export function ProgramLogsDialog({
  visible,
  setVisible,
  logs,
  onClose = () => {},
}: ProgramLogsDialogProps) {
  const [searchQuery, setSearchQuery] = useState("");

  // Initialize all levels as active
  const [activeLevels, setActiveLevels] = useState<
    Record<LogLevelProto, boolean>
  >(() => {
    const initial: Record<LogLevelProto, boolean> = {} as Record<
      LogLevelProto,
      boolean
    >;
    LOG_LEVELS.forEach((lvl) => {
      initial[lvl] = true;
    });
    return initial;
  });

  const toggleLevel = (lvl: LogLevelProto) =>
    setActiveLevels((prev) => ({ ...prev, [lvl]: !prev[lvl] }));

  // Filter logs by search + active levels
  const filteredLogs = useMemo(() => {
    return logs
      .filter((log) => {
        if (/^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\]:\s*$/.test(log.message))
          return false;
        if (
          searchQuery &&
          !log.message.toLowerCase().includes(searchQuery.toLowerCase())
        )
          return false;
        if (!activeLevels[log.level]) return false;
        return true;
      })
      .map((log) => ({
        key: log.timestamp,
        content: parseStyledMessage(log.message),
      }));
  }, [logs, searchQuery, activeLevels]);

  return (
    <AlertDialog
      visible={visible}
      onClose={() => {
        setVisible(false);
        onClose();
      }}
      className="w-[80vw] h-[90vh]"
      aria-label="Program Logs Dialog"
    >
      <Column className="h-full gap-5">
        <Row className="justify-between items-center p-2 gap-2">
          <input
            type="text"
            placeholder="Search logs..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-200 border rounded px-2 py-2 text-lg focus:outline-none focus:ring focus:ring-blue-400 border-zinc-800"
          />

          <div className="flex gap-1">
            {LOG_LEVELS.map((lvl) => (
              <Button
                key={lvl}
                onClickAction={() => toggleLevel(lvl)}
                enabledColors={
                  activeLevels[lvl]
                    ? LOG_LEVEL_COLORS[lvl]
                    : {
                        background: "#4B5060",
                        color: "#8A8F9C",
                        border: "#5A6074",
                        hoverBackground: "#5A6074",
                        hoverBorder: "#6B7080",
                      }
                }
                className="flex items-center gap-1 text-sm font-medium h-10"
              >
                <span className="align-middle">{LOG_LEVEL_ICONS[lvl]}</span>
                <span className="leading-none">
                  {LogLevelProto[lvl].replace("LOG_LEVEL_PROTO_", "")}
                </span>
              </Button>
            ))}
          </div>

          <Button
            onClickAction={() => {
              onClose();
              setVisible(false);
            }}
            enabledColors={{
              background: "#2A2D34",
              color: "#fff",
              border: "#3F4451",
              hoverBackground: "#3B4050",
              hoverBorder: "#5A6074",
            }}
            className="flex items-center gap-1 px-2 py-1 text-sm font-medium"
          >
            <X size={20} />
          </Button>
        </Row>

        {/* Scrollable logs */}
        <div
          className="flex-grow overflow-y-auto px-4 font-mono scrollbar scrollbar-thumb-gray-500 scrollbar-track-gray-200"
          role="log"
          aria-live="polite"
        >
          {filteredLogs.length > 0 ? (
            filteredLogs.map(({ key, content }) => (
              <div key={key} className="mb-1">
                {content}
              </div>
            ))
          ) : (
            <div className="text-gray-500 italic">No logs found.</div>
          )}
        </div>
      </Column>
    </AlertDialog>
  );
}
