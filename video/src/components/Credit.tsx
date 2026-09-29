import React from "react";
import { AbsoluteFill } from "remotion";

// Small on-screen attribution, required for CC BY and most CC BY-SA images.
export const Credit: React.FC<{ text: string }> = ({ text }) => (
  <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "flex-end", padding: 24 }}>
    <div
      style={{
        color: "rgba(255,255,255,0.75)",
        fontFamily: "Helvetica, Arial, sans-serif",
        fontSize: 18,
        textShadow: "0 1px 3px rgba(0,0,0,0.9)",
        maxWidth: "60%",
        textAlign: "right",
      }}
    >
      {text}
    </div>
  </AbsoluteFill>
);
