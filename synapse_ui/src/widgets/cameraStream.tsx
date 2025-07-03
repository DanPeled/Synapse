import { useState, useRef, useEffect } from "react";
import { baseCardColor, teamColor } from "@/services/style";
import { Eye, Fullscreen } from "lucide-react";
import { darken } from "polished";
import { Row } from "./containers";

export function CameraStream({ stream }: { stream: string | undefined }) {
  const [loaded, setLoaded] = useState(false);
  const [contextPos, setContextPos] = useState<{ x: number; y: number } | null>(
    null,
  );
  const imgRef = useRef<HTMLImageElement>(null);
  const contextMenuRef = useRef<HTMLDivElement>(null);

  if (!stream) {
    stream = "localhost";
  }

  const handleContextMenu = (e: React.MouseEvent) => {
    e.preventDefault();
    setContextPos({ x: e.clientX, y: e.clientY });
  };

  const handleFullscreen = () => {
    if (imgRef.current) {
      imgRef.current.requestFullscreen?.();
    }
    setContextPos(null); // hide menu
  };

  // Close context menu on outside click
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        contextMenuRef.current &&
        !contextMenuRef.current.contains(event.target as Node)
      ) {
        setContextPos(null);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  return (
    <div
      className="aspect-[3/2] w-full max-w-[435px] flex flex-col items-center justify-center rounded-lg border border-zinc-700"
      style={{
        maxHeight: "290px",
        height: "auto",
        backgroundColor: darken(0.2, baseCardColor),
        position: "relative",
      }}
    >
      {!loaded && (
        <>
          <Eye
            className="w-16 h-16 mb-2 opacity-100 animate-spin"
            color={teamColor}
          />
          <p style={{ color: teamColor }}>Camera Stream</p>
        </>
      )}

      <img
        ref={imgRef}
        src={stream}
        alt="Camera Stream"
        onLoad={() => setLoaded(true)}
        onError={() => setLoaded(false)}
        onContextMenu={handleContextMenu}
        style={{
          display: loaded ? "block" : "none",
          width: "100%",
          height: "auto",
          objectFit: "cover",
          cursor: "context-menu",
        }}
        key={stream}
      />

      {/* Custom context menu */}
      {contextPos && (
        <Row
          gap="gap-2"
          ref={contextMenuRef}
          className="z-50 bg-zinc-800 text-white px-2 py-1 rounded shadow cursor-pointer hover:bg-zinc-700"
          style={{
            top: contextPos.y,
            left: contextPos.x,
            position: "fixed",
            color: teamColor,
          }}
          onClick={handleFullscreen}
        >
          <Fullscreen /> Fullscreen
        </Row>
      )}
    </div>
  );
}
