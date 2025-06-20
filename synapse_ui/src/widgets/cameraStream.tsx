import { baseCardColor, teamColor } from "@/services/style";
import { Eye } from "lucide-react";
import { darken } from "polished";

export function CameraStream() {
  return (
    <div
      className="rounded-lg aspect-[3/2] w-full max-w-[435px] flex flex-col items-center justify-center"
      style={{
        maxHeight: "290px",
        height: "auto",
        backgroundColor: darken(0.2, baseCardColor),
      }}
    >
      <Eye
        className="w-16 h-16 mb-2 opacity-100 animate-spin"
        color={teamColor}
      />
      <p style={{ color: teamColor }}>Camera Stream</p>
      <p className="text-sm" style={{ color: teamColor }}>
        http://127.0.0.1:8080/
      </p>
    </div>
  );
}
