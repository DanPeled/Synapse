import { Eye } from "lucide-react";
import React, { useState, useEffect } from "react";
import { teamColor } from "../services/style";

export default function CameraStream({ url }) {
  const [loading, setLoading] = useState(true);
  const [imgKey, setImgKey] = useState(0);

  // Periodically reload image
  useEffect(() => {
    const interval = setInterval(() => {
      setImgKey(prev => prev + 1); // force remount
    }, 3000); // adjust interval as needed
    return () => clearInterval(interval);
  }, []);

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
      <div style={{ position: "relative", width: "60%", height: "auto" }}>
        <img
          key={imgKey}
          src={url}
          alt="Camera Stream"
          onLoad={() => setLoading(false)}
          onError={() => setLoading(true)}
          style={{
            width: "100%",
            height: "auto",
            display: loading ? "none" : "block",
          }}
        />

        {loading && (
          <div
            style={{
              position: "absolute",
              top: "50%",
              left: "50%",
              transform: "translate(-50%, -50%)",
              pointerEvents: "none",
            }}
          >
            <div style={{ animation: "spin 1.5s linear infinite" }}>
              <Eye size={40} color={teamColor} />
            </div>
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
