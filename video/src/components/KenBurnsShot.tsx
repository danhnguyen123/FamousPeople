import React from "react";
import {
  AbsoluteFill,
  Easing,
  Img,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import type { Shot } from "../schema";

const resolveSrc = (src: string) =>
  src.startsWith("http") ? src : staticFile(src);

// Start/end scale and translation (in % of frame) for each motion preset.
const motionRange = (shot: Shot) => {
  const driftX = (shot.focusX - 0.5) * 6;
  const driftY = (shot.focusY - 0.5) * 6;
  switch (shot.motion) {
    case "zoomIn":
      return { s: [1.05, 1.22], x: [0, -driftX], y: [0, -driftY] };
    case "zoomOut":
      return { s: [1.22, 1.05], x: [-driftX, 0], y: [-driftY, 0] };
    case "panLeft":
      return { s: [1.18, 1.18], x: [4, -4], y: [-driftY, -driftY] };
    case "panRight":
      return { s: [1.18, 1.18], x: [-4, 4], y: [-driftY, -driftY] };
    case "panUp":
      return { s: [1.18, 1.18], x: [-driftX, -driftX], y: [4, -4] };
    case "panDown":
      return { s: [1.18, 1.18], x: [-driftX, -driftX], y: [-4, 4] };
  }
};

export const KenBurnsShot: React.FC<{
  shot: Shot;
  fadeInFrames: number;
}> = ({ shot, fadeInFrames }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const src = resolveSrc(shot.src);
  const range = motionRange(shot);

  const progress = interpolate(frame, [0, durationInFrames], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.33, 0, 0.67, 1),
  });
  const scale = interpolate(progress, [0, 1], range.s);
  const x = interpolate(progress, [0, 1], range.x);
  const y = interpolate(progress, [0, 1], range.y);
  const opacity =
    fadeInFrames > 0
      ? interpolate(frame, [0, fadeInFrames], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        })
      : 1;

  return (
    <AbsoluteFill style={{ opacity, backgroundColor: "black" }}>
      {/* Blurred fill so portrait or small archival photos never leave black bars. */}
      <AbsoluteFill>
        <Img
          src={src}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
            filter: "blur(40px) brightness(0.55)",
            scale: "1.15",
          }}
        />
      </AbsoluteFill>
      <AbsoluteFill
        style={{
          scale: String(scale),
          translate: `${x}% ${y}%`,
        }}
      >
        <Img
          src={src}
          style={{ width: "100%", height: "100%", objectFit: "contain" }}
        />
      </AbsoluteFill>
      <AbsoluteFill
        style={{
          boxShadow: "inset 0 0 220px rgba(0,0,0,0.65)",
        }}
      />
    </AbsoluteFill>
  );
};
