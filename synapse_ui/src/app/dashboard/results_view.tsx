import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { PipelineResultMap } from "@/services/backend/dataStractures";
import { protoToSettingValue } from "@/services/controls_generator";
import { baseCardColor, teamColor } from "@/services/style";
import { Column } from "@/widgets/containers";
import { Placeholder } from "@/widgets/placeholder";
import { Activity } from "lucide-react";

export function ResultsView({ results }: { results?: PipelineResultMap }) {
  return (
    <Card
      style={{ backgroundColor: baseCardColor }}
      className="border-gray-700 min-h-0 flex flex-col"
    >
      <CardHeader>
        {results && results.size > 0 && (
          <div
            className="text-center justify-center flex font-bold flex-col"
            style={{ color: teamColor }}
          >
            <h1 className="text-2xl">Pipeline Results</h1>
            <div
              className="flex h-1 w-full"
              style={{ backgroundColor: teamColor }}
            ></div>
          </div>
        )}
      </CardHeader>
      <CardContent
        className={cn(
          "flex-grow flex min-h-132",
          results && results.size > 0 ? "" : "items-center justify-center",
        )}
        style={{ color: teamColor }}
      >
        {results && results.size > 0 ? (
          <Column>
            {Array.from(results.entries()).map(([key, value]) => (
              <div key={key}>
                <p className="text-lg">
                  {key} :{" "}
                  {value.value === undefined
                    ? ""
                    : String(protoToSettingValue(value.value))}
                </p>
                <br />
              </div>
            ))}
          </Column>
        ) : (
          <div className="text-center">
            <Activity className="w-16 h-16 mx-auto mb-2 opacity-50" />
            <p className="select-none">Pipeline Results</p>
            <p className="text-sm select-none">Results will appear here</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
