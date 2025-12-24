import { useState, useRef } from "react";
import { Eye, Fullscreen } from "lucide-react";
import { darken } from "polished";
import { cn } from "@/lib/utils";
import { baseCardColor, teamColor } from "@/services/style";

export function CameraStream({
  stream = "localhost",
  className,
}: {
  stream?: string;
  className?: string;
}) {
  const [loaded, setLoaded] = useState(false);
  const imgRef = useRef<HTMLImageElement>(null);

  return (
    <div
      className={cn(
        "relative w-full h-full overflow-hidden rounded-lg",
        className,
      )}
      style={{ backgroundColor: "transparent" }}
    >
      {/* Loading overlay */}
      {!loaded && (
        <div className="absolute inset-0 z-10 flex flex-col items-center justify-center">
          <Eye className="h-16 w-16 animate-spin" color={teamColor} />
          <p className="mt-2" style={{ color: teamColor }}>
            Camera Stream
          </p>
        </div>
      )}

      {/* Stream */}
      <img
        ref={imgRef}
        src={stream}
        alt="Camera Stream"
        onLoad={() => setLoaded(true)}
        onError={() => setLoaded(false)}
        className={cn(
          "absolute inset-0 w-full h-full transition-opacity",
          loaded ? "opacity-100" : "opacity-0",
          "object-contain", // 👈 change to cover if you want cropping
        )}
      />

      {/* Fullscreen */}
      {loaded && (
        <button
          onClick={() => imgRef.current?.requestFullscreen?.()}
          style={{ color: teamColor }}
          className="absolute bottom-2 right-2 z-20 rounded bg-zinc-800/80 p-2 hover:bg-zinc-700 cursor-pointer"
        >
          <Fullscreen className="h-5 w-5" />
        </button>
      )}
    </div>
  );
}
