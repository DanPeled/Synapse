import { Column, Row } from "../../widgets/containers";
import { styles, teamColor } from "../../services/style";
import Dropdown from "../../widgets/dropdown";
import CameraStream from "../../widgets/cameraStream";
import { Copy, Pen, Plus, Trash } from "lucide-react";
import { useEffect, useState } from "react";
import IconMenu from "../../widgets/iconMenu";
import AddPipelineDialog from "../../widgets/pipeline/addPipelineDialog";
import TabView from "../../widgets/tabview";
import Slider from "../../widgets/slider";
import { Transform3DVisualizer } from "../../widgets/trasform3DVisualizer";

function StreamAndPipelineControls({}) {
  const [showAddPipelineDialog, setShowAddPipelineDialog] = useState(false);
  const [pipelines, setPipelines] = useState(
    Array.of(
      { label: "Apriltag Pipeline", value: "ApriltagPipeline" },
      { label: "Colored Shape", value: "ColorPipeline" },
    ),
  );
  const [currentPipeline, setCurrentPipeline] = useState(null);

  useEffect(() => {
    if (pipelines.length > 0) {
      setCurrentPipeline(pipelines[0].value);
    }
  }, [pipelines]);

  const pipelineTypes = [
    { label: "Placeholder Pipeline", value: "ApriltagPipeline" },
    { label: "Another Placeholder", value: "ColorPipeline" },
  ];

  const dropdownWidth = "80%";
  return (
    <div
      style={{
        ...styles.placeholderCard,
        height: 200,
        gap: 10,
        paddingLeft: "50px",
      }}
    >
      <Dropdown
        label="Camera"
        options={[
          { label: "Monochrome (#0)", value: 0 },
          { label: "Colored (#1)", value: 1 },
        ]}
        width={dropdownWidth}
      />
      <Row>
        <Dropdown
          label="Pipeline"
          options={pipelines}
          width={dropdownWidth}
          onChange={(val) => {
            setCurrentPipeline(val);
          }}
        />
        <div style={{ display: "flex", alignItems: "center" }}>
          <IconMenu
            options={[
              {
                icon: <Pen />,
                onClick: () => console.log("Rename"),
                tooltip: "Rename",
              },
              {
                icon: <Plus />,
                onClick: () => {
                  setShowAddPipelineDialog(true);
                },
                tooltip: "Add Pipeline",
              },
              {
                icon: <Trash color="red" />,
                onClick: () => {
                  setPipelines(
                    pipelines.filter((val) => val.value !== currentPipeline),
                  );
                },
                tooltip: "Delete",
              },
              {
                icon: <Copy />,
                onClick: () => {
                  setPipelines([
                    ...pipelines,
                    {
                      label: `Copy of ${currentPipeline}`,
                      value: `Copy of ${currentPipeline}`,
                    },
                  ]);
                },
                tooltip: "Duplicate",
              },
            ]}
          />
        </div>
      </Row>
      <Dropdown
        label="Pipeline Type"
        options={pipelineTypes}
        width={dropdownWidth}
      />
      {showAddPipelineDialog && (
        <AddPipelineDialog
          visible={showAddPipelineDialog}
          setVisible={setShowAddPipelineDialog}
          addPipelines={(val) => {
            setPipelines([...pipelines, val]);
          }}
          style={{ width: "80%", height: "80%" }}
        />
      )}
    </div>
  );
}

function CameraView({}) {
  return (
    <div
      style={{
        ...styles.card,
        width: "60%",
        height: 430,
      }}
    >
      <h3 style={{ position: "relative", color: teamColor }}>
        <span>Camera Stream</span>
        <span
          style={{
            position: "absolute",
            left: "50%",
            transform: "translateX(-50%)",
            fontWeight: "normal",
            color: "red",
          }}
        >
          Processing @ 0 FPS – 0ms latency
        </span>
      </h3>
      <hr
        style={{
          border: "none",
          backgroundColor: "rgba(10, 10, 10, 0.3)",
          margin: "1px 0",
          width: "100%",
        }}
      />
      <CameraStream />
      <div
        style={{
          alignContent: "center",
          marginLeft: "auto",
          marginRight: "auto",
        }}
      >
        <Dropdown
          label="Process Step"
          options={[...Array(3).keys()].map((index) => ({
            label: `step_${index}`,
            value: index,
          }))}
          width={"100%"}
        />
      </div>
    </div>
  );
}

function PipelineConfigControl({}) {
  return (
    <TabView
      width="97%"
      tabs={[
        {
          key: 0,
          label: "Input",
          content: (
            <div>
              <Slider label="Brightness" labelGap="100px" />
              <Slider label="Exposure" labelGap="100px" />
              <Slider label="Camera Gain" labelGap="100px" />
              <Slider label="Saturation" labelGap="100px" />
              <Dropdown
                options={[
                  { label: "Normal", value: 0 },
                  { label: "90deg CW", value: 90 },
                  { label: "180deg", value: 180 },
                  { label: "90deg CCW", value: 270 },
                ]}
                label="Orientation"
              />
              <div style={{ height: 10 }}></div>
              <Dropdown
                options={[
                  { label: "1920x1080 @ 100FPS", value: 0 },
                  { label: "1080x720 @ 100FPS", value: 90 },
                  { label: "640x480 @ 100FPS", value: 180 },
                ]}
                label="Resolution"
              />
              <div style={{ height: 30 }}></div>
            </div>
          ),
        },
        { key: 1, label: "Pipeline", content: <div>Pipeline Settings</div> },
        { key: 2, label: "Output", content: <div>Output</div> },
      ]}
    />
  );
}

function ResultsView({}) {
  return (
    <div style={{ ...styles.placeholderCard, height: "640px", padding: "0px" }}>
      <h3 style={{ textAlign: "center", color: teamColor }}>Results</h3>
      <hr style={{ width: "98%", border: "1px solid rgba(60,60,60,0.5)" }} />
    </div>
  );
}

export default function Dashboard() {
  return (
    <Row style={{ gap: "0px" }}>
      <Column style={{ flex: 3, gap: "8px" }}>
        <div style={{ width: "158%" }}>
          {" "}
          {/*Only god knows why this works */}
          <CameraView />
        </div>
        <div style={{ width: "98.5%" }}>
          <PipelineConfigControl />
        </div>
      </Column>
      <Column style={{ flex: 2, position: "sticky" }}>
        <StreamAndPipelineControls />
        <ResultsView />
      </Column>
    </Row>
  );
}
