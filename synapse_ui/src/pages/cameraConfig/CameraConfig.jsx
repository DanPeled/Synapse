import { Column, Row } from "../../widgets/containers";
import { Transform3DVisualizer } from "../../widgets/trasform3DVisualizer";
import { styles } from "../../services/style";
import { OrbitControls as OrbitControlsImpl } from "three-stdlib";
import { useRef, useState } from "react";
import CameraStream from "../../widgets/cameraStream";
import Dropdown from "../../widgets/dropdown";
import TextInput from "../../widgets/textInput";
import * as THREE from "three";
import { Models } from "../../services/objects"

function CameraTransformAxis({ x, setX, y, setY, z, setZ }) {
  return <Row style={{ padding: 0 }}>
    <TextInput label="X:" textColor="red" width="120px" value={x} onChange={setX} />
    <TextInput label="Y:" textColor="green" width="120px" value={y} onChange={setY} />
    <TextInput label="Z:" textColor="blue" width="120px" value={z} onChange={setZ} />
  </Row>
}

function CameraTransform({ cameraID, robotID, setObject, getObject }) {
  const [robotWidth, setRobotWidth] = useState(Models.kRobotDefaults.width);
  const [robotLength, setRobotLength] = useState(Models.kRobotDefaults.length);

  return <Column style={{ gap: 0, padding: 0, margin: 0 }}>
    <h3>Camera Transform</h3>
    <Row style={{ padding: "10px 10px", }}
    >
      <Column>
        <h3>Camera Translation (Meters)</h3>
        <CameraTransformAxis />
      </Column>
      <div style={{ width: 40 }}></div>
      <Column>
        <h3>Camera Rotation (Degrees)</h3>
        <CameraTransformAxis />
      </Column>
    </Row >
    <div style={{ height: 40 }} />
    <Row>
      <TextInput label="Robot Width" onChange={(val) => {
        let obj = getObject(robotID);
        let config = Models.kRobotDefaults;
        config.width = val;
        obj.shape = Models.createRobotModel(config);
        setRobotWidth(val);
        setObject(robotID, obj);
      }}
        initialValue={robotWidth}
      />
      <TextInput label="Robot Length" onChange={(val) => {
        let obj = getObject(robotID);
        let config = Models.kRobotDefaults;
        config.length = val;
        obj.shape = Models.createRobotModel(config);
        setRobotLength(val);
        setObject(robotID, obj);
      }}
        initialValue={robotLength}
      />
    </Row>

  </Column >
}



export default function CameraConfig({ }) {
  const [fieldObjects, setFieldObjects] = useState([
    {
      id: "robot",
      transform: {
        translation: { x: 0, y: 0, z: 0 },
        rotation: { x: 0, y: 0, z: 0 },
      },
      shape: Models.createRobotModel()
    },
    {
      id: "camera",
      transform: {
        translation: { x: 0, y: 0, z: 1 },
        rotation: { x: 0, y: 0, z: 0 }
      },
      color: "white",
      shape: (
        <mesh>
          <boxGeometry args={[1, 0.5, 1]} />
          <meshStandardMaterial color={"white"} />
        </mesh>
      )
    }
  ]);

  return (
    <Row style={{ gap: "60px" }}>
      <Column style={{ flex: 1, maxWidth: "1030px" }}>
        <div style={{ ...styles.card, width: "100%", height: "400px" }}>
          <h2>Camera Settings</h2>
          <Dropdown options={
            [{ label: "Placeholder Camera", value: 0 }]
          } label="Camera" width="400px" />
          <CameraTransform robotID={"robot"} cameraID={"camera"} setObject={(id, obj) => {
            let objects = [...fieldObjects];
            objects[id] = obj;
            setFieldObjects(objects);
          }} getObject={(id) => {
            return fieldObjects.find((obj) => obj.id == id);
          }} />
        </div>
        <div style={{ ...styles.card, width: "100%", height: "700px" }}>
          <h2>Camera Calibration</h2>
        </div>
      </Column>

      <Column>
        <div
          style={{
            ...styles.card,
            width: "auto",
            height: "300px",
          }}
        >
          <CameraStream width="100%" height="100%" url={"http://127.0.0.1:8080/"} />
        </div>
        <div style={{ ...styles.card, width: "700px" }}>
          <Transform3DVisualizer height={"470px"} objects={fieldObjects} />
        </div>
      </Column>
    </Row>
  );
}
