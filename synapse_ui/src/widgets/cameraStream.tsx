import { useState } from "react";
import { baseCardColor, teamColor } from "@/services/style";
import { Eye } from "lucide-react";
import { darken } from "polished";

export function CameraStream({ stream }: { stream: string | undefined }) {
  const [loaded, setLoaded] = useState(false);
  if (!stream) {
    stream = "locahost";
  }

  return (
    <div
      className="aspect-[3/2] w-full max-w-[435px] flex flex-col items-center justify-center rounded-lg"
      style={{
        maxHeight: "290px",
        height: "auto",
        backgroundColor: darken(0.2, baseCardColor),
        position: "relative",
      }}
    >
      {/* Placeholder shown only before first frame loads */}
      {!loaded && (
        <>
          <Eye
            className="w-16 h-16 mb-2 opacity-100 animate-spin"
            color={teamColor}
          />
          <p style={{ color: teamColor }}>Camera Stream</p>
        </>
      )}

      {/* MJPEG Stream */}
      <img
        src={stream}
        alt="Camera Stream"
        onLoad={() => setLoaded(true)}
        onError={() => setLoaded(false)}
        style={{
          display: loaded ? "block" : "none",
          width: "100%",
          height: "auto",
          objectFit: "cover",
        }}
        // Important for MJPEG streams so browser doesn't cache
        key={stream}
      />
    </div>
  );
}
