import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { baseCardColor, teamColor } from "@/services/style";
import { Activity } from "lucide-react";

export function ResultsView() {
  return (
    <Card
      style={{ backgroundColor: baseCardColor }}
      className="border-gray-700 min-h-0 flex flex-col"
    >
      <CardHeader></CardHeader>
      <CardContent
        className="flex-grow flex items-center justify-center min-h-140"
        style={{ color: teamColor }}
      >
        <div className="text-center">
          <Activity className="w-16 h-16 mx-auto mb-2 opacity-50" />
          <p className="select-none">Pipeline Results</p>
          <p className="text-sm select-none">Results will appear here</p>
        </div>
      </CardContent>
    </Card>
  );
}
