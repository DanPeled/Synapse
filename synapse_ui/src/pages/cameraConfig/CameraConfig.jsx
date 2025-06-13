import { Column, Row } from "../../widgets/containers";
import { Transform3DVisualizer } from "../../widgets/trasform3DVisualizer";
import { styles } from "../../services/style";
import { OrbitControls as OrbitControlsImpl } from "three-stdlib";
import { useRef } from "react";
import CameraStream from "../../widgets/cameraStream";
import Dropdown from "../../widgets/dropdown";

export default function CameraConfig({}) {
  return (
    <Row>
      <Column style={{ flex: 1 }}>
        <div style={{ ...styles.card, width: "55%", height: "340px" }}>
          <h2>Camera Settings</h2>
          <Dropdown
            options={[{ label: "Placeholder Camera", value: 0 }]}
            label="Camera"
          />
          <h3>Camera Transform</h3>
        </div>
        <div style={{ ...styles.card, width: "55%", height: "700px" }}>
          <h2>Camera Calibration</h2>
        </div>
      </Column>

      <Column
        style={{
          flexShrink: 0,
          backgroundAttachment: "scroll",
          position: "fixed",
          right: "1%",
        }}
      >
        <div
          style={{
            ...styles.card,
            width: "auto",
            height: "300px",
          }}
        >
          <CameraStream width="100%" height="100%" />
        </div>
        <div style={{ ...styles.card, width: "700px" }}>
          <Transform3DVisualizer height={445} />
        </div>
      </Column>
    </Row>
  );
}
