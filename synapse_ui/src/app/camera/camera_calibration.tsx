import { useState } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { RefreshCw, Download, ChevronUp, ChevronDown, X } from "lucide-react";
import { Row } from "@/widgets/containers";
import { baseCardColor, teamColor } from "@/services/style";
import { AlertDialog } from "@/widgets/alertDialog";

// --- Calibration Data ---
const calibrationData = {
  timestamp: "2024-01-15 14:30:22",
  resolutionResults: [
    {
      resolution: "1920x1080",
      successful: 14,
      meanError: 0.298,
      maxError: 0.756,
      rmsError: 0.334,
      status: "excellent",
      cameraMatrix: { fx: 1234.56, fy: 1235.78, cx: 960.12, cy: 540.34 },
      distortionCoefficients: {
        k1: -0.2841,
        k2: 0.1024,
        p1: -0.0012,
        p2: 0.0008,
        k3: -0.0234,
      },
    },
    {
      resolution: "1280x720",
      successful: 12,
      meanError: 0.312,
      maxError: 0.623,
      rmsError: 0.341,
      status: "good",
      cameraMatrix: { fx: 823.04, fy: 823.85, cx: 640.08, cy: 360.23 },
      distortionCoefficients: {
        k1: -0.2856,
        k2: 0.1031,
        p1: -0.0011,
        p2: 0.0009,
        k3: -0.0241,
      },
    },
    {
      resolution: "640x480",
      successful: 16,
      meanError: 0.421,
      maxError: 0.892,
      rmsError: 0.456,
      status: "acceptable",
      cameraMatrix: { fx: 617.28, fy: 617.89, cx: 320.06, cy: 240.17 },
      distortionCoefficients: {
        k1: -0.2923,
        k2: 0.1087,
        p1: -0.0015,
        p2: 0.0012,
        k3: -0.0267,
      },
    },
  ],
};

const getStatusColor = (status: string) => {
  switch (status) {
    case "excellent":
      return "bg-green-500";
    case "good":
      return "bg-blue-500";
    case "acceptable":
      return "bg-yellow-500";
    default:
      return "bg-gray-500";
  }
};

function CalibrationHeader() {
  return (
    <div
      className="flex items-center justify-between"
      style={{ color: teamColor }}
    >
      <div className="flex items-center gap-3">
        <div>
          <h1 className="text-lg font-bold">Camera Intrinsic Calibration</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Determines the internal parameters of the camera lens to accurately
            map data from a 2D image into 3D space.
          </p>
        </div>
      </div>
      <Row className="items-center gap-3">
        <Button
          size="sm"
          style={{ color: teamColor }}
          className="hover:bg-zinc-700 cursor-pointer"
        >
          <Download className="w-4 h-4 mr-2" />
          Import Results
        </Button>
      </Row>
    </div>
  );
}

function ResolutionSelector({
  resolutions,
  selected,
  onSelect,
}: {
  resolutions: typeof calibrationData.resolutionResults;
  selected: (typeof calibrationData.resolutionResults)[number];
  onSelect: (res: (typeof calibrationData.resolutionResults)[number]) => void;
}) {
  const [calibrateResolutionVisible, setCalibrateResolutionVisible] =
    useState(false);

  return (
    <Card className="bg-zinc-900 border-gray-700" style={{ color: teamColor }}>
      <CardHeader className="pb-1">
        <CardTitle>Select Resolution</CardTitle>
        <CardDescription>
          View calibration parameters for specific resolution
        </CardDescription>
      </CardHeader>
      <CardContent className="pt-0">
        <Row className="items-center gap-2">
          {resolutions.map((result, index) => (
            <Button
              key={index}
              onClick={() => onSelect(result)}
              className={`${
                selected.resolution === result.resolution
                  ? "bg-stone-600 hover:bg-stone-500"
                  : "border-gray-600 bg-gray-700 hover:bg-gray-600 hover:border-zinc-700"
              } cursor-pointer`}
            >
              {result.resolution}
              <Badge
                className={`ml-2 ${getStatusColor(result.status)}`}
                variant="secondary"
              >
                {result.status}
              </Badge>
            </Button>
          ))}
          <Button
            variant="outline"
            size="sm"
            className="ml-4 border-gray-600 bg-gray-700 hover:bg-gray-600 hover:border-gray-500 cursor-pointer"
            style={{ color: teamColor }}
            onClick={() => {
              setCalibrateResolutionVisible(true);
            }}
          >
            <RefreshCw className="w-4 h-4 mr-2" />
            Calibrate
          </Button>
        </Row>

        <AlertDialog
          visible={calibrateResolutionVisible}
          onClose={() => setCalibrateResolutionVisible(false)}
          className="w-[80vw] h-[80vh]"
        >
          <Button
            onClick={() => setCalibrateResolutionVisible(false)}
            className="w-auto cursor-pointer hover:bg-zinc-700"
          >
            <span className="flex items-center justify-center gap-2">
              <X />
              Close
            </span>
          </Button>
        </AlertDialog>
      </CardContent>
    </Card>
  );
}

function CameraMatrixCard({
  data,
}: {
  data: (typeof calibrationData.resolutionResults)[number];
}) {
  return (
    <Card className="bg-zinc-900 border-gray-700" style={{ color: teamColor }}>
      <CardHeader>
        <CardTitle>Camera Matrix (K) - {data.resolution}</CardTitle>
        <CardDescription>
          Intrinsic camera parameters in pixel coordinates
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-3 gap-4 font-mono text-sm mb-4">
          <MatrixCell label="fx" value={data.cameraMatrix.fx} color="blue" />
          <MatrixCell label="0" value={0} />
          <MatrixCell label="cx" value={data.cameraMatrix.cx} color="green" />
          <MatrixCell label="0" value={0} />
          <MatrixCell label="fy" value={data.cameraMatrix.fy} color="blue" />
          <MatrixCell label="cy" value={data.cameraMatrix.cy} color="green" />
          <MatrixCell label="0" value={0} />
          <MatrixCell label="0" value={0} />
          <MatrixCell label="1" value={1} />
        </div>
        <div className="text-xs space-y-1">
          <p>
            <strong>fx, fy:</strong> Focal lengths
          </p>
          <p>
            <strong>cx, cy:</strong> Principal point
          </p>
        </div>
      </CardContent>
    </Card>
  );
}

function MatrixCell({
  label,
  value,
  color,
}: {
  label: string;
  value: number;
  color?: string;
}) {
  const bgColorMap: Record<string, string> = {
    red: "bg-red-700",
    green: "bg-green-700",
    blue: "bg-violet-600",
    gray: "bg-gray-700",
  };

  const textColorMap: Record<string, string> = {
    red: "text-red-300",
    green: "text-green-300",
    blue: "text-blue-300",
    gray: "text-gray-300",
  };

  const bgClass = bgColorMap[color ?? "gray"];
  const textClass = textColorMap[color ?? "gray"];

  return (
    <div
      className={`text-center p-3 rounded border border-gray-600 ${bgClass} 
        transform transition-transform duration-200 ease-in-out hover:scale-110`}
    >
      <div className={`font-semibold ${textClass}`}>{label}</div>
      <div className={textClass}>{value.toFixed(2)}</div>
    </div>
  );
}

function DistortionCoefficientsCard({
  data,
}: {
  data: (typeof calibrationData.resolutionResults)[number];
}) {
  return (
    <Card className="bg-zinc-900 border-gray-700" style={{ color: teamColor }}>
      <CardHeader>
        <CardTitle>Distortion Coefficients - {data.resolution}</CardTitle>
        <CardDescription>
          Radial and tangential distortion parameters
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          <div className="grid grid-cols-1 gap-3">
            {Object.entries(data.distortionCoefficients).map(([key, value]) => (
              <div
                key={key}
                className="flex items-center justify-between p-3 bg-gray-700 rounded border border-gray-600 
                           transform transition-transform duration-200 ease-in-out hover:scale-105"
              >
                <div className="flex items-center gap-3">
                  <Badge
                    variant="outline"
                    className="font-mono border-gray-500 text-gray-300"
                  >
                    {key}
                  </Badge>
                  <span className="text-sm">
                    {key.startsWith("k") ? "Radial" : "Tangential"}
                  </span>
                </div>
                <span className="font-mono font-semibold">
                  {value.toFixed(6)}
                </span>
              </div>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function ResolutionComparisonTable({
  resolutions,
  selected,
}: {
  resolutions: typeof calibrationData.resolutionResults;
  selected: string;
}) {
  return (
    <Card className="bg-zinc-900 border-gray-700" style={{ color: teamColor }}>
      <CardHeader>
        <CardTitle>Parameter Comparison Across Resolutions</CardTitle>
        <CardDescription>
          Compare focal lengths and principal points
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Table className="border-gray-700 items-center">
          <TableHeader>
            <TableRow className="border-gray-700 bg-zinc-800 hover:bg-zinc-800">
              <TableHead>Resolution</TableHead>
              <TableHead>fx</TableHead>
              <TableHead>fy</TableHead>
              <TableHead>cx</TableHead>
              <TableHead>cy</TableHead>
              <TableHead>Aspect Ratio</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {resolutions.map((result, index) => (
              <TableRow
                key={index}
                className={`border-gray-700 ${selected === result.resolution ? "bg-rose-900" : ""} hover:bg-`}
              >
                <TableCell className="font-mono">{result.resolution}</TableCell>
                <TableCell className="font-mono">
                  {result.cameraMatrix.fx.toFixed(2)}
                </TableCell>
                <TableCell className="font-mono">
                  {result.cameraMatrix.fy.toFixed(2)}
                </TableCell>
                <TableCell className="font-mono">
                  {result.cameraMatrix.cx.toFixed(2)}
                </TableCell>
                <TableCell className="font-mono">
                  {result.cameraMatrix.cy.toFixed(2)}
                </TableCell>
                <TableCell className="font-mono">
                  {(result.cameraMatrix.fx / result.cameraMatrix.fy).toFixed(4)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

export function CameraCalibrationModule() {
  const [selectedResolutionData, setSelectedResolutionData] = useState(
    calibrationData.resolutionResults[0],
  );

  const [showMoreInfo, setShowMoreInfo] = useState(false);

  return (
    <div style={{ color: teamColor }}>
      <div
        className="space-y-4"
        style={{
          backgroundColor: baseCardColor,
          borderRadius: "12px",
          padding: "24px",
        }}
      >
        <CalibrationHeader />

        <ResolutionSelector
          resolutions={calibrationData.resolutionResults}
          selected={selectedResolutionData}
          onSelect={setSelectedResolutionData}
        />

        {/* More Info Toggle Button below Select Resolution */}
        <div className="flex justify-center mt-2">
          <Button
            size="sm"
            variant="outline"
            onClick={() => setShowMoreInfo(!showMoreInfo)}
            className="flex items-center bg-zinc-800 hover:bg-zinc-700 cursor-pointer border-zinc-700"
            aria-expanded={showMoreInfo}
            aria-controls="detailed-info-section"
            style={{ color: teamColor }}
          >
            {showMoreInfo ? "Hide Details" : "Show Details"}
            {showMoreInfo ? (
              <ChevronUp className="w-4 h-4" />
            ) : (
              <ChevronDown className="w-4 h-4" />
            )}
          </Button>
        </div>

        {/* Collapsible Detailed Info Section */}
        <div
          id="detailed-info-section"
          className={`overflow-hidden transition-all duration-500 ease-in-out
                      ${showMoreInfo ? "max-h-[2000px] opacity-100 space-y-2" : "max-h-0 opacity-0 p-0"}`}
          style={{ color: teamColor }}
        >
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            <CameraMatrixCard data={selectedResolutionData} />
            <DistortionCoefficientsCard data={selectedResolutionData} />
          </div>
          <ResolutionComparisonTable
            resolutions={calibrationData.resolutionResults}
            selected={selectedResolutionData.resolution}
          />
        </div>
      </div>
    </div>
  );
}
