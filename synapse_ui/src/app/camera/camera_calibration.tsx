import { useEffect, useState } from "react";
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
  RefreshCw,
  Download,
  ChevronUp,
  ChevronDown,
  Trash,
} from "lucide-react";
import { Row } from "@/widgets/containers";
import { baseCardColor, teamColor } from "@/services/style";
import { CalibrationDialog } from "./calibration_dialog";
import { CalibrationDataProto, CameraProto } from "@/proto/v1/camera";
import { WebSocketWrapper } from "@/services/websocket";
import { useBackendContext } from "@/services/backend/backendContext";

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
  selectedCamera,
  socket,
}: {
  resolutions: string[];
  selected?: CalibrationDataProto;
  onSelect: (res: string) => void;
  selectedCamera?: CameraProto;
  socket?: WebSocketWrapper;
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
          {resolutions.map((resolution) => (
            <Button
              key={resolution}
              onClick={() => onSelect(resolution)}
              className={`${
                selected?.resolution === resolution
                  ? "bg-stone-600 hover:bg-stone-500"
                  : "border-gray-600 bg-gray-700 hover:bg-gray-600 hover:border-zinc-700"
              } cursor-pointer`}
            >
              {resolution}
              <Badge className={`ml-2`} variant="secondary">
                {/* {status} */}
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

        <CalibrationDialog
          visible={calibrateResolutionVisible}
          setVisible={setCalibrateResolutionVisible}
          initialResolution={selected?.resolution}
          camera={selectedCamera}
          socket={socket}
        />
      </CardContent>
    </Card>
  );
}

function CameraMatrixCard({ data }: { data: CalibrationDataProto }) {
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
          <MatrixCell
            label="fx"
            value={data.cameraMatrix.at(0) ?? 0}
            color="blue"
          />
          <MatrixCell label="0" value={0} />
          <MatrixCell
            label="cx"
            value={data.cameraMatrix.at(2) ?? 0}
            color="green"
          />
          <MatrixCell label="0" value={0} />
          <MatrixCell
            label="fy"
            value={data.cameraMatrix.at(4) ?? 0}
            color="blue"
          />
          <MatrixCell
            label="cy"
            value={data.cameraMatrix.at(5) ?? 0}
            color="green"
          />
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

function DistortionCoefficientsCard({ data }: { data: CalibrationDataProto }) {
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
            {Object.entries(data.distCoeffs).map(([key, value]) => (
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

export function CameraCalibrationModule({
  selectedCamera,
  socket,
}: {
  selectedCamera?: CameraProto;
  socket?: WebSocketWrapper;
}) {
  const [selectedResolutionData, setSelectedResolutionData] = useState<
    CalibrationDataProto | undefined
  >(undefined);

  const [resolutions, setResolutions] = useState<string[] | undefined>(
    undefined,
  );

  const { calibrationdata } = useBackendContext();

  useEffect(() => {
    if (selectedCamera) {
      const calibrations =
        calibrationdata.get(selectedCamera.index) ?? new Map();
      setResolutions(Array.from(calibrations.keys()));
    }
  }, [selectedCamera, calibrationdata]);

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
          resolutions={resolutions ?? []}
          selected={selectedResolutionData}
          onSelect={(resolution: string) => {
            if (selectedCamera) {
              const data = calibrationdata
                .get(selectedCamera.index)
                ?.get(resolution);

              if (data) {
                setSelectedResolutionData(data);
              }
            }
          }}
          selectedCamera={selectedCamera}
          socket={socket}
        />

        {/* More Info Toggle Button below Select Resolution */}
        {selectedResolutionData !== undefined && (
          <div className="flex justify-center mt-2 flex-col gap-4">
            <Button
              size="sm"
              variant="outline"
              onClick={() => {}}
              className="flex items-center bg-zinc-800 hover:bg-zinc-700 cursor-pointer border-zinc-700"
              aria-expanded={showMoreInfo}
              aria-controls="detailed-info-section"
              style={{ color: teamColor }}
            >
              <Trash /> Delete Calibration Data for{" "}
              {selectedResolutionData.resolution}
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => setShowMoreInfo(!showMoreInfo)}
              className="flex items-center bg-zinc-800 hover:bg-zinc-700 cursor-pointer border-zinc-700"
              aria-expanded={showMoreInfo}
              aria-controls="detailed-info-section"
              style={{ color: teamColor }}
            >
              {showMoreInfo
                ? "Hide Details & Actions"
                : "Show Details & Actions"}
              {showMoreInfo ? (
                <ChevronUp className="w-4 h-4" />
              ) : (
                <ChevronDown className="w-4 h-4" />
              )}
            </Button>
          </div>
        )}

        {/* Collapsible Detailed Info Section */}
        <div
          id="detailed-info-section"
          className={`overflow-hidden transition-all duration-500 ease-in-out
                      ${showMoreInfo ? "max-h-[2000px] opacity-100 space-y-2" : "max-h-0 opacity-0 p-0"}`}
          style={{ color: teamColor }}
        >
          {selectedResolutionData && (
            <>
              {" "}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                <CameraMatrixCard data={selectedResolutionData} />
                <DistortionCoefficientsCard data={selectedResolutionData} />
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
