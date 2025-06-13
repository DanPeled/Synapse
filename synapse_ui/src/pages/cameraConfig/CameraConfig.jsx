import { Column } from "../../widgets/containers";
import { Transform3DVisualizer } from "../../widgets/trasform3DVisualizer";
import { styles } from "../../services/style";
import { OrbitControls as OrbitControlsImpl } from 'three-stdlib';
import { useRef } from "react";

export default function CameraConfig({ }) {
  return <Column style={{ ...styles.card, width: "50%" }}>
    <Transform3DVisualizer />
  </Column>;
}
