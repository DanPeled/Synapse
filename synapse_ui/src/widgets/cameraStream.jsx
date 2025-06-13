import { Eye } from "lucide-react";
import React, { useState } from "react";
import { teamColor } from "../services/style";

export default function CameraStream({ url }) {
  const [loading, setLoading] = useState(true);

  return (
    <div
      style={{
        width: "100%",
        position: "relative",
        display: "flex",
        height: "100%",
        justifyContent: "center",
        alignItems: "center",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          position: "relative", // make this the positioning context for spinner
          width: "60%",
          height: "auto",
        }}
      >
        <img
          src={url}
          alt="Camera Stream"
          style={{
            width: "100%", // fill the wrapper div
            height: "auto",
            backgroundColor: "transparent",
            objectFit: "contain",
            display: "block",
          }}
          onLoad={() => setLoading(false)}
          onError={() => setLoading(false)}
        />

        {loading && (
          <div
            style={{
              position: "absolute",
              top: "-20%",
              left: "50%",
              pointerEvents: "none",
            }}
          >
            <Eye
              size={40}
              color={teamColor}
              style={{
                animation: "spin 1.5s linear infinite",
              }}
            />
          </div>
        )}
      </div>

      <style>{`
          @keyframes spin {
            0% { transform: rotate(0deg);}
            100% { transform: rotate(360deg);}
          }
        `}</style>
    </div>
  );
}
