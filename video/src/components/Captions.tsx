import React from "react";
import { AbsoluteFill, Sequence, useVideoConfig } from "remotion";
import type { DocumentaryProps } from "../schema";

export const Captions: React.FC<{ captions: DocumentaryProps["captions"] }> = ({
  captions,
}) => {
  const { fps } = useVideoConfig();
  return (
    <>
      {captions.map((c, i) => {
        const from = Math.round(c.startSec * fps);
        const duration = Math.max(1, Math.round((c.endSec - c.startSec) * fps));
        return (
          <Sequence key={i} name={`Caption ${i + 1}`} from={from} durationInFrames={duration}>
            <AbsoluteFill
              style={{ justifyContent: "flex-end", alignItems: "center", paddingBottom: 90 }}
            >
              <div
                style={{
                  maxWidth: "80%",
                  padding: "14px 28px",
                  borderRadius: 10,
                  background: "rgba(0,0,0,0.55)",
                  color: "white",
                  fontFamily: "Georgia, 'Times New Roman', serif",
                  fontSize: 46,
                  lineHeight: 1.25,
                  textAlign: "center",
                }}
              >
                {c.text}
              </div>
            </AbsoluteFill>
          </Sequence>
        );
      })}
    </>
  );
};
