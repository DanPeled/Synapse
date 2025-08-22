import { useState } from "react";
import { Table, TableBody, TableCell, TableRow } from "@/components/ui/table";
import { ChevronRight } from "lucide-react";
import { decode } from "@msgpack/msgpack";
import { teamColor } from "@/services/style";

function TreeNode({
  label,
  value,
  depth = 0,
  path = "",
  expandedMap,
  setExpandedMap,
}: {
  label?: string;
  value: unknown;
  depth?: number;
  path?: string;
  expandedMap: Record<string, boolean>;
  setExpandedMap: (map: Record<string, boolean>) => void;
}) {
  const isArray = Array.isArray(value);
  const isObject = typeof value === "object" && value !== null && !isArray;

  const expanded = expandedMap[path] || false;

  const toggle = () => {
    if (isArray || isObject) {
      setExpandedMap({ ...expandedMap, [path]: !expanded });
    }
  };

  return (
    <>
      <TableRow
        onClick={toggle}
        className="hover:bg-zinc-800/60 transition-colors cursor-pointer"
        style={{ borderColor: teamColor }}
      >
        <TableCell style={{ paddingLeft: depth * 16 }}>
          <div className="flex items-center">
            {isArray || isObject ? (
              <ChevronRight
                className={`w-4 h-4 mr-1 transition-transform duration-200 ease-in-out ${
                  expanded ? "rotate-90" : ""
                }`}
                style={{ color: teamColor }}
              />
            ) : (
              <span className="w-4 h-4 mr-1" />
            )}
            {label && (
              <span
                className="font-medium"
                style={{ color: depth > 0 ? "#de4ba6" : teamColor }}
              >
                {label}
              </span>
            )}
          </div>
        </TableCell>
        <TableCell>
          {!isArray && !isObject && (
            <span style={{ color: teamColor }}>{String(value)}</span>
          )}
          {isArray && (
            <span className="text-gray-700 italic select-none">
              [{value.length}]
            </span>
          )}
          {isObject && (
            <span className="text-gray-700 italic select-none">{`{...}`}</span>
          )}
        </TableCell>
      </TableRow>

      {(isArray || isObject) && expanded && (
        <>
          {isArray
            ? (value as unknown[]).map((val, idx) => (
                <TreeNode
                  key={idx}
                  label={`[${idx}]`}
                  value={val}
                  depth={depth + 1}
                  path={`${path}[${idx}]`}
                  expandedMap={expandedMap}
                  setExpandedMap={setExpandedMap}
                />
              ))
            : Object.entries(value as Record<string, unknown>).map(([k, v]) => (
                <TreeNode
                  key={k}
                  label={k}
                  value={v}
                  depth={depth + 1}
                  path={`${path}.${k}`}
                  expandedMap={expandedMap}
                  setExpandedMap={setExpandedMap}
                />
              ))}
        </>
      )}
    </>
  );
}

export function MsgPackTree({
  encoded,
  name,
}: {
  encoded: Uint8Array | ArrayBuffer;
  name: string;
}) {
  const [expandedMap, setExpandedMap] = useState<Record<string, boolean>>({});

  let decoded: unknown;
  try {
    decoded = decode(
      encoded instanceof ArrayBuffer ? new Uint8Array(encoded) : encoded,
    );
  } catch (e) {
    return (
      <TableRow
        key={String(encoded)}
        className="hover:bg-zinc-800/60 transition-colors"
        style={{ borderColor: teamColor }}
      >
        <TableCell colSpan={2} className="text-red-500">
          Failed to decode MsgPack: {String(e)}
        </TableCell>
      </TableRow>
    );
  }

  return (
    <Table>
      <TableBody>
        <TreeNode
          label={name}
          value={decoded}
          depth={0}
          path={name}
          expandedMap={expandedMap}
          setExpandedMap={setExpandedMap}
        />
      </TableBody>
    </Table>
  );
}
