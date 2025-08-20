import { useState } from "react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { PipelineResultMap } from "@/services/backend/dataStractures";
import { protoToSettingValue } from "@/services/controls_generator";
import { baseCardColor, teamColor } from "@/services/style";
import { Activity, Copy, Check } from "lucide-react";
import { Table, TableBody, TableCell, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

export function ResultsView({ results }: { results?: PipelineResultMap }) {
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  const copyToClipboard = (key: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(key);
    toast.success("Copied to clipboard!", {
      duration: 1000,
      style: {
        color: teamColor,
        backgroundColor: "rgb(30, 30, 30)",
        border: "none",
      },
    });
    setTimeout(() => setCopiedKey(null), 1500);
  };

  return (
    <>
      <Card
        style={{ backgroundColor: baseCardColor }}
        className="border-gray-700 min-h-0 flex flex-col shadow-lg rounded-2xl"
      >
        <CardContent
          className={cn(
            "flex-grow flex min-h-132 overflow-x-auto",
            results && results.size > 0 ? "" : "items-center justify-center",
          )}
          style={{ color: teamColor }}
        >
          <div className="flex-grow flex-col">
            {results && results.size > 0 && (
              <div
                className="text-center justify-center flex font-bold flex-col"
                style={{ color: teamColor }}
              >
                <div className="flex items-center gap-2 justify-center">
                  <Activity
                    className="w-5 opacity-50"
                    style={{ color: teamColor }}
                  />
                  <h1 className="text-2xl">Pipeline Results</h1>
                </div>
                <div
                  className="flex h-1 w-full rounded-full mt-2"
                  style={{ backgroundColor: teamColor }}
                />
              </div>
            )}
            {results && results.size > 0 ? (
              <Table>
                <TableBody>
                  {Array.from(results.entries()).map(([key, value]) => {
                    const val =
                      value.value === undefined
                        ? ""
                        : String(protoToSettingValue(value.value));
                    return (
                      <TableRow
                        key={key}
                        className="hover:bg-zinc-800/60 transition-colors"
                        style={{
                          borderColor: teamColor,
                        }}
                      >
                        <TableCell className="font-medium">{key}</TableCell>
                        <TableCell className="truncate max-w-xs">
                          {val}
                        </TableCell>
                        <TableCell className="text-right">
                          {val && (
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => copyToClipboard(key, val)}
                              className="hover:bg-zinc-700 rounded-xl cursor-pointer"
                            >
                              {copiedKey === key ? (
                                <Check
                                  className="h-4 w-4"
                                  style={{ color: teamColor }}
                                />
                              ) : (
                                <Copy
                                  className="h-4 w-4"
                                  style={{ color: teamColor }}
                                />
                              )}
                            </Button>
                          )}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            ) : (
              <div className="text-center">
                <Activity className="w-16 h-16 mx-auto mb-2 opacity-50" />
                <p className="select-none">Pipeline Results</p>
                <p className="text-sm select-none">Results will appear here</p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </>
  );
}
